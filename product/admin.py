from django.contrib import admin
from .models import (Category, Tag, Color, Size, Product, ProductTag, Collection, ProductCollection, Variation, ProductLike, 
                     CategoryAttribute,AttributeOption, UserProductView,ProductAttributeValue, ProductGallery, Brand, SpecificationKey,
                     ProductSpecification, ProductReview, SearchKeyword,UserSearch,ProductKeyword)
# Register your models here.
@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}

@admin.register(ProductGallery)
class ProductGalleryAdmin(admin.ModelAdmin):
    pass

@admin.register(ProductAttributeValue)
class ProductAttributeValueAdmin(admin.ModelAdmin):
    pass

@admin.register(AttributeOption)
class AttributeOptionAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    

@admin.register(CategoryAttribute)
class CategoryAttributeAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    

@admin.register(ProductTag)
class ProductTagAdmin(admin.ModelAdmin):
    pass


@admin.register(Variation)
class VariationAdmin(admin.ModelAdmin):
    list_display = ('product', 'color', 'size', 'stock', 'price')
    list_filter = ('color', 'size', 'product')
    search_fields = ('product__name',)

@admin.register(ProductLike)
class ProductLikeAdmin(admin.ModelAdmin):
    pass

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    pass

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    pass

@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ["name"]

@admin.register(Size)
class SizeAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ["name"]


class ProductVariantInline(admin.TabularInline):
    model = Variation
    extra = 1 
    fields = ('color', 'size', 'stock', 'price', 'is_active')
    autocomplete_fields = ('color', 'size')

class ProductCollectionInline(admin.TabularInline):
    model = ProductCollection
    extra = 1 
    fields = ('product')
    fields = ("product", "collection")

class ProductAttributeValueInline(admin.TabularInline):
    model = ProductAttributeValue
    extra = 1 
    fields = ('product','attribute','option',)
    autocomplete_fields = ('product','attribute','option')

@admin.register(ProductSpecification)
class ProductSpecificationAdmin(admin.ModelAdmin):
    pass

class ProductSpecificationInline(admin.TabularInline):
    model = ProductSpecification
    extra = 1 
    fields = ('product','key','value',)
    autocomplete_fields = ('product','key')


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ["name"]
    inlines=[ProductCollectionInline,]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ["name"]
    inlines=[ProductVariantInline,ProductAttributeValueInline, ProductSpecificationInline]

@admin.register(SpecificationKey)
class SpecificationKeyAdmin(admin.ModelAdmin):
    list_display = ('name','slug')
    list_filter = ('name',)
    search_fields = ('name',)

@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    pass

@admin.register(UserProductView)
class UserProductViewAdmin(admin.ModelAdmin):
    pass

@admin.register(SearchKeyword)
class SearchKeywordAdmin(admin.ModelAdmin):
    pass


@admin.register(UserSearch)
class UserSearchAdmin(admin.ModelAdmin):
    pass


@admin.register(ProductKeyword)
class ProductKeywordAdmin(admin.ModelAdmin):
    pass

