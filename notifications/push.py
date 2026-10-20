import json
import logging
from django.conf import settings
from django.db.models import Q
from pywebpush import WebPushException, webpush

from .models import PushSubscription

logger = logging.getLogger(__name__)


def send_push_to_user(user, notification):
    """Send a saved notification to all active subscriptions for a user."""

    private_key = getattr(settings, "VAPID_PRIVATE_KEY", "")
    subject = getattr(settings, "VAPID_ADMIN_EMAIL", "")

    if not private_key or not subject:
        logger.warning("VAPID push settings are not configured.")
        return {"sent": 0, "failed": 0}

    payload = json.dumps({
        "id": notification.pk,
        "title": notification.title,
        "message": notification.message,
        "link": notification.link,
        "category": notification.category,
    })

    # Include subscriptions owned by this user and subscriptions shared
    # with this user. distinct() prevents duplicate delivery.
    subscriptions = (
        PushSubscription.objects.filter(
            Q(user=user) | Q(users=user),
            is_active=True,
        ).distinct()
    )

    sent = 0
    failed = 0

    for subscription in subscriptions.iterator():
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {
                        "p256dh": subscription.p256dh,
                        "auth": subscription.auth,
                    },
                },
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={"sub": subject},
                ttl=60 * 60 * 24,
            )
            sent += 1

        except WebPushException as exc:
            failed += 1
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)

            if status_code in (404, 410):
                subscription.is_active = False
                subscription.save(update_fields=["is_active"])

            logger.warning(
                "Push failed for subscription %s; HTTP status: %s",
                subscription.pk,
                status_code,
            )

        except Exception:
            failed += 1
            logger.exception(
                "Unexpected push error for subscription %s",
                subscription.pk,
            )

    logger.info(
        "Push delivery for user %s, notification %s: sent=%s, failed=%s",
        user.pk,
        notification.pk,
        sent,
        failed,
    )

    return {"sent": sent, "failed": failed}