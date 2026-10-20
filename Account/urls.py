from django.urls import path
from .import views
from rest_framework_simplejwt.views import TokenRefreshView



urlpatterns =[
    # path('apitext/', views.apitext),
    path('checkemail/', views.CheckEmail),
    path('verifyemail/', views.sendVerifyEmailCode),
    path('reverifyemail/', views.ResendVerifyEmailCode),
    path('user/register/', views.CreateUser.as_view()),
    path('resend_status/', views.resend_status),
    path('userdetail/', views.userDetails),

    # TOKEN API URL 
    path('token/', views.CustomTokenObtainPairView.as_view()),
    path('token/refresh/', views.CustomRefreshTokenView.as_view()),
    path('logout/', views.LogoutView),
    path('isauthenticated/', views.is_authenticated),


    # 
    
]

