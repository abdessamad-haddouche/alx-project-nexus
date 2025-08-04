from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken


class BlacklistJWTAuthentication(JWTAuthentication):
    def get_validated_token(self, raw_token):
        validated_token = super().get_validated_token(raw_token)

        # Check if token is blacklisted
        jti = validated_token.get("jti")
        if jti:
            try:
                BlacklistedToken.objects.get(token__jti=jti)
                raise InvalidToken("Token has been blacklisted")
            except BlacklistedToken.DoesNotExist:
                pass

        return validated_token
