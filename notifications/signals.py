import logging
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from order.models import Order, Payment
from product.models import Product, Variation
from notifications.models import Notification
from .models import InventoryAlertState, Notification
from .services import notify_admins_once, notify_customer_once
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


logger = logging.getLogger(__name__)

LOW_STOCK_THRESHOLD = 10


ORDER_STATUS_MESSAGES = {
    "Processing": (
        "Your order is being processed.",
        "Your order is being processed - TemmyCollection",
    ),
    "Shipped": (
        "Your order has been shipped.",
        "Your order has been shipped - TemmyCollection",
    ),
    "At_Pickup_Station": (
        "Your order has arrived at the pickup station.",
        "Your order has arrived at the pickup station - TemmyCollection",
    ),
    "Ready_for_Pickup": (
        "Your order is ready for pickup.",
        "Your order is ready for pickup - TemmyCollection",
    ),
    "Collected": (
        "Your order has been collected successfully.",
        "Your order has been collected - TemmyCollection",
    ),
    "Delivered": (
        "Your order has been delivered successfully.",
        "Your order has been delivered - TemmyCollection",
    ),
    "Cancelled": (
        "Your order has been cancelled.",
        "Your order has been cancelled - TemmyCollection",
    ),
    "Successful": (
        "Your payment was successful and your order is confirmed.",
        "Payment successful - TemmyCollection",
    ),
}


ORDER_STATUS_TITLES = {
    "Processing": "Order processing",
    "Shipped": "Order shipped",
    "At_Pickup_Station": "Order arrived at pickup station",
    "Ready_for_Pickup": "Order ready for pickup",
    "Collected": "Order collected",
    "Delivered": "Order delivered",
    "Cancelled": "Order cancelled",
    "Successful": "Order confirmed",
}



# PAYMENTS: detect transition to successful
@receiver(pre_save,sender=Payment,dispatch_uid="notifications_payment_capture_previous_status",)
def capture_payment_previous_status(sender, instance, **kwargs):
    if kwargs.get("raw", False):
        return
    if not instance.pk:
        instance._previous_payment_status = None
        return

    instance._previous_payment_status = (
        sender.objects.filter(pk=instance.pk)
        .values_list("status", flat=True)
        .first()
    )


@receiver(post_save,sender=Payment,dispatch_uid="notifications_payment_success_admin",)
def notify_successful_payment(sender, instance, created, **kwargs):
    if kwargs.get("raw", False):
        return
    old_status = getattr(instance, "_previous_payment_status", None)

    if instance.status != "successful" or old_status == "successful":
        return

    order = (
        Order.objects.filter(payment=instance)
        .select_related("user")
        .first()
    )

    # Preserve the existing admin order alert.
    if order:
        notify_admins_once(
            event_key=f"order:{order.order_number}:paid",
            category=Notification.Category.ORDER,
            title="New paid order",
            message=(
                f"Order #{order.order_number} has been paid successfully. "
                f"Payment amount: {instance.currency} {instance.amount}."
            ),
            link="",
        )

    # Preserve the existing admin payment alert.
    notify_admins_once(
        event_key=f"payment:{instance.ref}:successful",
        category=Notification.Category.PAYMENT,
        title="Payment successful",
        message=(
            f"Payment of {instance.currency} {instance.amount} "
            "has been confirmed."
        ),
        link="",
    )

    # Notify the customer who owns the order/payment.
    customer = order.user if order and order.user_id else instance.user

    if customer:
        order_text = (
            f" for order #{order.order_number}" if order else ""
        )

        notify_customer_once(
            user=customer,
            event_key=f"payment:{instance.ref}:successful",
            category=Notification.Category.PAYMENT,
            title="Payment confirmed",
            message=(
                f"Your payment of {instance.currency} {instance.amount}"
                f"{order_text} has been confirmed successfully."
            ),
            email_subject="Payment confirmed - TemmyCollection",
            order=order,
        )


# ORDERS: capture previous status before saving
@receiver(pre_save,sender=Order,dispatch_uid="notifications_order_capture_previous_status",)
def capture_order_previous_status(sender, instance, **kwargs):
    if kwargs.get("raw", False):
        return
    if not instance.pk:
        instance._previous_order_status = None
        return

    instance._previous_order_status = (
        sender.objects.filter(pk=instance.pk)
        .values_list("status", flat=True)
        .first()
    )



@receiver(post_save,sender=Order,dispatch_uid="notifications_customer_order_status",)
def notify_customer_order_status(sender, instance, created, **kwargs):
    if kwargs.get("raw", False):
        return
    if created:
        return

    old_status = getattr(instance, "_previous_order_status", None)

    if not old_status or old_status == instance.status:
        return

    status_data = ORDER_STATUS_MESSAGES.get(instance.status)

    if not status_data:
        return

    customer = instance.user

    if not customer:
        return

    message, email_subject = status_data
    title = ORDER_STATUS_TITLES[instance.status]

    # Use one stable event key per order/status to prevent duplicates.
    notify_customer_once(
        user=customer,
        event_key=(
            f"order:{instance.order_number}:status:{instance.status}"
        ),
        category=Notification.Category.ORDER,
        title=title,
        message=f"{message} Order number: #{instance.order_number}.",
        email_subject=email_subject,
        order=instance,
    )


# INVENTORY: preserve existing admin low-stock alerts
def check_low_stock(item_type, item_id, stock, item_label,):
    should_notify = False
    event_key = None

    with transaction.atomic():
        state, _ = InventoryAlertState.objects.get_or_create(
            item_type=item_type,
            item_id=item_id,
        )

        state = InventoryAlertState.objects.select_for_update().get(
            pk=state.pk
        )

        if stock <= LOW_STOCK_THRESHOLD:
            if not state.is_low:
                state.is_low = True
                state.low_event_count += 1
                state.save(
                    update_fields=[
                        "is_low",
                        "low_event_count",
                        "updated_at",
                    ]
                )

                event_key = (
                    f"inventory:{item_type}:{item_id}:"
                    f"low:{state.low_event_count}"
                )
                should_notify = True

        elif state.is_low:
            state.is_low = False
            state.save(update_fields=["is_low", "updated_at"])

    if should_notify:
        notify_admins_once(
            event_key=event_key,
            category=Notification.Category.INVENTORY,
            title="Low inventory alert",
            message=(
                f"{item_label} has {stock} unit(s) remaining. "
                f"The low-stock threshold is {LOW_STOCK_THRESHOLD}. "
                "Please review inventory."
            ),
            link="",
        )


@receiver(post_save,sender=Product,dispatch_uid="notifications_product_low_stock",)
def notify_low_product_stock(sender, instance, **kwargs):
    if kwargs.get("raw", False):
        return
    if instance.variations.exists():
        return

    check_low_stock(
        item_type=InventoryAlertState.ItemType.PRODUCT,
        item_id=instance.pk,
        stock=instance.stock,
        item_label=instance.name,
    )


@receiver(post_save,sender=Variation,dispatch_uid="notifications_variation_low_stock",)
def notify_low_variation_stock(sender, instance, **kwargs):
    if kwargs.get("raw", False):
        return
    product = instance.product
    attributes = []

    if instance.color_id:
        attributes.append(f"Color: {instance.color.name}")

    if instance.size_id:
        attributes.append(f"Size: {instance.size.name}")

    label = product.name

    if attributes:
        label += " (" + ", ".join(attributes) + ")"

    check_low_stock(
        item_type=InventoryAlertState.ItemType.VARIATION,
        item_id=instance.pk,
        stock=instance.stock,
        item_label=label,
    )














def broadcast_notification(action, instance):
    channel_layer = get_channel_layer()
    group_target = f"user_{instance.recipient.id}"

    content = {
        "id": instance.id,
        "title": getattr(instance, "title", ""),
        "category": getattr(instance, "category", ""),
        "message": getattr(instance, "message", ""),
        "is_read": getattr(instance, "is_read", ""),
        "created_at": str(getattr(instance, "created_at", "")),
    }

    async_to_sync(channel_layer.group_send)(
        group_target,
        {
            "type": "send_notification",
            "action": action,
            "content": content,
        }
    )

    print(
        f"📡 Broadcasted {action} notification "
        # f"to channel group: {group_target}"
    )



@receiver(post_save, sender=Notification)
def send_realtime_notification(sender, instance, created, **kwargs):
    if kwargs.get("raw", False):
        return

    if created:
        print(f"🟢 Notification CREATED: "
            f"ID {instance.id} for {instance.recipient.email}"
        )

        broadcast_notification("create", instance)

    else:
        print(f"🟡 Notification UPDATED: "
            # f"ID {instance.id} for {instance.user.email}"
        )

        # broadcast_notification("update", instance)





