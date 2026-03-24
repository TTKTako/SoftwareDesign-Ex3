from django.db import models

from .user import User


class Library(models.Model):
    """
    Personal music library owned by exactly one authenticated user.
    Enforces the domain constraint of at most 20 songs via Song.clean().
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
        """Returns True when the library has reached the 20-song limit."""
        return self.songs.count() >= 20
