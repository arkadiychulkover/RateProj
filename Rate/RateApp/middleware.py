from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.tokens import RefreshToken
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


from django.utils.deprecation import MiddlewareMixin

class CookieJWTMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.path.startswith('/admin/'):
            return

        access_token = request.COOKIES.get('accessToken')
        refresh_token = request.COOKIES.get('refreshToken')

        request._should_refresh_access_token = False

        if not access_token and refresh_token:
            try:
                refresh = RefreshToken(refresh_token)
                new_access_token = str(refresh.access_token)
                
                request._new_access_token_value = new_access_token
                request._should_refresh_access_token = True

                authenticator = JWTAuthentication()
                validated_token = authenticator.get_validated_token(new_access_token)
                user = authenticator.get_user(validated_token)
                
                if user and user.is_active:
                    request.user = user
                    return 
            except Exception:
                pass

        if access_token:
            try:
                authenticator = JWTAuthentication()
                validated_token = authenticator.get_validated_token(access_token)
                user = authenticator.get_user(validated_token)
                if user and user.is_active:
                    request.user = user
                    return
            except Exception:
                pass
        
        request.user = AnonymousUser()

    def process_response(self, request, response):
        if getattr(request, '_should_refresh_access_token', False):
            new_token = getattr(request, '_new_access_token_value', None)
            if new_token:
                response.set_cookie(
                    key='accessToken',
                    value=new_token,
                    max_age=86400, 
                    httponly=True,
                    samesite='Lax',
                    secure=False 
                )
        return response
            
        