from django.shortcuts import render
from Account.models import Account
from product.models import Product, Category, Variation, Color, Size, Brand,Collection
from order.models import Order, OrderItem, Payment, ShippingAddress, ShippingZone,State, Shipment, ShipmentTracking
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from Account.serializers import UserSerializer
from .paginations import UserPagination
from product.paginations import ProductPagination
from product.serializers import ProductSerializer, CategorySerializer, CategoryMiniSerializer, CollectionSerializer,ColorSerializers, SizeSerializer,BrandSerializer
from order.serializers import OrderSerializer, OrderItemSerializer
from django.db.models import Sum,F,DecimalField,ExpressionWrapper
from django.db.models.functions import TruncMonth
from decimal import Decimal




# Create your views here.
# All USER
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def UsersApi(request):
    # if not request.user.has_perm('Account.can_view_account'):
    #     return Response(
    #         {"detail": "You do not have permission to publish projects."}, 
    #         status=403
    #     )
    users = Account.objects.filter(is_not_user=False).order_by('-date_joined')
    paginator = UserPagination()
    page = paginator.paginate_queryset(users, request)
    serializer = UserSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)

# ALL STAFF
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def StaffsApi(request):
    # if not request.user.has_perm('Account.can_view_account'):
    #     return Response(
    #         {"detail": "You do not have permission to publish projects."}, 
    #         status=403
    #     )
    users = Account.objects.filter(is_not_user=True, is_staff=True).order_by('-date_joined')
    paginator = UserPagination()
    page = paginator.paginate_queryset(users, request)
    serializer = UserSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)

# ALL WAITING STAFF
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def InterviewStaffsApi(request):
    # if not request.user.has_perm('Account.can_view_account'):
    #     return Response(
    #         {"detail": "You do not have permission to publish projects."}, 
    #         status=403
    #     )
    users = Account.objects.filter(is_not_user=True, is_staff=False).order_by('-date_joined')
    paginator = UserPagination()
    page = paginator.paginate_queryset(users, request)
    serializer = UserSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)

# ALL PRODUCT
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def productsAPI(request):
    # if not request.user.has_perm('product.can_view_product'):
    #     return Response(
    #         {"detail": "You do not have permission to view products."}, 
    #         status=403
    #     )
    products = Product.objects.all().order_by('-created_at')
    paginator = ProductPagination()
    page = paginator.paginate_queryset(products, request)
    serializer = ProductSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)

# CATEGORY
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def categoryAPI(request):
    # if not request.user.has_perm('product.can_view_category'):
    #     return Response(
    #         {"detail": "You do not have permission to view  category."}, 
    #         status=403
    #     )
    categories = Category.objects.select_related('parent').all().order_by('-created_at')
    serializer = CategorySerializer(categories, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def OrderAPI(request):
    # if not request.user.has_perm('order.can_view_order'):
    #     return Response(
    #         {"detail": "You do not have permission to View Orders."}, 
    #         status=403
    #     )
    orders = Order.objects.select_related('shipping_address', 'payment').all().order_by('-created_at')
    paginators = ProductPagination()
    page = paginators.paginate_queryset(orders, request)
    serializer = OrderSerializer(page, many=True)
    return paginators.get_paginated_response(serializer.data)

@api_view(['GET'])
@permission_classes([AllowAny])
def Dashboard(request):
    paid_items = OrderItem.objects.select_related('order').filter(order__status='Successful')

    # Total Revenue
    total_revenue = paid_items.aggregate(
        total=Sum(ExpressionWrapper(F('price') * F('quantity'), output_field=DecimalField()))
    )['total'] or 0

    # Total products Sold
    total_product_sold = paid_items.aggregate(
        total=Sum('quantity')
    )['total'] or 0

    # Monthly Revenue Sold
    monthly_revenue = (paid_items.annotate(month=TruncMonth('order__updated_at')).values('month').annotate(
        revenue=Sum(ExpressionWrapper(F('price') * F('quantity'), output_field=DecimalField()))
    ).order_by('month'))


    monthly_data = []
    monthly_sales = []

    for item in monthly_revenue:
        monthly_data.append({
            "month": item['month'].strftime('%b'),
            'revenue': item['revenue']
        })
        monthly_sales.append(item['revenue'])

    # Average Monthly Revenue
    avg_monthly_revenue = (
        sum(monthly_sales)/ len(monthly_sales)
        if monthly_sales else 0
    )

    return Response({
        "total_revenue": total_revenue,
        'total_products_sold': total_product_sold,
        'average_monthly_revenue': avg_monthly_revenue,
        'monthly_revenue': monthly_data,
    })

# ADDING API
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def addBrand(request):
    # if not request.user.has_perm('Account.can_view_account'):
    #     return Response(
    #         {"detail": "You do not have permission to publish projects."}, 
    #         status=403
    #     )
    data = request.data
    serializer = BrandSerializer(data=request.data, partial=True)
    if serializer.is_valid():
        category = Category.objects.filter(id=int(data.get('category'))).first()
        serializer.save(category=category)
        return Response({'success': 'Brand added successfully'}, status=200)
    return Response(serializer.errors)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def addColor(request):
    # if not request.user.has_perm('Account.can_view_account'):
    #     return Response(
    #         {"detail": "You do not have permission to publish projects."}, 
    #         status=403
    #     )
    data = request.data
    serializer = ColorSerializers(data={**data})
    if serializer.is_valid():
        serializer.save()
        return Response({'success': 'Color added successfully'}, status=200)
    return Response(serializer.errors)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def addSize(request):
    # if not request.user.has_perm('Account.can_view_account'):
    #     return Response(
    #         {"detail": "You do not have permission to publish projects."}, 
    #         status=403
    #     )
    data = request.data
    serializer = SizeSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({'success': 'Size added successfully'}, status=200)
    return Response(serializer.errors)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def AddProduct(request):
    # if not request.user.has_perm('product.can_add_product'):
    #     return Response(
    #         {"detail": "You do not have permission to add product."}, 
    #         status=403
    #     )
    data = request.data
    serializer = ProductSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({'success': 'Product added successfully'}, status=200)
    return Response(serializer.errors)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def AddCategory(request):
    # if not request.user.has_perm('product.can_add_category'):
    #     return Response(
    #         {"detail": "You do not have permission to add category."}, 
    #         status=403
    #     )
    data = request.data
    print(data)
    print(int(data.get('parent')))
    serializer = CategorySerializer(data=request.data, partial= True)
    if serializer.is_valid():
        parent = Category.objects.filter(id=int(data.get('parent'))).first()
        serializer.save(parent=parent)
        return Response({'success': 'Category added successfully'}, status=200)
    return Response(serializer.errors)
    # return Response({'success':'added successfully'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def AddCollection(request):
    # if not request.user.has_perm('product.can_add_collection'):
    #     return Response(
    #         {"detail": "You do not have permission to add collection."}, 
    #         status=403
    #     )
    data = request.data
    serializer = CollectionSerializer(data={**data})
    if serializer.is_valid():
        serializer.save()
        return Response({'success': 'Collection added successfully'}, status=200)
    return Response(serializer.errors)


