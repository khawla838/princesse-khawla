from django.urls import path
from .views import (
    PageListView,
    CustomLoginView,
    CustomLogoutView,
    RegisterView,
    CustomPasswordResetView,
    CustomPasswordResetDoneView,
    CustomPasswordResetConfirmView,
    CustomPasswordResetCompleteView,
    CustomPasswordChangeView,
    CustomPasswordChangeDoneView,
    SettingView,
    PageCreateView,
    PageUpdateView,
    PageDeleteView,
    translate_text,
)

app_name = "shared"
urlpatterns = [
    # Auth en premier — pas de protection
    path("auth/login/", CustomLoginView.as_view(), name="login"),
    path("auth/logout/", CustomLogoutView.as_view(), name="logout"),
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/password-reset/", CustomPasswordResetView.as_view(), name="password_reset"),
    path("auth/password-reset/done/", CustomPasswordResetDoneView.as_view(), name="password_reset_done"),
    path("auth/password-reset/<uidb64>/<token>/", CustomPasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("auth/password-reset/complete/", CustomPasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("auth/password-change/", CustomPasswordChangeView.as_view(), name="password_change"),
    path("auth/password-change/done/", CustomPasswordChangeDoneView.as_view(), name="password_change_done"),
    path("auth/settings/", SettingView.as_view(), name="settings"),
    path("api/translate/", translate_text, name="translate_text"),

    # Pages (staff only) — à la fin
    path("pages/", PageListView.as_view(), name="home"),
    path("pages/", PageListView.as_view(), name="pageList"),
    path("pages/create/", PageCreateView.as_view(), name="page_create"),
    path("pages/<int:pk>/update/", PageUpdateView.as_view(), name="page_update"),
    path("pages/<int:pk>/delete/", PageDeleteView.as_view(), name="page_delete"),
]