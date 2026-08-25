from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from .models import Category, Collection, SearchKeyword,UserSearch,ProductKeyword,UserProductView,Product, Brand,CategoryAttribute, AttributeOption,Color, Size, ProductLike, Variation, ProductReview
from .serializers import (CategorySerializer, CollectionSerializer, ProductSerializer, BrandSerializer, ColorSerializers,SizeSerializer, RepulsiveCategoryMiniSerializer,
                          ProductReviewSerializer, UserProductViewSerializer, )
from order.models import OrderItem, Cart
from order.serializers import CartItemSerializer
from .paginations import ProductPagination
from django.db.models import Prefetch, Exists, OuterRef, Value , BooleanField,Avg, Q, When,Case,IntegerField, Count
from rest_framework import status
from mptt.utils import get_cached_trees
from django.utils import timezone
from rest_framework.decorators import APIView
from datetime import datetime




# Create your views here.
@api_view(['GET'])
@permission_classes([AllowAny])
def CategoryViewApi(request):
    # Subquery: Check if any product exists in this category or its descendants
    has_products_subquery = Product.objects.filter(
        category__tree_id=OuterRef('tree_id'),
        category__lft__gte=OuterRef('lft'),
        category__rght__lte=OuterRef('rght')
    )

    # 1 SINGLE SQL QUERY
    active_categories = Category.objects.annotate(
        has_products=Exists(has_products_subquery)
    ).filter(
        has_products=True
    ).order_by('tree_id', 'lft')

    # Build the tree in Python memory (0 SQL queries)
    category_tree = get_cached_trees(active_categories)

    # Serialize cached tree
    serializer = RepulsiveCategoryMiniSerializer(category_tree, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([AllowAny])
def CategoryFilterViewApi(request):
    slug = request.GET.get('slug')

    if slug:
        category = Category.objects.select_related('parent').filter(
            slug=slug.lower()
        ).first()

        if not category:
            return Response({"error": "Category not found"}, status=404)
        
        fil_category = category.get_descendants(include_self=True)
        subcategories = Category.objects.select_related('parent').filter(
            parent__slug=slug.lower()
        ).order_by('created_at')

        results = []
        for subcategory in subcategories:
            subcategory_descendants = subcategory.get_descendants(include_self=True)
            if Product.objects.filter(category__in=subcategory_descendants).exists():
                results.append(subcategory)
    else:
        fil_category = []
        results = []
        categories = Category.objects.select_related('parent').filter(
            parent__isnull=True
        ).order_by('created_at')

        for category in categories:
            category_descendants = category.get_descendants(include_self=True)
            if Product.objects.filter(category__in= category_descendants).exists():
                results.append(category)
                fil_category.extend(category_descendants)

    brands = Brand.objects.prefetch_related('productbrands').filter(productbrands__category__in=fil_category).distinct()
    sizes = Size.objects.prefetch_related('variations').filter(variations__product__category__in=fil_category).distinct()
    colors = Color.objects.prefetch_related('variations').filter(variations__product__category__in=fil_category).distinct()
    attributes = CategoryAttribute.objects.select_related('category').filter(category__in=fil_category).distinct()
    collections = Collection.objects.select_related('category').filter(category__in=fil_category)[:3]
    if slug:
        serializer = CategorySerializer(category)
        subcategories_serializer = CategorySerializer(
            results,
            many=True
        )
        filter_attributes = []
        for attribute in attributes:
            options = AttributeOption.objects.select_related('attribute').prefetch_related('productattributevalue').filter(attribute=attribute, productattributevalue__product__category__in=fil_category).distinct()
            filter_attributes.append({
                "attribute": attribute.name,
                "options": [option.value for option in options]
            })
        return Response({
        "category": serializer.data,
        "subcategories": subcategories_serializer.data,
        "brands": BrandSerializer(brands, many=True).data,
        "colors": ColorSerializers(colors, many=True).data,
        "sizes": SizeSerializer(sizes, many=True).data,
        "topdeals":"",
        "collections": CollectionSerializer(collections, many=True).data,
        "attributes": filter_attributes,
    })
    else:
        serializer = CategorySerializer(results, many=True)
        return Response({
        "category": serializer.data,
        "brands": BrandSerializer(brands, many=True).data,
        "colors": ColorSerializers(colors, many=True).data,
        "sizes": SizeSerializer(sizes, many=True).data,
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def CollectionViewApi(request):
    # 1. Define reusable prefetched queryset for nested products
    if request.user.is_authenticated:
        user_likes= ProductLike.objects.filter(user=request.user, product=OuterRef('pk'))
        optimized_products_qs = Product.objects.select_related('category__parent').annotate(is_Liked=Exists(user_likes)).prefetch_related(
            Prefetch('variations',
                queryset=Variation.objects.select_related('color', 'size').filter(is_active=True)
            )
        )
    else:
        optimized_products_qs = Product.objects.select_related('category__parent').annotate(is_Liked= Value(False, output_field=BooleanField())).prefetch_related(
            Prefetch('variations',
                queryset=Variation.objects.select_related('color', 'size').filter(is_active=True)
            )
        )
    # 2. Reusable base queryset for Collection with optimized product chain
    base_queryset = Collection.objects.prefetch_related(
        Prefetch('product', queryset=optimized_products_qs)
    )
    slug = request.GET.get('slug')

    if slug:
        # Use .first() on the pre-optimized queryset
        collection = base_queryset.filter(slug=slug).first()
        if not collection:
            return Response({'detail': 'Collection not found'}, status=404)
        print(collection)
        serializer = CollectionSerializer(collection)
        return Response(serializer.data)

    else:
        # Filter collections that have products, order them, and paginate
        collections = (
            base_queryset.filter(product__isnull=False).distinct().order_by('-created_at')
        )

        paginator = ProductPagination()
        page = paginator.paginate_queryset(collections, request)
        serializer = CollectionSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

@api_view(['GET'])
@permission_classes([AllowAny])
def ProductFilterViewApi(request):
    # 1. Parse parameters
    category_slug = request.GET.get('category', None)
    brands = request.GET.getlist('brands')  # getlist defaults to []
    colors = request.GET.getlist('colors')
    sizes = request.GET.getlist('sizes')
    min_price = request.GET.get('minPrice', None)
    max_price = request.GET.get('maxPrice', None)

    # 2. Base QuerySet initialization with optimizations
    products = Product.objects.select_related('brand', 'category').prefetch_related('variations__color','variations__size').order_by('-created_at')

    # 3. Handle Annotation for 'is_Liked'
    if request.user.is_authenticated:
        is_liked_subquery = ProductLike.objects.filter(
            user=request.user, 
            product=OuterRef('pk')
        )
        products = products.annotate(is_Liked=Exists(is_liked_subquery))
    else:
        products = products.annotate(is_Liked=Value(False, output_field=BooleanField()))

    # 4. Filter by Category & MPTT Descendants
    if category_slug:
        category_obj = Category.objects.filter(slug=category_slug).first()
        if category_obj:
            category_objs = category_obj.get_descendants(include_self=True)
            products = products.filter(category__in=category_objs)
        else:
            # Category slug was provided but not found
            return Response([], status=status.HTTP_200_OK)

    # 5. Filter by Brands (No extra DB query needed)
    if brands:
        products = products.filter(brand__slug__in=brands)

    # 6. Filter by Colors
    if colors:
        products = products.filter(variations__color__slug__in=colors)

    # 7. Filter by Sizes
    if sizes:
        products = products.filter(variations__size__slug__in=sizes)

    # 8. Filter by Price Range
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)

    # 9. Avoid duplicate rows caused by M2M/Reverse Foreign Key joins
    products = products.distinct()

    # 10. Serialize and return response
    serializer = ProductSerializer(products, many=True, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([AllowAny])
def ProductViewApi(request):
    slug = request.GET.get('slug', None)
    productPurchase= False
    refresh_token = request.COOKIES.get('refresh_token')
    print(refresh_token)
    if slug:
        if request.user.is_authenticated:
            is_liked = ProductLike.objects.filter(user=request.user, product=OuterRef('pk'))
            product = Product.objects.select_related('brand', 'category').annotate(is_Liked=Exists(is_liked)).filter(slug=slug).first()
            serializer = ProductSerializer(product)
        elif refresh_token:
            return Response({'message':'unauthorized'}, status=401)
        else:
            product = Product.objects.select_related('brand', 'category').annotate(is_Liked=Value(False, output_field=BooleanField())).filter(slug=slug).first()
            serializer = ProductSerializer(product)

        if request.user.is_authenticated:
            order_Item = OrderItem.objects\
                .select_related('order__user','order__shipping_address', 'order__payment','product','variation')\
                    .filter(order__user=request.user, product=product.id).first()
            if order_Item:
                payment_status = order_Item.order.payment.status
                if payment_status != 'successful':
                    productPurchase = False
                else:
                    productPurchase = True
            else:
                productPurchase = False

        # RELATED PRODUCT
        relatedProducts = Product.objects.select_related('brand', 'category').filter(category=product.category).exclude(id=product.id)[:15]
        relatedProducts_serializer = ProductSerializer(relatedProducts, many=True)

        # RECENT PRODUCT VIEWED
        if request.user.is_authenticated:
            recentproductviewed = UserProductView.objects.filter(user=request.user).exclude(product=product).order_by('-created_at')[:15]
            recentproductviewed_serializer = UserProductViewSerializer(recentproductviewed, many=True)
            return Response({
                "product": serializer.data,
                'productPurchase': productPurchase ,
                'relatedProduct': relatedProducts_serializer.data,
                'recentProductViewed': recentproductviewed_serializer.data,
            })
        return Response({
            "product": serializer.data,
            'productPurchase': productPurchase ,
            'relatedProduct': relatedProducts_serializer.data,
        })
    return Response({'error': 'No Slug'})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ProductLikeApi(request):
    user=request.user
    productSlug = request.data.get('params',{}).get('productSlug')
    print(request.data)
    print(productSlug)
    product = Product.objects.filter(slug=productSlug).first()
    if not product:
        return Response({'error': 'Product not found'}, status=404)
    
    productLike = ProductLike.objects.filter(user=user, product=product).first()
    
    if productLike:
        productLike.delete()
        liked='delete'
    else:
        like = ProductLike.objects.create(
            product=product, user=user
        )
        liked=True

    return Response({'Liked': liked}, status=200)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def AddUserReviewAPi(request):
    data = request.data.get('params',{})
    user = request.user    
    order_Item = OrderItem.objects\
        .select_related('order__user','order__shipping_address', 'order__payment','product','variation')\
            .filter(order__user=user, product=data.get('product')).first()
    if not order_Item:
        return Response({'error':'no product purchase'}, status=404)
    
    payment_status = order_Item.order.payment.status
    if payment_status != 'successful':
        return Response({'error':'product not purchase'}, status=200)
    data.pop('product', None)
    serializer= ProductReviewSerializer(data={**data}, partial=True)
    if serializer.is_valid():
        serializer.save(user=user, orderItem=order_Item, product=order_Item.product)
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([AllowAny])
def ProductReviewAPi(request):
    product = request.GET.get('p')
    print(product)
    reviews = ProductReview.objects.select_related('product','user','orderItem').filter(product=product).order_by('-updated_at')
    star1= 0
    star2= 0
    star3= 0
    star4= 0
    star5= 0

    for review in reviews:
        if review.rating == 1:
            star1+=1
        elif review.rating == 2:
            star2+=1
        elif review.rating == 3:
            star3+=1
        elif review.rating == 4:
            star4+=1
        elif review.rating == 5:
            star5+=1
    star = [
        {'star':star5,'id':5},
        {'star':star4,'id':4},
        {'star':star3, 'id':3},
        {'star':star2, 'id':2},
        {'star':star1, 'id':1}
        ]
    overAll = reviews.aggregate(overAll= Avg('rating'))['overAll']
    serializer = ProductReviewSerializer(reviews, many=True)
    return Response({
        'data':serializer.data,
        'total_reviews': reviews.count(),
        
        'star':star,
        'overAll': overAll,
    },status=200)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def UserProductViewAPi(request):
    user = request.user
    products = UserProductView.objects.filter(user=user).order_by('-created_at')
    serializer = UserProductViewSerializer(products, many=True)
    return Response(serializer.data, status=200)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def AddUserProductViewAPi(request):
    user = request.user
    data = request.data.get('params', {})
    print(request.data)
    product =Product.objects.filter(id=data.get('product')).first()
    if not product:
        return Response({'error': 'Product Not Found'}, status=404)

    productviewed = UserProductView.objects.filter(user=user, product=product).first()
    if productviewed:
        serializer = UserProductViewSerializer(productviewed,data={},partial=True)
    else:
        serializer = UserProductViewSerializer(data={},partial=True)
        
    if serializer.is_valid():
        serializer.save(user=user, product=product, created_at=timezone.now())
        return Response(serializer.data)
    return serializer(serializer.errors, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def RecentViewedAPi(request):
    user= request.user
    product_viewed = UserProductView.objects.select_related('user').filter(user=user).order_by('-created_at')
    serializer = UserProductViewSerializer(product_viewed, many=True)
    return Response(serializer.data, status=200)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def WishListAPi(request):
    products = Product.objects.select_related('brand', 'category').prefetch_related('variations__color','variations__size').order_by('-created_at')
    is_liked_subquery = ProductLike.objects.filter(
        user=request.user, 
        product=OuterRef('pk')
    )
    products = products.annotate(is_Liked=Exists(is_liked_subquery)).filter(is_Liked=True)
    serializer = ProductSerializer(products, many=True)
    return Response(serializer.data, status=200)


# @api_view(['GET'])
# @permission_classes([AllowAny])
# def searchAPi(request):
#     data = request.data
#     search = data.get('search')

class ProductSearchView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        query = request.GET.get("q", "").strip()

        if not query:
            return Response({
                "query": "",
                "count": 0,
                "results": []
            })

        # -------------------------------------------------
        # Search products
        # -------------------------------------------------

        products = Product.objects.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(brand__name__icontains=query) |
            Q(category__name__icontains=query) |
            Q(tag__name__icontains=query) |
            Q(keywords__keyword__icontains=query),
            is_available=True
        ).distinct()

        # -------------------------------------------------
        # Add average rating
        # -------------------------------------------------

        products = products.annotate(
            average_rating=Avg(
                "reviews__rating",
                filter=Q(reviews__is_approved=True)
            )
        )

        # -------------------------------------------------
        # Add number of reviews
        # -------------------------------------------------

        products = products.annotate(
            review_count=Count(
                "reviews",
                filter=Q(reviews__is_approved=True),
                distinct=True
            )
        )

        # -------------------------------------------------
        # Calculate search relevance
        # -------------------------------------------------

        products = products.annotate(
            search_score=Case(

                # Exact product name
                When(
                    name__iexact=query,
                    then=Value(100)
                ),

                # Product name starts with query
                When(
                    name__istartswith=query,
                    then=Value(80)
                ),

                # Product name contains query
                When(
                    name__icontains=query,
                    then=Value(60)
                ),

                # Brand matches
                When(
                    brand__name__icontains=query,
                    then=Value(50)
                ),

                # Category matches
                When(
                    category__name__icontains=query,
                    then=Value(40)
                ),

                # Tag matches
                When(
                    tag__name__icontains=query,
                    then=Value(30)
                ),

                # Product keyword matches
                When(
                    keywords__keyword__icontains=query,
                    then=Value(30)
                ),

                # Description matches
                When(
                    description__icontains=query,
                    then=Value(10)
                ),

                default=Value(5),

                output_field=IntegerField()
            )
        )

        # -------------------------------------------------
        # Order results
        # -------------------------------------------------

        products = products.order_by(
            "-search_score",
            "-average_rating",
            "-review_count",
            "-created_at"
        )

        # -------------------------------------------------
        # Pagination
        # -------------------------------------------------

        try:
            page = int(request.GET.get("page", 1))
        except ValueError:
            page = 1

        try:
            page_size = int(request.GET.get("page_size", 20))
        except ValueError:
            page_size = 20

        # Prevent someone from requesting thousands
        page_size = min(page_size, 50)

        if page < 1:
            page = 1

        start = (page - 1) * page_size
        end = start + page_size

        total_count = products.count()

        products = products[start:end]

        # -------------------------------------------------
        # Save global search keyword
        # -------------------------------------------------

        keyword_obj, created = SearchKeyword.objects.get_or_create(
            keyword=query.lower()
        )

        SearchKeyword.objects.filter(
            id=keyword_obj.id
        ).update(
            search_count=keyword_obj.search_count + 1
        )

        # -------------------------------------------------
        # Save user's search history
        # -------------------------------------------------

        if request.user.is_authenticated:
            user_search = UserSearch.objects.filter(user=request.user,keyword=query).first()
            if user_search:
                user_search.created_at = datetime.now()
                user_search.save()
            else:
                UserSearch.objects.create(
                    user=request.user,
                    keyword=query
                )

        # -------------------------------------------------
        # Serialize
        # -------------------------------------------------

        serializer = ProductSerializer(
            products,
            many=True,
            context={"request": request}
        )

        return Response({
            "query": query,
            "count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": (
                (total_count + page_size - 1) // page_size
            ),
            "results": serializer.data
        })


class SearchSuggestionsView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):

        query = request.GET.get("q", "").strip()

        if not query:
            return Response({
                "query": "",
                "suggestions": []
            })

        suggestions = []

        # -------------------------------------------------
        # 1. Search popular search keywords
        # -------------------------------------------------

        keywords = SearchKeyword.objects.filter(
            keyword__icontains=query
        ).order_by(
            "-search_count"
        )[:5]

        for keyword in keywords:

            suggestions.append({
                "type": "keyword",
                "text": keyword.keyword
            })

        # -------------------------------------------------
        # 2. Search products
        # -------------------------------------------------

        products = Product.objects.filter(
            Q(name__icontains=query) |
            Q(brand__name__icontains=query) |
            Q(category__name__icontains=query) |
            Q(tag__name__icontains=query) |
            Q(keywords__keyword__icontains=query),
            is_available=True
        ).distinct().order_by(
            "-created_at"
        )[:5]

        for product in products:

            suggestions.append({
                "type": "product",
                "text": product.name,
                "slug": product.slug,
                "image": product.image.url if product.image else None
            })

        # -------------------------------------------------
        # Remove duplicate text
        # -------------------------------------------------

        unique_suggestions = []

        seen = set()

        for suggestion in suggestions:

            text = suggestion["text"].lower()

            if text not in seen:

                seen.add(text)

                unique_suggestions.append(
                    suggestion
                )

        return Response({
            "query": query,
            "suggestions": unique_suggestions[:10]
        })


# =========================================================
# 3. RECENT SEARCHES
# =========================================================
class RecentSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        searches = UserSearch.objects.filter(user=request.user).order_by("-created_at")
        results = []
        seen = set()

        for search in searches:
            keyword = search.keyword.strip()

            if not keyword:
                continue

            keyword_lower = keyword.lower()

            # Remove duplicates
            if keyword_lower in seen:
                continue

            seen.add(keyword_lower)
            results.append({
                "id": search.id,
                "keyword": keyword,
                "created_at": search.created_at
            })

            # Only return latest 10
            if len(results) >= 10:
                break

        return Response({
            "results": results
        })


