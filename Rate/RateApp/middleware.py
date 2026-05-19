from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth import get_user_model

User = get_user_model()


class CookieJWTAuthentication(JWTAuthentication):
    """DRF authentication — читает JWT из httpOnly куки accessToken."""
    def authenticate(self, request):
        raw_token = request.COOKIES.get('accessToken')
        if raw_token is None:
            return None
        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token


@database_sync_to_async
def get_user(token_key):
    try:
        token = AccessToken(token_key)
        return User.objects.get(id=token['user_id'])
    except Exception:
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        token = None
        for param in query_string.split("&"):
            if param.startswith("token="):
                token = param.split("=")[1]

        scope['user'] = await get_user(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)