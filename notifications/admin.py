from django.contrib import admin
from .models import Notification, PushSubscription


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ( "id", "title", "recipient", "audience", "category", "is_read", "created_at",)
    list_filter = ( "audience", "category", "is_read", "created_at",)
    search_fields = ("title","message","recipient__email","recipient__username",)
    readonly_fields = ("created_at",)
    list_select_related = ("recipient",)
    ordering = ("-created_at",)
    list_per_page = 25


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ( "id", "user", "is_active", "created_at", "updated_at",)
    list_filter = ("is_active", "created_at")
    search_fields = ("user__email","user__username","endpoint",)
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("user",)
    ordering = ("-created_at",)
    list_per_page = 25