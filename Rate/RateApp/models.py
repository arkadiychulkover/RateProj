from django.db import models

class User(AbstractUser):
    url_paths = models.JSONField(default=list)

    rating = models.FloatField(default=0)
    rated_count = models.IntegerField(default=0)

    friends = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=True
    )

    time_spent = models.DateTimeField(null=True, blank=True)

    email = models.EmailField(unique=True)

    def __str__(self):
        return f"ID: {self.id} {self.username} ({self.email}) - Rating: {self.rating:.2f} based on {self.rated_count} ratings"
    

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

    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['send_time']

    def __str__(self):
        return f"{self.sender} -> {self.recipient}"