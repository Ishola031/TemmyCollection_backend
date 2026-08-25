from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from datetime import timedelta
from django.utils.text import slugify
import random
from cloudinary.models import CloudinaryField


# Create your models here.
class MyAccountManager(BaseUserManager):
    def create_user(self, username, email, password=None):
        if not email:
            return ValueError("user must have an email address")
        if not username:
            return ValueError("user must have an username")
        
        email = self.normalize_email(email)
        user = self.model(
            email= email, username=username
        )
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, username,email, password):
        user = self.create_user(
            email=email, username=username, password=password
        )
        user.is_admin = True
        user.is_staff = True
        user.is_active = True
        user.is_superadmin = True
        user.save(using=self._db)
        return user
        
class Account(AbstractBaseUser, PermissionsMixin):
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(max_length=100, unique=True)
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    image = CloudinaryField('image', folder='users', blank=True, null=True)
    
    # required
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now_add=True)
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_not_user = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_superadmin = models.BooleanField(default=False)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    objects = MyAccountManager()
    
    
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def __str__(self):
        return self.email
    
    def has_perm(self, perm,obj=None):
        return self.is_admin
    
    def has_module_perms(self, app_label):
        return True
    
    def save(self, *args, **kwargs):
        if not self.username:
            while True:
                username = f"{slugify(self.first_name)}{random.randint(1000,999999)}"
                if not Account.objects.filter(username=username).exists():
                    self.username= username
                    break
            

        return super().save(*args, **kwargs)

class EmailVerification(models.Model):
    email = models.EmailField(unique=True)
    code = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now=True)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=6)
    def __str__(self):
        return self.email

class PendingSignup(models.Model):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    password = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=10)

class Notification(models.Model):
    class NotificationType(models.TextChoices):
        # Authentication
        WELCOME = 'welcome', 'Welcome / Signup'
        LOGIN_ALERT = 'login_alert', 'Security / Login Alert'
        
        # Cart & Stock
        OUT_OF_STOCK = 'out_of_stock', 'Item Out of Stock'
        PRICE_DROP = 'price_drop', 'Price Drop Alert'
        
        # Orders & Reservations
        RESERVATION_CONFIRMED = 'reservation_confirmed', 'Reservation Confirmed'
        RESERVATION_EXPIRING = 'reservation_expiring', 'Reservation Expiring'
        ORDER_PLACED = 'order_placed', 'Order Placed'
        ORDER_SHIPPED = 'order_shipped', 'Order Out for Delivery'

    user = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, choices=NotificationType.choices)
    
    # Track status & optional navigation links
    is_read = models.BooleanField(default=False)
    target_url = models.CharField(max_length=500, blank=True, null=True,help_text="Optional route to redirect when clicked (e.g., /cart or /orders/12)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_notification_type_display()} ({'Read' if self.is_read else 'Unread'})"


