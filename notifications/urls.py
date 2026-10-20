from django.urls import path

from .views import (CustomerNotificationListView, CustomerUnreadCountView, CustomerNotificationMarkReadView, CustomerNotificationMarkAllReadView, CustomerPushSubscriptionView,
    AdminNotificationListView, AdminUnreadCountView, AdminNotificationMarkReadView, AdminNotificationMarkAllReadView, AdminPushSubscriptionView, AdminNotificationCreateView,
)

urlpatterns = [
    # Customer notifications
    path("customer/", CustomerNotificationListView.as_view()),
    path("customer/unread-count/", CustomerUnreadCountView.as_view()),
    path("customer/<int:pk>/read/", CustomerNotificationMarkReadView.as_view()),
    path("customer/read-all/", CustomerNotificationMarkAllReadView.as_view()),
    path("customer/push-subscription/", CustomerPushSubscriptionView.as_view()),

    # Admin notifications
    path("admin/", AdminNotificationListView.as_view()),
    path("admin/unread-count/", AdminUnreadCountView.as_view()),
    path("admin/<int:pk>/read/", AdminNotificationMarkReadView.as_view()),
    path("admin/read-all/", AdminNotificationMarkAllReadView.as_view()),
    path("admin/push-subscription/", AdminPushSubscriptionView.as_view()),
    path("admin/send/", AdminNotificationCreateView.as_view()),
]