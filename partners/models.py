from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid, os, secrets, string
from django.core.exceptions import ValidationError


# ── Validators ────────────────────────────────────────────────────────────────

def validate_ad_image(value):
    pass

def validate_image_or_video(value):
    ext = os.path.splitext(value.name)[1].lower()
    allowed = ['.jpg', '.jpeg', '.png', '.webp', '.mp4', '.mov', '.avi']
    if ext not in allowed:
        raise ValidationError(f"Format non supporté. Autorisés : {', '.join(allowed)}")

def validate_mobile_image(value):
    ext = os.path.splitext(value.name)[1].lower()
    allowed = ['.jpg', '.jpeg', '.png', '.gif']
    if ext not in allowed:
        raise ValidationError("Format mobile non supporté.")
    if value.size > 5 * 1024 * 1024:
        raise ValidationError("Fichier trop lourd (Max 5MB).")

def validate_tablet_image(value):
    ext = os.path.splitext(value.name)[1].lower()
    allowed = ['.jpg', '.jpeg', '.png', '.gif']
    if ext not in allowed:
        raise ValidationError("Format tablette non supporté.")
    if value.size > 5 * 1024 * 1024:
        raise ValidationError("Fichier trop lourd (Max 5MB).")


# ── Models ────────────────────────────────────────────────────────────────────

class Partner(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='partner_profile',
        null=True, blank=True
    )

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_name  = models.CharField(max_length=255)
    email         = models.EmailField(unique=True)
    phone         = models.CharField(max_length=20, blank=True)
    logo          = models.ImageField(upload_to='partners/logos/', blank=True, null=True)

    is_active      = models.BooleanField(default=True)
    is_verified    = models.BooleanField(default=False)
    account_frozen = models.BooleanField(default=False)

    is_temporarily_disabled = models.BooleanField(default=False)
    disabled_reason         = models.TextField(blank=True, null=True)
    disabled_at             = models.DateTimeField(blank=True, null=True)
    reactivated_at          = models.DateTimeField(blank=True, null=True)

    CONTRACT_PERIODS = [
        ('1_month',   '1 Mois'),
        ('3_months',  '3 Mois'),
        ('6_months',  '6 Mois'),
        ('10_months', '10 Mois'),
        ('12_months', '12 Mois (1 An)'),
    ]
    PAYMENT_TYPES = [
        ('monthly', 'Paiement Mensuel'),
        ('total',   'Paiement Total'),
    ]

    contract_period = models.CharField(max_length=20, choices=CONTRACT_PERIODS, blank=True, null=True)
    payment_type    = models.CharField(max_length=10, choices=PAYMENT_TYPES, blank=True, null=True)
    contract_start  = models.DateField(blank=True, null=True)
    contract_end    = models.DateField(blank=True, null=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    validated_at    = models.DateTimeField(blank=True, null=True)

    reset_token            = models.CharField(max_length=255, blank=True, null=True)
    reset_token_expires_at = models.DateTimeField(blank=True, null=True)
    pending_email          = models.EmailField(blank=True, null=True)
    konnect_wallet_id      = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name        = 'Partenaire'
        verbose_name_plural = 'Partenaires'
        ordering            = ['-created_at']

    def __str__(self):
        return f"{self.company_name} ({self.email})"

    def clean(self):
        # Normalize email
        if self.email:
            self.email = self.email.lower()

        # Auto-fill email from linked user if email is empty
        if not self.email and self.user and self.user.email:
            self.email = self.user.email.lower()

        # Check email uniqueness with friendly error
        if self.email:
            qs = Partner.objects.filter(email=self.email)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    {'email': f"Un partenaire avec l'email '{self.email}' existe déjà."}
                )

    def save(self, *args, **kwargs):
        # Normalize email
        if self.email:
            self.email = self.email.lower()

        # Auto-fill email from linked user if email is empty
        if not self.email and self.user and self.user.email:
            self.email = self.user.email.lower()

        if not self.user:
            # No user linked — create one automatically from the email
            if not self.email:
                raise ValidationError("Un email est requis pour créer un partenaire.")
            user = User.objects.filter(username=self.email).first()
            if not user:
                user = User.objects.create_user(
                    username=self.email,
                    email=self.email,
                    password="Partner123"
                )
            self.user = user
        else:
            # User already linked — sync email from Partner → User
            if self.email and (self.user.email != self.email or self.user.username != self.email):
                self.user.email    = self.email
                self.user.username = self.email
                self.user.save()

        super().save(*args, **kwargs)

    def generate_reset_token(self) -> str:
        token = secrets.token_urlsafe(48)
        self.reset_token = token
        self.reset_token_expires_at = timezone.now() + timezone.timedelta(hours=1)
        self.save(update_fields=['reset_token', 'reset_token_expires_at'])
        return token

    def is_reset_token_valid(self, token: str) -> bool:
        if not self.reset_token or not self.reset_token_expires_at:
            return False
        return self.reset_token == token and timezone.now() <= self.reset_token_expires_at

    @property
    def is_contract_active(self) -> bool:
        if not self.contract_end:
            return False
        return timezone.now().date() <= self.contract_end

    @property
    def days_until_expiry(self):
        if not self.contract_end:
            return None
        return (self.contract_end - timezone.now().date()).days

    @property
    def can_add_content(self) -> bool:
        return (
            self.is_verified
            and self.is_contract_active
            and not self.account_frozen
            and not self.is_temporarily_disabled
        )

    @property
    def is_accessible(self) -> bool:
        return (
            self.is_active
            and not self.account_frozen
            and not self.is_temporarily_disabled
        )


# ── PartnerContract ───────────────────────────────────────────────────────────

class PartnerContract(models.Model):
    partner        = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='contracts')
    period         = models.CharField(max_length=20, choices=Partner.CONTRACT_PERIODS)
    payment_type   = models.CharField(max_length=10, choices=Partner.PAYMENT_TYPES)
    start_date     = models.DateField()
    end_date       = models.DateField()
    total_amount   = models.DecimalField(max_digits=10, decimal_places=3)
    monthly_amount = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    is_paid        = models.BooleanField(default=False)
    konnect_payment_ref = models.CharField(max_length=255, blank=True, null=True)
    paid_at        = models.DateTimeField(blank=True, null=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering            = ['-created_at']
        verbose_name        = 'Contrat Partenaire'
        verbose_name_plural = 'Contrats Partenaires'

    def __str__(self):
        return f"Contrat {self.partner.company_name} — {self.get_period_display()}"

    def mark_as_paid(self, payment_ref: str = None):
        self.is_paid = True
        self.paid_at = timezone.now()
        if payment_ref:
            self.konnect_payment_ref = payment_ref
        self.save(update_fields=['is_paid', 'paid_at', 'konnect_payment_ref'])

        self.partner.contract_start  = self.start_date
        self.partner.contract_end    = self.end_date
        self.partner.contract_period = self.period
        self.partner.payment_type    = self.payment_type
        self.partner.account_frozen  = False
        self.partner.save()


# ── Coupon ────────────────────────────────────────────────────────────────────

def generate_coupon_code():
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(8))


class Coupon(models.Model):
    CATEGORY_CHOICES = [
        ('subscription', 'Abonnement'),
        ('content',      'Contenu (Events & Ads)'),
        ('both',         'Les deux'),
    ]
    code                = models.CharField(max_length=20, unique=True, default=generate_coupon_code)
    description         = models.CharField(max_length=255, blank=True)
    discount_percentage = models.PositiveIntegerField()
    category            = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='both')
    is_active           = models.BooleanField(default=True)
    max_uses            = models.PositiveIntegerField(default=0)
    current_uses        = models.PositiveIntegerField(default=0)
    expires_at          = models.DateTimeField(blank=True, null=True)
    created_at          = models.DateTimeField(auto_now_add=True)

    def apply(self):
        self.current_uses += 1
        self.save(update_fields=['current_uses'])


# ── AdminNotification ─────────────────────────────────────────────────────────

class AdminNotification(models.Model):
    TYPE_CHOICES = [
        ('unpaid_subscription', 'Abonnement impayé'),
        ('unpaid_ad',           'Publicité impayée'),
        ('email_change',        'Changement email en attente'),
        ('new_partner',         'Nouveau partenaire'),
    ]
    partner    = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='notifications')
    type       = models.CharField(max_length=30, choices=TYPE_CHOICES)
    message    = models.TextField()
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


# ── PartnerEvent ──────────────────────────────────────────────────────────────

class PartnerEvent(models.Model):
    STATUS_CHOICES = [
        ('pending',  'En attente de validation'),
        ('approved', 'Approuvé'),
        ('rejected', 'Rejeté'),
        ('boosted',  'Boosté'),
    ]
    partner      = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='events')
    title        = models.CharField(max_length=255)
    title_en     = models.CharField(max_length=255, blank=True, default='')
    title_fr     = models.CharField(max_length=255, blank=True, default='')
    description     = models.TextField()
    description_en  = models.TextField(blank=True, default='')
    description_fr  = models.TextField(blank=True, default='')

    category     = models.ForeignKey('guard.EventCategory', on_delete=models.SET_NULL, null=True, blank=True)
    city         = models.ForeignKey('cities_light.City', on_delete=models.SET_NULL, null=True, blank=True)
    location     = models.ForeignKey('guard.Location', on_delete=models.SET_NULL, null=True, blank=True)

    event_time   = models.TimeField(blank=True, null=True)
    price        = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    start_date   = models.DateField()
    end_date     = models.DateField()
    link         = models.URLField(blank=True, null=True)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_boosted   = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def sync_main_fields(self):
        if self.title_en:
            self.title = self.title_en
        elif self.title_fr:
            self.title = self.title_fr
        if self.description_en:
            self.description = self.description_en
        elif self.description_fr:
            self.description = self.description_fr


# ── PartnerEventMedia ─────────────────────────────────────────────────────────

class PartnerEventMedia(models.Model):
    event       = models.ForeignKey(PartnerEvent, on_delete=models.CASCADE, related_name='media')
    file        = models.FileField(upload_to='partners/events/', validators=[validate_image_or_video])
    media_type  = models.CharField(max_length=10, default='image')
    order       = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        ext = os.path.splitext(self.file.name)[1].lower()
        self.media_type = 'video' if ext in ['.mp4', '.mov', '.avi'] else 'image'
        super().save(*args, **kwargs)


# ── PartnerAd ─────────────────────────────────────────────────────────────────

class PartnerAd(models.Model):
    partner          = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='ads')
    title            = models.CharField(max_length=255, blank=True, default='')
    mobile_image     = models.ImageField(upload_to='partners/ads/mobile/', validators=[validate_mobile_image], blank=True, null=True)
    tablet_image     = models.ImageField(upload_to='partners/ads/tablet/', validators=[validate_tablet_image], blank=True, null=True)
    destination_link = models.URLField(blank=True, default='')
    start_date       = models.DateField()
    end_date         = models.DateField()
    price_per_day    = models.DecimalField(max_digits=8, decimal_places=3, default=2.000)
    total_price      = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    status           = models.CharField(max_length=20, default='pending')
    created_at       = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        from decimal import Decimal
        nb_days = (self.end_date - self.start_date).days + 1
        self.total_price = Decimal(str(self.price_per_day)) * nb_days
        super().save(*args, **kwargs)