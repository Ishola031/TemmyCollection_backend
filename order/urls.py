from .import views
from django.urls import path

urlpatterns = [
    path('cart/addcartitem/', views.add_to_cartApi),
    path('cart/removecartitem/', views.RemoveCart),
    path('cart/', views.CartApi),
    path('cartcount/', views.CartCountApi),
    path('cart/checkout/', views.CreatecheckoutApi),
    path('cart/checkoutview/', views.CheckoutViewApi),
    path('states/', views.StateViewApi),
    path('mergecart/', views.mergeCartApi),
    path('useraddress/', views.userAddressApi),
    path('createuseraddress/', views.CreateUserAddress),
    path('initiatepayment/', views.initiate_payment),
    path('payment_callback/', views.payment_callback),
    path('user/orders/', views.OrderView),
    path('user/orderdetail/', views.OrderDetailView),
    path("pickup-stations/", views.PickupStationView, name="pickup-stations"
),
]