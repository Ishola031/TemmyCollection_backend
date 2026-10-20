from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class AdminCookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)

        if header is not None:
            raw_token = self.get_raw_token(header)

            if raw_token is not None:
                try:
                    validated_token = self.get_validated_token(raw_token)
                    return (self.get_user(validated_token), validated_token)

                except (InvalidToken, TokenError):
                    return None

        admin_access_token = request.COOKIES.get('admin_access_token')

        if not admin_access_token:
            return None

        try:
            validated_token = self.get_validated_token(admin_access_token)
            user = self.get_user(validated_token)
            return (user, validated_token)

        except (InvalidToken, TokenError):
            return None
