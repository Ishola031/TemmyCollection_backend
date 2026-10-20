from django.contrib import admin

from .models import (
    NewsletterSubscriber,
    NewsletterTemplate,
    NewsletterCampaign,
    NewsletterRecipient,
    NewsletterEvent,
)


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email","status","user","subscribed_at",)
    list_filter = ("status",)
    search_fields = ("email",)
    readonly_fields = ("subscribed_at","unsubscribed_at",)


@admin.register(NewsletterTemplate)
class NewsletterTemplateAdmin(admin.ModelAdmin):
    list_display = ("name","subject","created_at","updated_at",)
    search_fields = ("name", "subject")


@admin.register(NewsletterCampaign)
class NewsletterCampaignAdmin(admin.ModelAdmin):
    list_display = ("name","subject","status","recipients","created_at",)
    list_filter = ("status",)
    search_fields = ("name", "subject")


@admin.register(NewsletterRecipient)
class NewsletterRecipientAdmin(admin.ModelAdmin):
    list_display = ("email","campaign","status","sent_at","delivered_at",)
    list_filter = ("status",)
    search_fields = ("email",)


@admin.register(NewsletterEvent)
class NewsletterEventAdmin(admin.ModelAdmin):
    list_display = ("recipient","event_type","occurred_at",)
    list_filter = ("event_type",)
    search_fields = ("recipient__email",)



