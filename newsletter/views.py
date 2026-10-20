import logging
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import ( NewsletterSubscriber, NewsletterCampaign)
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination
from newsletter.models import (NewsletterSubscriber,NewsletterSubscriber)
from .serializers import ( NewsletterSubscriberSerializer, NewsletterCampaignSerializer)
from newsletter.tasks import send_newsletter_campaign
from admin_panel.auth import AdminCookieJWTAuthentication
from admin_panel.permissions import IsTemmyAdmin
from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from .brevo import (get_brevo_templates, get_brevo_campaign,send_brevo_test,)
from .email_builder import render_campaign_html
from .tasks import (sync_subscriber_to_brevo,sync_unsubscribe_with_brevo,send_newsletter_campaign,)




logger = logging.getLogger(__name__)
UNSUBSCRIBE_SALT = "newsletter.unsubscribe.v1"




class NewsletterPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class NewsletterUnsubscribeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()

        if not email:
            return Response({"email": ["Email is required."]},status=status.HTTP_400_BAD_REQUEST,)

        subscriber = NewsletterSubscriber.objects.filter(email=email).first()

        # Avoid revealing whether an email exists in the database.
        if subscriber:
            if subscriber.is_subscribed:
                subscriber.is_subscribed = False
                subscriber.save(update_fields=["is_subscribed","updated_at",])

                transaction.on_commit(lambda pk=subscriber.pk:sync_unsubscribe_with_brevo.delay(pk))

        return Response(
            {
                "message": (
                    "If the address was subscribed, "
                    "it has been unsubscribed."
                )
            },
            status=status.HTTP_200_OK,
        )


class NewsletterSubscribersView(ListAPIView):
    serializer_class = NewsletterSubscriberSerializer
    pagination_class = NewsletterPagination
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    def get_queryset(self):
        queryset = NewsletterSubscriber.objects.all().order_by("-created_at")
        search = self.request.query_params.get("search", "").strip()
        subscriber_status = self.request.query_params.get("status", "").strip().lower()

        if search:
            queryset = queryset.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )

        if subscriber_status == "subscribed":
            queryset = queryset.filter(is_subscribed=True)
        elif subscriber_status == "unsubscribed":
            queryset = queryset.filter(is_subscribed=False)

        return queryset


class NewsletterTemplatesView(APIView):
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    def get(self, request):
        try:
            data = get_brevo_templates()

            return Response({
                "results": data.get("templates", []),
                "count": len(data.get("templates", [])),
            })

        except Exception as exc:
            return Response({"error": str(exc)},status=status.HTTP_502_BAD_GATEWAY,)


class NewsletterAudiencePreviewView(APIView):
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    def post(self, request):
        recipient_type = request.data.get("recipient_type", "subscribers")
        queryset = NewsletterSubscriber.objects.filter(is_subscribed=True)

        if recipient_type == "selected":
            emails = request.data.get("recipient_emails", [])

            if not isinstance(emails, list):
                return Response({"error": "recipient_emails must be a list."},status=status.HTTP_400_BAD_REQUEST,)

            queryset = queryset.filter(email__in=emails)

        elif recipient_type != "subscribers":
            return Response({"error": "Unsupported recipient type."},status=status.HTTP_400_BAD_REQUEST,)

        return Response({
            "recipient_type": recipient_type,
            "count": queryset.count(),
            "emails": list(queryset.values_list("email", flat=True)[:100]),
        })


class NewsletterCampaignsView(APIView):
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    def get(self, request):
        queryset = NewsletterCampaign.objects.all().order_by("-created_at")
        search = request.query_params.get("search", "").strip()
        campaign_status = request.query_params.get("status", "").strip()

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(subject__icontains=search)
            )

        if campaign_status:
            queryset = queryset.filter(status=campaign_status)

        paginator = NewsletterPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = NewsletterCampaignSerializer(page,many=True,)

        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = NewsletterCampaignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        campaign = serializer.save(status="draft")

        return Response(NewsletterCampaignSerializer(campaign).data,status=status.HTTP_201_CREATED,)


class NewsletterCampaignSendDraftView(APIView):
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    def post(self, request, pk):
        campaign = get_object_or_404(NewsletterCampaign,pk=pk,)

        if campaign.status in {"sending", "sent"}:
            return Response(
                {
                    "message": "This campaign has already been sent or is sending.",
                    "status": campaign.status,
                },
                status=status.HTTP_409_CONFLICT,
            )

        if campaign.recipient_type == "selected":
            return Response(
                {
                    "error": (
                        "Selected-recipient sending needs a dedicated "
                        "Brevo list. This campaign has not been sent."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        send_newsletter_campaign.delay(campaign.pk)

        return Response(
            {
                "message": "Campaign sending has been queued.",
                "campaign_id": campaign.pk,
                "status": "queued",
            },
            status=status.HTTP_202_ACCEPTED,
        )


class NewsletterCampaignTestView(APIView):
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    def post(self, request):
        campaign_id = request.data.get("campaign_id")
        email = str(request.data.get("email", "")).strip().lower()

        if not email:
            return Response({"email": ["A test recipient email is required."]},status=status.HTTP_400_BAD_REQUEST,)

        campaign = get_object_or_404(NewsletterCampaign,pk=campaign_id,)

        try:
            html_content = render_campaign_html(campaign)

            send_brevo_test(
                email=email,
                subject=f"[TEST] {campaign.subject}",
                html_content=html_content,
                sender_name=campaign.sender_name,
                sender_email=campaign.sender_email,
            )

            return Response({
                "message": "Test email accepted by Brevo.",
                "email": email,
            })

        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class NewsletterCampaignRefreshView(APIView):
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    def post(self, request, pk):
        campaign = get_object_or_404(NewsletterCampaign, pk=pk,)

        if not campaign.brevo_campaign_id:
            return Response(
                {"error": ("This campaign has not been created in Brevo yet.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            data = get_brevo_campaign(campaign.brevo_campaign_id)
            statistics = data.get("statistics") or {}
            global_stats = statistics.get("globalStats") or {}
            delivered = global_stats.get("delivered", 0) or 0
            unique_views = global_stats.get("uniqueViews", 0) or 0
            unique_clicks = global_stats.get("uniqueClicks", 0) or 0

            opened_rate = (
                f"{(unique_views / delivered) * 100:.2f}%"
                if delivered
                else "0.00%"
            )

            click_rate = (
                f"{(unique_clicks / delivered) * 100:.2f}%"
                if delivered
                else "0.00%"
            )

            campaign.opened_rate = opened_rate
            campaign.click_rate = click_rate
            brevo_status = str(data.get("status", "")).lower()

            if brevo_status in {"sent", "suspended"}:
                campaign.status = brevo_status

            campaign.save(update_fields=["opened_rate","click_rate","status","updated_at",])

            return Response(NewsletterCampaignSerializer(campaign).data)

        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY,)


class NewsletterImageUploadView(APIView):
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    def post(self, request):
        image_file = request.FILES.get("image")

        if not image_file:
            return Response(
                {"image": ["Please select an image to upload."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if image_file.size > 5 * 1024 * 1024:
            return Response(
                {"image": ["The maximum image size is 5 MB."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        content_type = getattr(image_file, "content_type", "")

        if content_type not in { "image/jpeg", "image/png", "image/webp", "image/gif",}:
            return Response(
                {"image": ["Unsupported image type."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            import cloudinary.uploader

            result = cloudinary.uploader.upload(
                image_file,
                folder="newsletter",
                resource_type="image",
            )

            return Response(
                {
                    "url": result.get("secure_url"),
                    "public_id": result.get("public_id"),
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class NewsletterSubscribeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        print("NEWSLETTER SUBSCRIBE VIEW HIT")
        email = str(request.data.get("email", "")).strip().lower()

        if not email:
            return Response(
                {"email": ["Email is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_email(email)
        except ValidationError:
            return Response(
                {"email": ["Enter a valid email address."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            subscriber, created = NewsletterSubscriber.objects.get_or_create(
                email=email,
                defaults={
                    "status": NewsletterSubscriber.Status.SUBSCRIBED,
                    "subscribed_at": timezone.now(),
                },
            )

            if not created:
                subscriber.status = NewsletterSubscriber.Status.SUBSCRIBED
                subscriber.subscribed_at = timezone.now()
                subscriber.unsubscribed_at = None
                subscriber.save(update_fields=["status", "subscribed_at", "unsubscribed_at", "updated_at",])

        # The database transaction has finished at this point.
        sync_queued = False
        task_id = None

        try:
            print(f"QUEUEING BREVO SYNC FOR SUBSCRIBER: {subscriber.pk}")
            task = sync_subscriber_to_brevo.delay(subscriber.pk,send_welcome=created,)
            print(f"BREVO SYNC TASK QUEUED: {task.id}")
            task_id = task.id
            sync_queued = True

            logger.info(
                "Newsletter Brevo sync queued: subscriber_id=%s task_id=%s",
                subscriber.pk,
                task_id,
            )

        except Exception:
            logger.exception(
                "Could not queue Brevo sync for subscriber_id=%s",
                subscriber.pk,
            )

        return Response(
            {
                "message": "Subscription successful.",
                "subscriber": NewsletterSubscriberSerializer(subscriber).data,
                "brevo_sync_queued": sync_queued,
                "sync_task_id": task_id,
            },
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            ),
        )



