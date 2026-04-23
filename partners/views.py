from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import json
import uuid

from partners.models import Partner, PartnerEvent, PartnerEventMedia, PartnerAd, Coupon
from partners.forms import PartnerEventForm, PartnerAdForm
from partners import konnect
from shared.models import PricingSettings
from partners.receipt import send_receipt


# ── Décorateur unifié ─────────────────────────────────────────────────────────

def partner_required(view_func):
    @login_required(login_url='shared:login')
    def wrapper(request, *args, **kwargs):
        try:
            partner = request.user.partner_profile
        except Partner.DoesNotExist:
            return redirect('guard:dashboard')

        if not partner.is_active:
            messages.error(request, "Votre compte partenaire est désactivé.")
            from django.contrib.auth import logout
            logout(request)
            return redirect('shared:login')

        request.partner = partner
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# ── Dashboard ─────────────────────────────────────────────────────────────────

@partner_required
def partner_dashboard(request):
    partner = request.partner
    context = {
        'partner':           partner,
        'events_count':      partner.events.count(),
        'ads_count':         partner.ads.count(),
        'contract_active':   partner.is_contract_active,
        'days_until_expiry': partner.days_until_expiry,
        'can_add':           partner.can_add_content,
        'now':               timezone.now().date(),
    }
    return render(request, 'partners/dashboard.html', context)


# ── Événements ────────────────────────────────────────────────────────────────

@partner_required
def event_list(request):
    partner = request.partner
    events  = partner.events.all().order_by('-created_at')
    return render(request, 'partners/events/list.html', {
        'partner': partner,
        'events':  events,
        'can_add': partner.can_add_content,
    })


@partner_required
def event_create(request):
    partner = request.partner
    if not partner.can_add_content:
        messages.error(request, "Votre compte ne vous permet pas d'ajouter des événements.")
        return redirect('partners:event_list')

    form = PartnerEventForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        event         = form.save(commit=False)
        event.partner = partner
        event.save()
        files = request.FILES.getlist('media')
        for i, f in enumerate(files):
            PartnerEventMedia.objects.create(event=event, file=f, order=i)
        messages.success(request, f"Événement '{event.title}' créé avec succès.")
        return redirect('partners:event_list')

    return render(request, 'partners/events/create.html', {'partner': partner, 'form': form})


@partner_required
def event_boost(request, event_id):
    partner = request.partner
    event   = get_object_or_404(PartnerEvent, id=event_id, partner=partner)
    if event.is_boosted:
        return redirect('partners:event_list')
    days = (event.start_date - timezone.now().date()).days
    if days < 14:
        messages.error(request, f"Le Boost nécessite au moins 14 jours avant le début ({days} jour(s)).")
        return redirect('partners:event_list')
    if not partner.can_add_content:
        messages.error(request, "Votre compte est suspendu.")
        return redirect('partners:event_list')
    return redirect('partners:event_boost_payment', event_id=event.id)


@partner_required
def event_boost_payment(request, event_id):
    partner = request.partner
    event   = get_object_or_404(PartnerEvent, id=event_id, partner=partner)
    if event.is_boosted:
        return redirect('partners:event_list')
    if request.method == 'POST':
        BOOST_PRICE_MILLIMES = int(event.boost_price * 1000)
        order_id    = f"boost-{event.id}"
        base_url    = request.build_absolute_uri('/').rstrip('/')
        result = konnect.init_payment(
            amount_millimes=BOOST_PRICE_MILLIMES,
            order_id=order_id,
            description=f"Boost événement: {event.title}",
            webhook_url=f"{base_url}/partners/events/{event.id}/boost/webhook/",
            success_url=f"{base_url}/partners/events/{event.id}/boost/success/",
            fail_url=f"{base_url}/partners/events/",
        )
        if result.get('payUrl'):
            event.boost_payment_ref = result['paymentRef']
            event.save(update_fields=['boost_payment_ref'])
            return redirect(result['payUrl'])
        else:
            messages.error(request, f"Erreur Konnect : {result.get('error', 'Inconnu')}")
    return render(request, 'partners/events/boost_payment.html', {
        'partner': partner, 'event': event, 'boost_price': event.boost_price_display,
    })


@csrf_exempt
def event_boost_webhook(request, event_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            if data.get('status') == 'completed':
                event = PartnerEvent.objects.get(id=event_id)
                event.is_boosted        = True
                event.boosted_at        = timezone.now()
                event.status            = 'boosted'
                event.boost_payment_ref = data.get('payment_ref') or data.get('paymentRef', '')
                event.boost_paid_at     = timezone.now()
                event.save(update_fields=['is_boosted', 'boosted_at', 'status', 'boost_payment_ref', 'boost_paid_at'])
        except Exception:
            pass
    return JsonResponse({'received': True})


@partner_required
def event_boost_success(request, event_id):
    partner     = request.partner
    event       = get_object_or_404(PartnerEvent, id=event_id, partner=partner)
    payment_ref = request.GET.get('payment_ref', '')
    if payment_ref:
        result = konnect.verify_payment(payment_ref)
        if result.get('paid'):
            event.is_boosted        = True
            event.boosted_at        = timezone.now()
            event.status            = 'boosted'
            event.boost_payment_ref = payment_ref
            event.boost_paid_at     = timezone.now()
            event.save(update_fields=['is_boosted', 'boosted_at', 'status', 'boost_payment_ref', 'boost_paid_at'])
            send_receipt(partner, 'boost', {
                'label':     'Boost Evenement',
                'Evenement': event.title,
                'Periode':   f"{event.start_date} - {event.end_date}",
                'Duree':     f"{event.nb_days} jour(s)",
                'Reference': payment_ref,
                'amount':    f"{event.boost_price:.3f}",
            }, payment_ref=payment_ref)
            messages.success(request, f"Événement '{event.title}' boosté avec succès !")
        else:
            messages.error(request, "Paiement non confirmé.")
    return redirect('partners:event_list')


@partner_required
def event_delete(request, event_id):
    partner = request.partner
    event   = get_object_or_404(PartnerEvent, id=event_id, partner=partner)
    if request.method == 'POST':
        title = event.title
        event.delete()
        messages.success(request, f"Événement '{title}' supprimé.")
    return redirect('partners:event_list')


# ── Publicités ────────────────────────────────────────────────────────────────

@partner_required
def ad_list(request):
    partner = request.partner
    ads     = partner.ads.all().order_by('-created_at')
    pricing = PricingSettings.get()
    return render(request, 'partners/ads/list.html', {
        'partner':          partner,
        'ads':              ads,
        'can_add':          partner.can_add_content,
        'ad_price_per_day': pricing.ad_price_per_day,
    })


@partner_required
def ad_create(request):
    partner = request.partner
    if not partner.can_add_content:
        messages.error(request, "Votre compte ne vous permet pas de créer des publicités.")
        return redirect('partners:ad_list')
    pricing = PricingSettings.get()
    form    = PartnerAdForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        ad         = form.save(commit=False)
        ad.partner = partner
        ad.save()
        messages.success(request, "Publicité créée ! Confirmez pour procéder au paiement.")
        return redirect('partners:ad_confirm', ad_id=ad.id)
    return render(request, 'partners/ads/create.html', {
        'partner':          partner,
        'form':             form,
        'ad_price_per_day': pricing.ad_price_per_day,
    })


@partner_required
def ad_confirm(request, ad_id):
    partner = request.partner
    ad      = get_object_or_404(PartnerAd, id=ad_id, partner=partner)
    if request.method == 'POST':
        ad.status = 'confirmed'
        ad.save(update_fields=['status'])
        messages.success(request, "Publicité confirmée !")
        return redirect('partners:ad_payment', ad_id=ad.id)
    return render(request, 'partners/ads/confirm.html', {'partner': partner, 'ad': ad})


@partner_required
def ad_payment(request, ad_id):
    partner = request.partner
    ad      = get_object_or_404(PartnerAd, id=ad_id, partner=partner)
    if request.method == 'POST':
        amount_millimes = int(float(ad.total_price) * 1000)
        base_url        = request.build_absolute_uri('/').rstrip('/')
        result = konnect.init_payment(
            amount_millimes=amount_millimes,
            order_id=f"ad-{ad.id}",
            description=f"Publicité: {ad.title}",
            webhook_url=f"{base_url}/partners/ads/{ad.id}/webhook/",
            success_url=f"{base_url}/partners/ads/{ad.id}/success/",
            fail_url=f"{base_url}/partners/ads/",
        )
        if result.get('payUrl'):
            request.session['ad_payment_ref'] = result['paymentRef']
            return redirect(result['payUrl'])
        else:
            messages.error(request, f"Erreur Konnect : {result.get('error', 'Inconnu')}")
    return render(request, 'partners/ads/payment.html', {'partner': partner, 'ad': ad})


@csrf_exempt
def ad_webhook(request, ad_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            if data.get('status') == 'completed':
                ad        = PartnerAd.objects.get(id=ad_id)
                ad.status = 'active'
                ad.save(update_fields=['status'])
        except Exception:
            pass
    return JsonResponse({'received': True})


@partner_required
def ad_success(request, ad_id):
    partner     = request.partner
    ad          = get_object_or_404(PartnerAd, id=ad_id, partner=partner)
    payment_ref = request.GET.get('payment_ref') or request.session.pop('ad_payment_ref', '')
    send_receipt(partner, 'ad', {
        'label':   'Publicite FielMedina',
        'Periode': f"{ad.start_date} - {ad.end_date}",
        'Duree':   f"{ad.nb_days} jour(s)",
        'amount':  f"{ad.total_price:.3f}",
    }, payment_ref=payment_ref)
    messages.success(request, "Publicité activée avec succès !")
    return redirect('partners:ad_list')


@partner_required
def ad_delete(request, ad_id):
    partner = request.partner
    ad      = get_object_or_404(PartnerAd, id=ad_id, partner=partner)
    if request.method == 'POST':
        ad.delete()
        messages.success(request, "Publicité supprimée.")
    return redirect('partners:ad_list')


# ── Abonnement ────────────────────────────────────────────────────────────────

@partner_required
def subscription(request):
    partner = request.partner
    pricing = PricingSettings.get()
    from partners.pricing import SUBSCRIPTION_PRICES, PERIOD_LABELS, PERIOD_MONTHS
    periods           = {}
    base_price_1month = SUBSCRIPTION_PRICES['1_month']['total']
    for key, prices in SUBSCRIPTION_PRICES.items():
        saving = round((PERIOD_MONTHS[key] * base_price_1month) - prices['total'], 3)
        periods[key] = {
            'label':   PERIOD_LABELS[key],
            'total':   prices['total'],
            'monthly': round(prices['monthly'], 3),
            'saving':  saving if saving > 0 else 0,
        }
    if request.method == 'POST':
        period       = request.POST.get('period', '1_month')
        payment_type = request.POST.get('payment_type', 'total')
        from partners.pricing import calculate_subscription_price
        price_info      = calculate_subscription_price(period, payment_type)
        amount_millimes = int(float(price_info['first_payment']) * 1000)
        base_url        = request.build_absolute_uri('/').rstrip('/')
        result = konnect.init_payment(
            amount_millimes=amount_millimes,
            order_id=f"sub-{partner.id}-{period}",
            description=f"Abonnement FielMedina {price_info['period_label']}",
            webhook_url=f"{base_url}/partners/subscription/webhook/",
            success_url=f"{base_url}/partners/subscription/success/?period={period}&payment_type={payment_type}",
            fail_url=f"{base_url}/partners/subscription/",
        )
        if result.get('payUrl'):
            request.session['sub_period']       = period
            request.session['sub_payment_type'] = payment_type
            request.session['sub_payment_ref']  = result['paymentRef']
            return redirect(result['payUrl'])
        else:
            messages.error(request, f"Erreur Konnect : {result.get('error', 'Inconnu')}")
    return render(request, 'partners/subscription.html', {
        'partner':             partner,
        'periods':             periods,
        'contract_active':     partner.is_contract_active,
        'days_until_expiry':   partner.days_until_expiry,
        'boost_price_per_day': pricing.boost_price_per_day,
        'ad_price_per_day':    pricing.ad_price_per_day,
    })


@csrf_exempt
def subscription_webhook(request):
    if request.method == 'POST':
        try:
            data     = json.loads(request.body)
            order_id = data.get('orderId', '')
            if data.get('status') == 'completed' and order_id.startswith('sub-'):
                parts      = order_id.split('-')
                partner_id = parts[1]
                period     = '_'.join(parts[2:])
                _activate_subscription(partner_id, period, 'total', data.get('paymentRef', ''))
        except Exception:
            pass
    return JsonResponse({'received': True})


@partner_required
def subscription_success(request):
    partner      = request.partner
    period       = request.GET.get('period') or request.session.get('sub_period', '1_month')
    payment_type = request.GET.get('payment_type') or request.session.get('sub_payment_type', 'total')
    payment_ref  = request.session.get('sub_payment_ref', '')
    if payment_ref:
        result = konnect.verify_payment(payment_ref)
        if result.get('paid'):
            _activate_subscription(str(partner.id), period, payment_type, payment_ref)
            from partners.pricing import calculate_subscription_price, PERIOD_LABELS
            price_info = calculate_subscription_price(period, payment_type)
            send_receipt(partner, 'subscription', {
                'label':     f"Abonnement {PERIOD_LABELS.get(period, period)}",
                'Periode':   PERIOD_LABELS.get(period, period),
                'Type':      'Paiement total' if payment_type == 'total' else 'Mensuel',
                'Reference': payment_ref,
                'amount':    f"{price_info['total']:.3f}",
            }, payment_ref=payment_ref)
            messages.success(request, "Abonnement activé avec succès !")
            for k in ['sub_period', 'sub_payment_type', 'sub_payment_ref']:
                request.session.pop(k, None)
        else:
            messages.error(request, "Paiement non confirmé. Contactez le support.")
    return redirect('partners:subscription')


def _activate_subscription(partner_id, period, payment_type, payment_ref):
    from datetime import date
    from dateutil.relativedelta import relativedelta
    from partners.pricing import calculate_subscription_price, PERIOD_MONTHS
    try:
        partner    = Partner.objects.get(id=partner_id)
        price_info = calculate_subscription_price(period, payment_type)
        today      = date.today()
        end_date   = today + relativedelta(months=PERIOD_MONTHS.get(period, 1))
        partner.contract_period = period
        partner.payment_type    = payment_type
        partner.contract_start  = today
        partner.contract_end    = end_date
        partner.account_frozen  = False
        partner.is_verified     = True
        partner.save(update_fields=['contract_period', 'payment_type', 'contract_start',
                                    'contract_end', 'account_frozen', 'is_verified'])
        from partners.models import PartnerContract
        PartnerContract.objects.create(
            partner=partner, period=period, payment_type=payment_type,
            start_date=today, end_date=end_date,
            total_amount=price_info['total'], monthly_amount=price_info['monthly'],
            is_paid=True, paid_at=timezone.now(), konnect_payment_ref=payment_ref,
        )
    except Exception:
        pass


# ── Compte ────────────────────────────────────────────────────────────────────

@partner_required
def account(request):
    return render(request, 'partners/account.html', {'partner': request.partner})


@partner_required
def change_password(request):
    partner = request.partner
    if request.method == 'POST':
        from django.contrib.auth import update_session_auth_hash
        current = request.POST.get('current_password', '')
        new_pwd = request.POST.get('new_password', '')
        confirm = request.POST.get('confirm_password', '')
        if not request.user.check_password(current):
            messages.error(request, "Mot de passe actuel incorrect.")
        elif len(new_pwd) < 8:
            messages.error(request, "Le mot de passe doit contenir au moins 8 caractères.")
        elif new_pwd != confirm:
            messages.error(request, "Les mots de passe ne correspondent pas.")
        else:
            request.user.set_password(new_pwd)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "Mot de passe mis à jour avec succès !")
    return redirect('partners:account')


@partner_required
def change_email(request):
    partner = request.partner
    if request.method == 'POST':
        new_email     = request.POST.get('new_email', '').strip().lower()
        confirm_email = request.POST.get('confirm_email', '').strip().lower()

        if not new_email or new_email == partner.email:
            messages.error(request, "Email invalide ou identique à l'actuel.", extra_tags='email')
        elif new_email != confirm_email:
            messages.error(request, "Les emails ne correspondent pas.", extra_tags='email')
        elif Partner.objects.filter(email=new_email).exists():
            messages.error(request, "Cet email est déjà utilisé.", extra_tags='email')
        else:
            from partners.email_utils import send_email_change_confirmation
            send_email_change_confirmation(partner, new_email, request=request)
            messages.success(
                request,
                f"Un lien de vérification a été envoyé à '{new_email}'.",
                extra_tags='email'
            )

    return redirect('partners:account')


# ✅ Vue corrigée : vérification complète + messages avec extra_tags + redirect
def verify_email_change(request, token):
    # Trouver le partenaire avec ce token
    try:
        partner = Partner.objects.get(email_change_token=token)
    except Partner.DoesNotExist:
        messages.error(request, "Lien invalide ou déjà utilisé.", extra_tags='email')
        return redirect('partners:account')

    # Vérifier que new_email est défini
    new_email = (partner.new_email or partner.pending_email or '').strip().lower()
    if not new_email:
        messages.error(request, "Aucun nouvel email en attente.", extra_tags='email')
        return redirect('partners:account')

    # Vérifier unicité
    if Partner.objects.exclude(pk=partner.pk).filter(email=new_email).exists():
        partner.email_change_token = ''
        partner.new_email          = None
        partner.pending_email      = ''
        partner.save(update_fields=['email_change_token', 'new_email', 'pending_email'])
        messages.error(request, "Cet email est déjà utilisé par un autre compte.", extra_tags='email')
        return redirect('partners:account')

    # ── Mise à jour ───────────────────────────────────────────────────────────
    partner.email              = new_email
    partner.email_change_token = ''
    partner.new_email          = None
    partner.pending_email      = ''
    partner.save(update_fields=['email', 'email_change_token', 'new_email', 'pending_email'])

    user = partner.user
    if user:
        user.email    = new_email
        user.username = new_email
        user.save(update_fields=['email', 'username'])

    messages.success(
        request,
        f"Votre email a été mis à jour avec succès : {new_email}",
        extra_tags='email'
    )
    return redirect('partners:account')


# ── Coupon AJAX ───────────────────────────────────────────────────────────────

def coupon_verify(request):
    code     = request.GET.get('code', '').strip().upper()
    category = request.GET.get('category', 'both')
    if not code:
        return JsonResponse({'valid': False, 'error': 'Code manquant'})
    try:
        coupon = Coupon.objects.get(code=code, is_active=True)
    except Coupon.DoesNotExist:
        return JsonResponse({'valid': False, 'error': 'Code coupon invalide'})
    if coupon.category != 'both' and coupon.category != category:
        return JsonResponse({'valid': False, 'error': f"Ce coupon est réservé aux {coupon.get_category_display()}"})
    return JsonResponse({
        'valid':    True,
        'discount': coupon.discount_percentage,
        'code':     coupon.code,
        'category': coupon.get_category_display(),
    })

@partner_required
def toggle_account(request):
    partner = request.partner
    if request.method == 'POST':
        if partner.is_temporarily_disabled:
            partner.is_temporarily_disabled = False
            partner.reactivated_at          = timezone.now()
            partner.disabled_reason         = None
            partner.save(update_fields=['is_temporarily_disabled', 'reactivated_at', 'disabled_reason'])
            messages.success(request, "Compte réactivé.")
        else:
            partner.is_temporarily_disabled = True
            partner.disabled_at             = timezone.now()
            partner.disabled_reason         = request.POST.get('reason', 'Désactivation volontaire')
            partner.save(update_fields=['is_temporarily_disabled', 'disabled_at', 'disabled_reason'])
            messages.success(request, "Compte désactivé temporairement.")
    return redirect('partners:account')