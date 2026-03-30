from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
import json

from partners.models import Partner, PartnerEvent, PartnerEventMedia, PartnerAd
from partners.forms import PartnerLoginForm, PartnerEventForm, PartnerAdForm
from partners import konnect


# ── Décorateur ────────────────────────────────────────────────────────────────

def partner_required(view_func):
    def wrapper(request, *args, **kwargs):
        partner_id = request.session.get('partner_id')
        if not partner_id:
            return redirect('partners:login')
        try:
            request.partner = Partner.objects.get(id=partner_id, is_active=True)
        except Partner.DoesNotExist:
            request.session.flush()
            return redirect('partners:login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# ── Auth ──────────────────────────────────────────────────────────────────────

def partner_login(request):
    if request.session.get('partner_id'):
        return redirect('partners:dashboard')
    form = PartnerLoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        partner = form.cleaned_data['partner']
        request.session['partner_id'] = str(partner.id)
        request.session.set_expiry(60 * 60 * 24 * 7)
        messages.success(request, f"Bienvenue, {partner.company_name} !")
        return redirect('partners:dashboard')
    return render(request, 'partners/login.html', {'form': form})


def partner_logout(request):
    request.session.flush()
    return redirect('partners:login')


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
        messages.error(request, "Votre compte ne vous permet pas d'ajouter des evenements.")
        return redirect('partners:event_list')

    form = PartnerEventForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        event         = form.save(commit=False)
        event.partner = partner
        event.save()
        files = request.FILES.getlist('media')
        for i, f in enumerate(files):
            PartnerEventMedia.objects.create(event=event, file=f, order=i)

        if event.can_be_boosted:
            messages.success(request, f"Evenement '{event.title}' cree ! Vous pouvez le booster.")
        else:
            messages.success(request, f"Evenement '{event.title}' cree et en attente de validation admin.")
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
        messages.error(request, f"Le Booster necessite au moins 14 jours avant le debut ({days} jour(s)).")
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
    if not event.can_be_boosted:
        messages.error(request, "Cet evenement n'est plus eligible au boost.")
        return redirect('partners:event_list')

    if request.method == 'POST':
        BOOST_PRICE_MILLIMES = 20000
        order_id    = f"boost-{event.id}"
        base_url    = request.build_absolute_uri('/').rstrip('/')
        webhook_url = f"{base_url}/partners/events/{event.id}/boost/webhook/"
        success_url = f"{base_url}/partners/events/{event.id}/boost/success/"
        fail_url    = f"{base_url}/partners/events/"

        result = konnect.init_payment(
            amount_millimes = BOOST_PRICE_MILLIMES,
            order_id        = order_id,
            description     = f"Boost evenement: {event.title}",
            webhook_url     = webhook_url,
            success_url     = success_url,
            fail_url        = fail_url,
        )

        if result.get('payUrl'):
            event.boost_payment_ref = result['paymentRef']
            event.save(update_fields=['boost_payment_ref'])
            return redirect(result['payUrl'])
        else:
            messages.error(request, f"Erreur Konnect : {result.get('error', 'Inconnu')}")
            return redirect('partners:event_boost_payment', event_id=event.id)

    return render(request, 'partners/events/boost_payment.html', {
        'partner':     partner,
        'event':       event,
        'boost_price': '20.000 TND',
    })


@csrf_exempt
def event_boost_webhook(request, event_id):
    """Webhook Konnect — appelé automatiquement après paiement boost."""
    if request.method == 'POST':
        try:
            data        = json.loads(request.body)
            payment_ref = data.get('payment_ref') or data.get('paymentRef', '')
            status      = data.get('status', '')

            if status == 'completed' and payment_ref:
                event = PartnerEvent.objects.get(id=event_id)
                event.is_boosted        = True
                event.boosted_at        = timezone.now()
                event.status            = 'boosted'
                event.boost_payment_ref = payment_ref
                event.boost_paid_at     = timezone.now()
                event.save(update_fields=['is_boosted', 'boosted_at', 'status', 'boost_payment_ref', 'boost_paid_at'])
        except Exception:
            pass
    return JsonResponse({'received': True})


@partner_required
def event_boost_success(request, event_id):
    """Page de succès après paiement boost."""
    partner = request.partner
    event   = get_object_or_404(PartnerEvent, id=event_id, partner=partner)

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
            messages.success(request, f"Evenement '{event.title}' booste avec succes !")
        else:
            messages.error(request, "Paiement non confirme. Veuillez contacter le support.")

    return redirect('partners:event_list')


@partner_required
def event_delete(request, event_id):
    partner = request.partner
    event   = get_object_or_404(PartnerEvent, id=event_id, partner=partner)
    if request.method == 'POST':
        title = event.title
        event.delete()
        messages.success(request, f"Evenement '{title}' supprime.")
    return redirect('partners:event_list')


# ── Publicités ────────────────────────────────────────────────────────────────

@partner_required
def ad_list(request):
    partner = request.partner
    ads     = partner.ads.all().order_by('-created_at')
    return render(request, 'partners/ads/list.html', {
        'partner': partner,
        'ads':     ads,
        'can_add': partner.can_add_content,
    })


@partner_required
def ad_create(request):
    partner = request.partner

    if not partner.can_add_content:
        messages.error(request, "Votre compte ne vous permet pas de creer des publicites.")
        return redirect('partners:ad_list')

    form = PartnerAdForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        ad         = form.save(commit=False)
        ad.partner = partner
        ad.save()
        messages.success(request, f"Publicite '{ad.title}' creee ! Confirmez pour proceder au paiement.")
        return redirect('partners:ad_confirm', ad_id=ad.id)

    return render(request, 'partners/ads/create.html', {
        'partner': partner,
        'form':    form,
    })


@partner_required
def ad_confirm(request, ad_id):
    partner = request.partner
    ad      = get_object_or_404(PartnerAd, id=ad_id, partner=partner)

    if ad.is_confirmed:
        return redirect('partners:ad_payment', ad_id=ad.id)

    if request.method == 'POST':
        ad.is_confirmed = True
        ad.save(update_fields=['is_confirmed'])
        messages.success(request, "Publicite confirmee ! Finalisez le paiement.")
        return redirect('partners:ad_payment', ad_id=ad.id)

    return render(request, 'partners/ads/confirm.html', {
        'partner': partner,
        'ad':      ad,
    })


@partner_required
def ad_payment(request, ad_id):
    partner = request.partner
    ad      = get_object_or_404(PartnerAd, id=ad_id, partner=partner)

    if not ad.is_confirmed:
        return redirect('partners:ad_confirm', ad_id=ad.id)

    if ad.is_paid:
        messages.success(request, "Cette publicite est deja payee.")
        return redirect('partners:ad_list')

    if request.method == 'POST':
        amount_millimes = int(float(ad.total_price) * 1000)
        order_id        = f"ad-{ad.id}"
        base_url        = request.build_absolute_uri('/').rstrip('/')
        webhook_url     = f"{base_url}/partners/ads/{ad.id}/webhook/"
        success_url     = f"{base_url}/partners/ads/{ad.id}/success/"
        fail_url        = f"{base_url}/partners/ads/"

        result = konnect.init_payment(
            amount_millimes = amount_millimes,
            order_id        = order_id,
            description     = f"Publicite: {ad.title} ({ad.nb_days} jours)",
            webhook_url     = webhook_url,
            success_url     = success_url,
            fail_url        = fail_url,
        )

        if result.get('payUrl'):
            ad.konnect_payment_ref = result['paymentRef']
            ad.save(update_fields=['konnect_payment_ref'])
            return redirect(result['payUrl'])
        else:
            messages.error(request, f"Erreur Konnect : {result.get('error', 'Inconnu')}")

    return render(request, 'partners/ads/payment.html', {
        'partner': partner,
        'ad':      ad,
    })


@csrf_exempt
def ad_webhook(request, ad_id):
    """Webhook Konnect — appelé automatiquement après paiement publicite."""
    if request.method == 'POST':
        try:
            data        = json.loads(request.body)
            payment_ref = data.get('payment_ref') or data.get('paymentRef', '')
            status      = data.get('status', '')

            if status == 'completed' and payment_ref:
                ad         = PartnerAd.objects.get(id=ad_id)
                ad.is_paid = True
                ad.paid_at = timezone.now()
                ad.status  = 'active'
                ad.konnect_payment_ref = payment_ref
                ad.save(update_fields=['is_paid', 'paid_at', 'status', 'konnect_payment_ref'])
        except Exception:
            pass
    return JsonResponse({'received': True})


@partner_required
def ad_success(request, ad_id):
    """Page de succes apres paiement publicite."""
    partner = request.partner
    ad      = get_object_or_404(PartnerAd, id=ad_id, partner=partner)

    payment_ref = request.GET.get('payment_ref', '')
    if payment_ref:
        result = konnect.verify_payment(payment_ref)
        if result.get('paid'):
            ad.is_paid = True
            ad.paid_at = timezone.now()
            ad.status  = 'active'
            ad.konnect_payment_ref = payment_ref
            ad.save(update_fields=['is_paid', 'paid_at', 'status', 'konnect_payment_ref'])
            messages.success(request, f"Publicite '{ad.title}' activee avec succes !")
        else:
            messages.error(request, "Paiement non confirme. Contactez le support.")

    return redirect('partners:ad_list')


@partner_required
def ad_delete(request, ad_id):
    partner = request.partner
    ad      = get_object_or_404(PartnerAd, id=ad_id, partner=partner)

    if ad.is_confirmed:
        messages.error(request, "Une publicite confirmee ne peut pas etre supprimee.")
        return redirect('partners:ad_list')

    if request.method == 'POST':
        title = ad.title
        ad.delete()
        messages.success(request, f"Publicite '{title}' supprimee.")
    return redirect('partners:ad_list')


# ── Abonnement ────────────────────────────────────────────────────────────────

@partner_required
def subscription(request):
    partner = request.partner
    from partners.pricing import SUBSCRIPTION_PRICES, PERIOD_LABELS, PERIOD_MONTHS

    periods = {}
    base_price_1month = SUBSCRIPTION_PRICES['1_month']['total']
    for key, prices in SUBSCRIPTION_PRICES.items():
        saving = round(
            (PERIOD_MONTHS[key] * base_price_1month) - prices['total'], 3
        )
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
        price_info = calculate_subscription_price(period, payment_type)

        amount_millimes = int(float(price_info['first_payment']) * 1000)
        order_id        = f"sub-{partner.id}-{period}"
        base_url        = request.build_absolute_uri('/').rstrip('/')
        webhook_url     = f"{base_url}/partners/subscription/webhook/"
        success_url     = f"{base_url}/partners/subscription/success/?period={period}&payment_type={payment_type}"
        fail_url        = f"{base_url}/partners/subscription/"

        result = konnect.init_payment(
            amount_millimes = amount_millimes,
            order_id        = order_id,
            description     = f"Abonnement FielMedina {price_info['period_label']} ({payment_type})",
            webhook_url     = webhook_url,
            success_url     = success_url,
            fail_url        = fail_url,
        )

        if result.get('payUrl'):
            request.session['sub_period']       = period
            request.session['sub_payment_type'] = payment_type
            request.session['sub_payment_ref']  = result['paymentRef']
            return redirect(result['payUrl'])
        else:
            messages.error(request, f"Erreur Konnect : {result.get('error', 'Inconnu')}")

    return render(request, 'partners/subscription.html', {
        'partner':           partner,
        'periods':           periods,
        'contract_active':   partner.is_contract_active,
        'days_until_expiry': partner.days_until_expiry,
    })


@csrf_exempt
def subscription_webhook(request):
    """Webhook Konnect — paiement abonnement confirmé."""
    if request.method == 'POST':
        try:
            data        = json.loads(request.body)
            payment_ref = data.get('payment_ref') or data.get('paymentRef', '')
            status      = data.get('status', '')
            order_id    = data.get('orderId', '')

            if status == 'completed' and order_id.startswith('sub-'):
                parts      = order_id.split('-')
                period     = parts[-1] + '_' + parts[-2] if len(parts) >= 3 else parts[-1]
                partner_id = '-'.join(parts[1:-2]) if len(parts) > 3 else parts[1]
                _activate_subscription(partner_id, period, 'total', payment_ref)
        except Exception:
            pass
    return JsonResponse({'received': True})


@partner_required
def subscription_success(request):
    """Page succès après paiement abonnement."""
    partner      = request.partner
    period       = request.GET.get('period') or request.session.get('sub_period', '1_month')
    payment_type = request.GET.get('payment_type') or request.session.get('sub_payment_type', 'total')
    payment_ref  = request.session.get('sub_payment_ref', '')

    if payment_ref:
        result = konnect.verify_payment(payment_ref)
        if result.get('paid'):
            _activate_subscription(str(partner.id), period, payment_type, payment_ref)
            messages.success(request, f"Abonnement activé avec succès !")
            for k in ['sub_period', 'sub_payment_type', 'sub_payment_ref']:
                request.session.pop(k, None)
        else:
            messages.error(request, "Paiement non confirmé. Contactez le support.")

    return redirect('partners:subscription')


def _activate_subscription(partner_id: str, period: str, payment_type: str, payment_ref: str):
    """Active l'abonnement après paiement confirmé."""
    from datetime import date
    from dateutil.relativedelta import relativedelta
    from partners.pricing import calculate_subscription_price, PERIOD_MONTHS

    try:
        partner    = Partner.objects.get(id=partner_id)
        price_info = calculate_subscription_price(period, payment_type)
        today      = date.today()
        months     = PERIOD_MONTHS.get(period, 1)
        end_date   = today + relativedelta(months=months)

        partner.contract_period = period
        partner.payment_type    = payment_type
        partner.contract_start  = today
        partner.contract_end    = end_date
        partner.account_frozen  = False
        partner.is_verified     = True
        partner.save(update_fields=[
            'contract_period', 'payment_type',
            'contract_start', 'contract_end',
            'account_frozen', 'is_verified'
        ])

        from partners.models import PartnerContract
        PartnerContract.objects.create(
            partner        = partner,
            period         = period,
            payment_type   = payment_type,
            start_date     = today,
            end_date       = end_date,
            total_amount   = price_info['total'],
            monthly_amount = price_info['monthly'],
            is_paid        = True,
            paid_at        = timezone.now(),
            konnect_payment_ref = payment_ref,
        )
    except Exception:
        pass


# ── Gestion compte ────────────────────────────────────────────────────────────

@partner_required
def account(request):
    partner = request.partner
    return render(request, 'partners/account.html', {'partner': partner})


@partner_required
def change_password(request):
    partner = request.partner

    if request.method == 'POST':
        current  = request.POST.get('current_password', '')
        new_pwd  = request.POST.get('new_password', '')
        confirm  = request.POST.get('confirm_password', '')

        if not partner.check_password(current):
            messages.error(request, "Mot de passe actuel incorrect.")
            return redirect('partners:account')

        if len(new_pwd) < 8:
            messages.error(request, "Le mot de passe doit contenir au moins 8 caractères.")
            return redirect('partners:account')

        if new_pwd != confirm:
            messages.error(request, "Les mots de passe ne correspondent pas.")
            return redirect('partners:account')

        if current == new_pwd:
            messages.error(request, "Le nouveau mot de passe doit être différent de l'ancien.")
            return redirect('partners:account')

        partner.set_password(new_pwd)
        partner.save(update_fields=['password'])
        messages.success(request, "Mot de passe mis à jour avec succès !")

    return redirect('partners:account')


@partner_required
def change_email(request):
    partner = request.partner

    if request.method == 'POST':
        new_email     = request.POST.get('new_email', '').strip().lower()
        confirm_email = request.POST.get('confirm_email', '').strip().lower()

        if not new_email:
            messages.error(request, "L'email ne peut pas être vide.")
            return redirect('partners:account')

        if new_email == partner.email:
            messages.error(request, "Le nouvel email est identique à l'email actuel.")
            return redirect('partners:account')

        if new_email != confirm_email:
            messages.error(request, "Les emails ne correspondent pas.")
            return redirect('partners:account')

        if Partner.objects.filter(email=new_email).exclude(id=partner.id).exists():
            messages.error(request, "Cet email est déjà utilisé par un autre compte.")
            return redirect('partners:account')

        partner.pending_email = new_email
        partner.save(update_fields=['pending_email'])
        messages.success(request, f"Demande envoyée ! En attente de validation admin pour '{new_email}'.")

    return redirect('partners:account')


@partner_required
def cancel_email_change(request):
    partner = request.partner
    if request.method == 'POST':
        partner.pending_email = None
        partner.save(update_fields=['pending_email'])
        messages.success(request, "Demande de changement d'email annulée.")
    return redirect('partners:account')


from django.http import JsonResponse
from partners.models import Coupon


# ── Vérification coupon (AJAX) ────────────────────────────────────────────────

def coupon_verify(request):
    """
    GET /partners/coupon/verify/?code=ABC123&category=subscription
    Retourne JSON : { valid, discount, error }
    """
    code     = request.GET.get('code', '').strip().upper()
    category = request.GET.get('category', 'both')

    if not code:
        return JsonResponse({'valid': False, 'error': 'Code manquant'})

    try:
        coupon = Coupon.objects.get(code=code)
    except Coupon.DoesNotExist:
        return JsonResponse({'valid': False, 'error': 'Code coupon invalide'})

    if not coupon.is_valid:
        return JsonResponse({'valid': False, 'error': 'Ce coupon est expiré ou désactivé'})

    if coupon.category != 'both' and coupon.category != category:
        return JsonResponse({
            'valid': False,
            'error': f"Ce coupon est réservé aux {coupon.get_category_display()}"
        })

    return JsonResponse({
        'valid':    True,
        'discount': coupon.discount_percentage,
        'code':     coupon.code,
        'category': coupon.get_category_display(),
    })


# ── Désactivation temporaire partenaire ──────────────────────────────────────

@partner_required
def toggle_account(request):
    """Active ou désactive temporairement le compte partenaire lui-même."""
    partner = request.partner

    if request.method == 'POST':
        if partner.is_temporarily_disabled:
            partner.is_temporarily_disabled = False
            partner.reactivated_at          = timezone.now()
            partner.disabled_reason         = None
            partner.save(update_fields=['is_temporarily_disabled', 'reactivated_at', 'disabled_reason'])
            messages.success(request, "Votre compte a été réactivé.")
        else:
            reason = request.POST.get('reason', 'Désactivation volontaire')
            partner.is_temporarily_disabled = True
            partner.disabled_at             = timezone.now()
            partner.disabled_reason         = reason
            partner.save(update_fields=['is_temporarily_disabled', 'disabled_at', 'disabled_reason'])
            messages.success(request, "Votre compte a été désactivé temporairement.")

    return redirect('partners:account')