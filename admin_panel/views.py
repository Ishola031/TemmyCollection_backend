from django.contrib.auth import authenticate
from django.db.models import Prefetch, Count, Sum, Max, Avg, IntegerField,Case, When, Q, Value,DecimalField, F, ExpressionWrapper, Min
from django.db.models.functions import Coalesce, TruncMonth, TruncDate, TruncDay
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import json
from rest_framework import generics
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from django.views.decorators.csrf import csrf_exempt
from .permissions import IsTemmyAdmin
from .serializers import AdminLoginSerializer, AdminProductDetailSerializer, AdminReviewSerializer, AdminCategoryProductSerializer, AdminCategoryTreeSerializer, AdminBrandSerializer,AdminColorSerializer,AdminSizeSerializer,AdminProductCreateSerializer,AdminProductUpdateSerializer, AdminCouponSerializer, AdminReviewStatusSerializer, AdminCategorySerializer
from .auth import AdminCookieJWTAuthentication
from datetime import datetime, timedelta, time
from decimal import Decimal
from django.db import transaction, models
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from product.models import Variation, Category, Brand,Color,Size, ProductReview
from Account.models import Account
from order.models import Order, ShippingAddress, Product, OrderItem, OrderStatusHistory, Shipment,ShipmentTracking, PickupStation, Coupon, Payment, ReviewRating
from order.serializers import ShippingAddressSerializer, OrderSerializer, OrderItemSerializer, ShipmentTrackingSerializer,ShipmentSerializer,OrderStatusHistorySerializer
from rest_framework.parsers import MultiPartParser, FormParser
from newsletter.models import NewsletterSubscriber, NewsletterCampaign, NewsletterTemplate, NewsletterRecipient, NewsletterRecipient
from newsletter.serializers import (NewsletterSubscriberSerializer,NewsletterCampaignSerializer,NewsletterRecipientSerializer,
    NewsletterCampaignSerializer, NewsletterTemplateSerializer
)
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from newsletter.tasks import send_newsletter_campaign
import logging
from .models import StoreSettings
from .serializers import StoreSettingsSerializer

ADMIN_SESSION_TIMEOUT = 30 * 60
logger = logging.getLogger(__name__)

SUCCESSFUL_ORDER_STATUSES = [
    "Successful",
    "Processing",
    "Shipped",
    "At_Pickup_Station",
    "Ready_for_Pickup",
    "Collected",
    "Delivered",
]




# 
class AdminReviewPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login(request):
    serializer = AdminLoginSerializer(data=request.data)

    if not serializer.is_valid():
        return Response( serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['email']
    password = serializer.validated_data['password']

    user = authenticate(email=email,password=password)

    if user is None:
        return Response(
            {
                'success': False,
                'message': 'Invalid email or password.'
            },
            status=status.HTTP_401_UNAUTHORIZED
        )

    if not user.is_active:
        return Response(
            {
                'success': False,
                'message': 'This account is inactive.'
            },
            status=status.HTTP_403_FORBIDDEN
        )

    if user.is_banned:
        if user.is_ban_expired():
            user.is_banned = False
            user.ban_reason = None
            user.banned_at = None
            user.ban_expires_at = None
            user.banned_by = None

            user.save(update_fields=['is_banned', 'ban_reason', 'banned_at', 'ban_expires_at', 'banned_by'])
        else:
            return Response(
                {
                    'success': False,
                    'message': 'This account has been banned.',
                    'reason': user.ban_reason,
                    'expires_at': user.ban_expires_at
                },
                status=status.HTTP_403_FORBIDDEN
            )

    if not ( user.is_staff or user.is_admin or user.is_superadmin):
        return Response(
            {
                'success': False,
                'message': 'You are not authorized to access the admin site.'
            },
            status=status.HTTP_403_FORBIDDEN
        )

    now = timezone.now()
    user.last_activity = now
    user.last_login = now
    user.save(update_fields=[ 'last_activity', 'last_login'])
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)
    response = Response(
        {
            'success': True,
            'message': 'Admin login successful.'
        },
        status=status.HTTP_200_OK
    )

    # Access token
    response.set_cookie(
        key='admin_access_token',
        value=access_token,
        max_age=15 * 60,
        httponly=True,
        samesite='Lax',
        secure=False,
        path='/'
    )

    # Session cookie
    # No max_age means it disappears when the browser closes.
    response.set_cookie(
        key='admin_refresh_token',
        value=refresh_token,
        httponly=True,
        samesite='Lax',
        secure=False,
        path='/'
    )

    return response


@api_view(['POST'])
@authentication_classes([AdminCookieJWTAuthentication])
@permission_classes([AllowAny])
def admin_logout(request):
    response = Response(
        {
            'success': True,
            'message': 'Admin logged out successfully.'
        },
        status=status.HTTP_200_OK
    )

    response.delete_cookie( 'admin_access_token', path='/')
    response.delete_cookie( 'admin_refresh_token', path='/')
    return response


class AdminRefreshTokenView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('admin_refresh_token')

        if not refresh_token:
            return Response(
                {
                    'success': False,
                    'message': 'Admin session expired.'
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Make a mutable copy of the request data
        data = request.data.copy()

        # Put the admin refresh token into the copied data
        data['refresh'] = refresh_token

        try:
            # Temporarily replace request.data
            request._full_data = data
            response = super().post( request, *args, **kwargs)

            if response.status_code != status.HTTP_200_OK:
                return Response(
                    {
                        'success': False,
                        'message': 'Admin session expired.'
                    },
                    status=status.HTTP_401_UNAUTHORIZED
                )

            access_token = response.data.get('access')

            if not access_token:
                return Response(
                    {
                        'success': False,
                        'message': 'Unable to refresh token.'
                    },
                    status=status.HTTP_401_UNAUTHORIZED
                )

            res = Response(
                {
                    'success': True,
                    'refreshed': True
                },
                status=status.HTTP_200_OK
            )

            # IMPORTANT:
            # This is the ADMIN access token cookie.
            res.set_cookie(
                key='admin_access_token',
                value=access_token,
                max_age=15 * 60,
                httponly=True,
                samesite='Lax',
                secure=False,
                path='/'
            )

            return res

        except Exception as e:

            print("ADMIN REFRESH ERROR:", str(e))

            return Response(
                {
                    'success': False,
                    'message': 'Admin session expired.'
                },
                status=status.HTTP_401_UNAUTHORIZED
            )


@api_view(['GET'])
@authentication_classes([AdminCookieJWTAuthentication])
@permission_classes([IsAuthenticated,IsTemmyAdmin])
def admin_me(request):
    user = request.user
    now = timezone.now()

    if user.last_activity:
        inactive_time = (now - user.last_activity).total_seconds()

        if inactive_time > ADMIN_SESSION_TIMEOUT:
            response = Response(
                {
                    'success': False,
                    'message': 'Admin session expired due to inactivity.'
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

            response.delete_cookie( 'access_token', path='/')
            response.delete_cookie( 'admin_refresh_token', path='/')
            return response

    user.last_activity = now
    user.save(update_fields=['last_activity'])
    return Response(
        {
            'success': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone_number': user.phone_number,
                'image': user.image.url if user.image else None,
                'is_staff': user.is_staff,
                'is_admin': user.is_admin,
                'is_superadmin': user.is_superadmin,
                'is_active': user.is_active,
                'is_banned': user.is_banned,
                'last_login': user.last_login,
                'last_activity': user.last_activity,
            }
        },
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
@authentication_classes([AdminCookieJWTAuthentication])
@permission_classes([IsAuthenticated,IsTemmyAdmin])
def admin_auth_check(request):
    user = request.user
    now = timezone.now()

    if user.last_activity:
        inactive_time = (now - user.last_activity).total_seconds()

        if inactive_time > ADMIN_SESSION_TIMEOUT:
            return Response(
                {
                    'isAuthorized': False,
                    'message': 'Admin session expired.'
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

    user.last_activity = now
    user.save(update_fields=['last_activity'])

    return Response(
        {
            'isAuthorized': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'username': user.username,
                'is_staff': user.is_staff,
                'is_admin': user.is_admin,
                'is_superadmin': user.is_superadmin,
            }
        },
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@authentication_classes([AdminCookieJWTAuthentication])
@permission_classes([IsAuthenticated,IsTemmyAdmin])
def admin_activity(request):
    user = request.user
    now = timezone.now()

    if user.last_activity:
        inactive_time = (now - user.last_activity).total_seconds()
        if inactive_time > ADMIN_SESSION_TIMEOUT:
            response = Response(
                {
                    'success': False,
                    'message': 'Admin session expired due to inactivity.'
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

            response.delete_cookie('access_token',path='/')
            response.delete_cookie( 'admin_refresh_token', path='/')
            return response

    user.last_activity = now
    user.save(update_fields=['last_activity'])

    return Response({'success': True}, status=status.HTTP_200_OK)


class AdminCustomerPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AdminCustomerListView(APIView):
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTemmyAdmin]

    def get(self, request):
        customers = Account.objects.filter(is_not_user=False).annotate(
            order_count=Count('orders', distinct=True),
            total_spent=Sum('orders__total_price'),
            last_order_date=Max('orders__created_at'),
        ).order_by('-date_joined')

        search = request.GET.get('search', '').strip()
        if search:
            customers = customers.filter(
                email__icontains=search
            ) | customers.filter(
                username__icontains=search
            ) | customers.filter(
                first_name__icontains=search
            ) | customers.filter(
                last_name__icontains=search
            )

        status_filter = request.GET.get('status')

        if status_filter == 'active':
            customers = customers.filter(is_active=True)
        elif status_filter == 'inactive':
            customers = customers.filter(is_active=False)
        elif status_filter == 'banned':
            customers = customers.filter(is_banned=True)
        elif status_filter == 'not_banned':
            customers = customers.filter(is_banned=False)

        paginator = AdminCustomerPagination()
        page = paginator.paginate_queryset(customers, request)

        data = []
        for customer in page:
            data.append({
                'id': customer.id,
                'username': customer.username,
                'email': customer.email,
                'first_name': customer.first_name,
                'last_name': customer.last_name,
                'phone_number': customer.phone_number,
                'image': customer.image.url if customer.image else None,

                'is_active': customer.is_active,
                'is_banned': customer.is_banned,

                'order_count': customer.order_count,
                'total_spent': (
                    str(customer.total_spent)
                    if customer.total_spent
                    else '0.00'
                ),

                'last_order_date': customer.last_order_date,

                'date_joined': customer.date_joined,
                'last_login': customer.last_login,
            })

        return paginator.get_paginated_response(data)


class AdminCustomerDetailsView(APIView):
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTemmyAdmin]

    def get(self, request):
        username = request.GET.get('username', None)
        print(username)
        if not username:
            return Response({'error': 'username not found'}, status=404)

        customer = Account.objects.filter(username=username).annotate(
            order_count=Count('orders', distinct=True),
            total_spent=Sum('orders__sub_total'),
            last_order_date=Max('orders__created_at'),
            avg_order=Avg('orders__sub_total')
        ).first()

        addresses = ShippingAddressSerializer(customer.shipping_addresses.all(), many=True).data
        orders = OrderSerializer(customer.orders.all().annotate(items = Count('orderitems__quantity')), many=True).data

        orders_data = customer.orders.all().annotate(items = Count('orderitems__quantity'))
        successful_orders = orders_data.filter(status__in=['Successful','Shipped','Delivered']).count()

        pending_orders = orders_data.filter(status__in=['Pending',]).count()
        cancelled_orders = orders_data.filter(status__in=['Cancelled',]).count()


        data = {
            'id': customer.id,
            'username': customer.username,
            'email': customer.email,
            'first_name': customer.first_name,
            'last_name': customer.last_name,
            'phone_number': customer.phone_number,
            'image': customer.image.url if customer.image else None,

            'is_active': customer.is_active,
            'is_banned': customer.is_banned,

            # "addresses": addresses,

            'order_count': customer.order_count,
            # 'orders': orders,
            'cancelled_orders':cancelled_orders,
            'pending_orders':pending_orders,
            'successful_orders':successful_orders,


            'avg_order': customer.avg_order,
            'total_spent': (
                str(customer.total_spent)
                if customer.total_spent
                else '0.00'
            ),

            'last_order_date': customer.last_order_date,
            
            'date_joined': customer.date_joined,
            'last_login': customer.last_login,
        }
        return Response(data, status=200)


class ProductPagination(PageNumberPagination):
    page_size = 8

    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)
        response.data["current_page"] = self.page.number
        response.data["total_pages"] = self.page.paginator.num_pages
        return response


@api_view(['GET'])
@authentication_classes([AdminCookieJWTAuthentication])
@permission_classes([IsAuthenticated,IsTemmyAdmin])
def OrderAPI(request):
    username = request.GET.get('username', None)
    orders = Order.objects.select_related('shipping_address', 'payment').filter(user__username=username).order_by('-created_at')
    paginators = ProductPagination()
    page = paginators.paginate_queryset(orders, request)
    serializer = OrderSerializer(page, many=True)
    return paginators.get_paginated_response(serializer.data)


@api_view(['GET'])
@authentication_classes([AdminCookieJWTAuthentication])
@permission_classes([IsAuthenticated,IsTemmyAdmin])
def AddressesAPI(request):
    username = request.GET.get('username', None)
    orders = ShippingAddress.objects.select_related('user').filter(user__username=username).order_by('-created_at')
    paginators = ProductPagination()
    page = paginators.paginate_queryset(orders, request)
    serializer = ShippingAddressSerializer(page, many=True)
    return paginators.get_paginated_response(serializer.data)


class AdminCustomerStatsView(APIView):
    permission_classes = [ IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    def get(self, request):
        customers = Account.objects.filter( is_staff=False, is_admin=False, is_superadmin=False, is_not_user=False)
        active_customers = customers.filter( is_active=True, is_banned=False).count()
        total_customers = customers.count()
        now = timezone.now()
        new_this_month = customers.filter( date_joined__year=now.year, date_joined__month=now.month).count()
        successful_statuses = [ 'Successful', 'Shipped', 'Delivered']
        total_spent = customers.aggregate(
            total=Sum( 'orders__sub_total', filter=Q(orders__status__in=successful_statuses))
        )['total'] or 0

        customers_with_orders = customers.filter(orders__status__in=successful_statuses).distinct().count()

        if customers_with_orders:
            average_spend = (total_spent / customers_with_orders)
        else:
            average_spend = 0

        return Response({
            'success': True,
            'stats': {
                'total_customers': total_customers,
                'active_customers': active_customers,
                'new_this_month': new_this_month,
                'average_spend': average_spend,
            }
        })


def get_image_url(image):
    if not image:
        return None

    try:
        return image.url
    except (AttributeError, ValueError):
        return None


class DashboardView(APIView):
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    def get_period_dates(self, period, custom_start=None, custom_end=None):
        now = timezone.now()
        today = now.date()

        if period == "today":
            start = today
            end = today

        elif period == "yesterday":
            start = today - timedelta(days=1)
            end = start

        elif period == "7days":
            start = today - timedelta(days=6)
            end = today

        elif period == "week":
            start = today - timedelta(days=today.weekday())
            end = today

        elif period == "last_week":
            this_monday = today - timedelta(days=today.weekday())
            start = this_monday - timedelta(days=7)
            end = this_monday - timedelta(days=1)

        elif period == "month":
            start = today.replace(day=1)
            end = today

        elif period == "last_month":
            first_this_month = today.replace(day=1)
            last_month_end = first_this_month - timedelta(days=1)
            start = last_month_end.replace(day=1)
            end = last_month_end

        elif period == "year":
            start = today.replace(month=1, day=1)
            end = today

        elif period == "last_year":
            start = today.replace( year=today.year - 1, month=1, day=1,)
            end = today.replace( year=today.year - 1, month=12, day=31,)

        elif period == "custom" and custom_start and custom_end:
            try:
                start = datetime.strptime( custom_start, "%Y-%m-%d",).date()
                end = datetime.strptime( custom_end, "%Y-%m-%d",).date()

            except ValueError:
                start = today.replace(day=1)
                end = today
        else:
            period = "month"
            start = today.replace(day=1)
            end = today

        return period, start, end

    def percentage_change(self, current, previous):
        if previous == 0:
            if current == 0:
                return 0
            return 100

        return round(
            ((current - previous) / previous) * 100,
            2,
        )

    def money(self, value):
        return round(float(value or 0), 2)

    def get(self, request):
        period = request.GET.get("period", "month")
        custom_start = request.GET.get("start_date")
        custom_end = request.GET.get("end_date")

        period, start_date, end_date = self.get_period_dates( period, custom_start, custom_end,)

        # DATE RANGE
        start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        end_datetime = timezone.make_aware(datetime.combine( end_date, datetime.max.time(),))

        # PAYMENTS
        payments = Payment.objects.annotate(effective_date=Coalesce( "paid_at", "created_at",))
        period_payments = payments.filter(effective_date__range=(start_datetime, end_datetime,))
        successful_payments = period_payments.filter(status="successful")
        pending_payments = period_payments.filter(status="pending")
        refunded_payments = period_payments.filter(status="refunded")

        # ORDERS
        orders = (
            Order.objects.select_related("user", "payment", "coupon", "shipping_address", "pickup_station",)
            .filter(created_at__range=( start_datetime, end_datetime,))
        )
        successful_orders = orders.filter(payment__status="successful")
        cancelled_orders = orders.filter(status="Cancelled")
        pending_orders = orders.filter(status="Pending")
        processing_orders = orders.filter(status__in=[ "Successful", "Processing", "Shipped", "At_Pickup_Station", "Ready_for_Pickup",])
        delivered_orders = orders.filter(status="Delivered")
        collected_orders = orders.filter(status="Collected")
        shipped_orders = orders.filter(status="Shipped")

        # FINANCIAL DATA
        total_revenue = successful_payments.aggregate(total=Sum("amount"))["total"] or 0
        pending_payment_amount = pending_payments.aggregate(total=Sum("amount"))["total"] or 0
        refunded_amount = refunded_payments.aggregate(total=Sum("amount"))["total"] or 0
        product_sales = successful_orders.aggregate(total=Sum(ExpressionWrapper(
            F("sub_total") - F("coupon_discount"), 
            output_field=DecimalField(max_digits=14, decimal_places=2,)
        ,)))["total"] or 0

        coupon_discount = successful_orders.aggregate(total=Sum("coupon_discount"))["total"] or 0
        shipping_revenue = successful_orders.aggregate(total=Sum("shipping_price"))["total"] or 0
        average_order_value = successful_payments.aggregate(average=Avg("amount"))["average"] or 0

        # ---------------------------------------------------------
        # PRODUCT DISCOUNT
        # OrderItem.price = original price
        # OrderItem.discount = product percentage discount
        # ---------------------------------------------------------

        successful_items = OrderItem.objects.filter(order__in=successful_orders)
        product_discount_expression = ExpressionWrapper(F("price") * F("quantity") * F("discount") / Value(100),
            output_field=DecimalField( max_digits=14, decimal_places=2,),
        )

        product_discount = successful_items.aggregate(total=Sum(product_discount_expression))["total"] or 0

        # ORDER COUNTS
        total_orders = orders.count()
        successful_order_count = successful_orders.count()
        pending_order_count = pending_orders.count()
        processing_order_count = processing_orders.count()
        shipped_order_count = shipped_orders.count()
        delivered_order_count = delivered_orders.count()
        collected_order_count = collected_orders.count()
        cancelled_order_count = cancelled_orders.count()
        fulfilled_orders = (delivered_order_count + collected_order_count)
        fulfillment_rate = (
            (fulfilled_orders / total_orders) * 100
            if total_orders
            else 0
        )

        cancellation_rate = (
            (cancelled_order_count / total_orders) * 100
            if total_orders
            else 0
        )

        # CUSTOMERS
        customer_filter = Q( is_staff=False, is_admin=False, is_superadmin=False, is_not_user=False,)
        total_customers = Account.objects.filter(customer_filter).count()
        customers_with_orders = successful_orders.filter(user__isnull=False).values("user").distinct().count()
        returning_customers = (successful_orders.filter(user__isnull=False).values("user").annotate(order_count=Count("order_number")).filter(order_count__gt=1).count())

        # New customers based on customers whose first successful
        # order falls inside the selected period.
        customer_first_orders = (Order.objects.filter(payment__status="successful",user__isnull=False,)
            .values("user").annotate(first_order=TruncDate(Min("created_at"))))

        new_customers = sum(
            1
            for customer in customer_first_orders
            if customer["first_order"]
            and start_date
            <= customer["first_order"]
            <= end_date
        )

        # PRODUCTS
        total_products = Product.objects.count()
        published_products = Product.objects.filter(is_available=True).count()
        draft_products = Product.objects.filter(is_available=False).count()
        low_stock_products_count = Product.objects.filter(stock__gt=0,stock__lte=10,).count()
        out_of_stock_products_count = Product.objects.filter(stock=0).count()

        # COUPONS
        coupon_orders = successful_orders.filter(coupon__isnull=False)
        coupons_used = coupon_orders.count()
        coupon_orders_count = coupon_orders.values("coupon").distinct().count()
        most_used_coupon = (
            coupon_orders.values("coupon__code", "coupon__discount_type",)
            .annotate(usage=Count("order_number"), discount=Sum("coupon_discount"),)
            .order_by("-usage").first()
        )

        top_coupons = list(coupon_orders.values("coupon__code","coupon__discount_type",)
            .annotate(usage=Count("order_number"), discount=Sum("coupon_discount"),)
            .order_by("-usage")[:5]
        )

        formatted_top_coupons = []
        for coupon in top_coupons:
            formatted_top_coupons.append({
                "code": coupon["coupon__code"],
                "discount_type": coupon["coupon__discount_type"],
                "usage": coupon["usage"],
                "discount": self.money(coupon["discount"]),
            })

        # SHIPPING
        delivery_orders = successful_orders.filter(delivery_method="delivery")
        pickup_orders = successful_orders.filter(delivery_method="pickup")
        delivery_shipping_revenue = delivery_orders.aggregate(total=Sum("shipping_price"))["total"] or 0
        pickup_shipping_revenue = pickup_orders.aggregate(total=Sum("shipping_price"))["total"] or 0

        # ---------------------------------------------------------
        # PREVIOUS PERIOD
        # Used for dashboard percentage changes.
        # ---------------------------------------------------------
        period_length = ( end_date - start_date).days + 1
        previous_end = start_date - timedelta(days=1)
        previous_start = ( previous_end - timedelta(days=period_length - 1))
        previous_start_datetime = timezone.make_aware(
            datetime.combine(previous_start, datetime.min.time(),)
        )

        previous_end_datetime = timezone.make_aware(
            datetime.combine(previous_end,datetime.max.time(),)
        )

        previous_revenue = (
            Payment.objects.annotate(
                effective_date=Coalesce("paid_at","created_at",)
            ).filter(
                status="successful",
                effective_date__range=(previous_start_datetime, previous_end_datetime,),
            ).aggregate(total=Sum("amount"))["total"] or 0
        )

        previous_orders = Order.objects.filter(
            created_at__range=(
                previous_start_datetime,
                previous_end_datetime,
            )
        ).count()

        # REVENUE CHART
        monthly_revenue = []

        if period in ["today","yesterday","7days","week","last_week","custom",]:
            daily_revenue = (successful_payments.annotate(day=TruncDate("effective_date")).values("day").annotate(revenue=Sum("amount")).order_by("day"))
            revenue_map = {item["day"]: self.money(item["revenue"]) for item in daily_revenue}

            current_day = start_date
            while current_day <= end_date:
                monthly_revenue.append({
                    "label": current_day.strftime("%b %d"),
                    "date": str(current_day),
                    "revenue": revenue_map.get( current_day, 0,),
                })
                current_day += timedelta(days=1)
        else:
            monthly_data = (
                successful_payments.annotate(month=TruncMonth("effective_date"))
                .values("month").annotate(revenue=Sum("amount")).order_by("month")
            )

            revenue_map = {
                item["month"].strftime("%Y-%m"): self.money(item["revenue"])
                for item in monthly_data
            }

            current_month = start_date.replace(day=1)
            end_month = end_date.replace(day=1)

            while current_month <= end_month:
                key = current_month.strftime("%Y-%m")
                monthly_revenue.append({
                    "label": current_month.strftime("%b %Y"),
                    "date": key,
                    "revenue": revenue_map.get(key,0,),
                })

                if current_month.month == 12:
                    current_month = current_month.replace(year=current_month.year + 1, month=1,)
                else:
                    current_month = current_month.replace(month=current_month.month + 1)

        # ORDER STATUS
        order_status = {
            "delivered": delivered_order_count,
            "collected": collected_order_count,
            "processing": processing_order_count,
            "shipped": shipped_order_count,
            "pending": pending_order_count,
            "cancelled": cancelled_order_count,
        }

        # TOP PRODUCTS
        top_products = (
            successful_items.values("product","product__name","product__slug","product__image",)
            .annotate(
                quantity_sold=Sum("quantity"),
                revenue=Sum(ExpressionWrapper(F("price") * F("quantity") * (Value(100) - F("discount")) / Value(100),
                    output_field=DecimalField(max_digits=14, decimal_places=2,),)
                ),
            ).order_by("-quantity_sold")[:10]
        )

        formatted_top_products = []

        for product in top_products:
            formatted_top_products.append({
                "id": product["product"],
                "name": product["product__name"],
                "slug": product["product__slug"],
                "image": get_image_url(product["product__image"]),
                "quantity_sold": product["quantity_sold"],
                "revenue": self.money(product["revenue"]),
            })

        # LOW STOCK PRODUCTS
        low_stock_products = Product.objects.filter(stock__lte=10).order_by("stock")[:10]
        formatted_low_stock = []

        for product in low_stock_products:
            formatted_low_stock.append({
                "id": product.id,
                "name": product.name,
                "stock": product.stock,
                "is_out_of_stock": product.stock == 0,
                "slug": product.slug,
            })

        # RECENT ORDERS
        recent_orders = orders.order_by("-created_at")[:10]
        recent_order_data = []

        for order in recent_orders:
            customer_name = "Guest"

            if order.user:
                customer_name = (getattr(order.user, "name", None,) or getattr(order.user, "username", None,)
                    or getattr(order.user, "email", None,) or "Customer"
                )

            recent_order_data.append({
                "id": str(order.order_number),
                "order_number": str(order.order_number),
                "customer": customer_name,
                "status": order.status,
                "delivery_method": (order.delivery_method),
                "total": self.money(order.total_price),
                "coupon_discount": self.money(order.coupon_discount),
                "shipping_price": self.money(order.shipping_price),
                "created_at": order.created_at,
            })

        # RESPONSE
        response = {
            "period": period,
            "period_label": (f"{start_date} - {end_date}"),
            "start_date": str(start_date),
            "end_date": str(end_date),
            "financial": {
                "total_revenue": self.money(total_revenue),
                "product_sales": self.money(product_sales),
                "product_discount": self.money(product_discount),
                "coupon_discount": self.money(coupon_discount),
                "shipping_revenue": self.money(shipping_revenue),
                "pending_payment": self.money(pending_payment_amount),
                "refunded_amount": self.money(refunded_amount),
                "average_order_value": self.money(average_order_value),
            },

            "financial_change": {
                "revenue": self.percentage_change(float(total_revenue), float(previous_revenue),),
                "orders": self.percentage_change(total_orders, previous_orders,),
            },

            "orders": {
                "total": total_orders,
                "successful": successful_order_count,
                "pending": pending_order_count,
                "processing": processing_order_count,
                "shipped": shipped_order_count,
                "delivered": delivered_order_count,
                "collected": collected_order_count,
                "cancelled": cancelled_order_count,
                "fulfillment_rate": round(fulfillment_rate, 2,),
                "cancellation_rate": round(cancellation_rate, 2,),
            },

            "customers": {
                "total": total_customers,
                "new": new_customers,
                "returning": returning_customers,
                "with_orders": customers_with_orders,
            },

            "products": {
                "total": total_products,
                "published": published_products,
                "draft": draft_products,
                "low_stock": low_stock_products_count,
                "out_of_stock": out_of_stock_products_count,
            },

            "coupons": {
                "total_used": coupons_used,
                "total_discount": self.money(coupon_discount),
                "orders_using_coupon": (coupon_orders_count),
                "most_used": (
                    {
                        "code": most_used_coupon["coupon__code"],
                        "usage": most_used_coupon["usage"],
                        "discount": self.money(most_used_coupon["discount"]),
                    }
                    if most_used_coupon
                    else None
                ),
                "top_coupons": formatted_top_coupons,
            },

            "shipping": {
                "delivery_orders": delivery_orders.count(),
                "pickup_orders": pickup_orders.count(),
                "shipping_revenue": self.money(shipping_revenue),
                "delivery_shipping_revenue": self.money(delivery_shipping_revenue),
                "pickup_shipping_revenue": self.money(pickup_shipping_revenue),
            },

            "order_status": order_status,
            "monthly_revenue": monthly_revenue,
            "average_order_value": self.money(average_order_value),
            "average_order_value_change": 0,
            "customer_analytics": {
                "new_customers": new_customers,
                "returning_customers": returning_customers,
                "total_customers": total_customers,
                "customers_with_orders": (customers_with_orders),
            },

            "fulfillment": {
                "total_orders": total_orders,
                "fulfilled_orders": fulfilled_orders,
                "fulfillment_rate": round(fulfillment_rate,2,),
            },

            "recent_orders": recent_order_data,
            "top_products": formatted_top_products,
            "low_stock_products": formatted_low_stock,
        }
        return Response(response)


#  ORDER API
class OrdersView(APIView):
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    def get(self, request):
        orders = (
            Order.objects.select_related('user','shipping_address','shipping_address__state','pickup_station','pickup_station__state','payment','coupon',)
            .prefetch_related('orderitems__product','orderitems__variation',)
            .order_by('-created_at')
        )

        paginator = ProductPagination()
        page = paginator.paginate_queryset(orders, request)
        serializer = OrderSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class OrdersStatView(APIView):
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    def get(self, request):
        orders = Order.objects.select_related('shipping_address','payment').all().order_by('-created_at')
        total_orders = orders.count()
        successful_orders = orders.filter(status='Delivered').count()
        processing_orders = orders.filter(status__in=['Successful', 'Shipped']).count()
        pending_orders = orders.filter(status='Pending').count()
        cancelled_orders = orders.filter(status='Cancelled').count()

        # Current date
        now = timezone.now()

        # Start of current month
        current_month_start = now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)

        # Start of previous month
        previous_month_end = current_month_start
        previous_month_start = (current_month_start - timedelta(days=1)).replace(day=1)

        # Orders created this month
        current_month_orders = orders.filter(created_at__gte=current_month_start).count()

        # Orders created last month
        previous_month_orders = orders.filter(created_at__gte=previous_month_start,created_at__lt=previous_month_end).count()

        # Calculate percentage change
        if previous_month_orders > 0:
            order_change = ((current_month_orders - previous_month_orders) / previous_month_orders) * 100
        elif current_month_orders > 0:
            # No orders last month, but there are orders this month
            order_change = 100
        else:
            order_change = 0

        return Response({
            'total_orders': total_orders,
            'successful_orders': successful_orders,
            'processing_orders': processing_orders,
            'pending_orders': pending_orders,
            'cancelled_orders': cancelled_orders,
            'order_change': round(order_change, 2),
        })


@api_view(['GET'])
@authentication_classes([AdminCookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsTemmyAdmin])
def OrderDetailsView(request):
    orderid = request.GET.get('orderid')

    if not orderid:
        return Response(
            {'error': 'orderid is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    order = (
        Order.objects.select_related('user', 'shipping_address', 'shipping_address__state', 'shipping_address__state__zone', 'pickup_station', 'pickup_station__state', 'pickup_station__state__zone', 'payment', 'shipment',)
        .prefetch_related('orderitems__product','orderitems__variation','shipment__tracking_logs__admin','status_history__admin',)
        .filter(order_number=orderid).first()
    )

    if not order:
        return Response({'error': 'order not found'},status=status.HTTP_404_NOT_FOUND)

    # Order
    order_data = OrderSerializer(order).data

    # Order items
    order_items = order.orderitems.all()
    order_items_data = OrderItemSerializer(order_items,many=True).data

    # Shipment
    shipment_data = None
    tracking_logs_data = []
    shipment = getattr(order, 'shipment', None)

    if shipment:
        shipment_data = ShipmentSerializer(shipment).data
        tracking_logs = (shipment.tracking_logs.all().order_by('-created_at'))
        tracking_logs_data = ShipmentTrackingSerializer(tracking_logs,many=True).data

    # Order status history
    status_history = (order.status_history.all().order_by('-created_at'))
    status_history_data = OrderStatusHistorySerializer(status_history,many=True).data

    return Response({
        'order': order_data,
        'order_items': order_items_data,
        'shipment': shipment_data,
        'tracking_logs': tracking_logs_data,
        'status_history': status_history_data,
    })


@api_view(['POST'])
@authentication_classes([AdminCookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsTemmyAdmin])
def UpdateShipmentTrackingView(request):
    shipment_id = request.data.get('shipment_id')
    new_status = request.data.get('status')
    note = request.data.get('note', '').strip()

    if not shipment_id:
        return Response({'error': 'shipment_id is required'},status=status.HTTP_400_BAD_REQUEST)

    if not new_status:
        return Response({'error': 'status is required'},status=status.HTTP_400_BAD_REQUEST)

    try:
        shipment = Shipment.objects.select_related('order').get(id=shipment_id)
    except Shipment.DoesNotExist:
        return Response({'error': 'shipment not found'},status=status.HTTP_404_NOT_FOUND)

    valid_statuses = ['Processing', 'Picked_up', 'in_transit', 'At_Pickup_Station', 'Ready_for_Pickup', 'Collected', 'Out_for_Delivery', 'Delivered',]

    if new_status not in valid_statuses:
        return Response({'error': 'invalid shipment status'},status=status.HTTP_400_BAD_REQUEST)

    old_status = shipment.status
    if old_status == new_status:
        return Response({'error': f'Shipment is already {new_status}.'},status=status.HTTP_400_BAD_REQUEST)

    now = timezone.now()

    # PICKED UP
    if new_status == 'Picked_up':
        if not shipment.shipped_at:
            shipment.shipped_at = now

    # IN TRANSIT
    elif new_status == 'in_transit':
        if not shipment.shipped_at:
            shipment.shipped_at = now

    # OUT FOR DELIVERY
    elif new_status == 'Out_for_Delivery':
        if not shipment.shipped_at:
            shipment.shipped_at = now

    # DELIVERED
    elif new_status == 'Delivered':
        if not shipment.shipped_at:
            shipment.shipped_at = now

        shipment.delivered_at = now

    # COLLECTED
    elif new_status == 'Collected':
        if not shipment.shipped_at:
            shipment.shipped_at = now

        shipment.delivered_at = now

    shipment.status = new_status
    shipment.save(update_fields=['status','shipped_at','delivered_at',])

    # CREATE TRACKING LOG
    tracking = ShipmentTracking.objects.create(shipment=shipment, admin=request.user, status=new_status, note=note)

    return Response(
        {
            'message': 'Shipment tracking updated successfully',
            'shipment': ShipmentSerializer(shipment).data,
            'tracking': ShipmentTrackingSerializer(tracking).data,
        },
        status=status.HTTP_201_CREATED
    )


@api_view(["POST"])
@authentication_classes([AdminCookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsTemmyAdmin])
@transaction.atomic
def CreateShipmentView(request):
    orderid = request.data.get("orderid")
    courier_name = request.data.get("courier_name", "").strip()

    if not orderid:
        return Response({"error": "orderid is required."},status=400)

    if not courier_name:
        return Response({"error": "courier_name is required."},status=400)

    order = (
        Order.objects.select_related("user","shipping_address","pickup_station","payment","coupon",)
        .filter(order_number=orderid).first()
    )

    if not order:
        return Response({"error": "Order not found."},status=404)

    # Prevent duplicate shipment
    if hasattr(order, "shipment"):
        return Response({"error": "A shipment already exists for this order."},status=400)

    # Shipment can only be created for a successful order
    if order.status != "Successful":
        return Response(
            {
                "error": (
                    f"A shipment can only be created for a Successful order. "
                    f"Current status is {order.status}."
                )
            },
            status=400
        )

    now = timezone.now()

    # 1. Create shipment in Processing
    shipment = Shipment.objects.create(order=order,courier_name=courier_name,status="Processing",)

    # 2. Change Order: Successful -> Processing
    old_order_status = order.status
    order.status = "Processing"
    order.updated_at = now
    order.save(update_fields=["status","updated_at",])

    # 3. Create Order Status History
    order_history = OrderStatusHistory.objects.create(
        order=order,
        admin=request.user,
        old_status=old_order_status,
        new_status="Processing",
        note="Order moved to Processing when shipment was created.",
    )

    # 4. Create initial Shipment Tracking
    tracking = ShipmentTracking.objects.create(
        shipment=shipment,
        admin=request.user,
        status="Processing",
        note="Shipment created and order moved to Processing.",
    )

    # 5. Return everything
    return Response(
        {
            "message": "Shipment created and order moved to Processing.",
            "order": OrderSerializer(order).data,
            "shipment": ShipmentSerializer(shipment).data,
            "order_history": OrderStatusHistorySerializer(order_history).data,
            "tracking": ShipmentTrackingSerializer(tracking).data,
        },
        status=201,
    )


@api_view(["POST"])
@authentication_classes([AdminCookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsTemmyAdmin])
@transaction.atomic
def UpdateOrderStatusView(request):
    orderid = request.data.get("orderid")
    new_status = request.data.get("status")
    note = request.data.get("note", "").strip()

    if not orderid:
        return Response({"error": "orderid is required"}, status=400)

    if not new_status:
        return Response({"error": "status is required"}, status=400)

    order = (Order.objects.select_related("shipment", "shipping_address", "pickup_station", "payment", "user",).filter(order_number=orderid).first())

    if not order:
        return Response({"error": "Order not found."}, status=404)

    shipment = getattr(order, "shipment", None)
    is_pickup = order.delivery_method == "pickup"

    # AVAILABLE ADMIN STATUS FLOW
    if is_pickup:
        allowed_statuses = ["Processing", "Shipped", "At_Pickup_Station", "Ready_for_Pickup", "Collected", "Cancelled",]
    else:
        allowed_statuses = ["Processing","Shipped","Delivered","Cancelled",]

    if new_status not in allowed_statuses:
        return Response(
            {
                "error": "Invalid status.",
                "allowed_statuses": allowed_statuses,
            },status=400
        )

    # CANCELLED
    if new_status == "Cancelled":
        if order.status == "Cancelled":
            return Response({"error": "Order is already cancelled."},status=400)

        old_status = order.status
        order.status = "Cancelled"
        order.updated_at = timezone.now()
        order.save(update_fields=["status", "updated_at"])

        history = OrderStatusHistory.objects.create(
            order=order,
            admin=request.user,
            old_status=old_status,
            new_status="Cancelled",
            note=note,
        )

        return Response(
            {
                "message": "Order cancelled successfully.",
                "order": OrderSerializer(order).data,
                "history": OrderStatusHistorySerializer(history).data,
                "shipment": (ShipmentSerializer(shipment).data if shipment else None),
            },
            status=200
        )

    # PROCESSING
    if new_status == "Processing":
        if order.status not in ["Successful"]:
            return Response(
                {
                    "error": (
                        f"Order cannot be moved to Processing "
                        f"from {order.status}."
                    )
                },
                status=400
            )

        old_order_status = order.status
        order.status = "Processing"
        order.updated_at = timezone.now()
        order.save(update_fields=["status", "updated_at"])

        history = OrderStatusHistory.objects.create(
            order=order,
            admin=request.user,
            old_status=old_order_status,
            new_status="Processing",
            note=note,
        )

        # Shipment is updated automatically if it exists.
        if shipment:
            old_shipment_status = shipment.status
            shipment.status = "Processing"
            shipment.save(update_fields=["status"])

            if old_shipment_status != "Processing":
                ShipmentTracking.objects.create(
                    shipment=shipment,
                    admin=request.user,
                    status="Processing",
                    note=note or "Order moved to Processing.",
                )

        return Response(
            {
                "message": "Order moved to Processing.",
                "order": OrderSerializer(order).data,
                "history": OrderStatusHistorySerializer(history).data,
                "shipment": (ShipmentSerializer(shipment).data if shipment else None),
            }
        )

    # SHIPPED
    if new_status == "Shipped":
        if order.status != "Processing":
            return Response(
                {
                    "error": (
                        f"Order cannot be moved to Shipped "
                        f"from {order.status}."
                    )
                },
                status=400
            )

        if not shipment:
            return Response(
                {
                    "error": (
                        "A shipment must be created before "
                        "the order can be shipped."
                    )
                },
                status=400
            )

        old_order_status = order.status
        order.status = "Shipped"
        order.updated_at = timezone.now()
        order.save(update_fields=["status", "updated_at"])

        history = OrderStatusHistory.objects.create(
            order=order,
            admin=request.user,
            old_status=old_order_status,
            new_status="Shipped",
            note=note,
        )

        old_shipment_status = shipment.status
        shipment.status = "in_transit"
        if not shipment.shipped_at:
            shipment.shipped_at = timezone.now()

        shipment.save(update_fields=["status","shipped_at",])

        if old_shipment_status != "in_transit":
            ShipmentTracking.objects.create(
                shipment=shipment,
                admin=request.user,
                status="in_transit",
                note=note or "Shipment is now in transit.",
            )

        return Response(
            {
                "message": "Order shipped successfully.",
                "order": OrderSerializer(order).data,
                "history": OrderStatusHistorySerializer(history).data,
                "shipment": ShipmentSerializer(shipment).data,
            }
        )

    # HOME DELIVERY → DELIVERED
    if new_status == "Delivered":
        if is_pickup:
            return Response(
                {
                    "error": (
                        "Pickup orders should be completed "
                        "using the Collected status."
                    )
                },
                status=400
            )

        if order.status != "Shipped":
            return Response(
                {
                    "error": (
                        f"Order cannot be delivered "
                        f"from {order.status}."
                    )
                },
                status=400
            )

        if not shipment:
            return Response(
                {"error": "A shipment is required before delivery."}, status=400
            )

        old_order_status = order.status
        order.status = "Delivered"
        order.updated_at = timezone.now()
        order.save(update_fields=["status", "updated_at"])

        history = OrderStatusHistory.objects.create(
            order=order,
            admin=request.user,
            old_status=old_order_status,
            new_status="Delivered",
            note=note,
        )

        shipment.status = "Delivered"

        if not shipment.shipped_at:
            shipment.shipped_at = timezone.now()

        shipment.delivered_at = timezone.now()
        shipment.save(update_fields=["status","shipped_at","delivered_at",])

        ShipmentTracking.objects.create(
            shipment=shipment,
            admin=request.user,
            status="Delivered",
            note=note or "Shipment delivered successfully.",
        )

        return Response(
            {
                "message": "Order delivered successfully.",
                "order": OrderSerializer(order).data,
                "history": OrderStatusHistorySerializer(history).data,
                "shipment": ShipmentSerializer(shipment).data,
            }
        )

    # PICKUP → AT PICKUP STATION
    if new_status == "At_Pickup_Station":
        if not is_pickup:
            return Response(
                {
                    "error": (
                        "At_Pickup_Station is only available "
                        "for pickup orders."
                    )
                },
                status=400
            )

        if order.status != "Shipped":
            return Response(
                {
                    "error": (
                        "The order must be Shipped before "
                        "it can arrive at the pickup station."
                    )
                },
                status=400
            )

        if not shipment:
            return Response(
                {"error": "A shipment is required."}, status=400
            )

        if shipment.status != "in_transit":
            return Response(
                {
                    "error": (
                        f"Shipment cannot move to the pickup station "
                        f"from {shipment.status}."
                    )
                },
                status=400
            )

        shipment.status = "At_Pickup_Station"
        old_order_status= order.status
        order.status= 'At_Pickup_Station'
        order.updated_at = timezone.now()
        order.save(update_fields=['status','updated_at'])
        shipment.save(update_fields=["status"])


        history = OrderStatusHistory.objects.create(
            order=order,
            admin=request.user,
            old_status=old_order_status,
            new_status="At_Pickup_Station",
            note=note,
        )

        tracking = ShipmentTracking.objects.create(
            shipment=shipment,
            admin=request.user,
            status="At_Pickup_Station",
            note=note or "Shipment has arrived at the pickup station.",
        )

        return Response(
            {
                "message": "Shipment marked as arrived at pickup station.",
                "order": OrderSerializer(order).data,
                "history": None,
                "shipment": ShipmentSerializer(shipment).data,
                "tracking": {
                    "id": tracking.id,
                    "status": tracking.status,
                    "note": tracking.note,
                    "created_at": tracking.created_at,
                },
            }
        )

    # PICKUP → READY FOR PICKUP
    if new_status == "Ready_for_Pickup":
        if not is_pickup:
            return Response(
                {
                    "error": (
                        "Ready_for_Pickup is only available "
                        "for pickup orders."
                    )
                },
                status=400
            )

        if not shipment:
            return Response(
                {"error": "A shipment is required."},
                status=400
            )

        if shipment.status != "At_Pickup_Station":
            return Response(
                {
                    "error": (
                        "Shipment must first arrive at the "
                        "pickup station."
                    )
                },
                status=400
            )

        shipment.status = "Ready_for_Pickup"
        old_order_status = order.status
        order.status = 'Ready_for_Pickup'
        order.updated_at = timezone.now()
        order.save(update_fields=['status', 'updated_at'])

        history = OrderStatusHistory.objects.create(
            order=order,
            admin=request.user,
            old_status=old_order_status,
            new_status="Ready_for_Pickup",
            note=note,
        )
        shipment.save(update_fields=["status"])

        tracking = ShipmentTracking.objects.create(
            shipment=shipment,
            admin=request.user,
            status="Ready_for_Pickup",
            note=note or "Order is ready for pickup.",
        )

        return Response(
            {
                "message": "Order is now ready for pickup.",
                "order": OrderSerializer(order).data,
                "history": None,
                "shipment": ShipmentSerializer(shipment).data,
                "tracking": {
                    "id": tracking.id,
                    "status": tracking.status,
                    "note": tracking.note,
                    "created_at": tracking.created_at,
                },
            }
        )

    # PICKUP → COLLECTED
    if new_status == "Collected":
        if not is_pickup:
            return Response(
                {
                    "error": (
                        "Collected is only available "
                        "for pickup orders."
                    )
                },
                status=400
            )

        if not shipment:
            return Response(
                {"error": "A shipment is required."},
                status=400
            )

        if shipment.status != "Ready_for_Pickup":
            return Response(
                {
                    "error": (
                        "Order must be Ready_for_Pickup "
                        "before it can be collected."
                    )
                },
                status=400
            )

        old_order_status = order.status
        order.status = "Collected"
        order.updated_at = timezone.now()
        order.save(update_fields=["status", "updated_at"])

        history = OrderStatusHistory.objects.create(
            order=order,
            admin=request.user,
            old_status=old_order_status,
            new_status="Collected",
            note=note,
        )
        

        shipment.status = "Collected"
        shipment.save(update_fields=["status"])

        tracking = ShipmentTracking.objects.create(
            shipment=shipment,
            admin=request.user,
            status="Collected",
            note=note or "Order has been collected by the customer.",
        )

        return Response(
            {
                "message": "Order marked as collected.",
                "order": OrderSerializer(order).data,
                "history": None,
                "shipment": ShipmentSerializer(shipment).data,
                "tracking": {
                    "id": tracking.id,
                    "status": tracking.status,
                    "note": tracking.note,
                    "created_at": tracking.created_at,
                },
            }
        )

    return Response(
        {"error": "Unable to update order status."},
        status=400
    )


#  PRODUCT API
class InventoryStatView(APIView):
    permission_classes = [IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]
    LOW_STOCK_THRESHOLD = 5

    def get(self, request):
        products = Product.objects.annotate(
            variation_count=Count('variations',distinct=True),
            variation_stock=Coalesce(Sum('variations__stock'), Value(0),
                output_field=IntegerField()
            ),
        ).annotate(
            total_inventory=Case(
                When(variation_count__gt=0, then=F('variation_stock')),
                default=F('stock'),
                output_field=IntegerField()
            )
        )

        total_products = products.count()

        in_stock = products.filter(total_inventory__gt=self.LOW_STOCK_THRESHOLD).count()
        low_stock = products.filter(total_inventory__gt=0,total_inventory__lte=self.LOW_STOCK_THRESHOLD).count()
        out_of_stock = products.filter(total_inventory=0).count()
        return Response({
            "total_products": total_products,
            "in_stock": in_stock,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
        })


class InventoryProductPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50


class InventoryProductListView(APIView):
    permission_classes = [IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]
    LOW_STOCK_THRESHOLD = 5

    def get(self, request):
        search = request.GET.get("search", "").strip()
        status = request.GET.get("status", "").strip().lower()
        category = request.GET.get("category", "").strip()

        products = Product.objects.select_related("category", "brand",
        ).prefetch_related("variations__color", "variations__size",
        ).annotate(
            variation_count=Count("variations",distinct=True,),
            variation_stock=Coalesce(Sum("variations__stock"), Value(0),
                output_field=IntegerField(),
            ),
        ).annotate(
            total_inventory=Case(
                When( variation_count__gt=0, then=F("variation_stock"),),
                default=F("stock"),
                output_field=IntegerField(),
            )
        )

        # SEARCH
        if search:
            products = products.filter(
                Q(name__icontains=search)
                | Q(slug__icontains=search)
                | Q(category__name__icontains=search)
                | Q(brand__name__icontains=search)
            )

        # CATEGORY
        if category:
            products = products.filter(category__slug=category)

        # STATUS
        if status == "in_stock":
            products = products.filter(total_inventory__gt=self.LOW_STOCK_THRESHOLD)

        elif status == "low_stock":
            products = products.filter(total_inventory__gt=0, total_inventory__lte=self.LOW_STOCK_THRESHOLD,)

        elif status == "out_of_stock":
            products = products.filter(total_inventory=0)

        products = products.order_by("-created_at")

        # PAGINATION
        paginator = InventoryProductPagination()
        page = paginator.paginate_queryset(products,request,)

        data = []
        for product in page:
            variations = []
            for variation in product.variations.all():
                variation_name = []
                if variation.color:
                    variation_name.append(variation.color.name)

                if variation.size:
                    variation_name.append(variation.size.name)

                variations.append({
                    "id": variation.id,
                    "name": " / ".join(variation_name),
                    "color": (
                        variation.color.name
                        if variation.color
                        else None
                    ),
                    "size": (
                        variation.size.name
                        if variation.size
                        else None
                    ),
                    "stock": variation.stock,
                    "is_active": variation.is_active,
                })

            total_stock = product.total_inventory

            if total_stock == 0:
                product_status = "out_of_stock"

            elif total_stock <= self.LOW_STOCK_THRESHOLD:
                product_status = "low_stock"

            else:
                product_status = "in_stock"

            data.append({
                "id": product.id,
                "name": product.name,
                "slug": product.slug,
                "price": product.price,
                "category": {
                    "id": product.category.id,
                    "name": product.category.name,
                    "slug": product.category.slug,
                } if product.category else None,

                "brand": {
                    "id": product.brand.id,
                    "name": product.brand.name,
                } if product.brand else None,

                "stock": product.stock,
                "total_stock": total_stock,

                "has_variations": (product.variation_count > 0),
                "variations": variations,
                "status": product_status,
                "is_available": product.is_available,
                "image": (
                    product.image.url
                    if product.image
                    else None
                ),

                "created_at": product.created_at,
                "modified_date": product.modified_date,
            })

        return paginator.get_paginated_response(data)


class InventoryProductStockUpdateView(APIView):
    permission_classes = [IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    @transaction.atomic
    def patch(self, request, product_id):
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({"detail": "Product not found."},status=status.HTTP_404_NOT_FOUND,)

        variations = request.data.get("variations")
        product_stock = request.data.get("stock")

        # PRODUCT WITHOUT VARIATIONS
        if not product.variations.exists():
            if product_stock is None:
                return Response({"detail": "Stock is required."},status=status.HTTP_400_BAD_REQUEST,)

            try:
                product_stock = int(product_stock)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "Stock must be a valid number."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if product_stock < 0:
                return Response(
                    {"detail": "Stock cannot be negative."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            product.stock = product_stock
            product.save(update_fields=["stock", "modified_date"])

            return Response({
                "message": "Product stock updated successfully.",
                "product_id": product.id,
                "stock": product.stock,
            })

        # PRODUCT WITH VARIATIONS
        if not isinstance(variations, list):
            return Response({"detail": "Variations must be a list."}, status=status.HTTP_400_BAD_REQUEST,)

        updated_variations = []
        for item in variations:
            variation_id = item.get("id")
            stock = item.get("stock")

            if variation_id is None or stock is None:
                continue

            try:
                stock = int(stock)
            except (TypeError, ValueError):
                return Response(
                    {
                        "detail": (
                            f"Invalid stock for variation "
                            f"{variation_id}."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if stock < 0:
                return Response( {"detail": "Stock cannot be negative."}, status=status.HTTP_400_BAD_REQUEST,)

            try:
                variation = Variation.objects.get( id=variation_id, product=product,)
            except Variation.DoesNotExist:
                return Response(
                    {
                        "detail": (
                            f"Variation {variation_id} "
                            "does not belong to this product."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            variation.stock = stock
            variation.save()

            updated_variations.append({
                "id": variation.id,
                "stock": variation.stock,
                "is_active": variation.is_active,
            })

        return Response({
            "message": "Variation stock updated successfully.",
            "product_id": product.id,
            "variations": updated_variations,
        })


class InventoryProductStockView(APIView):
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTemmyAdmin]

    @transaction.atomic
    def patch(self, request, product_id):
        try:
            product = (Product.objects.select_for_update().prefetch_related("variations").get(id=product_id))
        except Product.DoesNotExist:
            return Response(
                {
                    "detail": "Product not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        variations = list(product.variations.all())

        # PRODUCT WITHOUT VARIATIONS
        if not variations:
            action = request.data.get("action")
            quantity = request.data.get("quantity")

            if action not in ["add", "subtract"]:
                return Response(
                    {
                        "detail": "Action must be either 'add' or 'subtract'."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                quantity = int(quantity)
            except (TypeError, ValueError):
                return Response(
                    {
                        "detail": "Quantity must be a valid number."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            if quantity < 0:
                return Response(
                    {
                        "detail": "Quantity cannot be negative."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            old_stock = product.stock

            if action == "add":
                product.stock += quantity

            elif action == "subtract":
                if quantity > product.stock:
                    return Response(
                        {
                            "detail": (
                                f"Cannot subtract {quantity}. "
                                f"Only {product.stock} items are in stock."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                product.stock -= quantity

            product.save(update_fields=["stock", "modified_date"])
            return Response(
                {
                    "detail": "Product stock updated successfully.",
                    "product": {
                        "id": product.id,
                        "name": product.name,
                        "stock": product.stock,
                        "total_stock": product.total_stock,
                    },
                    "change": {
                        "action": action,
                        "quantity": quantity,
                        "old_stock": old_stock,
                        "new_stock": product.stock,
                    },
                },
                status=status.HTTP_200_OK
            )

        # PRODUCT WITH VARIATIONS
        variation_data = request.data.get("variations")
        if not isinstance(variation_data, list):
            return Response({"detail": "Variations must be a list."}, status=status.HTTP_400_BAD_REQUEST)

        updated_variations = []
        for item in variation_data:
            variation_id = item.get("id")
            action = item.get("action")
            quantity = item.get("quantity")

            if not variation_id:
                return Response({"detail": "Variation ID is required."}, status=status.HTTP_400_BAD_REQUEST)

            if action not in ["add", "subtract"]:
                return Response(
                    {
                        "detail": (
                            f"Invalid action for variation "
                            f"{variation_id}."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                quantity = int(quantity)
            except (TypeError, ValueError):
                return Response(
                    {
                        "detail": (
                            f"Quantity for variation "
                            f"{variation_id} must be a valid number."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            if quantity < 0:
                return Response(
                    {
                        "detail": (
                            f"Quantity for variation "
                            f"{variation_id} cannot be negative."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                variation = next(
                    v for v in variations
                    if v.id == int(variation_id)
                )
            except (StopIteration, ValueError):
                return Response(
                    {
                        "detail": (
                            f"Variation {variation_id} "
                            f"does not belong to this product."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            old_stock = variation.stock

            if action == "add":
                variation.stock += quantity

            elif action == "subtract":
                if quantity > variation.stock:
                    return Response(
                        {
                            "detail": (
                                f"Cannot subtract {quantity} from "
                                f"variation {variation_id}. "
                                f"Only {variation.stock} items are in stock."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                variation.stock -= quantity

            # Variation.save() automatically updates is_active
            variation.save()

            updated_variations.append(
                {
                    "id": variation.id,
                    "stock": variation.stock,
                    "is_active": variation.is_active,
                    "action": action,
                    "quantity": quantity,
                    "old_stock": old_stock,
                    "new_stock": variation.stock,
                }
            )

        # Product.stock is not the source of truth when
        # variations exist. The total comes from Product.total_stock.
        product.refresh_from_db()

        return Response(
            {
                "detail": "Variation stock updated successfully.",
                "product": {
                    "id": product.id,
                    "name": product.name,
                    "stock": product.stock,
                    "total_stock": product.total_stock,
                },
                "variations": updated_variations,
            },
            status=status.HTTP_200_OK
        )


class AdminProductOptionsView(APIView):
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTemmyAdmin]

    def get(self, request):
        brands = Brand.objects.all().order_by("name")
        colors = Color.objects.all().order_by("name")
        sizes = Size.objects.all().order_by("name")

        return Response({
            "brands": AdminBrandSerializer(brands,many=True).data,
            "colors": AdminColorSerializer(colors,many=True).data,
            "sizes": AdminSizeSerializer(sizes,many=True).data,
        })


class AdminProductCategoryListView(APIView):
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTemmyAdmin]

    def get(self, request):
        categories = (Category.objects.filter(parent=None, active=True).prefetch_related("subcategories").order_by("name"))
        serializer = AdminCategoryTreeSerializer(categories,many=True)
        return Response(serializer.data)


class AdminProductCreateView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser,FormParser,]

    def post(self, request):
        # Normal product fields
        data = {
            "name": request.data.get("name"),
            "description": request.data.get("description"),
            "price": request.data.get("price"),
            "discount": request.data.get("discount"),
            "stock": request.data.get("stock"),
            "is_available": request.data.get("is_available"),
            "brand": request.data.get("brand"),
            "category": request.data.get("category"),
        }

        # MAIN PRODUCT IMAGE
        # Serializer expects: image
        main_image = request.FILES.get("image")
        if main_image:
            data["image"] = main_image

        # GALLERY IMAGES
        # Serializer expects: gallery
        gallery_images = request.FILES.getlist("gallery")
        if gallery_images:
            data["gallery"] = gallery_images

        # VARIATIONS
        # We support JSON sent from frontend
        variations = request.data.get("variations")
        if variations:
            try:
                data["variations"] = json.loads(variations)

            except (json.JSONDecodeError, TypeError):
                return Response(
                    {
                        "variations": ["Invalid variations data."]
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # SERIALIZER
        serializer = AdminProductCreateSerializer(data=data,context={"request": request,},)
        if serializer.is_valid():
            product = serializer.save()
            return Response(
                AdminProductCreateSerializer(product,context={"request": request,},).data,
                status=status.HTTP_201_CREATED,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


class AdminProductDetailView(APIView):
    permission_classes = [IsAuthenticated,IsTemmyAdmin,]
    authentication_classes = [AdminCookieJWTAuthentication,]

    def get(self, request, product_id):
        product = (Product.objects.select_related("category","brand",)
            .prefetch_related("images","variations__color","variations__size",)
            .filter(slug=product_id)
            .first()
        )

        if not product:
            return Response({"error": "Product not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AdminProductDetailSerializer(product)
        return Response(serializer.data,status=status.HTTP_200_OK,)

    def patch(self, request, product_id):
        product = (Product.objects.filter(slug=product_id).first())

        if not product:
            return Response({"error": "Product not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AdminProductUpdateSerializer(product,data=request.data,partial=True,)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated_product = serializer.save()

        # Return the same detail structure
        # used by the GET endpoint

        updated_product = (Product.objects.select_related("category","brand",)
            .prefetch_related("images","variations__color","variations__size",)
            .get(pk=updated_product.pk)
        )

        response_serializer = (
            AdminProductDetailSerializer(updated_product)
        )

        return Response(
            {
                "message": "Product updated successfully.",
                "product": response_serializer.data,
            },
            status=status.HTTP_200_OK,
        )



#  COUPON API
class AdminCouponStatsView(APIView):
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    def get(self, request):
        now = timezone.now()

        total_coupons = Coupon.objects.count()

        active_coupons = Coupon.objects.filter(
            is_active=True
        ).filter(
            Q(start_date__isnull=True) | Q(start_date__lte=now)
        ).filter(
            Q(expiry_date__isnull=True) | Q(expiry_date__gte=now)
        ).filter(
            Q(usage_limit__isnull=True) | Q(used_count__lt=models.F("usage_limit"))
        ).count()

        total_redemptions = (Order.objects.filter(coupon__isnull=False, status__in=SUCCESSFUL_ORDER_STATUSES,)
            .aggregate(total=Sum("coupon_discount"))
        )

        # Number of successful orders that used a coupon
        redemption_count = (Order.objects.filter(coupon__isnull=False, status__in=SUCCESSFUL_ORDER_STATUSES,).count())

        # Total amount customers actually saved
        discount_given = total_redemptions["total"] or 0

        return Response(
            {
                "total_coupons": total_coupons,
                "active_coupons": active_coupons,
                "total_redemptions": redemption_count,
                "discount_given": discount_given,
            },
            status=200,
        )


class AdminCouponListView(APIView):
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    def get(self, request):
        coupons = Coupon.objects.all().order_by("-created_at")
        search = request.GET.get("search", "").strip()
        coupon_status = request.GET.get("status", "").strip().lower()

        if search:
            coupons = coupons.filter(Q(code__icontains=search) | Q(discount_type__icontains=search))

        now = timezone.now()
        if coupon_status == "active":
            coupons = coupons.filter(
                is_active=True
            ).filter(
                Q(start_date__isnull=True) | Q(start_date__lte=now)
            ).filter(
                Q(expiry_date__isnull=True) | Q(expiry_date__gte=now)
            ).filter(
                Q(usage_limit__isnull=True) | Q(used_count__lt=models.F("usage_limit"))
            )

        elif coupon_status == "inactive":
            coupons = coupons.filter(is_active=False)

        elif coupon_status == "scheduled":
            coupons = coupons.filter(is_active=True, start_date__gt=now,)

        elif coupon_status == "expired":
            coupons = coupons.filter(expiry_date__lt=now)

        elif coupon_status == "used_up":
            coupons = coupons.filter(
                usage_limit__isnull=False,
                used_count__gte=models.F("usage_limit"),
            )

        paginator = PageNumberPagination()
        paginator.page_size = 10
        page = paginator.paginate_queryset(coupons,request,)
        serializer = AdminCouponSerializer(page,many=True,)
        return paginator.get_paginated_response(serializer.data)


    def post(self, request):
        serializer = AdminCouponSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors,status=400,)

        coupon = serializer.save()
        return Response(
            {
                "message": "Coupon created successfully.",
                "coupon": AdminCouponSerializer(coupon).data,
            },
            status=201,
        )


class AdminCouponDetailView(APIView):
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    def get_object(self, coupon_id):
        return Coupon.objects.filter(id=coupon_id).first()

    def get(self, request, coupon_id):
        coupon = self.get_object(coupon_id)

        if not coupon:
            return Response(
                {"error": "Coupon not found."},
                status=404,
            )

        serializer = AdminCouponSerializer(coupon)
        return Response(serializer.data,status=200,)

    def patch(self, request, coupon_id):
        coupon = self.get_object(coupon_id)

        if not coupon:
            return Response({"error": "Coupon not found."},status=404,)

        serializer = AdminCouponSerializer(coupon,data=request.data,partial=True,)

        if not serializer.is_valid():
            return Response(serializer.errors,status=400,)

        coupon = serializer.save()
        return Response(
            {
                "message": "Coupon updated successfully.",
                "coupon": AdminCouponSerializer(coupon).data,
            },
            status=200,
        )


    def delete(self, request, coupon_id):
        coupon = self.get_object(coupon_id)

        if not coupon:
            return Response({"error": "Coupon not found."},status=404,)

        coupon.is_active = False
        coupon.save(
            update_fields=["is_active", "updated_at",]
        )

        return Response(
            {"message": "Coupon deactivated successfully."},
            status=200,
        )


#  REVIEW API
class AdminReviewListView(generics.ListAPIView):
    serializer_class = AdminReviewSerializer
    pagination_class = AdminReviewPagination
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated,IsTemmyAdmin,]

    def get_queryset(self):
        queryset = ProductReview.objects.select_related("user","product",).order_by("-created_at")
        search = self.request.query_params.get("search", "").strip()
        review_status = self.request.query_params.get("status", "all").lower()
        rating = self.request.query_params.get("rating", "all")

        if search:
            queryset = queryset.filter(
                Q(user__name__icontains=search)
                | Q(user__username__icontains=search)
                | Q(user__email__icontains=search)
                | Q(product__name__icontains=search)
                | Q(comment__icontains=search)
            ).distinct()

        if review_status == "published":
            queryset = queryset.filter(is_approved=True)
        elif review_status == "hidden":
            queryset = queryset.filter(is_approved=False)
        elif review_status not in ("all", ""):
            return queryset.none()

        if rating != "all":
            try:
                rating_value = int(rating)
            except (TypeError, ValueError):
                return queryset.none()

            if rating_value not in range(1, 6):
                return queryset.none()

            queryset = queryset.filter(rating=rating_value)
        return queryset


class AdminReviewStatsView(APIView):
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated,IsTemmyAdmin,]

    def get(self, request):
        stats = ProductReview.objects.aggregate(
            total_reviews=Count("id"),
            average_rating=Avg("rating"),
            five_star_reviews=Count("id", filter=Q(rating=5),),
            published_reviews=Count("id", filter=Q(is_approved=True),),
            hidden_reviews=Count("id", filter=Q(is_approved=False),),
        )

        total = stats["total_reviews"] or 0
        five_star = stats["five_star_reviews"] or 0

        return Response({
            "total_reviews": total,
            "average_rating": round(stats["average_rating"] or 0, 2),
            "pending_reviews": 0,
            "published_reviews": stats["published_reviews"] or 0,
            "hidden_reviews": stats["hidden_reviews"] or 0,
            "five_star_reviews": five_star,
            "five_star_percentage": round(five_star / total * 100, 1) if total else 0,
        })


class AdminReviewDetailView(generics.UpdateAPIView):
    queryset = ProductReview.objects.all()
    serializer_class = AdminReviewStatusSerializer
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated,IsTemmyAdmin,]
    http_method_names = ["patch", "options", "head"]


#  NEWSLETTER API
class AdminNewsLetterStatsView(APIView):
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated,IsTemmyAdmin,]

    def get(self, request):
        subscribers = NewsletterSubscriber.objects.aggregate(
            total_subscribers=Count('id'),
            total_active_subscribers=Count('id', filter=Q(status=NewsletterSubscriber.Status.SUBSCRIBED)),
            total_unsubscribers=Count('id', filter=Q(status=NewsletterSubscriber.Status.UNSUBSCRIBED)),   
        )

        newslettercampaign = NewsletterCampaign.objects.aggregate(
            total_campaigns=Count('id'),
            campaigns_sent=Count('id', filter=Q(status=NewsletterCampaign.Status.SENT))
        )
        return Response({
            'total_subscribers': subscribers['total_subscribers'] or 0,
            'active_subscribers': subscribers['total_active_subscribers'] or 0,
            'unsubscribers': subscribers['total_unsubscribers'] or 0,
            'total_campaigns': newslettercampaign['total_campaigns'] or 0,
            "campaigns_sent": newslettercampaign['campaigns_sent'] or 0,
            'emails_delivered': NewsletterRecipient.objects.filter(status=NewsletterRecipient.Status.SENT).count()
        }, status=200)


class AdminNewsletterSubscriberListView(APIView):
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    def get(self, request):
        subscribers = NewsletterSubscriber.objects.all()
        search = request.GET.get("search", "").strip()
        subscribers_status = request.GET.get("status", "").strip().lower()

        if search:
            subscribers = subscribers.filter(
                Q(email__icontains=search) | Q(user__username__icontains=search)
            )

        if subscribers_status == "subscribed":
            subscribers = subscribers.filter(status=NewsletterSubscriber.Status.SUBSCRIBED)

        elif subscribers_status == "unsubscribed":
            subscribers = subscribers.filter(status=NewsletterSubscriber.Status.UNSUBSCRIBED)

        paginator = PageNumberPagination()
        paginator.page_size = 10
        page = paginator.paginate_queryset(subscribers, request)
        serializer = NewsletterSubscriberSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminNewsletterCampaignListCreateView(generics.ListCreateAPIView):
    serializer_class = NewsletterCampaignSerializer
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    def get_queryset(self):
        queryset = (
            NewsletterCampaign.objects.select_related("template", "created_by").prefetch_related(
                Prefetch("campaign_recipients", queryset=NewsletterRecipient.objects.order_by("created_at"), to_attr="prefetched_recipients",)
            ).order_by("-created_at")
        )

        search = self.request.query_params.get("search", "").strip()

        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(subject__icontains=search)
            )

        campaign_status = self.request.query_params.get("status")
        if campaign_status:
            queryset = queryset.filter(status=campaign_status)

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AdminNewsletterCampaignDetailView(generics.RetrieveAPIView):
    serializer_class = NewsletterCampaignSerializer
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]
    queryset = NewsletterCampaign.objects.select_related("template","created_by",)


class AdminNewsletterCampaignSendView(APIView):
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    def post(self, request, pk):
        with transaction.atomic():
            campaign = get_object_or_404(NewsletterCampaign.objects.select_for_update(), pk=pk,)
            allowed_statuses = {NewsletterCampaign.Status.DRAFT,NewsletterCampaign.Status.FAILED,}

            if campaign.status not in allowed_statuses:
                return Response(
                    {
                        "detail": (
                            "Only draft or failed campaigns can be sent. "
                            f"Current status: {campaign.status}."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not campaign.blocks:
                return Response(
                    {"detail": "The campaign has no content blocks."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            audience = request.data.get("audience",campaign.audience,)
            valid_audiences = {
                NewsletterCampaign.Audience.ALL,
                NewsletterCampaign.Audience.SELECTED,
            }

            if audience not in valid_audiences:
                return Response(
                    {"detail": "Invalid campaign audience."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            subscriber_ids = request.data.get("subscriber_ids")

            if audience == NewsletterCampaign.Audience.SELECTED:
                if subscriber_ids is not None:
                    if (not isinstance(subscriber_ids, list)or not subscriber_ids):
                        return Response(
                            {
                                "detail": (
                                    "Select at least one subscriber."
                                )
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    selected = NewsletterSubscriber.objects.filter(
                        pk__in=subscriber_ids,
                        status=NewsletterSubscriber.Status.SUBSCRIBED,
                    )

                    selected_ids = list(selected.values_list("pk", flat=True))
                    if len(set(subscriber_ids)) != len(selected_ids):
                        return Response(
                            {
                                "detail": (
                                    "One or more selected subscribers "
                                    "do not exist or are unsubscribed."
                                )
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    campaign.selected_subscribers.set(selected_ids)

                elif not campaign.selected_subscribers.filter(status=NewsletterSubscriber.Status.SUBSCRIBED).exists():
                    return Response(
                        {
                            "detail": (
                                "Select at least one subscribed "
                                "recipient before sending."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            else:
                campaign.selected_subscribers.clear()

            campaign.audience = audience
            campaign.status = NewsletterCampaign.Status.QUEUED
            campaign.queued_at = timezone.now()

            campaign.save(update_fields=[ "audience", "status", "queued_at",])
            campaign_id = str(campaign.pk)

        try:
            task = send_newsletter_campaign.delay(campaign_id)

        except Exception:
            NewsletterCampaign.objects.filter(
                pk=campaign_id,
                status=NewsletterCampaign.Status.QUEUED,
            ).update(status=NewsletterCampaign.Status.FAILED)

            return Response(
                {"detail": "Could not queue the campaign for sending."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "message": "Campaign queued for sending.",
                "campaign_id": campaign_id,
                "task_id": task.id,
                "status": NewsletterCampaign.Status.QUEUED,
                "audience": audience,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class AdminNewsletterCampaignRecipientsView(generics.ListAPIView):
    serializer_class = NewsletterRecipientSerializer
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    def get_queryset(self):
        campaign = get_object_or_404(NewsletterCampaign,pk=self.kwargs["pk"],)
        queryset = NewsletterRecipient.objects.filter(campaign=campaign).order_by("-sent_at", "email")
        recipient_status = self.request.query_params.get("status")

        if recipient_status:
            queryset = queryset.filter(status=recipient_status)

        return queryset


class AdminNewsletterTemplateListCreateView(generics.ListCreateAPIView):
    serializer_class = NewsletterTemplateSerializer
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    queryset = NewsletterTemplate.objects.select_related("created_by").all()
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AdminNewsletterTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = NewsletterTemplateSerializer
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    authentication_classes = [AdminCookieJWTAuthentication]

    queryset = NewsletterTemplate.objects.select_related("created_by").all()


class AdminNewsletterStatsView(APIView):
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTemmyAdmin]

    def get(self, request, *args, **kwargs):
        # 1. Subscriber statistics
        subscriber_stats = NewsletterSubscriber.objects.aggregate(
            total=Count("id"),
            subscribed=Count("id",filter=Q(status=NewsletterSubscriber.Status.SUBSCRIBED),),
            unsubscribed=Count("id",filter=Q(status=NewsletterSubscriber.Status.UNSUBSCRIBED),),
        )

        # 2. Welcome email statistics
        welcome_stats = NewsletterSubscriber.objects.aggregate(
            total=Count("id"),
            sent=Count("id",filter=Q(welcome_email_status=(NewsletterSubscriber.WelcomeEmailStatus.SENT)),),
            failed=Count("id",filter=Q(welcome_email_status=(NewsletterSubscriber.WelcomeEmailStatus.FAILED)),),
            pending=Count("id",filter=Q(welcome_email_status=(NewsletterSubscriber.WelcomeEmailStatus.NOT_SENT)),),
            sending=Count("id",filter=Q(welcome_email_status=(NewsletterSubscriber.WelcomeEmailStatus.SENDING)),),
        )

        # 3. Campaign statistics
        campaign_stats = NewsletterCampaign.objects.aggregate(
            total=Count("id"),
            draft=Count("id",filter=Q(status=NewsletterCampaign.Status.DRAFT),),
            queued=Count("id",filter=Q(status=NewsletterCampaign.Status.QUEUED),),
            sending=Count("id",filter=Q(status=NewsletterCampaign.Status.SENDING),),
            sent=Count("id",filter=Q(status=NewsletterCampaign.Status.SENT),),
            failed=Count("id",filter=Q(status=NewsletterCampaign.Status.FAILED),),
            cancelled=Count("id",filter=Q(status=NewsletterCampaign.Status.CANCELLED),),
        )

        # 4. Individual campaign-recipient email statistics
        recipient_stats = NewsletterRecipient.objects.aggregate(
            total=Count("id"),
            pending=Count("id",filter=Q(status=NewsletterRecipient.Status.PENDING),),
            sending=Count("id",filter=Q(status=NewsletterRecipient.Status.SENDING),),
            sent=Count("id",filter=Q(status=NewsletterRecipient.Status.SENT),),
            delivered=Count("id",filter=Q(status=NewsletterRecipient.Status.DELIVERED),),
            failed=Count("id",filter=Q(status=NewsletterRecipient.Status.FAILED),),
            bounced=Count("id",filter=Q(status=NewsletterRecipient.Status.BOUNCED),),
            complained=Count("id",filter=Q(status=NewsletterRecipient.Status.COMPLAINED),),
            opened=Count("id",filter=Q(opened_at__isnull=False),),
            clicked=Count("id",filter=Q(clicked_at__isnull=False),),
        )

        # A recipient is considered successful if the email was sent
        # or confirmed as delivered.
        recipient_stats["successful"] = (recipient_stats["sent"] + recipient_stats["delivered"])
        return Response({
            "subscribers": subscriber_stats,
            "welcome_emails": welcome_stats,
            "campaigns": campaign_stats,
            "campaign_emails": recipient_stats,
        })





class AdminCategoryPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminCategoryListCreateView(generics.ListCreateAPIView):
    serializer_class = AdminCategorySerializer
    pagination_class = AdminCategoryPagination
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTemmyAdmin]

    def get_queryset(self):
        queryset = Category.objects.select_related("parent").annotate(
            direct_product_count=Count("products",distinct=True,)
        )

        search = self.request.query_params.get("search", "").strip()
        status_filter = self.request.query_params.get("status")
        category_type = self.request.query_params.get("type")
        empty = self.request.query_params.get("empty")
        parent_id = self.request.query_params.get("parent")
        ordering = self.request.query_params.get("ordering", "-created_at")

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(slug__icontains=search)
                | Q(description__icontains=search)
            )

        if status_filter == "active":
            queryset = queryset.filter(active=True)
        elif status_filter == "inactive":
            queryset = queryset.filter(active=False)

        if category_type == "parent":
            queryset = queryset.filter(parent__isnull=True)
        elif category_type == "child":
            queryset = queryset.filter(parent__isnull=False)

        if parent_id:
            queryset = queryset.filter(parent_id=parent_id)

        if empty == "true":
            queryset = queryset.filter(products__isnull=True)
        elif empty == "false":
            queryset = queryset.filter(products__isnull=False)

        allowed_orderings = {
            "name", "-name",
            "created_at", "-created_at",
            "modified_date", "-modified_date",
            "direct_product_count", "-direct_product_count",
        }

        if ordering in allowed_orderings:
            queryset = queryset.order_by(ordering)

        return queryset.distinct()


class AdminCategoryStatsView(APIView):
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTemmyAdmin]

    def get(self, request):
        categories = Category.objects.all()
        total = categories.count()
        active = categories.filter(active=True).count()
        inactive = categories.filter(active=False).count()
        parents = categories.filter(parent__isnull=True).count()
        children = categories.filter(parent__isnull=False).count()
        assigned_products = Product.objects.values("pk").distinct().count()
        empty_categories = categories.filter(products__isnull=True).count()
        categories_with_products = 0

        for category in categories.only("id", "tree_id", "lft", "rght").iterator():
            has_products = Product.objects.filter(
                category__tree_id=category.tree_id,
                category__lft__gte=category.lft,
                category__rght__lte=category.rght,
            ).exists()

            if has_products:
                categories_with_products += 1

        return Response({
            "total_categories": total,
            "active_categories": active,
            "inactive_categories": inactive,
            "parent_categories": parents,
            "child_categories": children,
            "empty_categories": empty_categories,
            "categories_with_products": categories_with_products,
            "assigned_products": assigned_products,
        })


class AdminCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AdminCategorySerializer
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    queryset = Category.objects.select_related("parent").all()

    def get_queryset(self):
        return super().get_queryset().annotate(
            direct_product_count=Count("products",distinct=True,))

    def perform_destroy(self, instance):
        if instance.products.exists():
            raise ValidationError({
                "detail": (
                    "This category has assigned products. "
                    "Reassign them before deleting this category."
                )
            })

        if instance.get_children().exists():
            raise ValidationError({
                "detail": (
                    "This category has subcategories. "
                    "Move or delete them before deleting this category."
                )
            })

        instance.delete()


class AdminCategoryToggleActiveView(APIView):
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTemmyAdmin]

    def post(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        category.active = not category.active
        category.save(update_fields=["active", "modified_date"])

        return Response({
            "id": category.pk,
            "name": category.name,
            "active": category.active,
            "message": (
                "Category activated."
                if category.active
                else "Category deactivated."
            ),
        })


class AdminCategoryProductsView(generics.ListAPIView):
    serializer_class = AdminCategoryProductSerializer
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTemmyAdmin]
    pagination_class = AdminCategoryPagination

    def get_queryset(self):
        self.category = get_object_or_404(Category,pk=self.kwargs["pk"],)
        return Product.objects.filter(category=self.category).order_by("-created_at")




class AdminStoreSettingsView(APIView):
    authentication_classes = [AdminCookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTemmyAdmin]

    def get(self, request):
        settings = StoreSettings.load()
        serializer = StoreSettingsSerializer(settings)
        return Response(serializer.data)

    def patch(self, request):
        settings = StoreSettings.load()

        serializer = StoreSettingsSerializer(
            settings,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)



























