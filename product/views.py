from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from .models import Category, Collection, SearchKeyword,UserSearch,ProductKeyword,UserProductView,Product, Brand,CategoryAttribute, AttributeOption,Color, Size, ProductLike, Variation, ProductReview, ProductAttributeValue
from .serializers import (CategorySerializer, CollectionSerializer, ProductSerializer, BrandSerializer, ColorSerializers,SizeSerializer, RepulsiveCategoryMiniSerializer,
                          ProductReviewSerializer, UserProductViewSerializer, CategoryMiniSerializer)
from order.models import OrderItem, Cart
from decimal import Decimal, InvalidOperation
from order.serializers import CartItemSerializer
from .paginations import ProductPagination
from django.db.models import Prefetch, Exists, OuterRef, Value , BooleanField,Avg, Q, When,Case,IntegerField, Count, FloatField
from django.db.models.functions import Coalesce
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



@api_view(["GET"])
@permission_classes([AllowAny])
def ProductViewApi(request):
    slug = request.GET.get("slug")
    productPurchase = False
    refresh_token = request.COOKIES.get("refresh_token")

    if not slug:
        return Response(
            {"error": "No Slug"},
            status=400
        )

    # --------------------------------------------------
    # PRODUCT
    # --------------------------------------------------

    if request.user.is_authenticated:
        is_liked = ProductLike.objects.filter(
            user=request.user,
            product=OuterRef("pk")
        )

        product = (
            Product.objects
            .select_related("brand", "category")
            .annotate(
                is_Liked=Exists(is_liked)
            )
            .filter(slug=slug)
            .first()
        )

    elif refresh_token:
        return Response(
            {"message": "unauthorized"},
            status=401
        )

    else:
        product = (
            Product.objects
            .select_related("brand", "category")
            .annotate(
                is_Liked=Value(
                    False,
                    output_field=BooleanField()
                )
            )
            .filter(slug=slug)
            .first()
        )

    if not product:
        return Response(
            {"error": "Product not found"},
            status=404
        )

    serializer = ProductSerializer(product)

    # --------------------------------------------------
    # CHECK IF USER PURCHASED PRODUCT
    # --------------------------------------------------

    if request.user.is_authenticated:

        order_item = (
            OrderItem.objects
            .select_related(
                "order__user",
                "order__shipping_address",
                "order__payment",
                "product",
                "variation",
            )
            .filter(
                order__user=request.user,
                product=product.id
            )
            .first()
        )

        if order_item:
            payment_status = order_item.order.payment.status

            if payment_status == "successful":
                productPurchase = True

    # --------------------------------------------------
    # RELATED PRODUCTS
    # --------------------------------------------------

    related_products = (
        Product.objects
        .select_related("brand", "category")
        .filter(category=product.category)
        .exclude(id=product.id)[:15]
    )

    related_products_serializer = ProductSerializer(
        related_products,
        many=True
    )

    # --------------------------------------------------
    # RECENT PRODUCTS VIEWED
    # --------------------------------------------------

    if request.user.is_authenticated:

        recent_product_viewed = (
            UserProductView.objects
            .filter(user=request.user)
            .exclude(product=product)
            .select_related("product")
            .order_by("-created_at")[:15]
        )

        recent_product_viewed_serializer = UserProductViewSerializer(
            recent_product_viewed,
            many=True
        )

        return Response({
            "product": serializer.data,
            "productPurchase": productPurchase,
            "relatedProduct": related_products_serializer.data,
            "recentProductViewed": recent_product_viewed_serializer.data,
        })

    return Response({
        "product": serializer.data,
        "productPurchase": productPurchase,
        "relatedProduct": related_products_serializer.data,
    })


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















class ProductSearchView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        print(request.GET)
        query = request.GET.get("q", "").strip()
        brands = request.GET.getlist('brands')  # getlist defaults to []
        colors = request.GET.getlist('colors')
        sizes = request.GET.getlist('sizes')
        min_price = request.GET.get('minPrice', None)
        max_price = request.GET.get('maxPrice', None)
        sort = request.GET.get('sort', 'recommended')
        inStock = request.GET.get('inStock', 'true')
        discount = request.GET.get('discount', 10)
        rating = request.GET.get('rating', 1)

        selected_attributes ={
            key[len('attribute_'):]: value 
            for key, value in self.request.GET.items()
            if key.startswith('attribute_') and value.strip()
        }

        products = Product.objects.all()
        print(query)
        if query:
            fil_category = []
            results = []
            categories = Category.objects.select_related('parent').filter(
                name__icontains=query
            ).order_by('created_at')

            for category in categories:
                category_descendants = category.get_descendants(include_self=True)
                if Product.objects.filter(category__in= category_descendants).exists():
                    results.append(category)
                    fil_category.extend(category_descendants)

            
            products = Product.objects.prefetch_related('orderitems').filter(
                Q(name__icontains=query) |
                Q(description__icontains=query) |
                Q(brand__name__icontains=query) |
                Q(category__name__icontains=query) |
                Q(category__in=fil_category) |
                Q(tag__name__icontains=query) |
                Q(keywords__keyword__icontains=query),
                is_available=True
            ).distinct()

        print('2--',products.count())


        # Add average rating
        products = products.annotate(
            average_rating=Avg("reviews__rating", filter=Q(reviews__is_approved=True)),
            review_count=Count("reviews", filter=Q(reviews__is_approved=True), distinct=True),
            sold=Count('orderitems__quantity'),
            topRated=Coalesce(Avg('reviews__rating'), 0.0, output_field=FloatField()),
        )

        print('2--',products.count())

        # Calculate search relevance
        if query:
            products = products.annotate(
                search_score=Case(
                    # Exact product name
                    When(name__iexact=query, then=Value(100)),
                    # Product name starts with query
                    When(name__istartswith=query,then=Value(80)),
                    # Product name contains query
                    When(name__icontains=query,then=Value(60)),
                    # Brand matches
                    When(brand__name__icontains=query,then=Value(50)),
                    # Category matches
                    When(category__name__icontains=query,then=Value(40)),
                    # Tag matches
                    When(tag__name__icontains=query,then=Value(30)),
                    # Product keyword matches
                    When(keywords__keyword__icontains=query,then=Value(30)),
                    # Description matches
                    When(description__icontains=query,then=Value(10)),

                    default=Value(5),
                    output_field=IntegerField()
                )
            )

        # Order results
        if query:
            products = products.order_by(
                "-search_score",
                "-average_rating",
                "-review_count",
                "-created_at"
            )
        else:
            products = products.order_by(
                "-average_rating",
                "-review_count",
                "-created_at"
            )

        print('3--',products.count())


        # FILTERS
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
        
        print('4--',products.count())
        
        if sort == 'popularity':
            products = products.order_by('-sold','-created_at')
        elif sort == 'newest':
            products = products.order_by('-created_at')
        elif sort == 'price_asc':
            products = products.order_by('price', '-created_at')
        elif sort == 'price_desc':
            products = products.order_by('-price', '-created_at')
        elif sort == 'top_rating':
            products = products.order_by('-topRated', '-created_at')
        elif sort == 'big_discount':
            products = products.order_by('-discount', '-created_at')
        
        print('5--',products.count())
        if inStock == 'true':
            products = products.filter(
                Q(variations__stock__gt=0) | Q(stock__gt=0)
            )
        else:
            products = products.filter(
                Q(variations__stock__lte=0) | Q(stock__lte=0)
            )
        
        print('6--',products.count())
        if discount == '50':
            products = products.filter(discount__gte=50)
        elif discount == '40':
            products = products.filter(discount__gte=40)
        elif discount == '30':
            products = products.filter(discount__gte=30)
        elif discount == '20':
            products = products.filter(discount__gte=20)
        elif discount == '10':
            products = products.filter(discount__gte=10)

        print('7--',products.count())
        if rating == '5':
            products = products.filter(topRated__gte=5.0).order_by('topRated')
        elif rating == '4':
            products = products.filter(topRated__gte=4.0).order_by('topRated')
        elif rating == '3':
            products = products.filter(topRated__gte=3.0).order_by('topRated')
        elif rating == '2':
            products = products.filter(topRated__gte=2.0).order_by('topRated')
        elif rating == '1':
            products = products.filter(topRated__gte=1.0).order_by('topRated')

        print('8--',products.count())
        for attribute_slug, attribute_value in selected_attributes.items():
            attribute = CategoryAttribute.objects.filter(slug=attribute_slug).first()
            if attribute is None:
                raise

            valid_value = AttributeOption.objects.filter(value=attribute_value).first()
            if valid_value is None:
                raise
            
            matching_products_ids= list(
                ProductAttributeValue.objects.filter(attribute=attribute, option=valid_value).values_list('product_id', flat=True)
            )
            products = products.filter(id__in=matching_products_ids).distinct()

        
        

        categories = set()
        for product in products:
            categories.add(product.category.get_root())

        brands = Brand.objects.prefetch_related('productbrands').filter(productbrands__in=products).distinct()
        sizes = Size.objects.prefetch_related('variations').filter(variations__product__in=products).distinct()
        colors = Color.objects.prefetch_related('variations').filter(variations__product__in=products).distinct()

        
        # Save global search keyword
        keyword_obj, created = SearchKeyword.objects.get_or_create(
            keyword=query.lower()
        )

        SearchKeyword.objects.filter(
            id=keyword_obj.id
        ).update(
            search_count=keyword_obj.search_count + 1
        )

        # Save user's search history
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
        
        total_count = products.count()
        paginator = ProductPagination()
        page = paginator.paginate_queryset(products, request)
        serializer = ProductSerializer(page, many=True, context={"request": request})

        return Response({
            "filters":{
                "q": query,
                "category": CategoryMiniSerializer(categories, many=True).data,
                "brands": BrandSerializer(brands, many=True).data,
                "colors": ColorSerializers(colors, many=True).data,
                "sizes": SizeSerializer(sizes, many=True).data
            },
            "products": {
                "count": total_count,
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
                "results": serializer.data,
            },
        })








# class ProductFilterView(APIView):
#     """Browsable product listing with composable filters and faceted options.

#     Multi-value parameters accept repeated query keys or comma-separated values.
#     Example: ?brands=samsung,apple&colors=black&minPrice=10000&rating=4
#     """
#     permission_classes = [AllowAny]

#     @staticmethod
#     def _values(query_params, key):
#         values = []
#         for raw in query_params.getlist(key):
#             values.extend(part.strip() for part in raw.split(",") if part.strip())
#         return values

#     @staticmethod
#     def _decimal(value, name):
#         if value in (None, ""):
#             return None
#         try:
#             number = Decimal(value)
#             if not number.is_finite() or number < 0:
#                 raise InvalidOperation
#             return number
#         except (InvalidOperation, TypeError, ValueError):
#             raise ValueError(f"'{name}' must be a valid non-negative number.")

#     def get(self, request):
#         params = request.query_params
#         category_slug = params.get("category")

#         # Resolve the category scope, including all descendants.
#         if category_slug:
#             category = Category.objects.select_related("parent").filter(
#                 slug=category_slug.strip().lower(), active=True
#             ).first()
#             if not category:
#                 return Response({"error": "Category not found"}, status=status.HTTP_404_NOT_FOUND)
#             category_ids = list(category.get_descendants(include_self=True).values_list("pk", flat=True))
#             subcategories = Category.objects.filter(parent=category, active=True).order_by("name")
#             category_options = [category]
#         else:
#             category = None
#             roots = Category.objects.filter(parent__isnull=True, active=True).order_by("name")
#             category_ids = list(Category.objects.filter(active=True).values_list("pk", flat=True))
#             subcategories = Category.objects.none()
#             category_options = list(roots)

#         products = Product.objects.filter(category_id__in=category_ids).select_related(
#             "brand", "category"
#         ).annotate(
#             average_rating=Avg("reviews__rating", filter=Q(reviews__is_approved=True)),
#             review_count=Count("reviews", filter=Q(reviews__is_approved=True), distinct=True),
#             total_sold=Sum("orderitems__quantity"),
#         ).distinct()

#         try:
#             min_price = self._decimal(params.get("minPrice"), "minPrice")
#             max_price = self._decimal(params.get("maxPrice"), "maxPrice")
#             min_discount = self._decimal(params.get("minDiscount"), "minDiscount")
#             rating = self._decimal(params.get("rating"), "rating")
#         except ValueError as exc:
#             return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

#         if min_price is not None and max_price is not None and min_price > max_price:
#             return Response({"error": "minPrice cannot be greater than maxPrice."}, status=400)
#         if rating is not None and (rating < 1 or rating > 5):
#             return Response({"error": "rating must be between 1 and 5."}, status=400)
#         if min_discount is not None and min_discount > 100:
#             return Response({"error": "minDiscount cannot exceed 100."}, status=400)

#         brands = self._values(params, "brands") or self._values(params, "brand")
#         colors = self._values(params, "colors") or self._values(params, "color")
#         sizes = self._values(params, "sizes") or self._values(params, "size")
#         tags = self._values(params, "tags")
#         subcategory_slugs = self._values(params, "subcategories")

#         if subcategory_slugs:
#             chosen_categories = Category.objects.filter(
#                 slug__in=subcategory_slugs, pk__in=category_ids, active=True
#             ).values_list("pk", flat=True)
#             products = products.filter(category_id__in=chosen_categories)
#         if brands:
#             products = products.filter(brand__slug__in=brands)
#         if colors:
#             products = products.filter(variations__color__slug__in=colors, variations__is_active=True)
#         if sizes:
#             products = products.filter(variations__size__slug__in=sizes, variations__is_active=True)
#         if tags:
#             products = products.filter(tag__slug__in=tags)
#         if min_price is not None:
#             products = products.filter(price__gte=min_price)
#         if max_price is not None:
#             products = products.filter(price__lte=max_price)
#         if min_discount is not None:
#             products = products.filter(discount__gte=min_discount)
#         if rating is not None:
#             products = products.filter(average_rating__gte=rating)

#         available = (params.get("available") or "").strip().lower()
#         if available:
#             if available.lower() in ("true", "1", "yes"):
#                 products = products.filter(is_available=True)
#             elif available.lower() in ("false", "0", "no"):
#                 products = products.filter(is_available=False)
#             else:
#                 return Response({"error": "available must be true or false."}, status=400)

#         in_stock = (params.get("inStock") or "").strip().lower()
#         if in_stock:
#             if in_stock.lower() in ("true", "1", "yes"):
#                 products = products.filter(Q(stock__gt=0) | Q(variations__stock__gt=0, variations__is_active=True))
#             elif in_stock.lower() in ("false", "0", "no"):
#                 products = products.filter(stock__lte=0).exclude(variations__stock__gt=0, variations__is_active=True)
#             else:
#                 return Response({"error": "inStock must be true or false."}, status=400)

#         # Category-specific attribute facets: ?attribute_12=128GB or ?attribute_12=256GB
#         for key, selected_values in params.lists():
#             if not key.startswith("attribute_"):
#                 continue
#             try:
#                 attribute_id = int(key.removeprefix("attribute_"))
#             except ValueError:
#                 return Response({"error": f"Invalid attribute filter '{key}'."}, status=400)
#             values = [v for raw in selected_values for v in raw.split(",") if v]
#             if values:
#                 products = products.filter(
#                     attribute_values__attribute_id=attribute_id,
#                     attribute_values__option__value__in=values,
#                 )

#         # Sorting is allow-listed so clients cannot choose arbitrary ORM fields.
#         sort = params.get("sort", "recommended")
#         sort_fields = {
#             "recommended": ("-average_rating", "-review_count", "-created_at"),
#             "price_asc": ("price", "pk"),
#             "price_desc": ("-price", "pk"),
#             "newest": ("-created_at",),
#             "rating": ("-average_rating", "-review_count", "-created_at"),
#             "popular": ("-total_sold", "-created_at"),
#             "discount": ("-discount", "-created_at"),
#         }
#         if sort not in sort_fields:
#             return Response({"error": "Invalid sort option.", "allowed": list(sort_fields)}, status=400)
#         products = products.order_by(*sort_fields[sort])

#         # Build facets from the matching result set so the UI can update as users filter.
#         brands_facet = Brand.objects.filter(productbrands__in=products).distinct().order_by("name")
#         colors_facet = Color.objects.filter(variations__product__in=products, variations__is_active=True).distinct().order_by("name")
#         sizes_facet = Size.objects.filter(variations__product__in=products, variations__is_active=True).distinct().order_by("name")
#         attributes = CategoryAttribute.objects.filter(category_id__in=category_ids).distinct().order_by("name")
#         attribute_facets = []
#         for attribute in attributes:
#             options = AttributeOption.objects.filter(
#                 attribute=attribute,
#                 productattributevalue__product__in=products,
#             ).distinct().order_by("value")
#             option_rows = [{"id": option.id, "value": option.value} for option in options]
#             if option_rows:
#                 attribute_facets.append({"id": attribute.id, "name": attribute.name, "options": option_rows})

#         price_bounds = products.aggregate(min=Min("price"), max=Max("price"))
#         total_count = products.count()
#         paginator = ProductPagination()
#         page = paginator.paginate_queryset(products, request)
#         product_data = ProductSerializer(page, many=True, context={"request": request}).data

#         filters = {
#             "category": CategorySerializer(category).data if category else CategorySerializer(category_options, many=True).data,
#             "subcategories": CategorySerializer(subcategories, many=True).data if category else [],
#             "brands": BrandSerializer(brands_facet, many=True).data,
#             "colors": ColorSerializers(colors_facet, many=True).data,
#             "sizes": SizeSerializer(sizes_facet, many=True).data,
#             "attributes": attribute_facets,
#             "price": {"min": price_bounds["min"], "max": price_bounds["max"]},
#             "sort": list(sort_fields),
#         }
#         response = {
#             "filters": filters,
#             "products": {
#                 "count": total_count,
#                 "next": paginator.get_next_link(),
#                 "previous": paginator.get_previous_link(),
#                 "results": product_data,
#             },
#         }
#         if category:
#             response["collections"] = CollectionSerializer(
#                 Collection.objects.filter(category__in=category_ids).distinct()[:3], many=True
#             ).data
#         return Response(response)
















class ProductFilterView(APIView):
    permission_classes=[AllowAny]

    def get(self, request):
        category_slug = request.GET.get('category', None)
        brands = request.GET.getlist('brands')  # getlist defaults to []
        colors = request.GET.getlist('colors')
        sizes = request.GET.getlist('sizes')
        min_price = request.GET.get('minPrice', None)
        max_price = request.GET.get('maxPrice', None)
        sort = request.GET.get('sort', 'recommended')
        inStock = request.GET.get('inStock', 'true')
        discount = request.GET.get('discount', 10)
        rating = request.GET.get('rating', 1)


        selected_attributes ={
            key[len('attribute_'):]: value 
            for key, value in self.request.GET.items()
            if key.startswith('attribute_') and value.strip()
        }
        
        if category_slug:
            category = Category.objects.select_related('parent').filter(
                slug=category_slug.lower()
            ).first()

            if not category:
                return Response({"error": "Category not found"}, status=404)

            fil_category = category.get_descendants(include_self=True)
            subcategories = Category.objects.select_related('parent').filter(
                parent__slug=category_slug.lower()
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

        products = Product.objects.prefetch_related('orderitems').annotate(
            sold=Count('orderitems__quantity'),
            topRated=Coalesce(Avg('reviews__rating'), 0.0, output_field=FloatField()),
        ).filter(category__in=fil_category)

        products = products.annotate(
            average_rating=Avg(
                "reviews__rating",
                filter=Q(reviews__is_approved=True)
            ),
            review_count=Count(
                "reviews",
                filter=Q(reviews__is_approved=True),
                distinct=True
            )
        )

        # products = products.annotate(
        #     review_count=Count(
        #         "reviews",
        #         filter=Q(reviews__is_approved=True),
        #         distinct=True
        #     )
        # )

        products = products.order_by(
            "-average_rating",
            "-review_count",
            "-created_at"
        )

        if brands:
            products = products.filter(brand__slug__in=brands)
        if colors:
            products = products.filter(variations__color__slug__in=colors)
        if sizes:
            products = products.filter(variations__size__slug__in=sizes)
        if min_price:
            products = products.filter(price__gte=min_price)
        if max_price:
            products = products.filter(price__lte=max_price)


        if sort == 'popularity':
            products = products.order_by('-sold','-created_at')
        elif sort == 'newest':
            products = products.order_by('-created_at')
        elif sort == 'price_asc':
            products = products.order_by('price', '-created_at')
        elif sort == 'price_desc':
            products = products.order_by('-price', '-created_at')
        elif sort == 'top_rating':
            products = products.order_by('-topRated', '-created_at')
        elif sort == 'big_discount':
            products = products.order_by('-discount', '-created_at')

        if inStock == 'true':
            products = products.filter(
                Q(variations__stock__gt=0) | Q(stock__gt=0)
            )
        else:
            products = products.filter(
                Q(variations__stock__lte=0) | Q(stock__lte=0)
            )

        print(type(discount))
        print(rating)
        print(list(products.values_list('topRated', flat=True)))
        if discount == '50':
            products = products.filter(discount__gte=50)
        elif discount == '40':
            products = products.filter(discount__gte=40)
        elif discount == '30':
            products = products.filter(discount__gte=30)
        elif discount == '20':
            products = products.filter(discount__gte=20)
        elif discount == '10':
            products = products.filter(discount__gte=10)

        if rating == '5':
            products = products.filter(topRated__gte=5.0).order_by('topRated')
        elif rating == '4':
            products = products.filter(topRated__gte=4.0).order_by('topRated')
        elif rating == '3':
            products = products.filter(topRated__gte=3.0).order_by('topRated')
        elif rating == '2':
            products = products.filter(topRated__gte=2.0).order_by('topRated')
        elif rating == '1':
            products = products.filter(topRated__gte=1.0).order_by('topRated')

        
        for attribute_slug, attribute_value in selected_attributes.items():
            attribute = CategoryAttribute.objects.filter(slug=attribute_slug).first()
            if attribute is None:
                raise

            valid_value = AttributeOption.objects.filter(value=attribute_value).first()
            if valid_value is None:
                raise
            
            matching_products_ids= list(
                ProductAttributeValue.objects.filter(attribute=attribute, option=valid_value).values_list('product_id', flat=True)
            )
            products = products.filter(id__in=matching_products_ids).distinct()


            
        brands = Brand.objects.prefetch_related('productbrands').filter(productbrands__in=products).distinct()
        sizes = Size.objects.prefetch_related('variations').filter(variations__product__in=products).distinct()
        colors = Color.objects.prefetch_related('variations').filter(variations__product__in=products).distinct()
        attributes = CategoryAttribute.objects.select_related('category').prefetch_related('attributes__product').filter(attributes__product__in=products).distinct()
        collections = Collection.objects.select_related('category').filter(category__in=fil_category)[:3]

    
        total_count = products.count()
        paginator = ProductPagination()
        page = paginator.paginate_queryset(products, request)
        product_serializer = ProductSerializer(page, many=True, context={"request": request})

        if category_slug:
            serializer = CategorySerializer(category)
            subcategories_serializer = CategorySerializer( results, many=True)
            filter_attributes = []
            for attribute in attributes:
                options = AttributeOption.objects.select_related('attribute').prefetch_related('productattributevalue').filter(attribute=attribute, productattributevalue__product__category__in=fil_category).distinct()
                filter_attributes.append({
                    "attribute": attribute.name,
                    'slug': attribute.slug,
                    "options": [{'id':option.id, 'value':option.value} for option in options]
                })
            return Response({
            "filters":{
                "category": serializer.data,
                "subcategories": subcategories_serializer.data,
                "brands": BrandSerializer(brands, many=True).data,
                "colors": ColorSerializers(colors, many=True).data,
                "sizes": SizeSerializer(sizes, many=True).data,
                "attributes": filter_attributes,
            },
            "collections": CollectionSerializer(collections, many=True).data,
            "products": {
                "count": total_count,
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
                "results": product_serializer.data
            }
            
        })
        else:
            serializer = CategorySerializer(results, many=True)
            return Response({
            "filters":{
                "category": serializer.data,
                "brands": BrandSerializer(brands, many=True).data,
                "colors": ColorSerializers(colors, many=True).data,
                "sizes": SizeSerializer(sizes, many=True).data,
            },
            "products": {
                "count": total_count,
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
                "results": product_serializer.data
            }
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


