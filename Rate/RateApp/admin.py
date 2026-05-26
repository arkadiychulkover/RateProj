from django.contrib import admin
from django.utils.safestring import mark_safe
from .models import User, Message, FriendRequest, Rating, Image, LogEntry


class FriendsInline(admin.TabularInline):
    model = User.friends.through  
    fk_name = 'from_user'         
    extra = 1
    verbose_name = "Друг"
    verbose_name_plural = "Друзья"


class ImageInline(admin.TabularInline):
    model = Image
    extra = 1
    fields = ('url', 'get_preview')
    readonly_fields = ('get_preview',)

    @admin.display(description='Превью')
    def get_preview(self, obj):
        if obj.url:
            return mark_safe(f'<img src="{obj.url}" width="100" style="border-radius: 4px;" />')
        return "Нет изображения"


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    inlines = [FriendsInline, ImageInline]
    list_display = (
        "id", "username", "email", "rating", "rated_count", 
        "view_mode", "cabinet_zone", "is_active", "date_joined"
    )
    search_fields = ("username", "email", "first_name", "last_name")
    list_filter = ("is_active", "view_mode", "cabinet_zone", "date_joined")
    list_editable = ("is_active", "view_mode", "cabinet_zone")
    readonly_fields = ("rating", "rated_count")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "sender", "recipient", "short_text", "send_time", "is_read")
    search_fields = ("sender__username", "recipient__username", "message_text")
    list_filter = ("is_read", "send_time")
    list_editable = ("is_read",)
    
    @admin.display(description='Текст сообщения')
    def short_text(self, obj):
        if len(obj.message_text) > 50:
            return f"{obj.message_text[:50]}..."
        return obj.message_text


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "from_user", "to_user", "created_at", "is_accepted")
    search_fields = ("from_user__username", "to_user__username")
    list_filter = ("is_accepted", "created_at")
    list_editable = ("is_accepted",)


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "from_user", "value")
    search_fields = ("user__username", "from_user__username")
    list_filter = ("value",)


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "get_mini_preview", "url")
    search_fields = ("user__username", "url")
    
    @admin.display(description='Превью')
    def get_mini_preview(self, obj):
        if obj.url:
            return mark_safe(f'<img src="{obj.url}" width="60" style="border-radius: 4px;" />')
        return "Нет ссылки"


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "user", "log_type", "text")
    search_fields = ("user__username", "text", "log_type")
    list_filter = ("log_type", "created_at")


admin.site.site_header = "Панель управления RateProj"
admin.site.site_title = "Админка RateProj"
admin.site.index_title = "Управление базой данных маркетплейса"