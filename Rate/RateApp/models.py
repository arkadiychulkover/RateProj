from django.db import models
from rest_framework import serializers
from django.contrib.auth.models import AbstractUser
from enum import Enum, IntEnum


# ─── Enums ────────────────────────────────────────────────────────────────────

class CabinetZone(str, Enum):
    PROFILE_SETTINGS = "PROFILE_SETTINGS"
    CONTACT_LIST     = "CONTACT_LIST"
    CHANGING_ZONE    = "CHANGING_ZONE"
    STATISTICS       = "STATISTICS"


class ViewMode(str, Enum):
    PUBLIC  = "PUBLIC"
    PRIVATE = "PRIVATE"


class LogType(str, Enum):
    ACCEPT_FRIEND  = "ACCEPT_FRIEND"
    SEND_MESSAGE   = "SEND_MESSAGE"
    RATE           = "RATE"
    ADD_IMG        = "ADD_IMG"
    REMOVE_IMG     = "REMOVE_IMG"
    LOGIN          = "LOGIN"
    REGISTER       = "REGISTER"
    LOGOUT         = "LOGOUT"
    REMOVE_FRIEND  = "REMOVE_FRIEND"
    DELETE_ACCOUNT = "DELETE_ACCOUNT"
    PROFILE_VISIT  = "PROFILE_VISIT"
    FRIEND_REQUEST = "FRIEND_REQUEST"
    DELETE_FRIEND  = "DELETE_FRIEND"


class Rate(IntEnum):
    SUB3      = 1
    SUB5      = 2
    LLTN      = 3
    LTN       = 4
    HLTN      = 5
    LMTN      = 6
    MTN       = 7
    HMTN      = 8
    LHTN      = 9
    HTN       = 10
    HHTN      = 11
    CHAD_LITE = 12
    CHAD      = 13
    ADAM_LITE = 14
    TRUE_ADAM = 15

    @classmethod
    def get_name(cls, value):
        try:
            return cls(value).name.replace('_', ' ').title().replace(' ', '')
        except ValueError:
            return "Unknown"


# ─── LogFilter ────────────────────────────────────────────────────────────────

class LogFilter:
    """Filters a list of LogEntry ORM objects by user, type and date range."""

    def __init__(self):
        self.target_user_id: int | None = None
        self.log_types: list[str] = []
        self.start_date = None
        self.end_date   = None

    def apply_filter(self, logs):
        result = list(logs)
        if self.target_user_id is not None:
            result = [l for l in result if l.user_id == self.target_user_id]
        if self.log_types:
            result = [l for l in result if l.log_type in self.log_types]
        if self.start_date:
            result = [l for l in result if l.created_at >= self.start_date]
        if self.end_date:
            result = [l for l in result if l.created_at <= self.end_date]
        return result

    def clear(self):
        self.target_user_id = None
        self.log_types      = []
        self.start_date     = None
        self.end_date       = None


# ─── Django ORM Models ────────────────────────────────────────────────────────

class User(AbstractUser):
    url_paths    = models.JSONField(default=list)
    rating       = models.FloatField(default=0)
    rated_count  = models.IntegerField(default=0)

    friends = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=True
    )

    time_spent = models.DateTimeField(null=True, blank=True)
    email      = models.EmailField(unique=True)

    rated_users = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=False,
        related_name="rated_by"
    )

    # Cabinet state
    view_mode    = models.CharField(
        max_length=10,
        default=ViewMode.PUBLIC.value,
        choices=[(m.value, m.value) for m in ViewMode]
    )
    cabinet_zone = models.CharField(
        max_length=30,
        default=CabinetZone.PROFILE_SETTINGS.value,
        choices=[(z.value, z.value) for z in CabinetZone]
    )

    rated_users = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=False
    )

    def __str__(self):
        return (
            f"ID: {self.id} {self.username} ({self.email}) "
            f"- Rating: {self.rating:.2f} based on {self.rated_count} ratings"
        )


class Message(models.Model):
    message_text = models.TextField()

    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_messages"
    )
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="received_messages"
    )

    send_time = models.DateTimeField(auto_now_add=True)
    is_read   = models.BooleanField(default=False)

    class Meta:
        ordering = ['send_time']

    def __str__(self):
        return f"{self.sender} -> {self.recipient}"


class FriendRequest(models.Model):
    from_user   = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_requests")
    to_user     = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_requests")
    created_at  = models.DateTimeField(auto_now_add=True)
    is_accepted = models.BooleanField(default=False)


class Rating(models.Model):
    user      = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ratings")
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="given_ratings")
    value     = models.FloatField()


class Image(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="images")
    url  = models.TextField()


# Renamed from Log → LogEntry to avoid conflict with LogType enum
class LogEntry(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="logs")
    log_type   = models.CharField(max_length=30, default=LogType.LOGIN.value)
    text       = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.log_type}] {self.user} @ {self.created_at}"


# ─── Plain model classes (non-ORM) ────────────────────────────────────────────

class MessageModel:
    def __init__(self, sender_id, recipient_id, text, send_time=None, is_read=False):
        self.sender_id    = sender_id
        self.recipient_id = recipient_id
        self.text         = text
        self.send_time    = send_time
        self.is_read      = is_read


# ─── Serializers ──────────────────────────────────────────────────────────────

class UserSerializer(serializers.ModelSerializer):
    display_rating = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            'id', 'username', 'email',
            'url_paths', 'rating', 'rated_count',
            'display_rating', 'view_mode', 'cabinet_zone',
        ]

    def get_display_rating(self, obj):
        if obj.rated_count > 0:
            rating    = round(int(obj.rating) / obj.rated_count)
            tier_index = max(1, min(rating, 15))
            return Rate.get_name(tier_index)
        return "Unrated"


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Message
        fields = ['id', 'message_text', 'sender', 'recipient', 'send_time', 'is_read']


class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Image
        fields = ['id', 'url']


class LogEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model  = LogEntry
        fields = ['id', 'log_type', 'text', 'created_at']