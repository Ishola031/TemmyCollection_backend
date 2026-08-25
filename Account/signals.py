from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Notification


def broadcast_notification(action, instance):
    channel_layer = get_channel_layer()
    group_target = f"user_{instance.user.id}"

    content = {
        "id": instance.id,
        "title": getattr(instance, "title", ""),
        "message": getattr(instance, "message", ""),
        "created_at": str(getattr(instance, "created_at", "")),
    }

    async_to_sync(channel_layer.group_send)(
        group_target,
        {
            "type": "send_notification",
            "action": action,
            "content": content,
        }
    )

    print(
        f"📡 Broadcasted {action} notification "
        f"to channel group: {group_target}"
    )


@receiver(post_save, sender=Notification)
def send_realtime_notification(sender, instance, created, **kwargs):

    if created:
        print(
            f"🟢 Notification CREATED: "
            f"ID {instance.id} for {instance.user.email}"
        )

        broadcast_notification("create", instance)

    else:
        print(
            f"🟡 Notification UPDATED: "
            f"ID {instance.id} for {instance.user.email}"
        )

        broadcast_notification("update", instance)


@receiver(post_delete, sender=Notification)
def delete_realtime_notification(sender, instance, **kwargs):

    channel_layer = get_channel_layer()
    group_target = f"user_{instance.user.id}"

    async_to_sync(channel_layer.group_send)(
        group_target,
        {
            "type": "send_notification",
            "action": "delete",
            "content": {
                "id": instance.id,
            },
        }
    )

    print(
        f"🔴 Notification DELETED: "
        f"ID {instance.id} from channel group: {group_target}"
    )



