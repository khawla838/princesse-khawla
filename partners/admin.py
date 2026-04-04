from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from django.utils.html import format_html
from django import forms
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

        # Auto-fill email from selected user if email field is empty
        if not email and user and user.email:
            email = user.email.strip().lower()
            cleaned_data['email'] = email

        # Friendly duplicate check instead of raw IntegrityError
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
        'company_name', 'get_email', 'status_display',
        'contract_end', 'days_left_display',
        'pending_email_display', 'unpaid_alert_display'
    ]
    list_filter   = ['is_verified', 'is_active', 'account_frozen',
                     'is_temporarily_disabled', 'contract_period']
    search_fields = ['company_name', 'user__email', 'pending_email']
    readonly_fields = ['created_at', 'validated_at', 'id', 'disabled_at', 'reactivated_at']

    actions = [
        verify_partner, approve_email_change, reject_email_change,
        freeze_account, unfreeze_account,
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
        # Affiche l'email du Partner en priorité, sinon celui du User lié
        return obj.email or (obj.user.email if obj.user else '—')
    get_email.short_description = "Email"

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