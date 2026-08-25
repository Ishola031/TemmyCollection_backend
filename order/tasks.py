# order/tasks.py
import traceback
import logging
from celery import shared_task
from django.db import transaction, models
from .models import Order, OrderItem

logger = logging.getLogger(__name__)

@shared_task
def release_unpaid_order_reservation(order_number):
    try:
        with transaction.atomic():
            # 1. Fetch Order directly using order_number (its actual primary key)
            order = Order.objects.select_for_update().get(order_number=order_number)

            if order.status == 'Pending':
                # 2. Fetch order items directly using order foreign key
                items = OrderItem.objects.filter(order=order)

                for item in items:
                    qty = item.quantity
                    
                    # If item has a variation, update variation stock directly
                    if item.variation_id:
                        variation = item.variation
                        type(variation).objects.filter(pk=variation.pk).update(
                            stock=models.F('stock') + qty
                        )
                    # Otherwise update product stock directly
                    elif item.product_id:
                        product = item.product
                        type(product).objects.filter(pk=product.pk).update(
                            stock=models.F('stock') + qty
                        )

                # 3. Mark Order as Cancelled
                Order.objects.filter(order_number=order_number).update(status='Cancelled')
                
                logger.info(f"Successfully released stock for Order #{order_number}")

    except Exception as e:
        print("======== TRACEBACK ERROR ========")
        print(traceback.format_exc())
        print("======== END TRACEBACK ========")