from celery import shared_task
from django.db import transaction
from .models import Order


@shared_task
def release_unpaid_order_reservation(order_id):
    """
    Background task triggered 15 minutes after checkout initiation.
    If the order remains 'Pending' and payment was not marked 'successful',
    restores reserved stock levels and marks the order as 'Cancelled'.
    """
    try:
        with transaction.atomic():
            # Acquire row-level lock on the order
            order = Order.objects.select_for_update().get(id=order_id)

            # Check if order is still unpaid
            payment = getattr(order, 'payment', None)
            is_unpaid = order.status == 'Pending' and (
                not payment or payment.status != 'successful'
            )

            if is_unpaid:
                # 1. Iterate through order items and restore inventory stock
                order_items = order.order_items.select_related('product', 'variation').all()
                
                for item in order_items:
                    if item.variation:
                        # Lock variation row and restore stock
                        variation = type(item.variation).objects.select_for_update().get(pk=item.variation.pk)
                        variation.stock += item.quantity
                        variation.save()
                    elif item.product:
                        # Lock main product row and restore stock
                        product = type(item.product).objects.select_for_update().get(pk=item.product.pk)
                        product.stock += item.quantity
                        product.save()

                # 2. Mark order as Cancelled
                order.status = 'Cancelled'
                order.save()

                # 3. Update payment status if present
                if payment:
                    payment.status = 'expired'
                    payment.save()

                print(f"[RESERVATION EXPIRED] Order #{order.id} canceled and stock restored.")

    except Order.DoesNotExist:
        print(f"[RESERVATION TASK] Order #{order_id} not found.")
    except Exception as e:
        print(f"[RESERVATION TASK ERROR] Failed to release stock for Order #{order_id}: {str(e)}")