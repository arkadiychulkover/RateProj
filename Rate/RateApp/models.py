from django.db import models
from rest_framework import serializers
from django.contrib.auth.models import AbstractUser
from enum import Enum, IntEnum


# ── Django Models ─────────────────────────────────────────────────────────────

class User(AbstractUser):
    url_paths    = models.JSONField(default=list)
    rating       = models.FloatField(default=0)
    rated_count  = models.IntegerField(default=0)
    time_spent   = models.DateTimeField(null=True, blank=True)
    email        = models.EmailField(unique=True)

    # Поля для кабинета
    view_mode    = models.CharField(max_length=32, default='grid')
    cabinet_zone = models.CharField(max_length=64, default='main')

    friends = models.ManyToManyField(
        "self", blank=True, symmetrical=True
    )
    rated_users = models.ManyToManyField(
        "self", blank=True, symmetrical=False, related_name='rated_by'
    )

    def __str__(self):
        return f"ID:{self.id} {self.username} rating={self.rating:.2f}/{self.rated_count}"


class Message(models.Model):
    message_text = models.TextField()
    sender       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    recipient    = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_messages")
    send_time    = models.DateTimeField(auto_now_add=True)
    is_read      = models.BooleanField(default=False)

    class Meta:
        ordering = ['send_time']

    def __str__(self):
        return f"{self.sender} -> {self.recipient}"


class FriendRequest(models.Model):
    from_user  = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_requests")
    to_user    = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_requests")
    created_at = models.DateTimeField(auto_now_add=True)
    is_accepted = models.BooleanField(default=False)


class Rating(models.Model):
    user      = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ratings")
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="given_ratings")
    value     = models.FloatField()


class Image(models.Model):
    """Фотографии пользователя (макс. 2)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="images")
    url  = models.TextField()

    def __str__(self):
        return f"Image({self.id}) for {self.user.username}"


class LogType(models.TextChoices):
    ACCEPT_FRIEND  = "ACCEPT_FRIEND",  "Принял в друзья"
    SEND_MESSAGE   = "SEND_MESSAGE",   "Отправил сообщение"
    RATE           = "RATE",           "Поставил оценку"
    ADD_IMG        = "ADD_IMG",        "Добавил фото"
    REMOVE_IMG     = "REMOVE_IMG",     "Удалил фото"
    LOGIN          = "LOGIN",          "Вошёл в систему"
    REGISTER       = "REGISTER",       "Зарегистрировался"
    LOGOUT         = "LOGOUT",         "Вышел из системы"
    REMOVE_FRIEND  = "REMOVE_FRIEND",  "Удалил из друзей"
    DELETE_ACCOUNT = "DELETE_ACCOUNT", "Удалил аккаунт"
    PROFILE_VISIT  = "PROFILE_VISIT",  "Посмотрел профиль"
    FRIEND_REQUEST = "FRIEND_REQUEST", "Отправил заявку"


class LogEntry(models.Model):
    """Лог действий пользователя."""
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="logs")
    log_type   = models.CharField(max_length=32, choices=LogType.choices, default=LogType.LOGIN)
    text       = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.log_type}] {self.user.username}: {self.text[:60]}"


# ── Вспомогательные plain-классы ──────────────────────────────────────────────

class MessageModel:
    def __init__(self, sender_id, recipient_id, text, send_time=None, is_read=False):
        self.sender_id    = sender_id
        self.recipient_id = recipient_id
        self.text         = text
        self.send_time    = send_time
        self.is_read      = is_read


# ── Enum тиров рейтинга ───────────────────────────────────────────────────────

class Rate(IntEnum):
    SUB3       = 1
    SUB5       = 2
    LLTN       = 3
    LTN        = 4
    HLTN       = 5
    LMTN       = 6
    MTN        = 7
    HMTN       = 8
    LHTN       = 9
    HTN        = 10
    HHTN       = 11
    CHAD_LITE  = 12
    CHAD       = 13
    ADAM_LITE  = 14
    TRUE_ADAM  = 15

    @classmethod
    def get_name(cls, value):
        try:
            return cls(value).name.replace('_', ' ').title().replace(' ', '')
        except ValueError:
            return "Unknown"


# ── Сериализаторы ─────────────────────────────────────────────────────────────

class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Image
        fields = ['id', 'url']


class LogEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model  = LogEntry
        fields = ['id', 'log_type', 'text', 'created_at']


class UserSerializer(serializers.ModelSerializer):
    display_rating = serializers.SerializerMethodField()
    images         = ImageSerializer(many=True, read_only=True)

    class Meta:
        model  = User
        fields = ['id', 'username', 'email', 'url_paths', 'rating', 'rated_count',
                  'display_rating', 'images']

    def get_display_rating(self, obj):
        if obj.rated_count > 0:
            tier_index = max(1, min(round(obj.rating / obj.rated_count), 15))
            return Rate.get_name(tier_index)
        return "Unrated"


# ── LogFilter (используется в LogView) ───────────────────────────────────────

class LogFilter:
    def __init__(self):
        self.target_user_id = None
        self.log_types      = []
        self.start_date     = None
        self.end_date       = None

    def apply_filter(self, qs):
        if self.target_user_id:
            qs = qs.filter(user_id=self.target_user_id)
        if self.log_types:
            qs = qs.filter(log_type__in=self.log_types)
        if self.start_date:
            qs = qs.filter(created_at__date__gte=self.start_date)
        if self.end_date:
            qs = qs.filter(created_at__date__lte=self.end_date)
        return qs
