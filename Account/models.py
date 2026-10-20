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
            raise ValueError("user must have an email address")

        if not username:
            raise ValueError("user must have an username")

        email = self.normalize_email(email)
        user = self.model(email=email, username=username)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password):
        user = self.create_user(email=email, username=username, password=password)
        user.is_admin = True
        user.is_staff = True
        user.is_active = True
        user.is_superadmin = True
        user.save(using=self._db)

        return user


class Account(AbstractBaseUser, PermissionsMixin):
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    username = models.CharField(max_length=50,unique=True)
    email = models.EmailField(max_length=100,unique=True)
    phone_number = models.CharField(max_length=50,blank=True,null=True)
    image = CloudinaryField('image',folder='users',blank=True,null=True)

    # Account information
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(blank=True,null=True)
    last_activity = models.DateTimeField(blank=True,null=True)

    # Permissions
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_not_user = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_superadmin = models.BooleanField(default=False)

    # Account ban
    is_banned = models.BooleanField(default=False)
    ban_reason = models.TextField(blank=True,null=True)
    banned_at = models.DateTimeField(blank=True,null=True)
    ban_expires_at = models.DateTimeField(blank=True,null=True)
    banned_by = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True, related_name='banned_users')


    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    objects = MyAccountManager()

    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        return self.is_admin

    def has_module_perms(self, app_label):
        return True

    def is_ban_expired(self):
        if not self.is_banned:
            return False

        if self.ban_expires_at is None:
            return False

        return timezone.now() >= self.ban_expires_at

    def save(self, *args, **kwargs):
        if not self.username:
            while True:
                username = f"{slugify(self.first_name)}{random.randint(1000, 999999)}"

                if not Account.objects.filter(username=username).exists():
                    self.username = username
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



class CustomerActivity(models.Model):
    class ActivityType(models.TextChoices):
        ACCOUNT_CREATED = 'account_created', 'Account Created'
        PROFILE_UPDATED = 'profile_updated', 'Profile Updated'
        ORDER_PLACED = 'order_placed', 'Order Placed'
        PAYMENT_COMPLETED = 'payment_completed', 'Payment Completed'
        ORDER_SHIPPED = 'order_shipped', 'Order Shipped'
        ORDER_DELIVERED = 'order_delivered', 'Order Delivered'
        ORDER_CANCELLED = 'order_cancelled', 'Order Cancelled'
        ACCOUNT_BANNED = 'account_banned', 'Account Banned'
        ACCOUNT_UNBANNED = 'account_unbanned', 'Account Unbanned'

    user = models.ForeignKey(Account, on_delete=models.CASCADE,related_name='activities')
    activity_type = models.CharField(max_length=50, choices=ActivityType.choices)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.ForeignKey('order.Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='customer_activities')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['activity_type']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.title}"
