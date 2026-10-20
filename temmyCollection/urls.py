from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from debug_toolbar.toolbar import debug_toolbar_urls
from Account import views
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/admin/v2/', include('admin_panel.urls')),
    path("api/notifications/", include("notifications.urls")),
    path("api/n/",include("newsletter.urls"),),
    path('api/p/', include('product.urls')),
    path('api/o/', include('order.urls')),
    path('api/a/', include('Account.urls')),
    path('accounts/', include('allauth.urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('callback/', views.google_login_callback, name='callback'),

]+ debug_toolbar_urls()

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)