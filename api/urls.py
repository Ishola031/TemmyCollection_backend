from Account import views
from django.urls import path
from api.views import (UsersApi, productsAPI,categoryAPI, OrderAPI, AddCategory, Dashboard,
                       StaffsApi,addBrand, addColor, addSize)
urlpatterns = [
    path('signup/', views.admin_signup),
    path('signin/', views.admin_login),
    path('isauthorized/', views.IsAdminAuthenticated),
    path('users/', UsersApi),
    path('staffs/', StaffsApi),
    path('products/', productsAPI),
    path('categories/', categoryAPI),
    path('orders/', OrderAPI),
    path('addCategory/', AddCategory),
    path('dashboard/', Dashboard),
    path('addbrand/', addBrand),
    path('addcolor/', addColor),
    path('addsize/', addSize),

]