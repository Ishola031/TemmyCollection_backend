from .import views
from django.urls import path

urlpatterns = [
    path('categoryfilter/', views.CategoryFilterViewApi),
    path('category/', views.CategoryViewApi),
    path('adduserreview/', views.AddUserReviewAPi),
    path('productreview/', views.ProductReviewAPi),
    path('collection/', views.CollectionViewApi),
    path('product/filter/', views.ProductFilterViewApi),
    path('productdetail/', views.ProductViewApi),
    path('productlike/', views.ProductLikeApi),
    path('addproductviewed/', views.AddUserProductViewAPi),
]