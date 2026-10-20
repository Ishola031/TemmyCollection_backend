from django.conf import settings
from django.db import models





class Notification(models.Model):
    class Audience(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        ADMIN = "admin", "Admin"

    class Category(models.TextChoices):
        ORDER = "order", "Order"
        PAYMENT = "payment", "Payment"
        INVENTORY = "inventory", "Inventory"
        CUSTOMER = "customer", "Customer"
        PROMOTION = "promotion", "Promotion"
        SYSTEM = "system", "System"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="push_center_notifications",)
    audience = models.CharField(max_length=20, choices=Audience.choices,)
    event_key = models.CharField(max_length=255, unique=True, null=True, blank=True, editable=False,)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.SYSTEM,)
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True, default="")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
            models.Index(fields=["audience", "created_at"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.recipient}"



class PushSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="push_subscriptions",)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL,blank=True,related_name="shared_push_subscriptions",)
    endpoint = models.URLField(max_length=2000, unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    user_agent = models.CharField(max_length=500, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Push subscription for user {self.user_id}"


class InventoryAlertState(models.Model):
    class ItemType(models.TextChoices):
        PRODUCT = "product", "Product"
        VARIATION = "variation", "Variation"

    item_type = models.CharField(max_length=20,choices=ItemType.choices,)
    item_id = models.PositiveBigIntegerField()
    is_low = models.BooleanField(default=False)
    low_event_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["item_type", "item_id"],
                name="unique_inventory_alert_state",
            )
        ]

    def __str__(self):
        return f"{self.item_type} #{self.item_id} - low: {self.is_low}"