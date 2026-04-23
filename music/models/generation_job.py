from django.db import models

from .song import Song


class GenerationJob(models.Model):
    """
    Tracks a single AI generation task associated with a Song.
    Stores the external taskId (e.g. Suno's task ID) and its lifecycle status.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        TEXT_SUCCESS = "TEXT_SUCCESS", "Text Success"
        FIRST_SUCCESS = "FIRST_SUCCESS", "First Success"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    song = models.OneToOneField(
        Song, on_delete=models.CASCADE, related_name="generation_job"
    )
    # Identifier returned by the generation service (empty for failed pre-submission)
    task_id = models.CharField(max_length=255, blank=True)
    # Which strategy created this job: 'mock' | 'suno'
    strategy = models.CharField(max_length=20)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    audio_url = models.URLField(max_length=2048, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Generation Job"
        verbose_name_plural = "Generation Jobs"

    def __str__(self):
        return f"GenerationJob[{self.task_id or 'no-id'}] ({self.status})"
