import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class NewsletterSubscriber(models.Model):
    class Status(models.TextChoices):
        SUBSCRIBED = "subscribed", "Subscribed"
        UNSUBSCRIBED = "unsubscribed", "Unsubscribed"

    class WelcomeEmailStatus(models.TextChoices):
        NOT_SENT = "not_sent", "Not sent"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"


    welcome_email_status = models.CharField(max_length=20,choices=WelcomeEmailStatus.choices,default=WelcomeEmailStatus.NOT_SENT,db_index=True,)
    welcome_email_sent_at = models.DateTimeField(null=True,blank=True,)
    welcome_email_error = models.TextField(blank=True,default="",)
    email = models.EmailField(unique=True,db_index=True,)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,null=True,blank=True,related_name="newsletter_subscriptions",)
    status = models.CharField(max_length=20,choices=Status.choices,default=Status.SUBSCRIBED,db_index=True,)
    brevo_contact_id = models.PositiveBigIntegerField(null=True, blank=True)
    subscribed_at = models.DateTimeField(default=timezone.now,)
    unsubscribed_at = models.DateTimeField(null=True,blank=True,)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-subscribed_at"]

    def __str__(self):
        return self.email


class NewsletterTemplate(models.Model):
    name = models.CharField(max_length=150,unique=True,)
    description = models.TextField(blank=True,)
    subject = models.CharField(max_length=255,)
    preview_text = models.CharField(max_length=255,blank=True,)
    blocks = models.JSONField(default=list,blank=True,)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="newsletter_templates",)
    created_at = models.DateTimeField(auto_now_add=True,)
    updated_at = models.DateTimeField(auto_now=True,)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


class NewsletterCampaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUEUED = "queued", "Queued"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    class Audience(models.TextChoices):
        ALL = "all", "All subscribers"
        SELECTED = "selected", "Selected subscribers"


    audience = models.CharField(max_length=20,choices=Audience.choices,default=Audience.ALL,)
    selected_subscribers = models.ManyToManyField("NewsletterSubscriber",blank=True,related_name="selected_campaigns",)
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)
    brevo_campaign_id = models.PositiveBigIntegerField(null=True, blank=True)
    name = models.CharField(max_length=200,)
    subject = models.CharField(max_length=255,)
    preview_text = models.TextField(blank=True,)
    blocks = models.JSONField(default=list,blank=True,)
    template = models.ForeignKey(NewsletterTemplate,on_delete=models.SET_NULL,null=True,blank=True,related_name="campaigns",)
    status = models.CharField(max_length=20,choices=Status.choices,default=Status.DRAFT,db_index=True,)
    recipients = models.PositiveIntegerField(default=0,)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="newsletter_campaigns",)
    created_at = models.DateTimeField(auto_now_add=True,)
    updated_at = models.DateTimeField(auto_now=True,)
    queued_at = models.DateTimeField(null=True,blank=True,)
    sent_at = models.DateTimeField(null=True,blank=True,)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class NewsletterRecipient(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        BOUNCED = "bounced", "Bounced"
        FAILED = "failed", "Failed"
        COMPLAINED = "complained", "Spam Complaint"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)
    campaign = models.ForeignKey(NewsletterCampaign,on_delete=models.CASCADE,related_name="campaign_recipients",)
    subscriber = models.ForeignKey(NewsletterSubscriber,on_delete=models.SET_NULL,null=True,blank=True,related_name="campaign_recipients",)
    email = models.EmailField(db_index=True,)
    status = models.CharField(max_length=20,choices=Status.choices,default=Status.PENDING,db_index=True,)
    provider_message_id = models.CharField(max_length=255,blank=True,null=True,unique=True,)
    error_message = models.TextField(blank=True,)
    sent_at = models.DateTimeField(null=True,blank=True,)
    delivered_at = models.DateTimeField(null=True,blank=True,)
    opened_at = models.DateTimeField(null=True,blank=True,)
    clicked_at = models.DateTimeField(null=True,blank=True,)
    created_at = models.DateTimeField(auto_now_add=True,)

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "email"],
                name="unique_newsletter_campaign_recipient",
            ),
        ]

    def __str__(self):
        return f"{self.email} - {self.campaign.name}"


class NewsletterEvent(models.Model):
    recipient = models.ForeignKey(NewsletterRecipient,on_delete=models.CASCADE,related_name="events",)
    event_type = models.CharField(max_length=100,db_index=True,)
    provider_event_id = models.CharField(max_length=255,unique=True,)
    occurred_at = models.DateTimeField(null=True,blank=True,)
    payload = models.JSONField(default=dict,blank=True,)
    created_at = models.DateTimeField(auto_now_add=True,)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event_type} - {self.recipient.email}"



class WelcomeEmailStatus(models.TextChoices):
    NOT_SENT = "not_sent", "Not sent"
    SENDING = "sending", "Sending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"


welcome_email_status = models.CharField(max_length=20,choices=WelcomeEmailStatus.choices,default=WelcomeEmailStatus.NOT_SENT,db_index=True,)
welcome_email_sent_at = models.DateTimeField(null=True,blank=True,)
welcome_email_error = models.TextField(blank=True,default="",)







