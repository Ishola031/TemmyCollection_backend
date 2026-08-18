from rest_framework import serializers
from rest_framework.response import Response
from product.serializers import ProductSerializer, VariationSerializer
from .models import CartItem, Cart, Order, ShippingZone, ShippingAddress, Shipment,ShipmentTracking,State, Payment,OrderItem
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
    state_id = serializers.PrimaryKeyRelatedField(
        queryset=State.objects.all(), 
        source='state', 
        write_only=True
    )
    
    # This field handles the full output object data, but ignored on incoming POST data
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
        
class OrderSerializer(serializers.ModelSerializer):
    shipping_address = ShippingAddressSerializer(read_only=True)
    payment = PaymentSerializer(read_only=True)
    user = UserSerializer()
    class Meta:
        model = Order
        fields = ('order_number','user', 'shipping_address', 'payment',
                  'sub_total', 'shipping_price', 'total_price', 'status',
                  'order_note','created_at')

class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer()
    class Meta:
        model = OrderItem
        fields = ('id','order','product','variation','quantity',
                  'discount','price','created_at')

class ShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = ('order','tracking_number','courier_name','status','shipped_at',
                  'delivered_at')

class ShipmentTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentTracking
        fields = ('shipment','status','note', 'created_at')