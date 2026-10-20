
import logging
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from .models import Notification



logger = logging.getLogger(__name__)



def _deliver_push(user_id, notification_id):
    """Deliver a push only after the database transaction commits."""
    try:
        User = get_user_model()
        user = User.objects.filter(pk=user_id).first()
        notification = Notification.objects.filter(pk=notification_id).first()

        if not user or not notification:
            return

        from .push import send_push_to_user
        send_push_to_user(user, notification)

    except Exception:
        logger.exception(
            "Failed to deliver notification %s to user %s",
            notification_id,
            user_id,
        )


def notify_admins_once(event_key,category,title,message,link="",):
    """
    Save one notification per admin for a unique event.
    Push delivery is scheduled after the database transaction commits.
    """
    User = get_user_model()

    admins = User.objects.filter(is_active=True,).filter(
        Q(is_staff=True) | Q(is_admin=True) | Q(is_superadmin=True)
    ).distinct()

    created_count = 0

    for admin_user in admins.iterator():
        recipient_event_key = (f"{event_key}:admin:{admin_user.pk}")

        notification, created = Notification.objects.get_or_create(
            event_key=recipient_event_key,
            defaults={"recipient": admin_user,"audience": Notification.Audience.ADMIN,"category": category,"title": title,"message": message,"link": link,},
        )

        if created:
            created_count += 1

            transaction.on_commit(
                lambda user_id=admin_user.pk,
                notification_id=notification.pk: _deliver_push(
                    user_id,
                    notification_id,
                )
            )

    return created_count


def _deliver_customer_notification(user_id,notification_id,subject,email_message,order_id=None,):
    """Deliver push and email after the notification is committed."""
    User = get_user_model()

    user = User.objects.filter(pk=user_id).first()
    notification = Notification.objects.filter(pk=notification_id).first()

    if not user or not notification:
        return

    try:
        from .push import send_push_to_user
        send_push_to_user(user, notification)
        
    except Exception:
        logger.exception(
            "Customer push delivery failed for notification %s",
            notification_id,
        )

    try:
        from order.customer_notifications import (send_customer_order_email,)
        from order.models import Order

        order = None
        if order_id:
            order = Order.objects.filter(pk=order_id).first()

        send_customer_order_email(
            customer=user,
            subject=subject,
            title=notification.title,
            message=email_message,
            order=order,
            action_url=notification.link,
        )

    except Exception:
        logger.exception(
            "Customer email delivery failed for notification %s",
            notification_id,
        )


def notify_customer_once(user, event_key, category, title, message, email_subject, order=None, link="",):
    if not user or not user.email:
        return False

    recipient_event_key = f"customer:{user.pk}:{event_key}"

    notification, created = Notification.objects.get_or_create(
        event_key=recipient_event_key,
        defaults={
            "recipient": user,
            "audience": Notification.Audience.CUSTOMER,
            "category": category,
            "title": title,
            "message": message,
            "link": link,
        },
    )

    if not created:
        return False

    order_id = order.pk if order else None

    transaction.on_commit(
        lambda user_id=user.pk,
        notification_id=notification.pk,
        subject=email_subject,
        email_message=message,
        current_order_id=order_id: _deliver_customer_notification(
            user_id=user_id,
            notification_id=notification_id,
            subject=subject,
            email_message=email_message,
            order_id=current_order_id,
        )
    )

    return True



