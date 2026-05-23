from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import UserView, CabinetView

router = DefaultRouter()
router.register(r'users', UserView, basename='users')
router.register(r'cabinet', CabinetView, basename='cabinet')
router.register(r'logs', views.LogView, basename='logs')

urlpatterns = [
    path('lenta/', include(router.urls)),
    path('api/', include(router.urls)),
    path('logs/', include(router.urls)),

    # Pages
    path('', views.login_page, name='login_page'),
    path('login/', views.login_page, name='login_page'),
    path('register/', views.register_page, name='register_page'),
    path('cabinet/', views.cabinet_page, name='cabinet_page'),
    path('chat/', views.chat_home, name='chat_home'),
    path('chat/<int:user_id>/', views.chat_with, name='chat_with'),

    # Auth API
    path('api/register/', views.api_register, name='api_register'),
    path('api/login/', views.api_login, name='api_login'),
    path('api/me/', views.api_me, name='api_me'),
    path('api/logout/', views.api_logout, name='api_logout'),

    # Friends API
    path('api/friends/', views.api_get_friends, name='api_friends'),
    path('api/friends/search/', views.api_search_users, name='api_search_users'),
    path('api/friends/request/', views.api_send_friend_request, name='api_send_friend_request'),
    path('api/friends/requests/', views.api_get_friend_requests, name='api_get_friend_requests'),
    path('api/friends/accept/<int:req_id>/', views.api_accept_friend_request, name='api_accept_friend_request'),
    path('api/friends/reject/<int:req_id>/', views.api_reject_friend_request, name='api_reject_friend_request'),
    path('api/friends/remove/', views.api_remove_friend, name='api_remove_friend'),

    # Chat API
    path('api/chat/<int:user_id>/', views.api_get_chat, name='api_get_chat'),
]
