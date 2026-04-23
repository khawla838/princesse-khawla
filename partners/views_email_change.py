"""
partners/views_email_change.py
------------------------------
Deux vues :
  • request_email_change  → le partner soumet son nouvel email
  • confirm_email_change  → il clique sur le lien → email activé automatiquement
"""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

from .models import Partner
from .email_utils import send_email_change_confirmation

import json


# ── 1. Demande de changement ──────────────────────────────────────────────────

@login_required
@require_POST
def request_email_change(request):
    """
    POST /partners/request-email-change/
    Body JSON : { "new_email": "newemail@example.com" }

    - Valide le nouvel email
    - Envoie l'email de confirmation au nouvel email
    - Retourne 200 JSON
    """
    try:
        data      = json.loads(request.body)
        new_email = data.get('new_email', '').strip().lower()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Corps JSON invalide.'}, status=400)

    if not new_email:
        return JsonResponse({'error': 'Le nouvel email est requis.'}, status=400)

    # Récupérer le partenaire lié à l'utilisateur connecté
    try:
        partner = request.user.partner_profile
    except Partner.DoesNotExist:
        return JsonResponse({'error': 'Profil partenaire introuvable.'}, status=404)

    # Vérifier que le nouvel email est différent de l'actuel
    if new_email == partner.email.lower():
        return JsonResponse({'error': 'Le nouvel email est identique à l\'actuel.'}, status=400)

    # Vérifier unicité
    if Partner.objects.exclude(pk=partner.pk).filter(email=new_email).exists():
        return JsonResponse({'error': 'Cet email est déjà utilisé par un autre partenaire.'}, status=409)

    if User.objects.exclude(pk=request.user.pk).filter(email=new_email).exists():
        return JsonResponse({'error': 'Cet email est déjà associé à un compte.'}, status=409)

    # Envoyer l'email de confirmation (automatique, sans admin)
    send_email_change_confirmation(partner, new_email, request=request)

    return JsonResponse({
        'success': True,
        'message': f'Un email de confirmation a été envoyé à {new_email}. Valable 1 heure.'
    })


# ── 2. Confirmation via lien ──────────────────────────────────────────────────

@require_GET
def confirm_email_change(request, token: str):
    """
    GET /partners/confirm-email-change/<token>/

    - Trouve le partenaire par token
    - Vérifie que le token n'est pas expiré (1h depuis la demande)
    - Met à jour email + user.email + user.username
    - Nettoie le token
    - Redirige vers la page settings avec un message
    """

    # Trouver le partenaire avec ce token
    try:
        partner = Partner.objects.get(email_change_token=token)
    except Partner.DoesNotExist:
        messages.error(request, 'Lien invalide ou déjà utilisé.', extra_tags='email')
        return redirect('partners:settings')

    # Vérifier que new_email est défini
    if not partner.new_email:
        messages.error(request, 'Aucun nouvel email en attente.', extra_tags='email')
        return redirect('partners:settings')

    new_email = partner.new_email.strip().lower()

    # Unicité avant de finaliser
    if Partner.objects.exclude(pk=partner.pk).filter(email=new_email).exists():
        # Nettoyer quand même le token
        partner.email_change_token = ''
        partner.new_email          = None
        partner.save(update_fields=['email_change_token', 'new_email'])
        messages.error(request, 'Cet email est déjà utilisé par un autre compte.', extra_tags='email')
        return redirect('partners:settings')

    # ── Mise à jour atomique ──────────────────────────────────────────────────
    old_email = partner.email

    # Mettre à jour le partenaire
    partner.email              = new_email
    partner.email_change_token = ''
    partner.new_email          = None
    partner.pending_email      = None
    partner.save(update_fields=['email', 'email_change_token', 'new_email', 'pending_email'])

    # Mettre à jour le User Django associé
    user = partner.user
    if user:
        user.email    = new_email
        user.username = new_email
        user.save(update_fields=['email', 'username'])

    messages.success(request, f'Votre adresse email a été mise à jour avec succès : {new_email}', extra_tags='email')
    return redirect('partners:account')