from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Order
from Account.models import CustomerActivity
from Account.activity import create_customer_activity


@receiver(post_save, sender=Order)
def order_activity(sender, instance, created, **kwargs):
    if kwargs.get("raw", False):
        return
    if not instance.user:
        return

    if created:
        create_customer_activity(
            user=instance.user,
            activity_type=CustomerActivity.ActivityType.ORDER_PLACED,
            title='Order placed',
            description=f'Order #{instance.order_number} was placed.',
            order=instance
        )
        return


@receiver(pre_save, sender=Order)
def order_status_change(sender, instance, **kwargs):
    if kwargs.get("raw", False):
        return
    if not instance.pk:
        return

    try:
        old_order = Order.objects.get(pk=instance.pk)
    except Order.DoesNotExist:
        return

    if old_order.status == instance.status:
        return

    if not instance.user:
        return

    activity_type = None
    title = None

    if instance.status == 'Successful':
        activity_type = CustomerActivity.ActivityType.PAYMENT_COMPLETED
        title = 'Payment completed'

    elif instance.status == 'Shipped':
        activity_type = CustomerActivity.ActivityType.ORDER_SHIPPED
        title = 'Order shipped'

    elif instance.status == 'Delivered':
        activity_type = CustomerActivity.ActivityType.ORDER_DELIVERED
        title = 'Order delivered'

    elif instance.status == 'Cancelled':
        activity_type = CustomerActivity.ActivityType.ORDER_CANCELLED
        title = 'Order cancelled'

    if activity_type:
        create_customer_activity(
            user=instance.user,
            activity_type=activity_type,
            title=title,
            description=(
                f'Order #{instance.order_number} '
                f'status changed to {instance.status}.'
            ),
            order=instance
        )





