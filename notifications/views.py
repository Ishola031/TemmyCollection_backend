from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from Account.auth import CookieJWTAuthentication
from admin_panel.auth import AdminCookieJWTAuthentication
from admin_panel.permissions import IsTemmyAdmin

from .models import Notification, PushSubscription
from .serializers import NotificationSerializer, PushSubscriptionSerializer
from .push import send_push_to_user
from django.db import models
from django.db import transaction
from django.db.models import Q

User = get_user_model()


class NotificationListBase(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(
            recipient=self.request.user,
            audience=self.audience,
        ).order_by("-created_at")


class CustomerNotificationListView(NotificationListBase):
    authentication_classes = [CookieJWTAuthentication]
    audience = Notification.Audience.CUSTOMER


class AdminNotificationListView(NotificationListBase):
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    audience = Notification.Audience.ADMIN


class NotificationUnreadCountBase(APIView):
    permission_classes = [IsAuthenticated]
    audience = None

    def get(self, request):
        count = Notification.objects.filter(
            recipient=request.user,
            audience=self.audience,
            is_read=False,
        ).count()

        return Response({"unread_count": count})


class CustomerUnreadCountView(NotificationUnreadCountBase):
    authentication_classes = [CookieJWTAuthentication]
    audience = Notification.Audience.CUSTOMER


class AdminUnreadCountView(NotificationUnreadCountBase):
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    audience = Notification.Audience.ADMIN


class NotificationMarkReadBase(APIView):
    permission_classes = [IsAuthenticated]
    audience = None

    def post(self, request, pk):
        notification = get_object_or_404(
            Notification,
            pk=pk,
            recipient=request.user,
            audience=self.audience,
        )

        notification.is_read = True
        notification.save(update_fields=["is_read"])

        return Response({"detail": "Notification marked as read."})


class CustomerNotificationMarkReadView(NotificationMarkReadBase):
    authentication_classes = [CookieJWTAuthentication]
    audience = Notification.Audience.CUSTOMER


class AdminNotificationMarkReadView(NotificationMarkReadBase):
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    audience = Notification.Audience.ADMIN


class NotificationMarkAllReadBase(APIView):
    permission_classes = [IsAuthenticated]
    audience = None

    def post(self, request):
        updated = Notification.objects.filter(
            recipient=request.user,
            audience=self.audience,
            is_read=False,
        ).update(is_read=True)

        return Response({"detail": "Notifications marked as read.", "updated": updated})


class CustomerNotificationMarkAllReadView(NotificationMarkAllReadBase):
    authentication_classes = [CookieJWTAuthentication]
    audience = Notification.Audience.CUSTOMER


class AdminNotificationMarkAllReadView(NotificationMarkAllReadBase):
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    audience = Notification.Audience.ADMIN


class PushSubscriptionBase(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        endpoint = request.data.get("endpoint")

        if not endpoint:
            return Response(
                {"endpoint": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing = (
            PushSubscription.objects.select_for_update()
            .filter(endpoint=endpoint)
            .first()
        )

        if existing:
            serializer = PushSubscriptionSerializer(
                existing,
                data=request.data,
                partial=True,
            )
        else:
            serializer = PushSubscriptionSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if existing:
            existing.p256dh = data.get("p256dh", existing.p256dh)
            existing.auth = data.get("auth", existing.auth)
            existing.user_agent = data.get("user_agent", existing.user_agent)
            existing.is_active = True
            existing.save(update_fields=["p256dh","auth","user_agent","is_active","updated_at",])
            subscription = existing
            created = False
        else:
            subscription = PushSubscription.objects.create(
                user=request.user,
                endpoint=data["endpoint"],
                p256dh=data["p256dh"],
                auth=data["auth"],
                user_agent=data.get("user_agent", ""),
                is_active=True,
            )
            created = True

        # Register this account without changing the original owner.
        subscription.users.add(request.user)

        return Response(
            {
                "detail": "Push subscription saved.",
                "created": created,
            },
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            ),
        )

    @transaction.atomic
    def delete(self, request):
        endpoint = request.data.get("endpoint")

        if not endpoint:
            return Response(
                {"detail": "The endpoint field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscription = (
            PushSubscription.objects.select_for_update()
            .filter(endpoint=endpoint)
            .filter(
                Q(user=request.user) | Q(users=request.user)
            )
            .first()
        )

        if not subscription:
            return Response(
                {"detail": "Subscription not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if subscription.user_id == request.user.pk:
            other_users = subscription.users.exclude(
                pk=request.user.pk
            )

            if other_users.exists():
                # Keep the shared subscription for remaining accounts.
                new_owner = other_users.first()
                subscription.user = new_owner
                subscription.save(update_fields=["user", "updated_at"])
                subscription.users.remove(new_owner)
            else:
                subscription.delete()
                return Response({
                    "detail": "Subscription removed.",
                    "deleted": True,
                })
        else:
            subscription.users.remove(request.user)

        return Response({
            "detail": "Subscription removed for this account.",
            "deleted": True,
        })


class CustomerPushSubscriptionView(PushSubscriptionBase):
    authentication_classes = [CookieJWTAuthentication]


class AdminPushSubscriptionView(PushSubscriptionBase):
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTemmyAdmin]


class AdminNotificationCreateView(APIView):
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTemmyAdmin]

    def post(self, request):
        recipient_id = request.data.get("recipient_id")
        audience = request.data.get("audience")
        title = str(request.data.get("title", "")).strip()
        message = str(request.data.get("message", "")).strip()
        link = str(request.data.get("link", "")).strip()
        category = request.data.get("category",Notification.Category.SYSTEM,)

        # Validate audience
        if audience not in Notification.Audience.values:
            return Response(
                {"detail": "Audience must be 'customer' or 'admin'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate content
        if not title or not message:
            return Response(
                {"detail": "Title and message are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(title) > 200 or len(link) > 500:
            return Response(
                {"detail": "Title or link exceeds the allowed length."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if category not in Notification.Category.values:
            return Response(
                {"detail": "Invalid notification category."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build the eligible recipient queryset
        recipients = User.objects.filter(is_active=True)

        admin_filter = (
            models.Q(is_staff=True) | models.Q(is_admin=True) | models.Q(is_superadmin=True)
        )

        if audience == Notification.Audience.ADMIN:
            recipients = recipients.filter(admin_filter)
        else:
            recipients = recipients.exclude(admin_filter)

        # Send to one recipient or the entire audience
        if recipient_id:
            recipient = get_object_or_404(
                recipients.distinct(),
                pk=recipient_id,
            )

            notification = Notification.objects.create(
                recipient=recipient,
                audience=audience,
                category=category,
                title=title,
                message=message,
                link=link,
            )

            push_result = send_push_to_user(recipient, notification)

            return Response(
                {
                    "notification": NotificationSerializer(notification).data,
                    "push": push_result,
                },
                status=status.HTTP_201_CREATED,
            )

        # Create notifications for all eligible recipients
        notifications = [
            Notification(
                recipient=user,
                audience=audience,
                category=category,
                title=title,
                message=message,
                link=link,
            )
            for user in recipients.distinct()
        ]

        created_notifications = Notification.objects.bulk_create(
            notifications,
            batch_size=500,
        )

        # Send push messages only for this request's notifications
        push_sent = 0
        push_failed = 0

        for notification in created_notifications:
            result = send_push_to_user(notification.recipient,notification,)
            push_sent += result.get("sent", 0)
            push_failed += result.get("failed", 0)

        return Response(
            {
                "detail": "Notifications created.",
                "count": len(created_notifications),
                "push": {
                    "sent": push_sent,
                    "failed": push_failed,
                },
            },
            status=status.HTTP_201_CREATED,
        )


