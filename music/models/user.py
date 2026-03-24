from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Extended user model representing an Authenticated User in the domain.
    Replaces Django's default User to allow future customisation (e.g. Google OAuth).
    Guest access is represented by unauthenticated requests — no separate DB row needed.
    """

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
