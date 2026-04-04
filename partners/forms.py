from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from partners.models import Partner, PartnerEvent, PartnerAd


CSS = 'w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500'
CSS_SELECT = f'{CSS} bg-white'


class PartnerLoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': CSS,
        'placeholder': 'votre@email.com',
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': CSS,
        'placeholder': '••••••••',
    }))

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get('email')
        password = cleaned.get('password')

        if email and password:
            try:
                # 1. N-lawjou ala el partner mel email kahaw mel loul
                partner = Partner.objects.get(email=email)
            except Partner.DoesNotExist:
                raise ValidationError("Email ou mot de passe incorrect.")

            # 2. Thabet f-el password
            if not partner.check_password(password):
                raise ValidationError("Email ou mot de passe incorrect.")

            # 3. Thabet f-el "is_active" (Hna el moshkla el kbira)
            if not partner.is_active:
                raise ValidationError("Ce compte est inactif. Veuillez contacter l'administrateur.")

            # 4. Thabet f-el verification
            if not partner.is_verified:
                raise ValidationError("Votre compte est en attente de vérification.")

            # 5. Thabet f-el frozen (non-paiement)
            if partner.account_frozen:
                raise ValidationError("Votre compte est suspendu pour non-paiement.")

            cleaned['partner'] = partner
        return cleaned

class PartnerEventForm(forms.ModelForm):
    class Meta:
        model  = PartnerEvent
        fields = [
            # ── Titre / Description (champs principaux + bilingues) ──────────
            'title', 'description',
            'title_en', 'title_fr',
            'description_en', 'description_fr',
            # ── Event Details ────────────────────────────────────────────────
            'category',       # ✅ ForeignKey → guard.EventCategory
            'city',           # ✅ ForeignKey → cities_light.City
            'location',       # ✅ ForeignKey → guard.Location
            'start_date',
            'end_date',
            'event_time',     # ✅ nouveau
            'price',          # ✅ nouveau
            'link',
        ]
        widgets = {
            # ── Titre principal (hidden, sync via JS) ────────────────────────
            'title': forms.TextInput(attrs={
                'class':       CSS,
                'placeholder': 'Titre de l evenement',
            }),
            # ── Description principale (hidden, sync via JS) ─────────────────
            'description': forms.Textarea(attrs={
                'class':       f'{CSS} resize-none',
                'rows':        4,
                'placeholder': 'Description de l evenement...',
            }),
            # ── Champs bilingues (utilisés en hidden dans le template) ───────
            'title_en': forms.TextInput(attrs={'class': CSS}),
            'title_fr': forms.TextInput(attrs={'class': CSS}),
            'description_en': forms.Textarea(attrs={'class': f'{CSS} resize-none', 'rows': 4}),
            'description_fr': forms.Textarea(attrs={'class': f'{CSS} resize-none', 'rows': 4}),

            # ✅ Category dropdown — affiche les EventCategory de guard app
            'category': forms.Select(attrs={
                'class': CSS_SELECT,
            }),

            # ✅ City dropdown — affiche les villes de cities_light
            'city': forms.Select(attrs={
                'class': CSS_SELECT,
            }),

            # ✅ Location dropdown — affiche les locations de guard app
            'location': forms.Select(attrs={
                'class': CSS_SELECT,
            }),

            # ── Dates ────────────────────────────────────────────────────────
            'start_date': forms.DateInput(attrs={
                'class': CSS,
                'type':  'date',
            }),
            'end_date': forms.DateInput(attrs={
                'class': CSS,
                'type':  'date',
            }),

            # ✅ Heure
            'event_time': forms.TimeInput(attrs={
                'class': CSS,
                'type':  'time',
            }),

            # ✅ Prix
            'price': forms.NumberInput(attrs={
                'class':       CSS,
                'placeholder': 'Enter event price',
                'step':        '0.001',
                'min':         '0',
            }),

            # ── Lien (destination link) ──────────────────────────────────────
            'link': forms.URLInput(attrs={
                'class':       CSS,
                'placeholder': 'https://example.com',
            }),
        }

    # ── Validation date début : minimum +7 jours (INCHANGÉ) ──────────────────
    def clean_start_date(self):
        start_date = self.cleaned_data.get('start_date')
        if not start_date:
            return start_date
        today = timezone.now().date()
        delta = (start_date - today).days
        if delta < 7:
            raise ValidationError(
                f"La date de debut doit etre au minimum dans 7 jours (actuellement dans {delta} jour(s))."
            )
        return start_date

    # ── Validation prix ───────────────────────────────────────────────────────
    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price < 0:
            raise ValidationError("Le prix ne peut pas être négatif.")
        return price

    # ── Validation category obligatoire ──────────────────────────────────────
    def clean_category(self):
        category = self.cleaned_data.get('category')
        if not category:
            raise ValidationError("La catégorie est obligatoire.")
        return category

    # ── Validation city obligatoire ───────────────────────────────────────────
    def clean_city(self):
        city = self.cleaned_data.get('city')
        if not city:
            raise ValidationError("La ville est obligatoire.")
        return city

    def clean(self):
        cleaned    = super().clean()
        start_date = cleaned.get('start_date')
        end_date   = cleaned.get('end_date')
        if start_date and end_date and end_date < start_date:
            raise ValidationError("La date de fin ne peut pas etre avant la date de debut.")
        return cleaned


class PartnerAdForm(forms.ModelForm):
    class Meta:
        model  = PartnerAd
        fields = ['title', 'mobile_image', 'tablet_image', 'destination_link', 'start_date', 'end_date']
        widgets = {
            'title': forms.TextInput(attrs={
                'class':       CSS,
                'placeholder': 'e.g., Summer Campaign 2026',
            }),
            'destination_link': forms.URLInput(attrs={
                'class':       CSS,
                'placeholder': 'https://example.com',
            }),
            'start_date': forms.DateInput(attrs={
                'class': CSS,
                'type':  'date',
            }),
            'end_date': forms.DateInput(attrs={
                'class': CSS,
                'type':  'date',
            }),
        }

    def clean_mobile_image(self):
        mobile_image = self.cleaned_data.get('mobile_image')
        if not mobile_image:
            raise ValidationError("L'image mobile (320x50) est obligatoire.")
        return mobile_image

    def clean_tablet_image(self):
        tablet_image = self.cleaned_data.get('tablet_image')
        if not tablet_image:
            raise ValidationError("L'image tablet (728x90) est obligatoire.")
        return tablet_image

    def clean_destination_link(self):
        url = self.cleaned_data.get('destination_link')
        if not url:
            raise ValidationError("Le lien de destination est obligatoire.")
        return url

    def clean_start_date(self):
        start_date = self.cleaned_data.get('start_date')
        if not start_date:
            return start_date
        today = timezone.now().date()
        if start_date <= today:
            raise ValidationError("La date de debut doit etre dans le futur.")
        return start_date

    def clean(self):
        cleaned    = super().clean()
        start_date = cleaned.get('start_date')
        end_date   = cleaned.get('end_date')
        if start_date and end_date:
            if end_date < start_date:
                raise ValidationError("La date de fin ne peut pas etre avant la date de debut.")
            nb_days = (end_date - start_date).days + 1
            if nb_days < 1:
                raise ValidationError("La publicite doit durer au moins 1 jour.")
        return cleaned