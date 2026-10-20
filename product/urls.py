from .import views
from django.urls import path

urlpatterns = [
    path('categoryfilter/', views.CategoryFilterViewApi),
    path('category/', views.CategoryViewApi),
    path('adduserreview/', views.AddUserReviewAPi),
    path('productreview/', views.ProductReviewAPi),
    path('collection/', views.CollectionViewApi),
    path('product/filter/', views.ProductFilterView.as_view()),
    path('productdetail/', views.ProductViewApi),
    path('productlike/', views.ProductLikeApi),
    path('addproductviewed/', views.AddUserProductViewAPi),
    path('recentviewed/', views.RecentViewedAPi),
    path('wishlist/', views.WishListAPi),
    path('productsearch/', views.ProductSearchView.as_view()),
    path('searchsuggestion/', views.SearchSuggestionsView.as_view()),
    path('recentsearchview/', views.RecentSearchView.as_view()),
]