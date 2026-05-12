from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserView, CabinetView

router = DefaultRouter()
router.register(r'users', UserView, basename='users')
router.register(r'cabinet', CabinetView, basename='cabinet')

urlpatterns = [
    path('lenta/', include(router.urls)),
    path('', include(router.urls)),
]