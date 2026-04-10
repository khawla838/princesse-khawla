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


# ── Helpers prix — lisent PricingSettings depuis shared ──────────────────────

def _get_boost_price_per_day() -> float:
    try:
        from shared.models import PricingSettings
        return float(PricingSettings.get().boost_price_per_day)
    except Exception:
        return 5.000  # fallback si table pas encore migrée

def _get_ad_price_per_day() -> float:
    try:
        from shared.models import PricingSettings
        return float(PricingSettings.get().ad_price_per_day)
    except Exception:
        return 3.000  # fallback


# ── Models ────────────────────────────────────────────────────────────────────

class Partner(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='partner_profile',
        null=True, blank=True
    )
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_name = models.CharField(max_length=255)
    email        = models.EmailField(unique=True)
    phone        = models.CharField(max_length=20, blank=True)
    logo         = models.ImageField(upload_to='partners/logos/', blank=True, null=True)

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
    PAYMENT_STATUS_CHOICES = [
        ('active',     'Paiement actif'),
        ('not_active', 'Paiement non actif'),
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

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='not_active',
        verbose_name="Statut paiement"
    )

    is_trial       = models.BooleanField(default=False, verbose_name="Période d'essai")
    trial_start    = models.DateField(blank=True, null=True, verbose_name="Début du trial")
    trial_end      = models.DateField(blank=True, null=True, verbose_name="Fin du trial")
    trial_notified = models.BooleanField(default=False, verbose_name="Email expiration envoyé")

    class Meta:
        verbose_name        = 'Partenaire'
        verbose_name_plural = 'Partenaires'
        ordering            = ['-created_at']

    def __str__(self):
        return f"{self.company_name} ({self.email})"

    def clean(self):
        if self.email:
            self.email = self.email.lower()
        if not self.email and self.user and self.user.email:
            self.email = self.user.email.lower()
        if self.email:
            qs = Partner.objects.filter(email=self.email)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    {'email': f"Un partenaire avec l'email '{self.email}' existe déjà."}
                )

    def save(self, *args, **kwargs):
        from datetime import date
        from dateutil.relativedelta import relativedelta

        if self.email:
            self.email = self.email.lower()
        if not self.email and self.user and self.user.email:
            self.email = self.user.email.lower()

        if not self.user:
            if not self.email:
                raise ValidationError("Un email est requis pour créer un partenaire.")
            user = User.objects.filter(username=self.email).first()
            if not user:
                user = User.objects.create_user(
                    username=self.email, email=self.email, password="Partner123"
                )
            self.user = user
        else:
            if self.email and (self.user.email != self.email or self.user.username != self.email):
                self.user.email    = self.email
                self.user.username = self.email
                self.user.save()

        is_new = self._state.adding
        if is_new and not self.contract_start and not self.is_trial:
            today = date.today()
            self.is_trial        = True
            self.trial_start     = today
            self.trial_end       = today + relativedelta(months=6)
            self.contract_start  = today
            self.contract_end    = self.trial_end
            self.contract_period = '6_months'
            self.is_verified     = True
            self.is_active       = True
            self.payment_status  = 'active'

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
    def is_trial_active(self) -> bool:
        if not self.is_trial or not self.trial_end:
            return False
        return timezone.now().date() <= self.trial_end

    @property
    def is_trial_expired(self) -> bool:
        if not self.is_trial or not self.trial_end:
            return False
        return timezone.now().date() > self.trial_end

    @property
    def can_add_content(self) -> bool:
        return (
            self.is_active
            and self.is_verified
            and self.is_contract_active
            and not self.account_frozen
            and not self.is_temporarily_disabled
            and self.payment_status == 'active'
    )

    @property
    def is_accessible(self) -> bool:
        return (
            self.is_active
            and not self.account_frozen
            and not self.is_temporarily_disabled
            and self.payment_status == 'active'
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
        self.partner.payment_status  = 'active'
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
        ('trial_expired',       'Trial expiré'),
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
    partner         = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='events')
    title           = models.CharField(max_length=255)
    title_en        = models.CharField(max_length=255, blank=True, default='')
    title_fr        = models.CharField(max_length=255, blank=True, default='')
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
    boost_payment_ref = models.CharField(max_length=255, blank=True, null=True)
    boosted_at        = models.DateTimeField(blank=True, null=True)
    boost_paid_at     = models.DateTimeField(blank=True, null=True)

    def sync_main_fields(self):
        if self.title_en:
            self.title = self.title_en
        elif self.title_fr:
            self.title = self.title_fr
        if self.description_en:
            self.description = self.description_en
        elif self.description_fr:
            self.description = self.description_fr

    @property
    def nb_days(self) -> int:
        if not self.start_date or not self.end_date:
            return 0
        today = timezone.now().date()
        start = max(self.start_date, today)
        return (self.end_date - start).days + 1

    @property
    def boost_price(self) -> float:
        """Prix boost = nb_days × prix configuré dans PricingSettings."""
        return round(_get_boost_price_per_day() * self.nb_days, 3)

    @property
    def boost_price_display(self) -> str:
        return f"{self.boost_price:.3f} TND"

    @property
    def days_until_start(self) -> int:
        if not self.start_date:
            return 0
        return (self.start_date - timezone.now().date()).days

    @property
    def can_be_boosted(self) -> bool:
        return self.days_until_start >= 14


# ── PartnerEventMedia ─────────────────────────────────────────────────────────

class PartnerEventMedia(models.Model):
    event      = models.ForeignKey(PartnerEvent, on_delete=models.CASCADE, related_name='media')
    file       = models.FileField(upload_to='partners/events/', validators=[validate_image_or_video])
    media_type = models.CharField(max_length=10, default='image')
    order      = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

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
    price_per_day    = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    total_price      = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    status           = models.CharField(max_length=20, default='pending')
    created_at       = models.DateTimeField(auto_now_add=True)

    @property
    def nb_days(self) -> int:
        if not self.start_date or not self.end_date:
            return 0
        return (self.end_date - self.start_date).days + 1

    @property
    def ad_price(self) -> float:
        """Prix pub = nb_days × prix configuré dans PricingSettings."""
        return round(_get_ad_price_per_day() * self.nb_days, 3)

    @property
    def ad_price_display(self) -> str:
        return f"{self.ad_price:.3f} TND"

    def save(self, *args, **kwargs):
        from decimal import Decimal
        # Récupère le prix depuis PricingSettings à chaque sauvegarde
        self.price_per_day = Decimal(str(_get_ad_price_per_day()))
        self.total_price   = Decimal(str(self.ad_price))
        super().save(*args, **kwargs)


class Receipt(models.Model):
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Compteur de reçus"

    @classmethod
    def next(cls) -> str:
        from django.db import transaction
        with transaction.atomic():
            obj, _ = cls.objects.select_for_update().get_or_create(id=1)
            obj.last_number += 1
            obj.save(update_fields=['last_number'])
            return f"{obj.last_number:06d}"

class ReceiptHistory(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ('subscription', 'Abonnement'),
        ('boost',        'Boost Événement'),
        ('ad',           'Publicité'),
    ]

    partner        = models.ForeignKey(Partner, on_delete=models.SET_NULL, null=True, blank=True, related_name='receipts')
    receipt_number = models.CharField(max_length=20, unique=True)
    payment_type   = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    amount         = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    client_code    = models.CharField(max_length=20, blank=True)
    payment_ref    = models.CharField(max_length=255, blank=True)
    label          = models.CharField(max_length=255, blank=True)
    details        = models.JSONField(default=dict, blank=True)
    sent_to_email  = models.EmailField(blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Reçu'
        verbose_name_plural = 'Reçus'
        ordering            = ['-created_at']

    def __str__(self):
        return f"Reçu N°{self.receipt_number} — {self.get_payment_type_display()} — {self.sent_to_email}"