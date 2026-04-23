"""
partners/email_utils.py
-----------------------
Sends the email change confirmation email.
Language is automatically detected from the partner's browser (Accept-Language header)
via Django's LocaleMiddleware — uses the project's own .po translation files.
"""

import secrets
import base64
import os
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import gettext as _
from django.conf import settings
from email.mime.image import MIMEImage


def send_email_change_confirmation(partner, new_email: str, request=None) -> None:
    """
    1. Detects language from browser via LocaleMiddleware (Accept-Language header).
    2. Generates a secure token and saves it on the Partner.
    3. Renders the HTML template with translated strings from .po files.
    4. Sends the email in the correct language (EN default, FR if browser is French).
    """

    # ── 1. Detect language from browser ──────────────────────────────────────
    lang = 'en'
    if request:
        browser_lang = translation.get_language()  # set by LocaleMiddleware
        if browser_lang and browser_lang.startswith('fr'):
            lang = 'fr'

    # ── 2. Activate the detected language so _() uses the right .po file ─────
    with translation.override(lang):

        # ── 3. Token ──────────────────────────────────────────────────────────
        token = secrets.token_urlsafe(48)
        partner.email_change_token = token
        partner.new_email          = new_email
        partner.save(update_fields=['email_change_token', 'new_email'])

        # ── 4. Confirmation URL ───────────────────────────────────────────────
        if request:
            base_url = request.build_absolute_uri('/').rstrip('/')
        else:
            base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')

        confirmation_url = f"{base_url}/partners/verify-email/{token}/"

        # ── 5. Translated strings (from .po files) ────────────────────────────
        company_name = getattr(settings, 'COMPANY_NAME', 'FielMedina')

        context = {
            'partner_name':     partner.company_name,
            'company_name':     company_name,
            'new_email':        new_email,
            'confirmation_url': confirmation_url,
            'logo_url':         'cid:logo_img', # ✅ CID pour meilleure compatibilité
            'lang':             lang,
            't': {
                'header_h1':     _('Confirm your new email address'),
                'header_sub':    _('Email address change request'),
                'greeting':      _('Hello'),
                'body':          _('We received a request to change the email address associated with your partner account. Please confirm your new address by clicking the button below.'),
                'label':         _('New email address'),
                'expiry':        _('This link expires in <strong>1 hour</strong>'),
                'btn':           _('Confirm my new email'),
                'fallback':      _("If the button doesn't work, copy and paste this link into your browser:"),
                'warning_title': _("Didn't request this change?"),
                'warning_body':  _('Simply ignore this email — your current address will remain unchanged. If you believe your account has been compromised, please contact our support team immediately.'),
                'footer':        _('This email was sent automatically by'),
                'no_reply':      _('Please do not reply to this email.'),
            },
        }

        # ── 6. Render HTML template ───────────────────────────────────────────
        html_content = render_to_string('partners/emails/email_change_confirm.html', context)

        # ── 7. Plain text fallback ────────────────────────────────────────────
        text_content = (
            f"{context['t']['greeting']} {partner.company_name},\n\n"
            f"{context['t']['body']}\n\n"
            f"{confirmation_url}\n\n"
            f"{context['t']['warning_title']} {context['t']['warning_body']}"
        )

        # ── 8. Send ───────────────────────────────────────────────────────────
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@fielmedina.com')

        msg = EmailMultiAlternatives(
            subject    = _('Confirm your new email address — FielMedina'),
            body       = text_content,
            from_email = from_email,
            to         = [new_email],
        )
        msg.mixed_subtype = 'related'  # ✅ Nécessaire pour que les images CID s'affichent
        msg.attach_alternative(html_content, "text/html")

        # ✅ Attacher le logo en tant que CID (Content-ID)
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'icon.png')
        if os.path.exists(logo_path):
            with open(logo_path, 'rb') as f:
                img = MIMEImage(f.read())
                img.add_header('Content-ID', '<logo_img>')
                img.add_header('Content-Disposition', 'inline', filename='icon.png')
                msg.attach(img)

        msg.send(fail_silently=False)