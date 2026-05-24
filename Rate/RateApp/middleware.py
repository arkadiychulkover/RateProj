from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth import get_user_model
from django.utils.deprecation import MiddlewareMixin

User = get_user_model()


# ── DRF: читает JWT из httpOnly-куки (используется в ViewSet) ────────────────

class CookieJWTAuthentication(JWTAuthentication):
    """
    DRF authentication backend.
    Берёт access-токен из httpOnly-куки 'accessToken'.
    Подключается в authentication_classes = [CookieJWTAuthentication].
    """
    def authenticate(self, request):
        raw_token = request.COOKIES.get('accessToken')
        if raw_token is None:
            return None
        try:
            validated_token = self.get_validated_token(raw_token)
            return self.get_user(validated_token), validated_token
        except Exception:
            return None


# ── Django Middleware: устанавливает request.user для обычных view ────────────

class CookieJWTMiddleware(MiddlewareMixin):
    """
    Django WSGI middleware.
    Если в куках есть валидный 'accessToken' — ставит request.user.
    Иначе — AnonymousUser (не трогает сессию Django Admin).
    Включить в settings.MIDDLEWARE перед AuthenticationMiddleware:

        'RateApp.middleware.CookieJWTMiddleware',
    """
    def process_request(self, request):
        # Не вмешиваемся в Django Admin (у него своя сессионная auth)
        if request.path.startswith('/admin/'):
            return

        raw_token = request.COOKIES.get('accessToken')
        if raw_token:
            try:
                auth = JWTAuthentication()
                validated = auth.get_validated_token(raw_token)
                user = auth.get_user(validated)
                if user and user.is_active:
                    request.user = user
                    return
            except Exception:
                pass

        request.user = AnonymousUser()


# ── Channels (WebSocket): JWT из query-string ?token=... ─────────────────────

@database_sync_to_async
def _get_user_from_token(token_key: str):
    try:
        token = AccessToken(token_key)
        return User.objects.get(id=token['user_id'])
    except Exception:
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    ASGI / Channels middleware.
    Читает JWT из query-string: ws://host/ws/chat/?token=<access_token>
    Используется в asgi.py:

        application = JWTAuthMiddleware(URLRouter(websocket_urlpatterns))
    """
    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode()
        token = None
        for param in query_string.split('&'):
            if param.startswith('token='):
                token = param.split('=', 1)[1]
                break

        scope['user'] = await _get_user_from_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)
