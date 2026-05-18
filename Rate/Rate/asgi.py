import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path
from RateApp.middleware import JWTAuthMiddleware
from RateApp.consumers import ChatConsumer

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Rate.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JWTAuthMiddleware(
        URLRouter([
            path("ws/chat/<int:recipient_id>/", ChatConsumer.as_asgi()),
        ])
    ),
})