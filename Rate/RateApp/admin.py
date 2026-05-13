from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Message, FriendRequest, Rating, Log, Image

admin.site.register(User, UserAdmin)
admin.site.register(Message)
admin.site.register(FriendRequest)
admin.site.register(Rating)
admin.site.register(Log)
admin.site.register(Image)
