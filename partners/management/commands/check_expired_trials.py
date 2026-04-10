from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from partners.models import Partner


class Command(BaseCommand):
    help = 'Vérifie les trials et envoie les emails de notification'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()

        all_trial_partners = Partner.objects.filter(
            is_trial=True,
            trial_end__isnull=False,
            is_active=True,
        )

        for partner in all_trial_partners:
            days_left = (partner.trial_end - today).days

            # ── Email J-30 ─────────────────────────────────────────────────
            if days_left == 30:
                try:
                    send_mail(
                        subject="⏰ Votre période d'essai FielMedina expire dans 30 jours",
                        message=f"""Bonjour {partner.company_name},

Votre période d'essai gratuite sur FielMedina expire le {partner.trial_end.strftime('%d/%m/%Y')},
soit dans 30 jours.

📢 Nous vous informons également que nos conditions générales d'utilisation ont été mises à jour.

Pour continuer à bénéficier de nos services sans interruption,
nous vous invitons à souscrire à l'un de nos abonnements dès maintenant :
{settings.SITE_URL}/partners/subscription/

Cordialement,
L'équipe FielMedina""",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[partner.email],
                        fail_silently=False,
                    )
                    self.stdout.write(f"✅ Email J-30 envoyé à {partner.email}")
                except Exception as e:
                    self.stdout.write(f"❌ Erreur J-30 pour {partner.email}: {e}")

            # ── Email J-7 ──────────────────────────────────────────────────
            if days_left == 7:
                try:
                    send_mail(
                        subject="🚨 URGENT — Votre période d'essai expire dans 7 jours",
                        message=f"""Bonjour {partner.company_name},

URGENT : Votre période d'essai gratuite expire le {partner.trial_end.strftime('%d/%m/%Y')},
soit dans 7 jours seulement !

📢 Rappel : nos conditions générales d'utilisation ont été mises à jour.
Après expiration, votre compte sera suspendu automatiquement.

Abonnez-vous maintenant pour continuer :
{settings.SITE_URL}/partners/subscription/

Cordialement,
L'équipe FielMedina""",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[partner.email],
                        fail_silently=False,
                    )
                    self.stdout.write(f"✅ Email J-7 envoyé à {partner.email}")
                except Exception as e:
                    self.stdout.write(f"❌ Erreur J-7 pour {partner.email}: {e}")

        # ── Expiration + suspension ────────────────────────────────────────
        expired_partners = Partner.objects.filter(
            is_trial=True,
            trial_end__lt=today,
            trial_notified=False,
            is_active=True,
        )
        for partner in expired_partners:
            try:
                send_mail(
                    subject="❌ Votre période d'essai FielMedina a expiré",
                    message=f"""Bonjour {partner.company_name},

Votre période d'essai gratuite de 6 mois sur FielMedina a expiré le {partner.trial_end.strftime('%d/%m/%Y')}.

Votre compte a été suspendu automatiquement.

Pour réactiver votre compte, veuillez souscrire à un abonnement :
{settings.SITE_URL}/partners/subscription/

Cordialement,
L'équipe FielMedina""",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[partner.email],
                    fail_silently=False,
                )
                partner.trial_notified = True
                partner.is_verified    = False
                partner.account_frozen = True
                partner.save(update_fields=['trial_notified', 'is_verified', 'account_frozen'])
                self.stdout.write(f"✅ Suspendu + email envoyé : {partner.email}")
            except Exception as e:
                self.stdout.write(f"❌ Erreur pour {partner.email}: {e}")

# Après la boucle des expirés — suspend les non payants
unpaid_partners = Partner.objects.filter(
    is_trial=False,
    payment_status='active',
    contract_end__lt=today,
    is_active=True,
)
for partner in unpaid_partners:
    partner.payment_status = 'not_active'
    partner.account_frozen = True
    partner.save(update_fields=['payment_status', 'account_frozen'])
    self.stdout.write(f"🔴 Paiement désactivé + suspendu : {partner.email}")