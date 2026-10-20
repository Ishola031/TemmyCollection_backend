from rest_framework import serializers
from Account.models import Account, CustomerActivity, PendingSignup
from order.models import ShippingAddress, Order, OrderItem, ShippingAddress, ReviewRating, Coupon
from product.models import Category, Color,Size,Brand,Variation, Product, ProductImage, ProductGallery, ProductReview, Category
from django.utils import timezone
from django.utils.text import slugify
from django.db import transaction
from .models import StoreSettings
from django.db.models import Sum


from product.serializers import (VariationSerializer, ProductImageSerializer,)

class AdminCustomerSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    ban_expired = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'phone_number', 'image', 'is_active', 'is_banned', 'ban_reason', 'banned_at',
            'ban_expires_at', 'banned_by', 'ban_expired', 'is_staff', 'is_admin', 'is_superadmin', 'date_joined', 'last_login', 'last_activity',
        )

        read_only_fields = (
            'id', 'full_name', 'banned_at', 'banned_by', 'date_joined', 'last_login', 'last_activity', 'ban_expired',
        )

    def get_full_name(self, obj):
        return obj.full_name().strip()

    def get_ban_expired(self, obj):
        return obj.is_ban_expired()


class AdminBanSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True, allow_blank=False)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class AdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class AdminUserListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'phone_number', 'image', 'is_active', 'is_staff', 'is_admin', 'is_superadmin', 'is_banned',
            'ban_reason', 'banned_at', 'ban_expires_at', 'banned_by', 'date_joined', 'last_login', 'last_activity',
        ]

    def get_full_name(self, obj):
        return obj.full_name()


class AdminUserDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    banned_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'phone_number', 'image', 'is_active', 'is_staff', 'is_admin', 'is_superadmin',
            'is_banned', 'ban_reason', 'banned_at', 'ban_expires_at', 'banned_by', 'banned_by_name', 'date_joined', 'last_login', 'last_activity',
        ]

    def get_full_name(self, obj):
        return obj.full_name()

    def get_banned_by_name(self, obj):
        if not obj.banned_by:
            return None

        return {
            'id': obj.banned_by.id,
            'username': obj.banned_by.username,
            'email': obj.banned_by.email,
        }


class BanUserSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True, allow_blank=False,max_length=500)
    expires_at = serializers.DateTimeField(required=False,allow_null=True)

    def validate_expires_at(self, value):
        if value and value <= timezone.now():
            raise serializers.ValidationError('Ban expiration must be in the future.')
        return value


class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ( 'first_name', 'last_name', 'email', 'password')
        extra_kwargs = {
            'password': {'write_only': True, 'style': {'input_type': 'password'}},
        }


class CustomerSerializer(serializers.ModelSerializer):
    orders = serializers.IntegerField(read_only=True)
    total_spent = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    average_order = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Account
        fields = (
            'id', 'username', 'first_name', 'last_name', 'email', 'phone_number', 'image', 'date_joined', 'last_login', 'is_active', 'is_banned', 'orders',
            'total_spent', 'ave _order',
        )

class CustomerDetailSerializer(serializers.ModelSerializer):
    orders = serializers.IntegerField(read_only=True)
    total_spent = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    average_order = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Account
        fields = (
            'id', 'username', 'first_name', 'last_name', 'email', 'phone_number', 'image', 'date_joined',
            'last_login', 'is_active', 'is_banned', 'ban_reason', 'banned_at', 'ban_expires_at', 'orders', 'total_spent', 'average_order',
        )


class UserSerializer(serializers.ModelSerializer):
    code = serializers.CharField(write_only=True)

    class Meta:
        model = Account
        fields = (
            'email', 'code', 'username', 'first_name', 'last_name', 'phone_number', 'date_joined'
        )

        extra_kwargs = {
            'password': {
                'write_only': True,
                'style': {'input_type': 'password'}
            },
            'username': {'required': False},
            'code': {'required': False},
            'first_name': {'read_only': True},
            'last_name': {'read_only': True},
            'phone_number': {'read_only': True},
            'date_joined': {'read_only': True},
        }

    def create(self, validated_data):
        validated_data.pop('code')

        import random
        email = validated_data.get("email")
        base = email.split("@")[0]
        randomNum = random.randint(1000, 9999)
        username = f"{base}{randomNum}"
        formData = PendingSignup.objects.get(email=email)
        user = Account.objects.create(
            email=email,
            first_name=formData.first_name,
            last_name=formData.last_name,
            username=username,
            password=formData.password
        )

        user.save()
        formData.delete()
        return user


class UserInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = (
            'id', 'username', 'first_name', 'last_name'
        )


class CustomerOrderSerializer(serializers.ModelSerializer):
    items = serializers.IntegerField(read_only=True)
    class Meta:
        model = Order
        fields = (
            'order_number', 'created_at', 'total_price', 'status', 'items',
        )


class CustomerAddressSerializer(serializers.ModelSerializer):
    state = serializers.CharField(
        source='state.name',
        read_only=True
    )

    class Meta:
        model = ShippingAddress
        fields = (
            'id', 'address_type', 'first_name', 'last_name', 'phone1', 'phone2', 'address_line_1', 'country',
            'state', 'city', 'is_default', 'created_at',
        )


class CustomerActivitySerializer(serializers.ModelSerializer):
    activity_type = serializers.CharField(source='get_activity_type_display')

    class Meta:
        model = CustomerActivity
        fields = (
            'id', 'activity_type', 'title', 'description', 'order', 'created_at',
        )


class CustomerOrderSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [ "order_number", "created_at", "total_price", "status", "items",]

    def get_items(self, obj):
        return obj.orderitems.count()


class CustomerAddressSerializer(serializers.ModelSerializer):
    state = serializers.CharField(source="state.name", read_only=True)

    class Meta:
        model = ShippingAddress
        fields = [
            "id", "address_type", "first_name", "last_name", "phone1", "phone2", "address_line_1", "country", "state",
            "city", "is_default", "created_at",
        ]


class CustomerReviewSerializer(serializers.ModelSerializer):
    product = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = ReviewRating
        fields = [
            "id", "product", "subject", "review", "rating", "status", "created_at", "updated_at",
        ]


class CustomerDetailSerializer(serializers.ModelSerializer):
    orders = serializers.SerializerMethodField()
    addresses = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    total_orders = serializers.SerializerMethodField()
    successful_orders = serializers.SerializerMethodField()
    cancelled_orders = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            "id", "email", "username", "first_name", "last_name", "phone_number", "image", "date_joined", "last_login", "last_activity", "is_active", "is_banned", "ban_reason",
            "banned_at", "ban_expires_at", "total_orders", "successful_orders", "cancelled_orders", "total_spent", "review_count", "orders", "addresses", "reviews",
        ]

    def get_image(self, obj):
        if obj.image:
            try:
                return obj.image.url
            except Exception:
                return None

        return None

    def get_orders(self, obj):
        orders = (Order.objects.filter(user=obj).select_related("payment").order_by("-created_at"))
        return CustomerOrderSerializer(orders,many=True).data

    def get_addresses(self, obj):
        addresses = (ShippingAddress.objects.filter(user=obj).select_related("state").order_by("-is_default", "-created_at"))
        return CustomerAddressSerializer(addresses, many=True).data

    def get_reviews(self, obj):
        reviews = (ReviewRating.objects.filter(user=obj).select_related("product").order_by("-created_at"))

        return CustomerReviewSerializer(reviews,many=True).data

    def get_total_orders(self, obj):
        return Order.objects.filter(user=obj).count()

    def get_successful_orders(self, obj):
        return Order.objects.filter(user=obj,status="Successful").count()

    def get_cancelled_orders(self, obj):
        return Order.objects.filter(user=obj,status="Cancelled").count()

    def get_total_spent(self, obj):
        from django.db.models import Sum
        total = (Order.objects.filter(user=obj, status__in=[ "Successful", "Shipped", "Delivered",]).aggregate(total=Sum("total_price"))["total"])
        return total or 0

    def get_review_count(self, obj):
        return ReviewRating.objects.filter(user=obj).count()

class AdminProductDetailSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()
    brand = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    images = ProductImageSerializer(many=True, read_only=True)
    variations = VariationSerializer(many=True, read_only=True)
    total_stock = serializers.IntegerField(read_only=True)
    total_sold = serializers.SerializerMethodField()
    total_revenue = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id", "name", "slug", "description", "price", "discount", "image", "images", "stock", "total_stock", "is_available", "category",
            "brand", "variations", "total_sold", "total_revenue", "rating", "review_count", "created_at", "modified_date",
        )

    def get_category(self, obj):
        if not obj.category:
            return None

        return {
            "id": obj.category.id,
            "name": str(obj.category),
        }

    def get_brand(self, obj):
        if not obj.brand:
            return None

        return {
            "id": obj.brand.id,
            "name": str(obj.brand),
        }

    def get_total_sold(self, obj):
        result = (
            OrderItem.objects.filter(product=obj, order__payment__status="successful", order__status__in=[
                "Successful", "Processing", "Shipped", "At_Pickup_Station", "Ready_for_Pickup", "Collected", "Delivered",
            ],).aggregate(total=Sum("quantity"))
        )

        return result["total"] or 0

    def get_total_revenue(self, obj):
        items = OrderItem.objects.filter( product=obj, order__payment__status="successful", order__status__in=[
                "Successful", "Processing", "Shipped", "At_Pickup_Station", "Ready_for_Pickup", "Collected", "Delivered",
            ],
        )

        total = 0
        for item in items:
            total += item.price * item.quantity

        return total

    def get_review_count(self, obj):
        return ReviewRating.objects.filter( product=obj, status=True,).count()

    def get_rating(self, obj):
        result = (
            ReviewRating.objects.filter(product=obj, status=True,).aggregate(average=Sum("rating"))
        )

        review_count = ReviewRating.objects.filter(product=obj, status=True,).count()
        if not review_count:
            return 0

        return round(result["average"] / review_count, 1)
    
    def get_image(self, obj):
        if not obj.image:
            return None

        try:
            return obj.image.url
        except Exception:
            return None


class AdminCategoryTreeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ( "id", "name", "slug", "parent", "children",)

    def get_children(self, obj):
        children = obj.subcategories.filter(active=True).order_by("name")
        return AdminCategoryTreeSerializer( children, many=True, context=self.context).data


class AdminBrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ("id","name",)


class AdminColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Color
        fields = ( "id", "name", "hexcode",)


class AdminSizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Size
        fields = ( "id", "name",)

class AdminVariationCreateSerializer(serializers.ModelSerializer):
    color = serializers.PrimaryKeyRelatedField(queryset=Color.objects.all(), allow_null=True, required=False,)
    size = serializers.PrimaryKeyRelatedField(queryset=Size.objects.all(), allow_null=True, required=False,)

    class Meta:
        model = Variation
        fields = ("id", "color", "size", "stock", "price", "is_active",)
        read_only_fields = ("id", "is_active",)

    def validate(self, attrs):
        color = attrs.get("color")
        size = attrs.get("size")

        if not color and not size:
            raise serializers.ValidationError("A variation must have a color or size.")

        return attrs

class AdminProductGallerySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductGallery
        fields = ("id", "image")

class AdminProductCreateSerializer(serializers.ModelSerializer):
    brand = serializers.PrimaryKeyRelatedField(queryset=Brand.objects.all())
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    variations = AdminVariationCreateSerializer(many=True,required=False)
    gallery = serializers.ListField(child=serializers.ImageField(), required=False, write_only=True)

    class Meta:
        model = Product
        fields = (
            "id", "name", "slug", "description", "price", "discount", "stock", "is_available",
            "brand", "category", "image", "variations", "gallery",
        )
        read_only_fields = ( "id", "slug",)

    @transaction.atomic
    def create(self, validated_data):
        variations_data = validated_data.pop("variations",[])
        gallery_images = validated_data.pop("gallery",[])
        name = validated_data["name"]
        slug = slugify(name)
        original_slug = slug
        counter = 1

        while Product.objects.filter(slug=slug).exists():
            slug = f"{original_slug}-{counter}"
            counter += 1

        validated_data["slug"] = slug
        product = Product.objects.create(**validated_data)

        # Create variations
        for variation_data in variations_data:
            Variation.objects.create(product=product, **variation_data)

        # Create gallery images
        for image in gallery_images:
            ProductImage.objects.create(product=product, image=image)
        return product

class AdminVariationUpdateSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    color = serializers.PrimaryKeyRelatedField(queryset=Color.objects.all(), allow_null=True, required=False,)
    size = serializers.PrimaryKeyRelatedField(queryset=Size.objects.all(), allow_null=True, required=False,)

    class Meta:
        model = Variation
        fields = ("id", "color", "size", "stock", "price",)

    def validate(self, attrs):
        color = attrs.get("color")
        size = attrs.get("size")

        if not color and not size:
            raise serializers.ValidationError("A variation must have a color or size.")

        stock = attrs.get("stock")
        if stock is not None and stock < 0:
            raise serializers.ValidationError("Variation stock cannot be negative.")

        price = attrs.get("price")
        if price is not None and price < 0:
            raise serializers.ValidationError("Variation price cannot be negative.")

        return attrs

class AdminProductUpdateSerializer(serializers.ModelSerializer):
    brand = serializers.PrimaryKeyRelatedField(queryset=Brand.objects.all(), required=False,)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), required=False,)
    image = serializers.ImageField(required=False, allow_null=True,)
    gallery = serializers.ListField(child=serializers.ImageField(), required=False, write_only=True,)
    removed_images = serializers.ListField(child=serializers.IntegerField(), required=False, write_only=True,)
    variations = serializers.JSONField(required=False, write_only=True,)

    class Meta:
        model = Product
        fields = (
            "id", "name", "description", "price", "discount", "stock", "is_available", "brand", "category", "image", "gallery", "removed_images", "variations",
        )
        read_only_fields = ("id",)

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative.")

        return value

    def validate_discount(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Discount must be between 0 and 100.")

        return value


    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock cannot be negative.")

        return value

    def validate_variations(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Variations must be a list.")

        serializer = AdminVariationUpdateSerializer( data=value, many=True,)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    @transaction.atomic
    def update(self, instance, validated_data):
        variations_data = validated_data.pop("variations", None)
        gallery_images = validated_data.pop("gallery", [])
        removed_image_ids = validated_data.pop("removed_images", [])
        name_changed = ("name" in validated_data and validated_data["name"] != instance.name)
        for field, value in validated_data.items():
            setattr( instance, field, value)

        if name_changed:
            new_slug = slugify(instance.name)
            original_slug = new_slug
            counter = 1

            while (Product.objects.filter(slug=new_slug).exclude(pk=instance.pk).exists()):
                new_slug = (f"{original_slug}-{counter}")
                counter += 1
            instance.slug = new_slug

        instance.save()

        if removed_image_ids:
            ProductImage.objects.filter(id__in=removed_image_ids, product=instance,).delete()

        for image in gallery_images:
            ProductImage.objects.create( product=instance, image=image,)

        if variations_data is not None:
            existing_variation_ids = []
            for variation_data in variations_data:
                variation_id = variation_data.pop("id",None)

                if variation_id:
                    try:
                        variation = (Variation.objects.get(id=variation_id,product=instance,))

                    except Variation.DoesNotExist:
                        raise serializers.ValidationError({
                            "variations": (
                                f"Variation {variation_id} "
                                "does not belong to this product."
                            )
                        })

                    for field, value in variation_data.items():
                        setattr(variation, field, value)
                    variation.save()
                    existing_variation_ids.append(variation.id)

                else:
                    variation = Variation.objects.create(product=instance, **variation_data)
                    existing_variation_ids.append(variation.id)

            Variation.objects.filter(product=instance).exclude(id__in=existing_variation_ids).delete()
        return instance


class AdminCouponSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    discount_display = serializers.SerializerMethodField()
    usage_display = serializers.SerializerMethodField()

    class Meta:
        model = Coupon
        fields = (
            "id", "code", "discount_type", "discount_value", "discount_display", "minimum_order_amount", "maximum_discount", "usage_limit", "used_count", "usage_display",
            "start_date", "ex _date", "is_active", "status", "created_at", "updated_at",
        )

        read_only_fields = (
            "id", "used_count", "status", "discount_display", "usage_display", "created_at", "updated_at",
        )

    def validate_code(self, value):
        value = value.strip().upper()
        queryset = Coupon.objects.filter(code__iexact=value)

        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)

        if queryset.exists():
            raise serializers.ValidationError("A coupon with this code already exists.")

        return value

    def validate(self, attrs):
        discount_type = attrs.get("discount_type", getattr(self.instance, "discount_type",None))
        discount_value = attrs.get("discount_value", getattr(self.instance,"discount_value",None))
        minimum_order_amount = attrs.get("minimum_order_amount",getattr(self.instance, "minimum_order_amount", 0))
        maximum_discount = attrs.get("maximum_discount", getattr(self.instance, "maximum_discount",None))

        start_date = attrs.get("start_date",getattr( self.instance, "start_date", None))
        expiry_date = attrs.get("expiry_date",getattr( self.instance, "expiry_date", None))

        if discount_value is not None and discount_value <= 0:
            raise serializers.ValidationError({"discount_value": "Discount value must be greater than 0."})

        if minimum_order_amount is not None and minimum_order_amount < 0:
            raise serializers.ValidationError({"minimum_order_amount": "Minimum order amount cannot be negative."})

        if maximum_discount is not None and maximum_discount <= 0:
            raise serializers.ValidationError({"maximum_discount": "Maximum discount must be greater than 0."})

        if ( discount_type == "percentage" and discount_value is not None and discount_value > 100):
            raise serializers.ValidationError({"discount_value": "Percentage discount cannot be greater than 100."})

        if ( start_date and expiry_date and expiry_date <= start_date):
            raise serializers.ValidationError({"expiry_date": "Expiry date must be after the start date."})

        if ( discount_type == "fixed" and maximum_discount is not None):
            raise serializers.ValidationError({"maximum_discount": "Maximum discount is only used for percentage coupons."})

        return attrs

    def get_status(self, obj):
        from django.utils import timezone
        now = timezone.now()

        if not obj.is_active:
            return "inactive"

        if obj.start_date and now < obj.start_date:
            return "scheduled"

        if obj.expiry_date and now > obj.expiry_date:
            return "expired"

        if ( obj.usage_limit is not None and obj.used_count >= obj.usage_limit):
            return "used_up"

        return "active"

    def get_discount_display(self, obj):
        if obj.discount_type == "percentage":
            return f"{obj.discount_value}%"

        return f"₦{obj.discount_value:,.2f}"

    def get_usage_display(self, obj):
        if obj.usage_limit is None:
            return f"{obj.used_count} / Unlimited"

        return f"{obj.used_count} / {obj.usage_limit}"


class AdminReviewSerializer(serializers.ModelSerializer):
    customer = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    product_name = serializers.CharField(source="product.name",read_only=True,)
    review = serializers.CharField( source="comment", read_only=True,)
    status_label = serializers.SerializerMethodField()

    class Meta:
        model = ProductReview
        fields = [
            "id", "customer", "customer_email", "product", "product_name", "rating", "review", "is_approved", "status_label", "is_verified_purchase", "helpful_votes", "unhelpful_votes", "created_at", "updated_at",
        ]

    def get_customer(self, obj):
        user = obj.user

        if not user:
            return "Guest Customer"

        return (
            getattr(user, "name", None)
            or user.full_name()
            or getattr(user, "username", None)
            or getattr(user, "email", None)
            or "Customer"
        )

    def get_customer_email(self, obj):
        return getattr(obj.user, "email", "") or ""

    def get_status_label(self, obj):
        return "Published" if obj.is_approved else "Hidden"


class AdminReviewStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductReview
        fields = ["is_approved"]


class AdminCategorySerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source="parent.name",read_only=True,default=None,)
    direct_product_count = serializers.IntegerField(read_only=True)
    children_count = serializers.SerializerMethodField()
    total_product_count = serializers.SerializerMethodField()
    depth = serializers.IntegerField(source="level", read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id", "name", "slug", "image", "image_url", "parent", "parent_name", "description", "active",
            "direct_product_count", "children_count", "total_product_count", "depth", "created_at", "modified_date",
        ]
        read_only_fields = [
            "id", "created_at", "modified_date", "direct_product_count", "children_count", "total_product_count", "depth", "image_url", "parent_name",
        ]
        extra_kwargs = {
            "slug": {"required": False},
        }

    def get_children_count(self, obj):
        return obj.get_children().count()

    def get_total_product_count(self, obj):
        return Product.objects.filter(
            category__tree_id=obj.tree_id,
            category__lft__gte=obj.lft,
            category__rght__lte=obj.rght,
        ).count()

    def get_image_url(self, obj):
        if not obj.image:
            return None

        try:
            return obj.image.url
        except (ValueError, AttributeError):
            return None

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError("Category name cannot be empty.")

        return value

    def validate(self, attrs):
        parent = attrs.get("parent", getattr(self.instance, "parent", None),)

        if self.instance and parent:
            if parent.pk == self.instance.pk:
                raise serializers.ValidationError({"parent": "A category cannot be its own parent."})

            if parent.tree_id == self.instance.tree_id:
                if ( parent.lft >= self.instance.lft and parent.rght <= self.instance.rght):
                    raise serializers.ValidationError({
                        "parent": ( "A category cannot be moved inside " "its own descendant.")
                    })

        return attrs

    def create(self, validated_data):
        name = validated_data["name"]
        base_slug = slugify(name) or "category"
        slug = base_slug
        number = 2

        while Category.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{number}"
            number += 1

        validated_data["slug"] = slug

        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Preserve existing URLs when editing category names.
        validated_data.pop("slug", None)

        return super().update(instance, validated_data)


class AdminCategoryProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id", "name", "slug", "price", "stock", "is_available", "image",
        ]



class StoreSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreSettings
        fields = [ "store_name", "store_email", "store_phone", "store_address", "maintenance_mode", "maintenance_message", "updated_at",]
        read_only_fields = ["updated_at"]

    def validate_store_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Store name cannot be empty.")
        return value

    def validate_maintenance_message(self, value):
        if len(value) > 5000:
            raise serializers.ValidationError("Maintenance message cannot exceed 5000 characters.")
        return value



