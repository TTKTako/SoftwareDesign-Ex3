import uuid

from django.db import models

from .song import Song
from .user import User


class SharedLink(models.Model):
    """
    Secure, unique shareable URL token for a specific song.
    Guests may view song metadata via this link; login required to stream audio (FR-5.3).
    """

    song = models.OneToOneField(
        Song, on_delete=models.CASCADE, related_name="shared_link"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="shared_links"
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Shared Link"
        verbose_name_plural = "Shared Links"

    def __str__(self):
        return f"Share/{self.token} → {self.song}"
