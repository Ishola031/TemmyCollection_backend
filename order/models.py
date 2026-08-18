from django.db import models
from product.models import Product, Variation
from Account.models import Account
import uuid
# Create your models here.
class Cart(models.Model):
    cart_id = models.CharField(max_length=250, default=uuid.uuid4, unique=True)
    user = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True, related_name='carts')
    date_added = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.cart_id
    
class CartItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='productvariations')
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='cartitems')
    variations = models.ForeignKey(Variation, on_delete= models.CASCADE, related_name='variations', null=True, blank=True)
    quantity = models.IntegerField()
    is_active = models.BooleanField(default=True)

    def sub_total(self):
        return self.product.price * self.quantity
    
    def __str__(self):
        return str(self.product)

class ShippingZone(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name
    
class State(models.Model):
    name = models.CharField(max_length=100)
    zone = models.ForeignKey(ShippingZone, on_delete=models.CASCADE, related_name='states')

    def __str__(self):
        return self.name
    
class ShippingAddress(models.Model):
    address_type = models.CharField(max_length=30)
    user = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='shipping_addresses')
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone1 = models.CharField(max_length=15)
    phone2 = models.CharField(max_length=15, blank=True, null=True)
    address_line_1 = models.CharField(max_length=255)
    country = models.CharField(max_length=50, default='Nigeria')
    state = models.ForeignKey(State, on_delete=models.PROTECT)
    city = models.CharField(max_length=50)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return self.first_name
    

    
class Payment(models.Model):
    STATUS = (
        ("pending", "Pending"),
        ("successful", "Successful"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    )

    ref = models.CharField(max_length=255, unique=True)
    user = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='NGN')
    status = models.CharField(max_length=20, default='pending', choices=STATUS)
    payment_method = models.CharField(max_length=50, blank=True)  # card, bank, etc.
    gateway = models.CharField(max_length=50, blank=True)  # paystack, stripe
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Transaction {self.ref} - {self.status}"

class Order(models.Model):
    STATUS = (
    ("Pending", "Pending"),
    ("Successful", "Successful"),
    ("Shipped", "Shipped"),
    ("Delivered", "Delivered"),
    ("Cancelled", "Cancelled"),
)
    order_number = models.UUIDField(primary_key=True,default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, related_name='orders')
    shipping_address = models.ForeignKey(ShippingAddress, on_delete=models.PROTECT)
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, null=True, related_name='order')
    sub_total = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, default='Pending', choices=STATUS)
    order_note = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    
    def __str__(self):
        return f"Order {self.order_number} - {self.status}"
    
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='orderitems')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variation = models.ForeignKey(Variation, on_delete=models.CASCADE, null=True)
    quantity = models.PositiveIntegerField()
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.product.name
    
class Shipment(models.Model):
    STATUS = (
    ("Processing", "Processing"),
    ("Picked_up", "Picked Up"),
    ("in_transit", "In Transit"),
    ("Delivered", "Delivered"),
)
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    tracking_number = models.CharField(max_length=100, unique=True)
    courier_name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, default='Processing', choices=STATUS)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.order.order_number - {self.tracking_number}}"
    
class ShipmentTracking(models.Model):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='tracking_logs')
    status = models.CharField(max_length=100)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tracking - {self.shipment.tracking_number}"

class ReviewRating(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    subject = models.CharField(max_length=100, blank=True)
    review = models.TextField(max_length=500, blank=True)
    rating = models.FloatField()
    ip = models.CharField(max_length=20, blank=True)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)