from django.urls import path

from .views import (admin_login,admin_logout,admin_me,admin_auth_check,admin_activity,AdminRefreshTokenView,AdminCustomerListView,AdminCustomerStatsView,AdminCustomerDetailsView,OrderAPI,
    AddressesAPI, DashboardView, OrdersStatView, OrdersView, OrderDetailsView, UpdateOrderStatusView, CreateShipmentView, UpdateShipmentTrackingView,InventoryStatView,
    InventoryProductListView, InventoryProductStockUpdateView, InventoryProductStockView,AdminProductDetailView, AdminProductCategoryListView,AdminProductOptionsView,
    AdminProductCreateView, AdminCouponListView, AdminCouponDetailView, AdminCouponStatsView, AdminReviewListView, AdminReviewStatsView, AdminReviewDetailView,
    AdminNewsletterSubscriberListView,AdminNewsletterCampaignListCreateView, AdminNewsletterCampaignDetailView, AdminNewsletterCampaignSendView,
    AdminNewsletterCampaignRecipientsView, AdminNewsletterTemplateDetailView,AdminNewsletterTemplateListCreateView,AdminNewsletterStatsView, AdminCategoryDetailView, AdminCategoryListCreateView,
    AdminCategoryStatsView, AdminCategoryToggleActiveView, AdminCategoryProductsView, AdminStoreSettingsView
)





urlpatterns = [
    # AUTHENTICATIONS
    path('login/',admin_login,name='admin-login'),
    path('logout/',admin_logout,name='admin-logout'),
    path('refresh/',AdminRefreshTokenView.as_view(),name='admin-refresh'),
    path('me/',admin_me,name='admin-me'),
    path('auth-check/',admin_auth_check,name='admin-auth-check'),
    path('activity/',admin_activity,name='admin-activity'),

    # CUSTOMERS
    path('customers/',AdminCustomerListView.as_view(),name='admin-customers'),
    path('customers/stats/',AdminCustomerStatsView.as_view(),name='admin-customer-stats'),
    # path('customers/<int:customer_id>/',AdminCustomerDetailView.as_view(),name='admin-customer-detail'),
    path('customersdetails/', AdminCustomerDetailsView.as_view()),

    # ORDERS
    path('userorders/', OrderAPI),
    path('useraddresses/', AddressesAPI),
    path('dashboard/', DashboardView.as_view()),
    path('orderstat/', OrdersStatView.as_view()),
    path('orders/', OrdersView.as_view()),
    path('orderdetails/', OrderDetailsView),
    path('orders/status/update/', UpdateOrderStatusView, name='update-order-status'),
    path('orders/shipment/create/',CreateShipmentView,name='create-shipment'),
    path('orders/shipment/tracking/update/',UpdateShipmentTrackingView,name='update-shipment-tracking'),

    # INVENTORYS
    path( "inventory/stats/", InventoryStatView.as_view(), name="inventory-stats"),
    path( "inventory/products/", InventoryProductListView.as_view(), name="inventory-products",),
    path( "inventory/products/<int:product_id>/stock/", InventoryProductStockUpdateView.as_view(), name="inventory-product-stock-update",),
    path( "products/<int:product_id>/stock/", InventoryProductStockView.as_view(), name="inventory-product-stock",),
    path( "products/categories/", AdminProductCategoryListView.as_view(), name="admin-product-categories",),
    path( "products/options/", AdminProductOptionsView.as_view(), name="admin-product-options",),
    path( "products/", AdminProductCreateView.as_view(), name="admin-product-create",),
    path("products/<slug:product_id>/", AdminProductDetailView.as_view(), name="admin-product-detail",),

    # COUPONS
    path( "coupons/", AdminCouponListView.as_view(), name="admin-coupon-list",),
    path( "coupons/stats/", AdminCouponStatsView.as_view(), name="admin-coupon-stats",),
    path( "coupons/<int:coupon_id>/", AdminCouponDetailView.as_view(), name="admin-coupon-detail",),

    # REVIEWS
    path( "reviews/", AdminReviewListView.as_view(), name="admin-reviews",),
    path( "reviews/stats/", AdminReviewStatsView.as_view(), name="admin-review-stats",),
    path( "reviews/<int:pk>/", AdminReviewDetailView.as_view(), name="admin-review-detail",),

    # NEWSLETTER
    path("newsletter/subscribers/",AdminNewsletterSubscriberListView.as_view(),name="admin-newsletter-subscribers",),
    path("newsletter/stats/", AdminNewsletterStatsView.as_view(), name="admin-newsletter-stats",),
    path( "campaigns/", AdminNewsletterCampaignListCreateView.as_view(), name="admin-newsletter-campaign-list-create",),
    path( "campaigns/<uuid:pk>/", AdminNewsletterCampaignDetailView.as_view(), name="admin-newsletter-campaign-detail",),
    path( "campaigns/<uuid:pk>/send/", AdminNewsletterCampaignSendView.as_view(), name="admin-newsletter-campaign-send",),
    path( "campaigns/<uuid:pk>/recipients/", AdminNewsletterCampaignRecipientsView.as_view(), name="admin-newsletter-campaign-recipients",),
    path( "templates/", AdminNewsletterTemplateListCreateView.as_view(), name="admin-newsletter-template-list-create",),
    path( "templates/<int:pk>/", AdminNewsletterTemplateDetailView.as_view(), name="admin-newsletter-template-detail",),

    # CATEGORIES
    path("categories/stats/", AdminCategoryStatsView.as_view(), name="admin-category-stats",),

    # Catgory list and creation
    path( "categories/", AdminCategoryListCreateView.as_view(), name="admin-category-list-create",),

    # Category details, update and deletion
    path("categories/<int:pk>/", AdminCategoryDetailView.as_view(), name="admin-category-detail",),

    # Activate or deactivate a category
    path("categories/<int:pk>/toggle-active/", AdminCategoryToggleActiveView.as_view(), name="admin-category-toggle-active",),

    # Products directly assigned to a category
    path("categories/<int:pk>/products/", AdminCategoryProductsView.as_view(), name="admin-category-products",),

    # SETTINGS
    path("settings/", AdminStoreSettingsView.as_view(), name="admin-store-settings",),
]


