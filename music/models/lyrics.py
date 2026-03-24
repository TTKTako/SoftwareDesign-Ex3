from django.db import models

from .song import Song


class Lyrics(models.Model):
    """
    Lyrics for a song: custom text, AI-generated text, or instrumental (no lyrics).
    Composition of Song (Song *-- Lyrics in the domain diagram).
    """

    class Mode(models.TextChoices):
        CUSTOM = "custom", "Custom"
        AI_GENERATED = "ai_generated", "AI Generated"
        INSTRUMENTAL = "instrumental", "Instrumental"

    song = models.OneToOneField(
        Song, on_delete=models.CASCADE, related_name="lyrics"
    )
    mode = models.CharField(
        max_length=20, choices=Mode.choices, default=Mode.AI_GENERATED
    )
    # Empty string when mode is INSTRUMENTAL
    content = models.TextField(blank=True)

    class Meta:
        verbose_name = "Lyrics"
        verbose_name_plural = "Lyrics"

    def __str__(self):
        return f"{self.get_mode_display()} lyrics — {self.song}"
