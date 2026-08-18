from rest_framework import serializers
from Account.serializers import UserInfoSerializer
from .models import (Collection, Product, Category, Color, Size,
                     Variation, UserProductView,ProductLike, Brand,SpecificationKey,ProductSpecification, ProductReview)
from django.db.models import Exists, OuterRef

class ColorSerializers(serializers.ModelSerializer):
    class Meta:
        model = Color
        fields = ("id", "name", "slug", "hexcode")
        read_only_fields = ["slug"]


class SizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Size
        fields = ("id", "name", "slug")
        read_only_fields = ["slug"]


class CategoryMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent")


class CategorySerializer(serializers.ModelSerializer):
    parent = CategoryMiniSerializer(read_only=True)
    image = serializers.SerializerMethodField()
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "image", "parent", "description", "active", "created_at")
        read_only_fields = ["slug"]

    def get_image(self, obj):
        if obj.image:
            # Returns the Cloudinary CDN URL string
            return obj.image.url
        return None

class RepulsiveCategoryMiniSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'children']

    def get_children(self, obj):
        # Access in-memory cached children populated by get_cached_trees()
        cached_children = obj.get_children()

        # If we are at the top-level (root node), serialize its immediate children without further recursion
        if cached_children and obj.is_root_node():
            # Creating a non-recursive representation for first-level children
            return CategoryChildSerializer(cached_children, many=True).data
        
        return []


class CategoryChildSerializer(serializers.ModelSerializer):
    """Simple serializer for first-level children with no nested descendants."""
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']



class VariationSerializer(serializers.ModelSerializer):
    color = ColorSerializers(read_only=True)
    size = SizeSerializer(read_only=True)

    class Meta:
        model = Variation
        fields = ("id", "color", "size", "price", "stock", "is_active")


class ProductInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name", "slug")


class SpecificationKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecificationKey
        fields = ('id', 'name', 'slug')


class ProductSpecificationSerializer(serializers.ModelSerializer):
    key= SpecificationKeySerializer()
    class Meta:
        model = ProductSpecification
        fields = ('id', 'product', 'key', 'value')


class ProductSerializer(serializers.ModelSerializer):
    # Declarative relation leverages DRF prefetching automatically
    variations = VariationSerializer(many=True, read_only=True)
    category = CategoryMiniSerializer(read_only=True)
    is_Liked = serializers.BooleanField(read_only=True)
    specs= ProductSpecificationSerializer(many=True, read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id", "name", "slug", "description", "is_Liked","variations",'specs',
            "price", "image", "stock", "discount", 
            "is_available", "category", "created_at"
        )
    def get_image(self, obj):
        if obj.image:
            # Returns the Cloudinary CDN URL string
            return obj.image.url
        return None


class CollectionSerializer(serializers.ModelSerializer):
    product = ProductSerializer(many=True, read_only=True)

    class Meta:
        model = Collection
        fields = ("id", "name", "slug", "product", "created_at")


class ProductLikeSerializer(serializers.ModelSerializer):
    # Fixed inheritance from ModelField -> ModelSerializer
    class Meta:
        model = ProductLike
        fields = ("product", "user")


class BrandSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    class Meta:
        model = Brand
        fields = ("id", "name", "slug", "image", "created_at")

    def get_image(self, obj):
        if obj.image:
            # Returns the Cloudinary CDN URL string
            return obj.image.url
        return None


class ProductReviewSerializer(serializers.ModelSerializer):
    user = UserInfoSerializer()
    product = ProductInfoSerializer()
    class Meta:
        model = ProductReview
        fields = ('id', 'product', 'user', 'orderItem', 'rating','comment', 'is_verified_purchase', 'is_approved', 'helpful_votes', 'unhelpful_votes', 'created_at', 'updated_at')

class UserProductViewSerializer(serializers.ModelSerializer):
    product= ProductSerializer()
    class Meta:
        model = UserProductView
        fields = ('id', 'product', 'user')



