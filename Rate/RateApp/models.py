from django.db import models
from rest_framework import serializers
from django.contrib.auth.models import AbstractUser
from enum import Enum, IntEnum


class User(AbstractUser):
    url_paths = models.JSONField(default=list)
    rating = models.FloatField(default=0)
    rated_count = models.IntegerField(default=0)
    friends = models.ManyToManyField("self", blank=True, symmetrical=True)
    time_spent = models.DateTimeField(null=True, blank=True)
    email = models.EmailField(unique=True)
    rated_users = models.ManyToManyField("self", blank=True, symmetrical=False, related_name='rated_by')

    def __str__(self):
        return f"ID: {self.id} {self.username} ({self.email}) - Rating: {self.rating:.2f}"


class Message(models.Model):
    message_text = models.TextField()
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_messages")
    send_time = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['send_time']

    def __str__(self):
        return f"{self.sender} -> {self.recipient}"


class FriendRequest(models.Model):
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_requests")
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_requests")
    created_at = models.DateTimeField(auto_now_add=True)
    is_accepted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.from_user} -> {self.to_user}"


class Rating(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ratings")
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="given_ratings")
    value = models.FloatField()


class Log(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="logs")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Image(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="images")
    url = models.TextField()

class UserModel:
    def __init__(self, user_id, username, email):
        self.username = username
        self.email = email
        self.id = user_id

        self.rated_users = set()
        self.friends = set()
        self.messages = []
        self.images = []
        self.rating = []
        self.logs = []

class MessageModel:
    def __init__(self, sender_id, recipient_id, text, send_time=None, is_read=False):
        self.sender_id = sender_id
        self.recipient_id = recipient_id
        self.text = text
        self.send_time = send_time
        self.is_read = is_read

class Rate:
    def __init__(self, value):
        self.value = value


# ── Enums ──────────────────────────────────────────────────────────────────────

class LogAction(Enum):
    ACCEPT_FRIEND = "ACCEPT_FRIEND"
    SEND_MESSAGE = "SEND_MESSAGE"
    RATE = "RATE"
    ADD_IMG = "ADD_IMG"
    REMOVE_IMG = "REMOVE_IMG"
    LOGIN = "LOGIN"
    REGISTER = "REGISTER"
    LOGOUT = "LOGOUT"
    REMOVE_FRIEND = "REMOVE_FRIEND"
    DELETE_ACCOUNT = "DELETE_ACCOUNT"
    PROFILE_VISIT = "PROFILE_VISIT"
    FRIEND_REQUEST = "FRIEND_REQUEST"


class RateTier(IntEnum):
    SUB3 = 1
    SUB5 = 2
    LLTN = 3
    LTN = 4
    HLTN = 5
    LMTN = 6
    MTN = 7
    HMTN = 8
    LHTN = 9
    HTN = 10
    HHTN = 11
    CHAD_LITE = 12
    CHAD = 13
    ADAM_LITE = 14
    TRUE_ADAM = 15

    @classmethod
    def get_name(cls, value):
        try:
            return cls(value).name.replace('_', ' ').title().replace(' ', '')
        except ValueError:
            return "Unknown"


# ── Serializers ───────────────────────────────────────────────────────────────

class UserSerializer(serializers.ModelSerializer):
    display_rating = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'url_paths', 'rating', 'rated_count', 'display_rating']

    def get_display_rating(self, obj):
        if obj.rated_count > 0:
            rating = round(int(obj.rating) / obj.rated_count)
            tier_index = max(1, min(rating, 15))
            return RateTier.get_name(tier_index)
        return 0
