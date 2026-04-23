from django.urls import path
from partners import views

app_name = 'partners'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.partner_dashboard, name='dashboard'),

    # Événements
    path('events/',                               views.event_list,          name='event_list'),
    path('events/create/',                        views.event_create,        name='event_create'),
    path('events/<int:event_id>/boost/',          views.event_boost,         name='event_boost'),
    path('events/<int:event_id>/boost/payment/',  views.event_boost_payment, name='event_boost_payment'),
    path('events/<int:event_id>/boost/webhook/',  views.event_boost_webhook, name='event_boost_webhook'),
    path('events/<int:event_id>/boost/success/',  views.event_boost_success, name='event_boost_success'),
    path('events/<int:event_id>/delete/',         views.event_delete,        name='event_delete'),

    # Publicités
    path('ads/',                     views.ad_list,    name='ad_list'),
    path('ads/create/',              views.ad_create,  name='ad_create'),
    path('ads/<int:ad_id>/confirm/', views.ad_confirm, name='ad_confirm'),
    path('ads/<int:ad_id>/payment/', views.ad_payment, name='ad_payment'),
    path('ads/<int:ad_id>/webhook/', views.ad_webhook, name='ad_webhook'),
    path('ads/<int:ad_id>/success/', views.ad_success, name='ad_success'),
    path('ads/<int:ad_id>/delete/',  views.ad_delete,  name='ad_delete'),

    # Abonnement
    path('subscription/',         views.subscription,         name='subscription'),
    path('subscription/webhook/', views.subscription_webhook, name='subscription_webhook'),
    path('subscription/success/', views.subscription_success, name='subscription_success'),

    # Compte
    path('account/',              views.account,             name='account'),
    path('account/password/',     views.change_password,     name='change_password'),
    path('account/email/',        views.change_email,        name='change_email'),
    path('verify-email/<str:token>/', views.verify_email_change, name='verify_email_change'),
    path('account/toggle/',       views.toggle_account,      name='toggle_account'),

    # Coupon (AJAX)
    path('coupon/verify/', views.coupon_verify, name='coupon_verify'),
]