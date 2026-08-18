"""
URL configuration for temmyCollection project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from debug_toolbar.toolbar import debug_toolbar_urls
from Account import views
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/admin/v1/', include('api.urls')),
    path('api/p/', include('product.urls')),
    path('api/o/', include('order.urls')),
    path('api/a/', include('Account.urls')),
    path('accounts/', include('allauth.urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('callback/', views.google_login_callback, name='callback'),

]+ debug_toolbar_urls()

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)