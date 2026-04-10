from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from modeltranslation.admin import TranslationAdmin
from .models import Page, UserProfile, UserPreference, PricingSettings


@admin.register(Page)
class PageAdmin(TranslationAdmin):
    list_display  = ["title", "slug", "is_active", "created_at"]
    list_filter   = ["is_active", "created_at"]
    search_fields = ["title", "slug", "content"]
    list_editable = ["is_active"]
    ordering      = ["slug"]

    fieldsets = (
        (_("Basic Information"), {"fields": ("slug", "is_active")}),
        (_("Content"),           {"fields": ("title", "content")}),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display  = ("user", "user_type", "subscription_plan",
                     "subscription_status", "subscription_renews_at", "created_at")
    list_filter   = ("user_type", "subscription_status")
    search_fields = ("user__username", "user__email")

    def save_model(self, request, obj, form, change):
        obj.user.is_staff = obj.user_type == UserProfile.UserType.STAFF
        obj.user.save(update_fields=["is_staff"])
        super().save_model(request, obj, form, change)


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display  = ("user_uid", "first_visit", "traveling_with", "interests", "created_at")
    list_filter   = ("first_visit", "traveling_with")
    search_fields = ("user_uid", "traveling_with")


# ── PricingSettings (Singleton) ───────────────────────────────────────────────

@admin.register(PricingSettings)
class PricingSettingsAdmin(admin.ModelAdmin):
    list_display  = ('boost_price_per_day', 'ad_price_per_day', 'updated_by', 'updated_at')
    readonly_fields = ('updated_at',)

    fields = ('boost_price_per_day', 'ad_price_per_day', 'updated_by', 'updated_at')

    def has_add_permission(self, request):
        # Pas de bouton "Add" si le singleton existe déjà
        return not PricingSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)