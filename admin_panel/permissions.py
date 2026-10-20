from rest_framework.permissions import BasePermission


class IsTemmyAdmin(BasePermission):
    message = "You do not have permission to access the admin panel."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if not user.is_active:
            return False

        if user.is_banned:
            return False

        if not (user.is_staff
            or user.is_admin
            or user.is_superadmin
        ):
            return False

        return True




