from django.core.exceptions import ValidationError
from django.db import models

from .library import Library


class Song(models.Model):
    """
    A generated audio track stored in a user's library.
    Composed of Metadata, VoiceStyle, and Lyrics (each a separate entity).

    status tracks the AI generation lifecycle:
      PENDING → GENERATING → COMPLETED | FAILED
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        GENERATING = "generating", "Generating"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    library = models.ForeignKey(
        Library, on_delete=models.CASCADE, related_name="songs"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    is_private = models.BooleanField(default=True)
    audio_file = models.FileField(upload_to="songs/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Song"
        verbose_name_plural = "Songs"

    def __str__(self):
        if hasattr(self, "metadata"):
            return self.metadata.title
        return f"Song #{self.pk}"

    def clean(self):
        # Enforce the 20-song library limit on creation only
        if not self.pk and self.library.is_full:
            raise ValidationError(
                "Library limit reached: a library cannot hold more than 20 songs."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
