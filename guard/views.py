from django.http import HttpResponseRedirect, Http404, JsonResponse
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import (
    CreateView, UpdateView, DeleteView,
    ListView, TemplateView, DetailView,
)
from partners.models import Receipt 
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.utils import timezone
from django.shortcuts import redirect, get_object_or_404
from django.views import View
from django.db import models

import logging
logger = logging.getLogger(__name__)

from shared.models import UserProfile
try:
    from shared.models import City, SubRegion
except ImportError:
    City = SubRegion = None

from .forms import (
    LocationForm, ImageLocationFormSet,
    EventForm, ImageEventFormSet,
    TipForm,
    HikingForm, HikingLocationFormSet, ImageHikingFormSet,
    AdForm,
    PublicTransportForm, PublicTransportFormSet,
    PartnerForm, SponsorForm,
)
from .models import (
    LocationCategory, Location,
    Event, Tip,
    Hiking, Ad,
    PublicTransport,
    Partner, Sponsor,
)

try:
    from partners.models import PartnerEvent, PartnerAd, Partner as PartnerAccount
except ImportError:
    PartnerEvent = PartnerAd = PartnerAccount = None

# ── API HELPERS ───────────────────────────────────────────────────────────────

def get_cities_by_country(request, country_id=None):
    c_id = country_id or request.GET.get('country_id')
    if City and c_id:
        cities = City.objects.filter(country_id=c_id).order_by('name')
        return JsonResponse([{'id': c.id, 'name': c.name} for c in cities], safe=False)
    return JsonResponse([], safe=False)

def get_subregions_by_city(request, city_id=None):
    c_id = city_id or request.GET.get('city_id')
    if SubRegion and c_id:
        subregions = SubRegion.objects.filter(city_id=c_id).order_by('name')
        return JsonResponse([{'id': s.id, 'name': s.name} for s in subregions], safe=False)
    return JsonResponse([], safe=False)

def get_all_subregions(request):
    if SubRegion:
        subregions = SubRegion.objects.all().order_by('name')
        return JsonResponse([{'id': s.id, 'name': s.name} for s in subregions], safe=False)
    return JsonResponse([], safe=False)

def get_locations_by_city(request, city_id=None):
    c_id = city_id or request.GET.get('city_id')
    if Location and c_id:
        locations = Location.objects.filter(city_id=c_id).order_by('name')
        return JsonResponse([{'id': l.id, 'name': l.name} for l in locations], safe=False)
    return JsonResponse([], safe=False)

def get_schedules(request):
    return JsonResponse({'status': 'feature_not_implemented'}, status=200)

# ── MIXINS ────────────────────────────────────────────────────────────────────

class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_active and (
            self.request.user.is_staff or self.request.user.is_superuser
        )

# ── DASHBOARD ─────────────────────────────────────────────────────────────────

class DashboardView(StaffRequiredMixin, LoginRequiredMixin, TemplateView):
    template_name = "guard/views/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["db_stats"] = {
            "total_locations": Location.objects.count(),
            "total_events": Event.objects.count(),
            "total_ads": Ad.objects.count(),
        }
        return context

# ── LOCATIONS ─────────────────────────────────────────────────────────────────

class LocationsListView(StaffRequiredMixin, LoginRequiredMixin, ListView):
    model = Location
    template_name = "guard/views/locations/list.html"
    context_object_name = "locations"

class LocationCreateView(StaffRequiredMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Location
    form_class = LocationForm
    template_name = "guard/views/locations/index.html"
    success_url = reverse_lazy("guard:locationsList")
    success_message = _("Lieu créé.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["image_formset"] = ImageLocationFormSet(
            self.request.POST or None,
            self.request.FILES or None,
            instance=self.object if hasattr(self, 'object') else None
        )
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        if context["image_formset"].is_valid():
            self.object = form.save()
            context["image_formset"].instance = self.object
            context["image_formset"].save()
            return super().form_valid(form)
        return self.form_invalid(form)

class LocationUpdateView(LocationCreateView, UpdateView):
    success_message = _("Lieu mis à jour.")

class LocationDeleteView(StaffRequiredMixin, LoginRequiredMixin, DeleteView):
    model = Location
    success_url = reverse_lazy("guard:locationsList")

# ── EVENTS ────────────────────────────────────────────────────────────────────

class EventListView(StaffRequiredMixin, LoginRequiredMixin, ListView):
    model = Event
    template_name = "guard/views/events/list.html"
    context_object_name = "events"

class EventCreateView(StaffRequiredMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Event
    form_class = EventForm
    template_name = "guard/views/events/index.html"
    success_url = reverse_lazy("guard:eventsList")
    success_message = _("Événement créé.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["image_formset"] = ImageEventFormSet(
            self.request.POST or None,
            self.request.FILES or None,
            instance=self.object if hasattr(self, 'object') else None
        )
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        if context["image_formset"].is_valid():
            self.object = form.save()
            context["image_formset"].instance = self.object
            context["image_formset"].save()
            return super().form_valid(form)
        return self.form_invalid(form)

class EventUpdateView(EventCreateView, UpdateView):
    success_message = _("Événement mis à jour.")

class EventDeleteView(StaffRequiredMixin, LoginRequiredMixin, DeleteView):
    model = Event
    success_url = reverse_lazy("guard:eventsList")

# ── ADS ───────────────────────────────────────────────────────────────────────

class AdListView(StaffRequiredMixin, LoginRequiredMixin, ListView):
    model = Ad
    template_name = "guard/views/ads/list.html"
    context_object_name = "ads"

class AdCreateView(StaffRequiredMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Ad
    form_class = AdForm
    template_name = "guard/views/ads/index.html"
    success_url = reverse_lazy("guard:adsList")
    success_message = _("Publicité créée.")

class AdUpdateView(AdCreateView, UpdateView):
    success_message = _("Publicité mise à jour.")

class AdDeleteView(StaffRequiredMixin, LoginRequiredMixin, DeleteView):
    model = Ad
    template_name = "guard/views/ads/partials/confirm_model.html"
    success_url = reverse_lazy("guard:adsList")

# ── PARTNERS ──────────────────────────────────────────────────────────────────

class PartnerListView(StaffRequiredMixin, LoginRequiredMixin, ListView):
    model = Partner
    template_name = "guard/views/partners/list.html"
    context_object_name = "partners"

class PartnerCreateView(StaffRequiredMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Partner
    form_class = PartnerForm
    template_name = "guard/views/partners/index.html"
    success_url = reverse_lazy("guard:partnersList")
    success_message = _("Partenaire créé.")

class PartnerUpdateView(PartnerCreateView, UpdateView):
    success_message = _("Partenaire mis à jour.")

class PartnerDeleteView(StaffRequiredMixin, LoginRequiredMixin, DeleteView):
    model = Partner
    template_name = "guard/views/partners/delete.html"
    success_url = reverse_lazy("guard:partnersList")

# ── SPONSORS ──────────────────────────────────────────────────────────────────

class SponsorListView(StaffRequiredMixin, LoginRequiredMixin, ListView):
    model = Sponsor
    template_name = "guard/views/sponsors/list.html"
    context_object_name = "sponsors"

class SponsorCreateView(StaffRequiredMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Sponsor
    form_class = SponsorForm
    template_name = "guard/views/sponsors/index.html"
    success_url = reverse_lazy("guard:sponsorsList")
    success_message = _("Sponsor créé.")

class SponsorUpdateView(SponsorCreateView, UpdateView):
    success_message = _("Sponsor mis à jour.")

class SponsorDeleteView(StaffRequiredMixin, LoginRequiredMixin, DeleteView):
    model = Sponsor
    template_name = "guard/views/sponsors/delete.html"
    success_url = reverse_lazy("guard:sponsorsList")

# ── HIKING ────────────────────────────────────────────────────────────────────

class HikingListView(StaffRequiredMixin, LoginRequiredMixin, ListView):
    model = Hiking
    template_name = "guard/views/hiking/list.html"
    context_object_name = "hikings"

class HikingCreateView(StaffRequiredMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Hiking
    form_class = HikingForm
    template_name = "guard/views/hiking/index.html"
    success_url = reverse_lazy("guard:hikingsList")
    success_message = _("Randonnée créée.")

class HikingUpdateView(HikingCreateView, UpdateView):
    success_message = _("Randonnée mise à jour.")

class HikingDeleteView(StaffRequiredMixin, LoginRequiredMixin, DeleteView):
    model = Hiking
    success_url = reverse_lazy("guard:hikingsList")

# ── PUBLIC TRANSPORT ──────────────────────────────────────────────────────────

class PublicTransportListView(StaffRequiredMixin, LoginRequiredMixin, ListView):
    model = PublicTransport
    template_name = "guard/views/publicTransports/list.html"
    context_object_name = "transports"

class PublicTransportCreateView(StaffRequiredMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = PublicTransport
    form_class = PublicTransportForm
    template_name = "guard/views/publicTransports/index.html"
    success_url = reverse_lazy("guard:publicTransportsList")
    success_message = _("Transport créé.")

class PublicTransportUpdateView(PublicTransportCreateView, UpdateView):
    success_message = _("Transport mis à jour.")

class PublicTransportDeleteView(StaffRequiredMixin, LoginRequiredMixin, DeleteView):
    model = PublicTransport
    template_name = "guard/views/publicTransports/partials/confirm_model.html"
    success_url = reverse_lazy("guard:publicTransportsList")

# ── TIPS ──────────────────────────────────────────────────────────────────────

class TipsListView(StaffRequiredMixin, LoginRequiredMixin, ListView):
    model = Tip
    template_name = "guard/views/tips/list.html"
    context_object_name = "tips"

class TipCreateView(StaffRequiredMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Tip
    form_class = TipForm
    template_name = "guard/views/tips/index.html"
    success_url = reverse_lazy("guard:tipsList")
    success_message = _("Astuce créée.")

class TipUpdateView(TipCreateView, UpdateView):
    success_message = _("Astuce mise à jour.")

class TipDeleteView(StaffRequiredMixin, LoginRequiredMixin, DeleteView):
    model = Tip
    success_url = reverse_lazy("guard:tipsList")

# ── TRACKING ──────────────────────────────────────────────────────────────────

class AdTrackingView(View):
    def get(self, request, pk):
        ad = get_object_or_404(Ad, pk=pk)
        return HttpResponseRedirect(ad.destination_link) if ad.destination_link else redirect('guard:adsList')

class EventTrackingView(View):
    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        return HttpResponseRedirect(event.link) if event.link else redirect('guard:eventsList')

class EventClickView(EventTrackingView): pass
class AdClickView(AdTrackingView): pass

# ── SUBSCRIBERS ───────────────────────────────────────────────────────────────

class SubscribersListView(StaffRequiredMixin, LoginRequiredMixin, ListView):
    model = UserProfile
    template_name = "guard/views/subscribers/list.html"
    context_object_name = "subscribers"

@login_required
def check_user_type(request):
    if request.user.is_staff:
        return redirect('guard:dashboard')
    return redirect('/')
# ── PRICING SETTINGS ──────────────────────────────────────────────────────────

from shared.models import PricingSettings

class PricingSettingsView(StaffRequiredMixin, LoginRequiredMixin, TemplateView):
    template_name = "guard/views/pricing_settings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pricing"] = PricingSettings.get()
        return context

    def post(self, request, *args, **kwargs):
        pricing = PricingSettings.get()
        boost = request.POST.get("boost_price_per_day")
        ad    = request.POST.get("ad_price_per_day")
        if boost:
            pricing.boost_price_per_day = boost
        if ad:
            pricing.ad_price_per_day = ad
        pricing.updated_by = request.user
        pricing.save()
        messages.success(request, "Prix mis à jour avec succès.")
        return redirect(request.path)

# ── RECEIPTS ──────────────────────────────────────────────────────────────────

from partners.models import ReceiptHistory

class ReceiptListView(StaffRequiredMixin, LoginRequiredMixin, ListView):
    model               = ReceiptHistory
    template_name       = "guard/views/receipts/list.html"
    context_object_name = "receipts"
    ordering            = ['-created_at']
    paginate_by         = 25

    def get_queryset(self):
        qs = super().get_queryset().select_related('partner')
        q  = self.request.GET.get('q', '').strip()
        pt = self.request.GET.get('payment_type', '').strip()
        if q:
            qs = qs.filter(
                models.Q(receipt_number__icontains=q) |
                models.Q(sent_to_email__icontains=q)  |
                models.Q(partner__company_name__icontains=q)
            )
        if pt:
            qs = qs.filter(payment_type=pt)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q']            = self.request.GET.get('q', '')
        context['payment_type'] = self.request.GET.get('payment_type', '')
        return context

# ── EMAIL CHANGE REQUESTS ─────────────────────────────────────────────────────
# Ajoutez ces imports en haut de views.py si pas déjà présents :
# from partners.models import PartnerAccount  (déjà importé)

from django.views import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator


class EmailChangeListView(StaffRequiredMixin, LoginRequiredMixin, TemplateView):
    template_name = "guard/views/partners/email_changes.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Tous les partenaires avec un email en attente
        context['pending'] = PartnerAccount.objects.filter(
            pending_email__isnull=False
        ).exclude(pending_email='').order_by('-created_at')
        return context

    def post(self, request, *args, **kwargs):
        partner_id = request.POST.get('partner_id')
        action     = request.POST.get('action')  # 'approve' ou 'reject'

        partner = get_object_or_404(PartnerAccount, id=partner_id)

        if action == 'approve' and partner.pending_email:
            old_email         = partner.email
            new_email         = partner.pending_email

            # Met à jour l'email du partenaire et de son User
            partner.email         = new_email
            partner.pending_email = None
            partner.save(update_fields=['email', 'pending_email'])

            if partner.user:
                partner.user.email    = new_email
                partner.user.username = new_email
                partner.user.save()

            messages.success(request, f"Email de {partner.company_name} mis à jour : {old_email} → {new_email}")

        elif action == 'reject':
            partner.pending_email = None
            partner.save(update_fields=['pending_email'])
            messages.warning(request, f"Demande de changement d'email de {partner.company_name} rejetée.")

        return redirect('guard:email_changes')