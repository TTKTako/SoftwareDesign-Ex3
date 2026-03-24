from django.db import models

from .song import Song


class Metadata(models.Model):
    """
    Descriptive metadata for a song: title, mood, theme, occasion, duration.
    Composition of Song (Song *-- Metadata in the domain diagram).
    """

    class Mood(models.TextChoices):
        HAPPY = "happy", "Happy"
        SAD = "sad", "Sad"
        ENERGETIC = "energetic", "Energetic"
        CALM = "calm", "Calm"
        ROMANTIC = "romantic", "Romantic"
        ANGRY = "angry", "Angry"
        MELANCHOLIC = "melancholic", "Melancholic"

    class Occasion(models.TextChoices):
        BIRTHDAY = "birthday", "Birthday"
        WEDDING = "wedding", "Wedding"
        PARTY = "party", "Party"
        RELAXATION = "relaxation", "Relaxation"
        WORKOUT = "workout", "Workout"
        GENERAL = "general", "General"

    song = models.OneToOneField(
        Song, on_delete=models.CASCADE, related_name="metadata"
    )
    title = models.CharField(max_length=255)
    mood = models.CharField(max_length=50, choices=Mood.choices)
    theme = models.CharField(max_length=255)
    occasion = models.CharField(max_length=50, choices=Occasion.choices)
    duration = models.DurationField(null=True, blank=True)

    class Meta:
        verbose_name = "Metadata"
        verbose_name_plural = "Metadata"

    def __str__(self):
        return self.title
