from django.contrib import admin
from .models import (Cart, CartItem, Payment, Order, OrderItem, ReviewRating,
                     ShippingZone, ShippingAddress, ShipmentTracking, Shipment, State, 
)
# Register your models here.

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    pass

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    pass

@admin.register(ShippingZone)
class ShipingZoneAdmin(admin.ModelAdmin):
    pass

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    pass

@admin.register(ShippingAddress)
class ShippingAddressAdmin(admin.ModelAdmin):
    pass

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    pass

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    pass

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    pass

@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    pass

@admin.register(ShipmentTracking)
class ShipmentTrackingAdmin(admin.ModelAdmin):
    pass

@admin.register(ReviewRating)
class ReviewRatingAdmin(admin.ModelAdmin):
    pass