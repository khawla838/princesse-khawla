from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import (
    Location,
    ImageLocation,
    ImageEvent,
    LocationCategory,
    Event,
    EventCategory,
    Tip,
    Hiking,
    ImageHiking,
    Ad,
    HikingLocation,
    PublicTransport,
    PublicTransportTime,
    PublicTransportType,
    Partner,
    Sponsor,
)
from modeltranslation.admin import TranslationAdmin
from partners.models import ReceiptHistory
from guard.models import DashboardStatistics, ActivityLog, NotificationLog


class ImageInline(admin.TabularInline):
    model = ImageLocation
    extra = 1


@admin.register(Location)
class LocationAdmin(TranslationAdmin):
    list_display = ["name", "country", "city", "category", "created_at"]
    list_filter = ["country", "is_active_ads", "category"]
    search_fields = ["name", "story", "city__name", "country__name", "category__name"]
    inlines = [ImageInline]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("country", "city", "is_active_ads", "category")},
        ),
        (
            _("Location Details"),
            {
                "fields": (
                    "name",
                    "latitude",
                    "longitude",
                    "openFrom",
                    "openTo",
                    "closedDays",
                    "admissionFee",
                    "story",
                )
            },
        ),
    )


@admin.register(LocationCategory)
class LocationCategoryAdmin(TranslationAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]


class ImageEventInline(admin.TabularInline):
    model = ImageEvent
    extra = 1


@admin.register(Event)
class EventAdmin(TranslationAdmin):
    list_display = [
        "name",
        "location",
        "client",
        "startDate",
        "endDate",
        "price",
        "boost",
        "created_at",
    ]
    list_filter = ["startDate", "endDate", "location", "boost"]
    search_fields = ["name", "description", "location__name", "client__user__username"]
    inlines = [ImageEventInline]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("name", "client", "location", "category")},
        ),
        (
            _("Event Schedule"),
            {
                "fields": (
                    "startDate",
                    "endDate",
                    "time",
                    "link",
                    "short_link",
                    "short_id",
                )
            },
        ),
        (_("Details"), {"fields": ("price", "description", "boost")}),
    )


@admin.register(EventCategory)
class EventCategoryAdmin(TranslationAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]


@admin.register(Tip)
class TipAdmin(TranslationAdmin):
    list_display = ["city", "created_at"]
    list_filter = ["city"]
    search_fields = ["city__name"]


class HikingLocationInline(admin.TabularInline):
    model = HikingLocation
    extra = 1


class ImageHikingInline(admin.TabularInline):
    model = ImageHiking
    extra = 1


@admin.register(Hiking)
class HikingAdmin(TranslationAdmin):
    list_display = [
        "city",
        "name",
    ]
    list_filter = ["city", "name", "locations"]
    search_fields = [
        "name",
        "description",
    ]
    inlines = [HikingLocationInline, ImageHikingInline]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("name", "city", "description")},
        ),
        (
            _("Geolocation"),
            {"fields": ("latitude", "longitude")},
        ),
    )


@admin.register(Ad)
class AdAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "client",
        "clicks",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "client"]
    search_fields = ["name", "link", "client__user__username"]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("name", "client", "is_active")},
        ),
        (
            _("Ad Images"),
            {"fields": ("image_mobile", "image_tablet")},
        ),
        (
            _("Link Information"),
            {
                "fields": (
                    "link",
                    "short_link",
                    "short_id",
                )
            },
        ),
        (_("Statistics"), {"fields": ("clicks",)}),
    )


@admin.register(PublicTransportType)
class PublicTransportTypeAdmin(TranslationAdmin):
    list_display = ["name"]
    search_fields = ["name"]


class PublicTransportTimeInline(admin.TabularInline):
    model = PublicTransportTime
    extra = 1


@admin.register(PublicTransport)
class PublicTransportAdmin(admin.ModelAdmin):
    list_display = [
        "city",
        "publicTransportType",
        "fromRegion",
        "toRegion",
    ]
    list_filter = [
        "city",
        "publicTransportType",
    ]
    search_fields = [
        "city__name",
    ]
    inlines = [PublicTransportTimeInline]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("publicTransportType", "city", "fromRegion", "toRegion")},
        ),
    )

    class Media:
        js = ("admin/js/public_transport_admin.js",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name in ["fromRegion", "toRegion"]:
            # If we are editing an existing object, filter subregions by city
            obj_id = request.resolver_match.kwargs.get("object_id")
            if obj_id:
                try:
                    obj = self.get_object(request, obj_id)
                    if obj and obj.city:
                        from cities_light.models import SubRegion

                        kwargs["queryset"] = SubRegion.objects.filter(
                            region=obj.city.region
                        )
                except Exception:
                    pass
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# @admin.register(Partner)
# class PartnerAdmin(admin.ModelAdmin):
#     list_display = ["name", "image", "link"]
#     search_fields = ["name"]

#     fieldsets = (
#         (
#             _("Basic Information"),
#             {"fields": ("name", "image", "link")},
#         ),
#     )


@admin.register(Sponsor)
class SponsorAdmin(admin.ModelAdmin):
    list_display = ["name", "image", "link"]
    search_fields = ["name"]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("name", "image", "link")},
        ),
    )

@admin.register(DashboardStatistics)
class DashboardStatisticsAdmin(admin.ModelAdmin):
    """
    Admin panel pour visualiser les statistiques du dashboard.
    Tous les champs sont en lecture seule (mis à jour par les signaux).
    """
    readonly_fields = [
        'total_locations', 'locations_this_month',
        'total_events', 'upcoming_events', 'events_this_month',
        'total_hikings', 'hikings_this_month',
        'total_ads', 'active_ads',
        'total_fcm_devices', 'ios_devices', 'android_devices',
        'active_users_30d',
        'notifications_sent_24h', 'notifications_failed_24h',
        'error_count_24h',
        'updated_at', 'created_at'
    ]
    
    list_display = ['updated_at', 'total_locations', 'total_events', 'total_hikings']
    ordering = ['-updated_at']
    
    fieldsets = (
        (_('Locations'), {
            'fields': ('total_locations', 'locations_this_month'),
        }),
        (_('Events'), {
            'fields': ('total_events', 'upcoming_events', 'events_this_month'),
        }),
        (_('Hikings'), {
            'fields': ('total_hikings', 'hikings_this_month'),
        }),
        (_('Advertisements'), {
            'fields': ('total_ads', 'active_ads'),
        }),
        (_('Devices & Users'), {
            'fields': ('total_fcm_devices', 'ios_devices', 'android_devices', 'active_users_30d'),
        }),
        (_('Notifications (24h)'), {
            'fields': ('notifications_sent_24h', 'notifications_failed_24h'),
        }),
        (_('System'), {
            'fields': ('error_count_24h', 'last_error_message'),
        }),
        (_('Timestamps'), {
            'fields': ('updated_at', 'created_at'),
        }),
    )
    
    def has_add_permission(self, request):
        """Empêche la création manuelle de statistiques"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Empêche la suppression des statistiques"""
        return False


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """
    Admin panel pour visualiser le journal d'activité du système.
    Chaque action créée/modifiée est loggée automatiquement via les signaux.
    """
    list_display = ['timestamp', 'activity_type', 'entity_name', 'entity_type', 'success']
    list_filter = ['activity_type', 'success', 'entity_type', 'timestamp']
    search_fields = ['entity_name', 'entity_id', 'user']
    readonly_fields = ['timestamp', 'activity_type', 'entity_type', 'entity_id']
    ordering = ['-timestamp']
    
    fieldsets = (
        (_('Activity'), {
            'fields': ('activity_type', 'timestamp'),
        }),
        (_('Entity'), {
            'fields': ('entity_type', 'entity_id', 'entity_name'),
        }),
        (_('Details'), {
            'fields': ('user', 'success', 'error_message', 'details'),
        }),
    )
    
    def has_add_permission(self, request):
        """Logs sont créés automatiquement, pas d'ajout manuel"""
        return False


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    """
    Admin panel pour visualiser l'historique des notifications push envoyées.
    Utile pour auditer les notifications et détecter les problèmes.
    """
    list_display = ['timestamp', 'notification_type', 'status', 'device_count_succeeded', 'device_count_attempted']
    list_filter = ['status', 'notification_type', 'timestamp']
    search_fields = ['title', 'entity_id']
    readonly_fields = ['timestamp', 'response']
    ordering = ['-timestamp']
    
    fieldsets = (
        (_('Notification Info'), {
            'fields': ('notification_type', 'entity_type', 'entity_id', 'timestamp'),
        }),
        (_('Content'), {
            'fields': ('title', 'body'),
        }),
        (_('Delivery'), {
            'fields': ('status', 'device_count_attempted', 'device_count_succeeded'),
        }),
        (_('Response'), {
            'fields': ('response',),
            'classes': ('collapse',),
        }),
    )
    
    def has_add_permission(self, request):
        """Logs sont créés automatiquement"""
        return False


@admin.register(ReceiptHistory)
class ReceiptHistoryAdmin(admin.ModelAdmin):
    list_display  = ['receipt_number', 'partner', 'payment_type', 'amount', 'sent_to_email', 'created_at']
    list_filter   = ['payment_type', 'created_at']
    search_fields = ['receipt_number', 'sent_to_email', 'partner__company_name', 'payment_ref']
    readonly_fields = [
        'receipt_number', 'partner', 'payment_type', 'amount',
        'client_code', 'payment_ref', 'label', 'details',
        'sent_to_email', 'created_at',
    ]
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False