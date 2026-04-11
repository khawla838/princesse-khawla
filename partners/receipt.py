import os
import secrets
import string
from io import BytesIO
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta

from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.utils import timezone
from django.core.files.base import ContentFile  # ← AJOUT
from xhtml2pdf import pisa

TVA_RATE = Decimal('0.19')
TIMBRE = Decimal('1.000')

COMPANY = {
    'name': 'Dacnis',
    'address': 'Avenue Ibn El Jazzar, Immeuble Avicenne B101, 1er étage, 4000 Sousse, Tunisie',
    'email': 'contact@dacnis.tn',
    'phone': '+216 24 203 141',
    'website': 'www.dacnis.tn',
    'matricule': '193856/X/A/M/000',
}

def fetch_resources(uri, rel):
    if uri.startswith(settings.STATIC_URL):
        relative_path = uri.replace(settings.STATIC_URL, "")
        path = os.path.join(settings.BASE_DIR, 'static', relative_path)
    elif uri.startswith(settings.MEDIA_URL):
        relative_path = uri.replace(settings.MEDIA_URL, "")
        path = os.path.join(settings.MEDIA_ROOT, relative_path)
    else:
        path = uri
    if not os.path.isfile(path):
        print(f"--- ERREUR PDF : Fichier introuvable : {path} ---")
    return path

def generate_pdf(html):
    buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=buffer, link_callback=fetch_resources)
    if pisa_status.err:
        print("--- ERREUR lors de la génération du PDF ---")
    buffer.seek(0)
    return buffer.read()

def _generate_client_code(payment_ref: str) -> str:
    if payment_ref and len(payment_ref) >= 8:
        return f"CL-{payment_ref[:8].upper()}"
    chars = string.ascii_uppercase + string.digits
    return f"CL-{''.join(secrets.choice(chars) for _ in range(8))}"

def _compute_amounts(amount_str: str):
    ht = Decimal(str(amount_str)).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
    tva = (ht * TVA_RATE).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
    ttc = (ht + tva + TIMBRE).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
    return {
        'amount_ht': f"{ht:.3f}",
        'tva_amount': f"{tva:.3f}",
        'amount_ttc': f"{ttc:.3f}",
    }

def send_receipt(partner, payment_type: str, details: dict, payment_ref: str = ''):
    from partners.models import Receipt as ReceiptCounter, ReceiptHistory

    receipt_number = ReceiptCounter.next()
    now = timezone.now()
    echeance = now + timedelta(days=30)
    client_code = _generate_client_code(payment_ref)
    amounts = _compute_amounts(details.get('amount', '0'))

    context = {
        'company': COMPANY,
        'partner': partner,
        'payment_type': payment_type,
        'details': details,
        'date': now,
        'echeance': echeance,
        'receipt_number': receipt_number,
        'client_code': client_code,
        'payment_ref': payment_ref or '—',
        **amounts,
    }

    # 1. Rendu HTML
    html = render_to_string('partners/receipt.html', context)

    # 2. Conversion en PDF
    pdf = generate_pdf(html)

    # 3. Envoi email
    subject = f"Reçu N°{receipt_number} — {details.get('label', 'Dacnis')}"
    email = EmailMessage(
        subject=subject,
        body=f"Bonjour,\n\nVeuillez trouver ci-joint votre reçu de paiement pour {details.get('label')}.\n\nMerci de votre confiance.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[partner.email],
    )
    filename = f"recu_{receipt_number}_{now.strftime('%Y%m%d')}.pdf"
    email.attach(filename, pdf, 'application/pdf')
    email.send(fail_silently=True)

    # 4. Historique en base de données + sauvegarde PDF  ← CORRECTION ICI
    try:
        history = ReceiptHistory.objects.create(
            partner=partner,
            receipt_number=receipt_number,
            payment_type=payment_type,
            amount=float(amounts['amount_ttc']),
            client_code=client_code,
            payment_ref=payment_ref or '',
            label=details.get('label', ''),
            details=details,
            sent_to_email=partner.email,
        )
        # Sauvegarde du PDF dans le champ pdf_file
        history.pdf_file.save(filename, ContentFile(pdf), save=True)

    except Exception as e:
        print(f"Erreur sauvegarde historique : {e}")