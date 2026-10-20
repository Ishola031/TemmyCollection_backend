from django.urls import path

from .views import (
    # ResendWebhookView,
    NewsletterUnsubscribeView,
    NewsletterSubscribeView
)

urlpatterns = [
    # path("webhooks/resend/",ResendWebhookView.as_view(),name="newsletter-resend-webhook",),
    path("unsubscribe/",NewsletterUnsubscribeView.as_view(),name="newsletter-unsubscribe",),
    path("subscribe/",NewsletterSubscribeView.as_view(),),
]