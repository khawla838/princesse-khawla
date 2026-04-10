from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from django.utils.html import format_html
from django import forms
from django.core.mail import send_mail
from django.conf import settings
from .models import (
    Partner, PartnerContract, PartnerEvent,
    PartnerEventMedia, PartnerAd, Coupon, AdminNotification
)

# ── Actions ───────────────────────────────────────────────────────────────────

def approve_email_change(modeladmin, request, queryset):
    count = 0
    for partner in queryset.filter(pending_email__isnull=False):
        partner.user.email = partner.pending_email
        partner.user.save(update_fields=['email'])
        partner.pending_email = None
        partner.save(update_fields=['pending_email'])
        count += 1
    messages.success(request, f"{count} changement(s) d'email approuvé(s).")
approve_email_change.short_description = "✅ Approuver le changement d'email"

def reject_email_change(modeladmin, request, queryset):
    count = queryset.filter(pending_email__isnull=False).update(pending_email=None)
    messages.success(request, f"{count} changement(s) rejeté(s).")
reject_email_change.short_description = "❌ Rejeter le changement d'email"

def freeze_account(modeladmin, request, queryset):
    count = queryset.update(account_frozen=True)
    messages.success(request, f"{count} compte(s) suspendu(s).")
freeze_account.short_description = "🔒 Suspendre le compte"

def unfreeze_account(modeladmin, request, queryset):
    count = queryset.update(account_frozen=False)
    messages.success(request, f"{count} compte(s) réactivé(s).")
unfreeze_account.short_description = "🔓 Réactiver le compte"

def verify_partner(modeladmin, request, queryset):
    count = queryset.update(is_verified=True, validated_at=timezone.now())
    messages.success(request, f"{count} partenaire(s) vérifié(s).")
verify_partner.short_description = "✅ Vérifier le partenaire"

def send_terms_changed_email(modeladmin, request, queryset):
    from datetime import date
    today = date.today()
    count_email = 0
    count_frozen = 0

    for partner in queryset:
        should_freeze = (
            (partner.is_trial and partner.trial_end and partner.trial_end < today)
            or
            (not partner.is_trial and (not partner.contract_end or partner.contract_end < today))
        )

        try:
            if should_freeze:
                send_mail(
                    subject="📢 Mise à jour conditions + Suspension de votre compte FielMedina",
                    message=f"""Bonjour {partner.company_name},

Nous vous informons que les conditions générales d'utilisation de FielMedina ont été mises à jour.

Suite à cette mise à jour, votre compte a été suspendu car votre période d'essai
ou votre abonnement n'est plus actif.

Pour réactiver votre compte, veuillez souscrire à un abonnement :
{settings.SITE_URL}/partners/subscription/

Cordialement,
L'équipe FielMedina""",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[partner.email],
                    fail_silently=False,
                )
                partner.account_frozen = True
                partner.is_verified    = False
                partner.save(update_fields=['account_frozen', 'is_verified'])
                count_frozen += 1
            else:
                send_mail(
                    subject="📢 Mise à jour des conditions générales FielMedina",
                    message=f"""Bonjour {partner.company_name},

Nous vous informons que les conditions générales d'utilisation de FielMedina ont été mises à jour.

Pour consulter les nouvelles conditions et continuer à utiliser nos services :
{settings.SITE_URL}/partners/subscription/

Cordialement,
L'équipe FielMedina""",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[partner.email],
                    fail_silently=False,
                )
            count_email += 1
        except Exception as e:
            messages.error(request, f"Erreur pour {partner.email}: {e}")

    messages.success(
        request,
        f"{count_email} email(s) envoyé(s). {count_frozen} compte(s) suspendu(s)."
    )
send_terms_changed_email.short_description = "📧 Envoyer email conditions + suspendre non payants"


def convert_trial_to_paid(modeladmin, request, queryset):
    count = 0
    for partner in queryset.filter(is_trial=True):
        partner.is_trial       = False
        partner.is_verified    = True
        partner.account_frozen = False
        partner.save(update_fields=['is_trial', 'is_verified', 'account_frozen'])
        count += 1
    messages.success(request, f"{count} partenaire(s) converti(s) en payant.")
convert_trial_to_paid.short_description = "💳 Convertir trial → payant"


def send_trial_expiry_email(modeladmin, request, queryset):
    count = 0
    for partner in queryset:
        try:
            send_mail(
                subject="Votre période d'essai FielMedina a expiré",
                message=f"""Bonjour {partner.company_name},

Votre période d'essai gratuite de 6 mois sur FielMedina a expiré le {partner.trial_end.strftime('%d/%m/%Y') if partner.trial_end else '—'}.

Pour continuer à bénéficier de nos services :
{settings.SITE_URL}/partners/subscription/

Cordialement,
L'équipe FielMedina""",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[partner.email],
                fail_silently=False,
            )
            partner.trial_notified = True
            partner.is_verified    = False
            partner.save(update_fields=['trial_notified', 'is_verified'])
            count += 1
        except Exception as e:
            messages.error(request, f"Erreur pour {partner.email}: {e}")
    messages.success(request, f"{count} email(s) d'expiration envoyé(s).")
send_trial_expiry_email.short_description = "⏰ Envoyer email expiration trial"


# ── Partner Admin Form ────────────────────────────────────────────────────────

class PartnerAdminForm(forms.ModelForm):
    class Meta:
        model  = Partner
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        user  = cleaned_data.get('user')
        email = cleaned_data.get('email', '')

        if email:
            email = email.strip().lower()
            cleaned_data['email'] = email

        if not email and user and user.email:
            email = user.email.strip().lower()
            cleaned_data['email'] = email

        if email:
            qs = Partner.objects.filter(email=email)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    f"Un partenaire avec l'email '{email}' existe déjà. "
                    f"Veuillez utiliser un autre email ou un autre utilisateur."
                )

        return cleaned_data


# ── Admin Partner ─────────────────────────────────────────────────────────────

@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    form = PartnerAdminForm

    list_display  = [
        'company_name', 'get_email', 'status_display', 'trial_display',
        'contract_end', 'days_left_display',
        'pending_email_display', 'unpaid_alert_display',
    ]
    list_filter   = ['is_verified', 'is_active', 'account_frozen',
                     'is_temporarily_disabled', 'contract_period',
                     'is_trial', 'trial_notified']
    search_fields = ['company_name', 'user__email', 'pending_email']
    readonly_fields = ['created_at', 'validated_at', 'id',
                       'disabled_at', 'reactivated_at',
                       'trial_start', 'trial_end', 'trial_notified']

    actions = [
        verify_partner,
        approve_email_change, reject_email_change,
        freeze_account, unfreeze_account,
        send_terms_changed_email,
        convert_trial_to_paid,
        send_trial_expiry_email,
    ]

    fieldsets = (
        ('Identité', {
            'fields': ('id', 'user', 'company_name', 'email', 'phone', 'logo')
        }),
        ('Statut', {
            'fields': ('is_active', 'is_verified', 'account_frozen',
                       'is_temporarily_disabled', 'disabled_reason',
                       'disabled_at', 'reactivated_at', 'validated_at')
        }),
        ('Contrat', {
            'fields': ('contract_period', 'payment_type', 'contract_start', 'contract_end')
        }),
        ("Période d'essai", {
            'fields': ('is_trial', 'trial_start', 'trial_end', 'trial_notified'),
            'classes': ('collapse',),
        }),
        ('Email en attente', {
            'fields': ('pending_email',),
            'classes': ('collapse',),
        }),
        ('Dates', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    def get_email(self, obj):
        return obj.email or (obj.user.email if obj.user else '—')
    get_email.short_description = "Email"

    def trial_display(self, obj):
        if not obj.is_trial:
            return '—'
        if obj.is_trial_expired:
            return format_html('<span style="color:red">🔴 Trial expiré</span>')
        if obj.trial_end:
            days = (obj.trial_end - timezone.now().date()).days
            return format_html('<span style="color:green">🟢 Trial — {} j restants</span>', days)
        return format_html('<span style="color:blue">🔵 Trial</span>')
    trial_display.short_description = "Trial"

    def status_display(self, obj):
        if obj.is_temporarily_disabled:
            return format_html('<span style="color:orange">⏸ Désactivé</span>')
        if obj.account_frozen:
            return format_html('<span style="color:red">🔒 Suspendu</span>')
        if obj.is_verified:
            return format_html('<span style="color:green">✅ Actif</span>')
        return format_html('<span style="color:gray">⏳ En attente</span>')
    status_display.short_description = "Statut"

    def days_left_display(self, obj):
        days = obj.days_until_expiry
        if days is None:
            return "—"
        if days <= 0:
            return format_html('<span style="color:red">Expiré</span>')
        return f"{days} jours"
    days_left_display.short_description = "Expiration"

    def pending_email_display(self, obj):
        if obj.pending_email:
            return format_html('<span style="color:orange">⏳ {}</span>', obj.pending_email)
        return "—"
    pending_email_display.short_description = "Email en attente"

    def unpaid_alert_display(self, obj):
        days = obj.days_until_expiry
        if days is not None and days <= -10:
            return format_html('<span style="color:red;font-weight:bold">🚨 Impayé {}j</span>', abs(days))
        return "—"
    unpaid_alert_display.short_description = "⚠️ Alerte impayé"


# ── Admin Event ────────────────────────────────────────────────────────────────

@admin.register(PartnerEvent)
class PartnerEventAdmin(admin.ModelAdmin):
    list_display    = ['title', 'partner', 'status', 'start_date', 'is_published']
    list_filter     = ['status', 'is_published']
    search_fields   = ['title', 'partner__company_name']
    readonly_fields = ['created_at', 'updated_at']


# ── Admin Ad ───────────────────────────────────────────────────────────────────

@admin.register(PartnerAd)
class PartnerAdAdmin(admin.ModelAdmin):
    list_display    = ['title', 'partner', 'status', 'start_date', 'end_date', 'total_price']
    list_filter     = ['status']
    search_fields   = ['title', 'partner__company_name']
    readonly_fields = ['created_at', 'total_price']


# ── Autres ─────────────────────────────────────────────────────────────────────

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display    = ['code', 'discount_percentage', 'is_active', 'current_uses']
    readonly_fields = ['created_at', 'current_uses']

admin.site.register(PartnerContract)
admin.site.register(AdminNotification)
admin.site.register(PartnerEventMedia)

def activate_payment(modeladmin, request, queryset):
    count = queryset.update(payment_status='active')
    messages.success(request, f"{count} paiement(s) activé(s).")
activate_payment.short_description = "💚 Activer le paiement"

def deactivate_payment(modeladmin, request, queryset):
    count = 0
    for partner in queryset:
        partner.payment_status = 'not_active'
        partner.account_frozen = True
        partner.save(update_fields=['payment_status', 'account_frozen'])
        count += 1
    messages.success(request, f"{count} paiement(s) désactivé(s) + compte(s) suspendu(s).")
deactivate_payment.short_description = "🔴 Désactiver le paiement + suspendre"

