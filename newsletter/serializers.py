import re

from rest_framework import serializers

from .models import (
    NewsletterSubscriber,
    NewsletterTemplate,
    NewsletterCampaign,
    NewsletterRecipient,
)


ALLOWED_BLOCK_TYPES = {"heading","paragraph","image","button","divider","spacer","product","product_grid","social_links",}


def validate_blocks(value):
    if not isinstance(value, list):
        raise serializers.ValidationError("Blocks must be a list.")

    if len(value) > 100:
        raise serializers.ValidationError("A newsletter cannot contain more than 100 blocks.")

    for block in value:
        if not isinstance(block, dict):
            raise serializers.ValidationError("Every block must be an object.")

        if block.get("type") not in ALLOWED_BLOCK_TYPES:
            raise serializers.ValidationError(f"Unsupported block type: {block.get('type')}")

        for key, item in block.items():
            if isinstance(item, str) and len(item) > 20000:
                raise serializers.ValidationError(f"Block field '{key}' is too long.")

        for key in ("url", "image_url", "href"):
            url = block.get(key)

            if url:
                if not isinstance(url, str):
                    raise serializers.ValidationError(f"{key} must be a string.")

                if not re.match(r"^https?://", url, re.I):
                    raise serializers.ValidationError(f"{key} must use HTTP or HTTPS.")

    return value


class NewsletterSubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscriber
        fields = ["id","email","user","status","subscribed_at","unsubscribed_at",]
        read_only_fields = ["id","user","subscribed_at","unsubscribed_at",]


class NewsletterSubscribeSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class NewsletterRecipientSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterRecipient
        fields = ["id", "subscriber", "email", "status", "provider_message_id", "error_message", "sent_at", "delivered_at", "opened_at", "clicked_at", "created_at",]
        read_only_fields = fields


class NewsletterCampaignSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name",read_only=True,default=None,)
    recipients = serializers.SerializerMethodField()
    recipient_details = serializers.SerializerMethodField()
    sent_count = serializers.SerializerMethodField()
    successful_count = serializers.SerializerMethodField()
    failed_count = serializers.SerializerMethodField()
    bounced_count = serializers.SerializerMethodField()
    delivered_count = serializers.SerializerMethodField()
    opened_count = serializers.SerializerMethodField()
    clicked_count = serializers.SerializerMethodField()
    pending_count = serializers.SerializerMethodField()
    complained_count = serializers.SerializerMethodField()

    class Meta:
        model = NewsletterCampaign
        fields = [ "id", "name", "subject", "preview_text", "blocks", "template", "template_name", "status", "created_by", "created_at", "updated_at", "queued_at", "sent_at", "recipients",
            "recipient_details", "sent_count", "successful_count", "failed_count", "bounced_count", "delivered_count", "opened_count", "clicked_count", "pending_count", "complained_count",
        ]

        read_only_fields = [ "id", "status", "created_by", "created_at", "updated_at", "queued_at", "sent_at", "recipients", "recipient_details", "sent_count", "successful_count",
            "failed_count", "bounced_count", "delivered_count", "opened_count", "clicked_count", "pending_count", "complained_count",
        ]

    def _get_recipients(self, obj):
        recipients = getattr(obj, "prefetched_recipients", None,)

        if recipients is None:
            recipients = obj.campaign_recipients.all()

        return list(recipients)

    def _count(self, obj, predicate):
        return sum(1 for recipient in self._get_recipients(obj) if predicate(recipient))

    def get_recipients(self, obj):
        return len(self._get_recipients(obj))

    def get_recipient_details(self, obj):
        return NewsletterRecipientSerializer(self._get_recipients(obj), many=True,).data

    def get_sent_count(self, obj):
        return self._count(obj, lambda r: r.status == NewsletterRecipient.Status.SENT,)

    def get_successful_count(self, obj):
        return self._count(obj,
            lambda r: r.status in {NewsletterRecipient.Status.SENT, NewsletterRecipient.Status.DELIVERED,},
        )

    def get_failed_count(self, obj):
        return self._count(obj, lambda r: r.status == NewsletterRecipient.Status.FAILED,)

    def get_bounced_count(self, obj):
        return self._count(obj, lambda r: r.status == NewsletterRecipient.Status.BOUNCED,)

    def get_delivered_count(self, obj):
        return self._count(obj, lambda r: r.status == NewsletterRecipient.Status.DELIVERED,)

    def get_opened_count(self, obj):
        return self._count(obj, lambda r: r.opened_at is not None)

    def get_clicked_count(self, obj):
        return self._count(obj, lambda r: r.clicked_at is not None)

    def get_pending_count(self, obj):
        return self._count(obj, lambda r: r.status in {NewsletterRecipient.Status.PENDING, NewsletterRecipient.Status.SENDING,},)

    def get_complained_count(self, obj):
        return self._count(obj, lambda r: r.status == NewsletterRecipient.Status.COMPLAINED,)

    def validate_blocks(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Blocks must be a list.")

        if len(value) > 100:
            raise serializers.ValidationError("A campaign cannot contain more than 100 blocks.")

        allowed_types = {"heading", "paragraph", "image", "button", "divider", "spacer", "product", "product_grid", "social_links",}

        for block in value:
            if not isinstance(block, dict):
                raise serializers.ValidationError("Each block must be an object.")

            if block.get("type") not in allowed_types:
                raise serializers.ValidationError(f"Unsupported block type: {block.get('type')}")

        return value

    def validate(self, attrs):
        template = attrs.get("template", getattr(self.instance, "template", None),)
        blocks = attrs.get("blocks",getattr(self.instance, "blocks", None),)

        if not blocks and template:
            attrs["blocks"] = template.blocks
        elif not blocks:
            raise serializers.ValidationError({"blocks": ("Add campaign content or select a template.")})
        return attrs


class NewsletterTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterTemplate
        fields = ["id","name","description","subject","preview_text","blocks","created_by","created_at","updated_at",]
        read_only_fields = ["id","created_by","created_at","updated_at",]

    def validate_blocks(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Blocks must be a list.")

        if len(value) > 100:
            raise serializers.ValidationError("A template cannot contain more than 100 blocks.")

        allowed_types = {"heading","paragraph","image","button","divider","spacer","product","product_grid","social_links",}

        for index, block in enumerate(value):
            if not isinstance(block, dict):
                raise serializers.ValidationError(f"Block {index + 1} must be an object.")

            if block.get("type") not in allowed_types:
                raise serializers.ValidationError(f"Block {index + 1} has an unsupported type.")

        return value




