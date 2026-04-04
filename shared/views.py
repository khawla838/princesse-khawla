from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import (
    CreateView,
    UpdateView,
    DeleteView,
    ListView,
    TemplateView,
)
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json
from .translator import get_translator
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
    PasswordChangeView,
    PasswordChangeDoneView,
)
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.contrib import messages

from .models import Page

from .forms import (
    LoginForm,
    RegisterForm,
    FlowbitePasswordResetForm,
    FlowbiteSetPasswordForm,
    FlowbitePasswordChangeForm,
    ProfileUpdateForm,
    PageForm,
)


class CustomLoginView(LoginView):
    template_name = "guard/auth/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = False  # ← False pour éviter le loop

    def get_success_url(self):
        user = self.request.user

        # 1. Admin ou Staff → Guard Dashboard
        if user.is_superuser or user.is_staff:
            return reverse_lazy('guard:dashboard')

        # 2. Partner actif → Partner Dashboard
        if hasattr(user, 'partner_profile'):
            try:
                if user.partner_profile.is_active:
                    return reverse_lazy('partners:dashboard')
            except Exception:
                pass

        # 3. Default → partner dashboard (jamais login pour éviter loop)
        return reverse_lazy('partners:dashboard')

    def form_valid(self, form):
        messages.success(self.request, _("Welcome back!"))
        return super().form_valid(form)


class RegisterView(CreateView):
    form_class = RegisterForm
    template_name = "guard/auth/register.html"
    success_url = reverse_lazy("shared:login")

    def form_valid(self, form):
        form.save()
        messages.success(
            self.request, _("Account created successfully. Please log in.")
        )
        return super().form_valid(form)


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy("shared:login")


class CustomPasswordResetView(PasswordResetView):
    template_name = "guard/auth/password_reset.html"
    form_class = FlowbitePasswordResetForm
    email_template_name = "guard/auth/password_reset_email.txt"
    subject_template_name = "guard/auth/password_reset_subject.txt"
    success_url = reverse_lazy("shared:password_reset_done")


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = "guard/auth/password_reset_done.html"


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "guard/auth/password_reset_confirm.html"
    form_class = FlowbiteSetPasswordForm
    success_url = reverse_lazy("shared:password_reset_complete")


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "guard/auth/password_reset_complete.html"


class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = "guard/auth/password_change.html"
    form_class = FlowbitePasswordChangeForm
    success_url = reverse_lazy("shared:password_change_done")

    def form_valid(self, form):
        messages.success(self.request, _("Password updated successfully."))
        return super().form_valid(form)


class CustomPasswordChangeDoneView(LoginRequiredMixin, PasswordChangeDoneView):
    template_name = "guard/auth/password_change_done.html"


class SettingView(LoginRequiredMixin, TemplateView):
    template_name = "guard/auth/settings.html"

    def get(self, request, *args, **kwargs):
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, _("Profile updated successfully."))
            return redirect("shared:settings")
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = getattr(self.request.user, "profile", None)
        context["user_profile"] = profile
        context["profile_form"] = kwargs.get("form") or ProfileUpdateForm(
            instance=self.request.user
        )
        context["subscription_rows"] = self._build_subscription_rows(profile)
        context["subscription_alert"] = self._build_subscription_alert(profile)
        return context

    def _build_subscription_rows(self, profile):
        if not profile:
            return [
                {
                    "plan": _("Konnect subscription"),
                    "status": _("Not available"),
                    "started": None,
                    "renews": None,
                    "days_left": _("—"),
                }
            ]
        days_left = profile.subscription_days_left
        return [
            {
                "plan": profile.subscription_plan or _("Pending Konnect setup"),
                "status": profile.subscription_status_label,
                "started": profile.subscription_started_at,
                "renews": profile.subscription_renews_at,
                "days_left": days_left if days_left is not None else _("—"),
            }
        ]

    def _build_subscription_alert(self, profile):
        if not profile or not profile.is_subscription_expiring:
            return None
        return {
            "level": "warning",
            "days_left": profile.subscription_days_left,
            "renew_date": profile.subscription_renews_at,
        }


class PageListView(UserPassesTestMixin, LoginRequiredMixin, ListView):
    model = Page
    template_name = "guard/views/pages/list.html"
    context_object_name = "pages"
    ordering = ["slug"]

    def test_func(self):
        return self.request.user.is_staff


class PageCreateView(UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Page
    form_class = PageForm
    template_name = "guard/views/pages/index.html"
    success_url = reverse_lazy("shared:pageList")
    success_message = _("Page created successfully.")

    def test_func(self):
        return self.request.user.is_staff


class PageUpdateView(UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Page
    form_class = PageForm
    template_name = "guard/views/pages/index.html"
    success_url = reverse_lazy("shared:pageList")
    success_message = _("Page updated successfully.")

    def test_func(self):
        return self.request.user.is_staff


class PageDeleteView(UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, DeleteView):
    model = Page
    success_url = reverse_lazy("shared:pageList")
    success_message = _("Page deleted successfully.")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)

    def test_func(self):
        return self.request.user.is_staff


@login_required
@require_POST
def translate_text(request):
    try:
        data = json.loads(request.body)
        text = data.get("text", "")
        source_lang = data.get("source_lang", "en")
        target_lang = data.get("target_lang", "fr")
        preserve_html = data.get("preserve_html", False)

        if not text:
            return JsonResponse(
                {"success": False, "error": "No text provided"}, status=400
            )

        translator = get_translator()
        translated_text = translator.translate(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
            preserve_html=preserve_html,
        )

        return JsonResponse({"success": True, "translated_text": translated_text})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)