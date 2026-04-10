import os
import uuid
from datetime import timedelta
from django.contrib.auth import get_user_model
from io import BytesIO
from PIL import Image as PilImage
from django.core.files.base import ContentFile
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.urls import reverse
from django.utils import timezone
from django.dispatch import receiver
from tinymce.models import HTMLField
from django.utils.translation import gettext_lazy as _


class OptimizedImageModel(models.Model):
    image = models.ImageField(upload_to="images/")
    image_mobile = models.ImageField(upload_to="images/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.image and (not self.pk or hasattr(self.image, "file")):
            try:
                img = PilImage.open(self.image)

                if img.mode != "RGB":
                    img = img.convert("RGB")

                img_main = img.copy()
                if img_main.width > 1920:
                    ratio = 1920 / float(img_main.width)
                    height = int((float(img_main.height) * float(ratio)))
                    img_main = img_main.resize(
                        (1920, height), PilImage.Resampling.LANCZOS
                    )

                output_main = BytesIO()
                img_main.save(output_main, format="JPEG", quality=80)
                output_main.seek(0)

                original_name = os.path.basename(self.image.name)
                name_base, _ = os.path.splitext(original_name)
                filename = f"{name_base}.jpg"

                self.image = ContentFile(output_main.read(), name=filename)

                img_mobile = img.copy()
                if img_mobile.width > 500:
                    ratio = 500 / float(img_mobile.width)
                    height = int((float(img_mobile.height) * float(ratio)))
                    img_mobile = img_mobile.resize(
                        (500, height), PilImage.Resampling.LANCZOS
                    )

                output_mobile = BytesIO()
                img_mobile.save(output_mobile, format="JPEG", quality=80)
                output_mobile.seek(0)

                self.image_mobile = ContentFile(
                    output_mobile.read(), name=f"mobile_{filename}"
                )

                try:
                    if self.image.storage.exists(self.image.name):
                        self.image.storage.delete(self.image.name)
                except Exception:
                    pass

            except Exception as e:
                print(f"Error processing image: {e}")
                pass

        super().save(*args, **kwargs)


@receiver(post_delete)
def cleanup_optimized_image_files(sender, instance, **kwargs):
    if not issubclass(sender, OptimizedImageModel):
        return

    if (
        hasattr(instance, "image")
        and instance.image
        and os.path.isfile(instance.image.path)
    ):
        os.remove(instance.image.path)

    if (
        hasattr(instance, "image_mobile")
        and instance.image_mobile
        and os.path.isfile(instance.image_mobile.path)
    ):
        os.remove(instance.image_mobile.path)

    try:
        if hasattr(instance, "image") and instance.image:
            directory = os.path.dirname(instance.image.path)
            if os.path.exists(directory) and not os.listdir(directory):
                os.rmdir(directory)
    except Exception:
        pass


class Page(models.Model):
    slug = models.SlugField(unique=True, verbose_name=_("URL Slug"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    title = models.CharField(max_length=255, verbose_name=_("Title"))
    content = HTMLField(verbose_name=_("Content"))

    class Meta:
        verbose_name = _("Page")
        verbose_name_plural = _("Pages")
        ordering = ["slug"]

    def __str__(self):
        return self.title


User = get_user_model()


class UserProfile(models.Model):
    class UserType(models.TextChoices):
        STAFF = "staff", _("Staff")
        CLIENT_PARTNER = "client_partner", _("Client / Partners")

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    user_type = models.CharField(
        max_length=32, choices=UserType.choices, default=UserType.CLIENT_PARTNER
    )
    subscription_plan = models.CharField(
        max_length=100,
        blank=True,
        default="Trial",
        help_text=_("Placeholder until Konnect subscription is attached."),
    )
    subscription_status = models.CharField(
        max_length=32,
        blank=True,
        default="trial",
    )
    subscription_started_at = models.DateField(null=True, blank=True)
    subscription_renews_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("User profile")
        verbose_name_plural = _("User profiles")

    def __str__(self) -> str:
        return f"{self.user.get_username()} ({self.get_user_type_display()})"

    @property
    def is_staff_type(self) -> bool:
        return self.user_type == self.UserType.STAFF

    @property
    def subscription_days_left(self):
        if not self.subscription_renews_at:
            return None
        return (self.subscription_renews_at - timezone.now().date()).days

    @property
    def is_subscription_expiring(self) -> bool:
        days_left = self.subscription_days_left
        return days_left is not None and days_left <= 7

    @property
    def subscription_status_label(self) -> str:
        mapping = {
            "trial": _("Trial"),
            "active": _("Active"),
            "grace": _("Grace period"),
            "expired": _("Expired"),
        }
        key = (self.subscription_status or "").lower()
        return mapping.get(key, key.capitalize() or _("Pending"))


@receiver(post_save, sender=User)
def ensure_profile_exists(sender, instance, created, **kwargs):
    today = timezone.now().date()
    default_type = (
        UserProfile.UserType.STAFF
        if instance.is_staff
        else UserProfile.UserType.CLIENT_PARTNER
    )
    profile, created_profile = UserProfile.objects.get_or_create(
        user=instance,
        defaults={
            "user_type": default_type,
            "subscription_started_at": today,
            "subscription_renews_at": today + timedelta(days=30),
        },
    )
    updated_fields = []
    if profile.user_type == UserProfile.UserType.CLIENT_PARTNER and instance.is_staff:
        profile.user_type = UserProfile.UserType.STAFF
        updated_fields.append("user_type")
    if not profile.subscription_started_at:
        profile.subscription_started_at = today
        updated_fields.append("subscription_started_at")
    if not profile.subscription_renews_at:
        profile.subscription_renews_at = today + timedelta(days=30)
        updated_fields.append("subscription_renews_at")
    if updated_fields:
        profile.save(update_fields=updated_fields)


class UserPreference(models.Model):
    user_uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    first_visit = models.BooleanField(verbose_name=_("First visit"))
    traveling_with = models.CharField(max_length=20, verbose_name=_("Traveling with"))
    interests = models.JSONField(verbose_name=_("Interests"))
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("User Preference")
        verbose_name_plural = _("User Preferences")

    def __str__(self):
        return self.user_uid


class Package(models.Model):
    name = models.CharField(max_length=255, verbose_name=_("Name"))
    description = models.TextField(verbose_name=_("Description"))
    price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Price")
    )
    duration = models.IntegerField(verbose_name=_("Duration"))
    duration_unit = models.CharField(max_length=255, verbose_name=_("Duration Unit"))
    features = models.JSONField(verbose_name=_("Features"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Package")
        verbose_name_plural = _("Packages")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("package_detail", kwargs={"pk": self.pk})

    class Meta:
        verbose_name        = _("Paramètres de prix")
        verbose_name_plural = _("Paramètres de prix")

    def __str__(self):
        return f"Boost: {self.boost_price_per_day} TND/j | Pub: {self.ad_price_per_day} TND/j"

    @classmethod
    def get(cls):
        """Récupère ou crée le singleton."""
        obj, _ = cls.objects.get_or_create(pk=1, defaults={
            'boost_price_per_day': 5.000,
            'ad_price_per_day': 3.000,
        })
        return obj

# ── À ajouter à la fin de shared/models.py ───────────────────────────────────

class PricingSettings(models.Model):
    """
    Singleton — pk=1 toujours.
    Prix configurables depuis l'admin Django.
    """
    boost_price_per_day = models.DecimalField(
        max_digits=8, decimal_places=3,
        default=5.000,
        verbose_name=_("Prix boost événement (TND/jour)"),
        help_text=_("Prix facturé par jour pour booster un événement partenaire.")
    )
    ad_price_per_day = models.DecimalField(
        max_digits=8, decimal_places=3,
        default=3.000,
        verbose_name=_("Prix publicité (TND/jour)"),
        help_text=_("Prix facturé par jour pour une publicité partenaire.")
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pricing_updates'
    )

    class Meta:
        verbose_name        = _("Paramètres de prix")
        verbose_name_plural = _("Paramètres de prix")

    def __str__(self):
        return f"Boost: {self.boost_price_per_day} TND/j | Pub: {self.ad_price_per_day} TND/j"

    @classmethod
    def get(cls) -> 'PricingSettings':
        obj, _ = cls.objects.get_or_create(pk=1, defaults={
            'boost_price_per_day': 5.000,
            'ad_price_per_day':    3.000,
        })
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1  # force singleton
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # interdit la suppression
