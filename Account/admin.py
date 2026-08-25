from django.contrib import admin
from .models import Account, EmailVerification, Notification
from django.contrib.auth.admin import UserAdmin
# Register your models here.

class AccountAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'username', 'last_login', 'is_active','date_joined')
    ordering = ('date_joined',)
    list_display_links = ('email', 'first_name', 'last_name')
    readonly_fields = ('last_login', 'date_joined')
    list_filter= ()
    fieldsets = (
        (None,{'fields': ('email','username','first_name', 'last_name','phone_number','image','password')}),
        ('Permissions',{'fields': ('is_staff','is_not_user','is_active', 'is_admin','is_superuser', 'groups', 'user_permissions')}),
        ('Others', {'fields': ('date_joined', 'last_login',)})
    )

    add_fieldsets = (
        (None,{
            'classes': ('wide',),
            'fields': ('email', 'username', 'first_name', 'password1', 'password2','is_active', 'is_staff')
        }),
    )



@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    pass
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    pass

admin.site.register(Account, AccountAdmin)