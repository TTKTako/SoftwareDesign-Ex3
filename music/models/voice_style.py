from django.db import models

from .song import Song


class VoiceStyle(models.Model):
    """
    Voice style selection for a song (Male, Female, Robotic, Duet).
    Composition of Song (Song *-- VoiceStyle in the domain diagram).
    """

    class Style(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        ROBOTIC = "robotic", "Robotic"
        DUET = "duet", "Duet"

    song = models.OneToOneField(
        Song, on_delete=models.CASCADE, related_name="voice_style"
    )
    style = models.CharField(max_length=20, choices=Style.choices)

    class Meta:
        verbose_name = "Voice Style"
        verbose_name_plural = "Voice Styles"

    def __str__(self):
        return f"{self.get_style_display()} — {self.song}"
