import logging
import requests
from html import escape
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .models import ( NewsletterCampaign, NewsletterRecipient,NewsletterSubscriber)
from .services import ( render_newsletter_email, send_email_via_resend,)
from .brevo import ( create_brevo_contact, unsubscribe_brevo_contact, create_brevo_campaign, send_brevo_campaign, send_brevo_welcome_email,send_brevo_campaign_email)
logger = logging.getLogger(__name__)
from django.conf import settings







# 
@shared_task(bind=True,autoretry_for=(Exception,),retry_backoff=True,retry_kwargs={"max_retries": 5},)
def sync_unsubscribe_with_brevo(self, subscriber_id):
    subscriber = NewsletterSubscriber.objects.get(pk=subscriber_id)

    if subscriber.status == NewsletterSubscriber.Status.SUBSCRIBED:
        return {
            "success": False,
            "skipped": True,
            "reason": "Subscriber is still subscribed.",
        }

    unsubscribe_brevo_contact(subscriber.email)

    return {
        "success": True,
        "subscriber_id": subscriber.pk,
    }


# 
@shared_task(bind=True,autoretry_for=(Exception,),retry_backoff=True,retry_kwargs={"max_retries": 5},)
def send_newsletter_welcome_email(self, subscriber_id):
    # Claim the email before making the external API request.
    with transaction.atomic():
        subscriber = (NewsletterSubscriber.objects
            .select_for_update()
            .select_related("user")
            .get(pk=subscriber_id)
        )

        if subscriber.status != NewsletterSubscriber.Status.SUBSCRIBED:
            return {
                "success": False,
                "skipped": True,
                "reason": "Subscriber is no longer subscribed.",
            }

        if subscriber.welcome_email_status in {NewsletterSubscriber.WelcomeEmailStatus.SENT, NewsletterSubscriber.WelcomeEmailStatus.SENDING,}:
            return {
                "success": True,
                "skipped": True,
                "reason": "Welcome email is already sent or in progress.",
            }

        subscriber.welcome_email_status = (NewsletterSubscriber.WelcomeEmailStatus.SENDING)
        subscriber.welcome_email_error = ""
        subscriber.save(update_fields=[ "welcome_email_status", "welcome_email_error", "updated_at",])

    try:
        user = subscriber.user
        first_name = (
            getattr(user, "first_name", "")
            if user
            else ""
        )

        result = send_brevo_welcome_email(email=subscriber.email,first_name=first_name,)

        # Record success only after Brevo accepts the email request.
        subscriber.welcome_email_status = (NewsletterSubscriber.WelcomeEmailStatus.SENT)
        subscriber.welcome_email_sent_at = timezone.now()
        subscriber.welcome_email_error = ""
        subscriber.save(update_fields=["welcome_email_status","welcome_email_sent_at","welcome_email_error","updated_at",])
        logger.info("Welcome email accepted by Brevo for subscriber_id=%s",subscriber.pk,)

        return {
            "success": True,
            "subscriber_id": subscriber.pk,
            "email": subscriber.email,
            "brevo_response": result,
        }

    except Exception as exc:
        logger.exception("Welcome email failed for subscriber_id=%s",subscriber.pk,)
        NewsletterSubscriber.objects.filter(pk=subscriber.pk).update(
            welcome_email_status=(NewsletterSubscriber.WelcomeEmailStatus.FAILED),
            welcome_email_error=str(exc)[:5000],
            updated_at=timezone.now(),
        )
        raise

# 
@shared_task(bind=True,autoretry_for=(Exception,),retry_backoff=True,retry_kwargs={"max_retries": 5},)
def sync_subscriber_to_brevo(self,subscriber_id,send_welcome=False,):
    subscriber = NewsletterSubscriber.objects.select_related("user").get(pk=subscriber_id)

    if subscriber.status != NewsletterSubscriber.Status.SUBSCRIBED:
        return {
            "success": False,
            "skipped": True,
            "reason": "Subscriber is not subscribed.",
        }

    user = subscriber.user
    first_name = getattr(user, "first_name", "") if user else ""
    last_name = getattr(user, "last_name", "") if user else ""

    result = create_brevo_contact(
        email=subscriber.email,
        first_name=first_name,
        last_name=last_name,
        subscribed=True,
    )

    contact_id = result.get("id")

    if not contact_id:
        raise RuntimeError(f"Brevo did not return a contact ID for {subscriber.email}.")

    NewsletterSubscriber.objects.filter(pk=subscriber.pk).update(
        brevo_contact_id=contact_id,
        updated_at=timezone.now(),
    )

    welcome_task_id = None

    # Only queue a welcome email for a brand-new subscription.
    if send_welcome:
        welcome_task = send_newsletter_welcome_email.delay(subscriber.pk)
        welcome_task_id = welcome_task.id

    return {
        "success": True,
        "subscriber_id": subscriber.pk,
        "brevo_contact_id": contact_id,
        "welcome_email_queued": bool(welcome_task_id),
        "welcome_task_id": welcome_task_id,
    }


def render_newsletter_blocks(blocks, preview_text=""):
    parts = []

    if preview_text:
        parts.append(
            '<div style="display:none;max-height:0;overflow:hidden;'
            'opacity:0;color:transparent;">'
            f'{escape(preview_text)}</div>'
        )

    store_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000",).rstrip("/")

    for block in blocks or []:
        block_type = block.get("type")
        content = escape(str(block.get("content", "")))
        url = escape(str(block.get("url", "")), quote=True)

        if block_type == "heading":
            text = escape(str(block.get("text", block.get("content", ""))))
            parts.append(f'<h2 style="font-size:24px;margin:20px 0;">{text}</h2>')

        elif block_type == "paragraph":
            parts.append(
                f'<p style="font-size:16px;line-height:1.7;">'
                f'{content}</p>'
            )

        elif block_type == "image":
            image_url = escape(
                str(block.get("url", block.get("src", ""))),
                quote=True,
            )
            alt = escape(str(block.get("alt", "")), quote=True)

            if image_url.startswith(("https://", "http://")):
                parts.append(
                    f'<img src="{image_url}" alt="{alt}" '
                    'style="display:block;width:100%;max-width:600px;'
                    'height:auto;margin:16px auto;border:0;">'
                )

        elif block_type == "button":
            label = escape(str(block.get("label", block.get("text", "Shop Now"))))
            button_url = block.get("url", store_url)
            button_url = str(button_url)

            if button_url.startswith(("https://", "http://")):
                button_url = escape(button_url, quote=True)
                parts.append(
                    '<p style="text-align:center;margin:24px 0;">'
                    f'<a href="{button_url}" '
                    'style="display:inline-block;background:#111;color:#fff;'
                    'padding:14px 28px;text-decoration:none;'
                    'border-radius:5px;font-weight:bold;">'
                    f'{label}</a></p>'
                )

        elif block_type == "divider":
            parts.append(
                '<hr style="border:0;border-top:1px solid #eee;'
                'margin:24px 0;">'
            )

        elif block_type == "spacer":
            try:
                height = max(0,min(int(block.get("height", 20)), 200),)
            except (ValueError, TypeError):
                height = 20

            parts.append(f'<div style="height:{height}px;"></div>')

        elif block_type == "product":
            name = escape(str(block.get("name", "")))
            price = escape(str(block.get("price", "")))
            image = str(block.get("image", ""))
            product_url = str(block.get("url", ""))

            if image.startswith(("https://", "http://")):
                image = escape(image, quote=True)
                parts.append(
                    f'<img src="{image}" alt="{name}" '
                    'style="max-width:100%;height:auto;">'
                )

            parts.append(f'<p><strong>{name}</strong></p>')

            if price:
                parts.append(f'<p>{price}</p>')

            if product_url.startswith(("https://", "http://")):
                product_url = escape(product_url, quote=True)
                parts.append(
                    f'<p><a href="{product_url}">View product</a></p>'
                )

        elif block_type == "product_grid":
            items = block.get("products", block.get("items", []))

            if isinstance(items, list):
                for item in items[:30]:
                    if not isinstance(item, dict):
                        continue

                    name = escape(str(item.get("name", "")))
                    price = escape(str(item.get("price", "")))
                    item_url = str(item.get("url", ""))
                    image = str(item.get("image", ""))

                    parts.append(
                        '<div style="display:inline-block;vertical-align:top;'
                        'width:45%;margin:2%;text-align:center;">'
                    )

                    if image.startswith(("https://", "http://")):
                        image = escape(image, quote=True)
                        parts.append(
                            f'<img src="{image}" alt="{name}" '
                            'style="width:100%;height:auto;">'
                        )

                    parts.append(f'<p><strong>{name}</strong></p>')

                    if price:
                        parts.append(f'<p>{price}</p>')

                    if item_url.startswith(("https://", "http://")):
                        item_url = escape(item_url, quote=True)
                        parts.append(
                            f'<a href="{item_url}">Shop now</a>'
                        )

                    parts.append('</div>')

        elif block_type == "social_links":
            links = block.get("links", [])

            if isinstance(links, list):
                for item in links[:20]:
                    if not isinstance(item, dict):
                        continue

                    social_url = str(item.get("url", ""))
                    label = escape(str(item.get("label", "Follow us")))

                    if social_url.startswith(("https://", "http://")):
                        social_url = escape(social_url, quote=True)
                        parts.append(
                            f'<a href="{social_url}">{label}</a> '
                        )

    return f"""
    <!doctype html>
    <html>
      <body style="margin:0;padding:24px;font-family:Arial,sans-serif;
                   color:#222;background:#fff;">
        <div style="max-width:600px;margin:0 auto;">
          <h1 style="text-align:center;font-size:25px;">
            TemmyCollection
          </h1>
          {''.join(parts)}
          <hr style="border:0;border-top:1px solid #eee;margin-top:32px;">
          <p style="font-size:12px;color:#777;text-align:center;">
            You received this email because you subscribed to
            TemmyCollection newsletter.
          </p>
        </div>
      </body>
    </html>
    """


@shared_task(bind=True, max_retries=0)
def send_newsletter_campaign(self, campaign_id):
    campaign = NewsletterCampaign.objects.get(pk=campaign_id)
    allowed_statuses = {NewsletterCampaign.Status.QUEUED,NewsletterCampaign.Status.SENDING,}

    if campaign.status not in allowed_statuses:
        return {
            "success": False,
            "reason": (
                f"Campaign cannot be sent from status "
                f"'{campaign.status}'."
            ),
        }

    campaign.status = NewsletterCampaign.Status.SENDING
    campaign.save(update_fields=["status"])

    if campaign.audience == NewsletterCampaign.Audience.SELECTED:
        subscribers = campaign.selected_subscribers.filter(status=NewsletterSubscriber.Status.SUBSCRIBED).order_by("pk")
    else:
        subscribers = NewsletterSubscriber.objects.filter(status=NewsletterSubscriber.Status.SUBSCRIBED).order_by("pk")

    html_content = render_newsletter_blocks(campaign.blocks,campaign.preview_text,)

    sent_count = 0
    failed_count = 0
    logger.warning(
        "NEWSLETTER DEBUG campaign=%s audience=%s selected_ids=%s selected_emails=%s",
        campaign.pk,
        campaign.audience,
        list(campaign.selected_subscribers.values_list("pk", flat=True)),
        list(campaign.selected_subscribers.values_list("email", flat=True)),
    )
    for subscriber in subscribers.iterator():
        recipient, _ = NewsletterRecipient.objects.get_or_create(
            campaign=campaign,
            email=subscriber.email,
            defaults={
                "subscriber": subscriber,
                "status": NewsletterRecipient.Status.PENDING,
            },
        )

        # Do not resend emails already accepted by Brevo.
        if recipient.status in {NewsletterRecipient.Status.SENT,NewsletterRecipient.Status.DELIVERED,}:
            sent_count += 1
            continue

        # Recheck subscription status before sending.
        if subscriber.status != NewsletterSubscriber.Status.SUBSCRIBED:
            continue

        recipient.subscriber = subscriber
        recipient.status = NewsletterRecipient.Status.SENDING
        recipient.error_message = ""
        recipient.save(update_fields=["subscriber","status","error_message",])

        try:
            result = send_brevo_campaign_email(
                email=recipient.email,
                subject=campaign.subject,
                preview_text=campaign.preview_text,
                html_content=html_content,
            )

            recipient.status = NewsletterRecipient.Status.SENT
            recipient.provider_message_id = result.get("messageId", "")
            recipient.sent_at = timezone.now()
            recipient.error_message = ""
            recipient.save(update_fields=["status","provider_message_id","sent_at","error_message",])
            sent_count += 1

        except Exception as exc:
            logger.exception(
                "Campaign email failed: campaign=%s recipient=%s",
                campaign.pk,
                recipient.email,
            )

            recipient.status = NewsletterRecipient.Status.FAILED
            recipient.error_message = str(exc)[:5000]

            recipient.save(update_fields=["status","error_message",])
            failed_count += 1

    # A partially failed campaign remains retryable.
    campaign.status = (
        NewsletterCampaign.Status.FAILED
        if failed_count
        else NewsletterCampaign.Status.SENT
    )

    campaign.sent_at = timezone.now()
    campaign.save(update_fields=["status", "sent_at"])

    return {
        "success": failed_count == 0,
        "campaign_id": str(campaign.pk),
        "sent": sent_count,
        "failed": failed_count,
        "audience": campaign.audience,
    }





