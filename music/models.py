import uuid
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class User(AbstractUser):
    """
    Extended user model (Authenticated User in the domain).
    Replaces Django's default User to allow future customisation.
    Guest access is represented by unauthenticated requests — no DB row needed.
    """

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"


class Library(models.Model):
    """
    Personal music library owned by one authenticated user.
    Enforces the domain constraint of at most 20 songs.
    """

    owner = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="library"
    )

    class Meta:
        verbose_name = "Library"
        verbose_name_plural = "Libraries"

    def __str__(self):
        return f"{self.owner.username}'s Library"

    @property
    def is_full(self):
        return self.songs.count() >= 20


class Song(models.Model):
    """
    A generated audio track stored in a user's library.
    Composed of Metadata, VoiceStyle, and Lyrics (each a separate entity
    per the domain model).
    """

    STATUS_PENDING = "pending"
    STATUS_GENERATING = "generating"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_GENERATING, "Generating"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    library = models.ForeignKey(
        Library, on_delete=models.CASCADE, related_name="songs"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
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
        # Enforce the 20-song library limit on creation
        if not self.pk and self.library.is_full:
            raise ValidationError(
                "Library limit reached: a library cannot hold more than 20 songs."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Metadata(models.Model):
    """
    Descriptive metadata for a song: title, mood, theme, occasion, duration.
    Composition of Song (Song *-- Metadata).
    """

    MOOD_CHOICES = [
        ("happy", "Happy"),
        ("sad", "Sad"),
        ("energetic", "Energetic"),
        ("calm", "Calm"),
        ("romantic", "Romantic"),
        ("angry", "Angry"),
        ("melancholic", "Melancholic"),
    ]
    OCCASION_CHOICES = [
        ("birthday", "Birthday"),
        ("wedding", "Wedding"),
        ("party", "Party"),
        ("relaxation", "Relaxation"),
        ("workout", "Workout"),
        ("general", "General"),
    ]

    song = models.OneToOneField(
        Song, on_delete=models.CASCADE, related_name="metadata"
    )
    title = models.CharField(max_length=255)
    mood = models.CharField(max_length=50, choices=MOOD_CHOICES)
    theme = models.CharField(max_length=255)
    occasion = models.CharField(max_length=50, choices=OCCASION_CHOICES)
    duration = models.DurationField(null=True, blank=True)

    class Meta:
        verbose_name = "Metadata"
        verbose_name_plural = "Metadata"

    def __str__(self):
        return self.title


class VoiceStyle(models.Model):
    """
    Voice style selection for a song (Male, Female, Robotic, Duet).
    Composition of Song (Song *-- VoiceStyle).
    """

    STYLE_MALE = "male"
    STYLE_FEMALE = "female"
    STYLE_ROBOTIC = "robotic"
    STYLE_DUET = "duet"
    STYLE_CHOICES = [
        (STYLE_MALE, "Male"),
        (STYLE_FEMALE, "Female"),
        (STYLE_ROBOTIC, "Robotic"),
        (STYLE_DUET, "Duet"),
    ]

    song = models.OneToOneField(
        Song, on_delete=models.CASCADE, related_name="voice_style"
    )
    style = models.CharField(max_length=20, choices=STYLE_CHOICES)

    class Meta:
        verbose_name = "Voice Style"
        verbose_name_plural = "Voice Styles"

    def __str__(self):
        return f"{self.get_style_display()} — {self.song}"


class Lyrics(models.Model):
    """
    Lyrics for a song: custom text, AI-generated, or instrumental (none).
    Composition of Song (Song *-- Lyrics).
    """

    MODE_CUSTOM = "custom"
    MODE_AI_GENERATED = "ai_generated"
    MODE_INSTRUMENTAL = "instrumental"
    MODE_CHOICES = [
        (MODE_CUSTOM, "Custom"),
        (MODE_AI_GENERATED, "AI Generated"),
        (MODE_INSTRUMENTAL, "Instrumental"),
    ]

    song = models.OneToOneField(
        Song, on_delete=models.CASCADE, related_name="lyrics"
    )
    mode = models.CharField(
        max_length=20, choices=MODE_CHOICES, default=MODE_AI_GENERATED
    )
    # Empty when mode is instrumental
    content = models.TextField(blank=True)

    class Meta:
        verbose_name = "Lyrics"
        verbose_name_plural = "Lyrics"

    def __str__(self):
        return f"{self.get_mode_display()} lyrics — {self.song}"


class SharedLink(models.Model):
    """
    Secure, unique shareable URL token for a specific song.
    Guests may view song metadata via this link; login required to stream audio.
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
