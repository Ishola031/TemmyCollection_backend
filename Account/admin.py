from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Account, EmailVerification


@admin.register(Account)
class AccountAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'username', 'phone_number', 'is_active', 'is_banned', 'is_staff', 'last_login', 'date_joined',)
    list_display_links = ('email','first_name','last_name',)
    ordering = ('-date_joined',)
    readonly_fields = ('last_login', 'date_joined', 'banned_at',)
    list_filter = ('is_active', 'is_banned', 'is_staff', 'is_admin', 'is_superuser', 'date_joined',)
    search_fields = ('email', 'username', 'first_name', 'last_name', 'phone_number',)
    fieldsets = (
        (None, {'fields': ('email', 'username', 'first_name', 'last_name', 'phone_number', 'image', 'password',)},),
        ('Account Status', {'fields': ('is_active', 'is_banned', 'ban_reason', 'ban_expires_at', 'banned_at', 'banned_by',)},),
        ('Permissions', {'fields': ('is_staff', 'is_not_user', 'is_admin', 'is_superuser', 'groups', 'user_permissions',)},),
        ('Account Information', {'fields': ( 'date_joined', 'last_login',)},),
    )
    add_fieldsets = (
        (None,{
                'classes': ('wide',),
                'fields': ( 'email', 'username', 'first_name', 'last_name', 'phone_number', 'password1', 'password2', 'is_active', 'is_staff',),
        },),
    )


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'email',)
    search_fields = ('email',)


