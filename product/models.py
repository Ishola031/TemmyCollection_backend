from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from Account.models import Account
# from order.models import OrderItem
from mptt.models import MPTTModel, TreeForeignKey
from cloudinary.models import CloudinaryField
from django.core.validators import MaxValueValidator, MinValueValidator
# Create your models here.

class Category(MPTTModel):
    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=50)
    image = CloudinaryField('image', folder='categories',blank=True, null=True)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, related_name='subcategories', blank=True, null=True)
    description = models.TextField(max_length=500, null=True, blank=True)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    class MPTTMeta:
        order_insertion_by = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if self._state.adding:
            if not self.slug:
                self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Brand(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField()
    image = CloudinaryField('image', folder='brands',blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True) 
    created_at = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Tag(models.Model):
    name = models.CharField(max_length=50)
    slug = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Color(models.Model):
    name = models.CharField(max_length=50)
    hexcode = models.CharField(max_length=50)
    slug = models.SlugField()

    def __str__(self):
        return self.name
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
class Size(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField()

    def __str__(self):
        return self.name
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)






class Product(models.Model):
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(max_length=500, blank=True)
    price = models.IntegerField(default=0)
    image = CloudinaryField('image', folder='products',blank=True, null=True)
    stock = models.IntegerField(default=0)
    discount = models.IntegerField(default=0)
    is_available = models.BooleanField(default=True)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='productbrands')
    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE)
    tag = models.ManyToManyField(Tag, related_name='tag', through='ProductTag')
    created_at = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)


    @property
    def total_stock(self):
        if self.variations.exists():
            return sum(
                variation.stock
                for variation in self.variations.all()
            )

        return self.stock
    
    def get_url(self):
        return reverse("product_detail", args=[self.category.slug, self.slug])
    
    def __str__(self):
        return self.name
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    







variation_category_choice = (
    ('color', 'color'),
    ('size', 'size'),
)




class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images"
    )
    image = CloudinaryField(
        "image",
        folder="products"
    )
    is_main = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


    def save(self, *args, **kwargs):
        if self.is_main:
            ProductImage.objects.filter(
                product=self.product,
                is_main=True
            ).exclude(
                pk=self.pk
            ).update(
                is_main=False
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} image"


class ProductTag(models.Model):
    Product = models.ForeignKey(Product, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

class Collection(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=200, unique=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    product = models.ManyToManyField(Product, through='ProductCollection')
    created_at = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
class ProductCollection(models.Model):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name='productcollections')
    product = models.ForeignKey(Product, on_delete=models.CASCADE , related_name='collectionproducts')

    def __str__(self):
        return f"{self.collection.name} - {self.product.name}"

class VariarionManager(models.Manager):
    def colors(self):
        return super(VariarionManager, self).filter(variation_category='color', is_active=True)
    def sizes(self):
        return super(VariarionManager, self).filter(variation_category='size', is_active=True)
        
class Variation(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variations')
    color = models.ForeignKey(Color, on_delete=models.CASCADE, null=True, related_name='variations', blank=True)
    size = models.ForeignKey(Size, on_delete=models.CASCADE, null=True, related_name='variations', blank=True)
    stock = models.IntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=False)

    class Meta:
        unique_together = ('product', 'color', 'size')

    def __str__(self):
        return f"{self.product.name} - {self.color.name}"
    
    def save(self, *args, **kwargs):
        if self.stock <=0:
            self.is_active = False
        else:
            self.is_active = True
        super().save(*args, **kwargs)

class ProductLike(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='productLikes')
    user = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} -{self.product}"
    
class ProductGallery(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='productgallery')
    image = CloudinaryField('image', blank=True, null=True)

    def __str__(self):
        return self.product.name

class CategoryAttribute(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='attributes')
    created_at = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
class AttributeOption(models.Model):
    attribute = models.ForeignKey(CategoryAttribute, on_delete=models.CASCADE, related_name='options')
    value = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.attribute.name} - {self.value}"
    
class ProductAttributeValue(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='attribute_values')
    attribute = models.ForeignKey(CategoryAttribute, on_delete=models.CASCADE, related_name='attributes')
    option = models.ForeignKey(AttributeOption, on_delete=models.CASCADE, related_name='productattributevalue')
    created_at = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} - {self.attribute.name} - {self.option.value}"
    
class SpecificationKey(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField()

    def __str__(self):
        return self.name

class ProductSpecification(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='specs')
    key = models.ForeignKey(SpecificationKey, on_delete=models.PROTECT)
    value = models.CharField(max_length=20)

    class Meta:
        unique_together = ('product', 'key')

class ProductReview(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, related_name='reviews')
    
    # Use string reference 'order.OrderItem' to break the circular import
    orderItem = models.OneToOneField( 'order.OrderItem',  on_delete=models.SET_NULL,  null=True,  blank=True,  related_name='review')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField()
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    helpful_votes = models.PositiveIntegerField(default=0)
    unhelpful_votes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class UserProductView(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='userproductviews')
    user = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='userproductviews')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}-{self.product.name}"


class SearchKeyword(models.Model):
    keyword = models.CharField(max_length=255,unique=True)
    search_count= models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.keyword

class UserSearch(models.Model):
    user = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='searches')
    keyword=models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} - {self.keyword}"

class ProductKeyword(models.Model):
    product=models.ForeignKey(Product, on_delete=models.CASCADE, related_name='keywords')
    keyword=models.CharField(max_length=100)

    def __str__(self):
        return self.keyword

