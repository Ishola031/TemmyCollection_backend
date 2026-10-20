from rest_framework import serializers
from .models import Notification, PushSubscription


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [ "id", "audience", "category", "title", "message", "link", "is_read", "created_at",]
        read_only_fields = fields


class PushSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushSubscription
        fields = ["endpoint", "p256dh", "auth", "user_agent"]

    def validate_endpoint(self, value):
        if not value.startswith("https://"):
            raise serializers.ValidationError("A valid HTTPS push endpoint is required.")
        
        return value



