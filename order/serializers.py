from rest_framework import serializers
from product.serializers import ProductSerializer, VariationSerializer
from .models import CartItem, Cart, Order, ShippingZone, ShippingAddress, Shipment,ShipmentTracking,State, Payment,OrderItem,OrderStatusHistory, PickupStation
from Account.serializers import UserSerializer


# Serializers Class

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer()
    variations = VariationSerializer()
    class Meta:
        model = CartItem
        fields = ('id','product', 'cart', 'variations', 'quantity', 'is_active')


class CartSerializer(serializers.ModelSerializer):
    cartitems = CartItemSerializer(many= True)
    class Meta:
        model = Cart
        fields = ('id','cart_id','cartitems')


class ShippingZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingZone
        fields = ('name', 'price')


class StateSerializer(serializers.ModelSerializer):
    class Meta:
        model = State
        fields = ('id','name', 'zone')


class ShippingAddressSerializer(serializers.ModelSerializer):
    state_id = serializers.PrimaryKeyRelatedField(queryset=State.objects.all(),  source='state',  write_only=True)
    state = StateSerializer(read_only=True)
    class Meta:
        model = ShippingAddress
        fields = ('id','user', 'address_type','first_name', 'last_name', 'phone1', 'phone2',
                  'address_line_1', 'country', 'state', 'state_id','city', 'created_at')

  
class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ('ref','user','amount','currency','status','payment_method',
                  'gateway','paid_at','created_at')


class PickupStationSerializer(serializers.ModelSerializer):
    state = StateSerializer(read_only=True)
    class Meta:
        model = PickupStation
        fields = (
            'id', 'name', 'address', 'city', 'state', 'phone_number', 'opening_time', 'closing_time', 'pickup_fee', 'is_active',
        )


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer()
    variation = VariationSerializer(read_only=True)
    class Meta:
        model = OrderItem
        fields = (
            'id', 'order', 'product', 'variation', 'quantity', 'discount', 'price', 'created_at'
        )

class ShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = ('id','order','tracking_number','courier_name','status','shipped_at',
                  'delivered_at')


class ShipmentTrackingSerializer(serializers.ModelSerializer):
    admin = UserSerializer(read_only=True)
    class Meta:
        model = ShipmentTracking
        fields = (
            'id', 'shipment', 'admin', 'status', 'note', 'created_at',
        )


class OrderSerializer(serializers.ModelSerializer):
    shipping_address = ShippingAddressSerializer(read_only=True)
    pickup_station = PickupStationSerializer(read_only=True)
    payment = PaymentSerializer(read_only=True)
    user = UserSerializer()
    items = OrderItemSerializer(source='orderitems', many=True, read_only=True)
    coupon_code = serializers.CharField(source='coupon.code', read_only=True, allow_null=True)
    class Meta:
        model = Order
        fields = (
            'order_number', 'user', 'delivery_method', 'shipping_address', 'pickup_station', 'payment', 'items', 'sub_total', 'coupon', 'coupon_code',
            'coupon_discount', 'shipping_price', 'total_price', 'status', 'order_note', 'created_at', 'updated_at',
        )


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    admin = UserSerializer(read_only=True)
    class Meta:
        model = OrderStatusHistory
        fields = (
            'id', 'order', 'admin', 'old_status', 'new_status', 'note', 'created_at',
        )

