from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import GenerationJob, Library, Lyrics, Metadata, SharedLink, Song, User, VoiceStyle


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin for the custom User model, extending Django's built-in UserAdmin."""
    pass


# ---------------------------------------------------------------------------
# Inline admins for Song compositions
# ---------------------------------------------------------------------------

class MetadataInline(admin.StackedInline):
    model = Metadata
    extra = 1
    can_delete = False


class VoiceStyleInline(admin.StackedInline):
    model = VoiceStyle
    extra = 1
    can_delete = False


class LyricsInline(admin.StackedInline):
    model = Lyrics
    extra = 1
    can_delete = False


# ---------------------------------------------------------------------------
# Song admin — exposes all compositions as inlines
# ---------------------------------------------------------------------------

@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = ("__str__", "library", "status", "is_private", "created_at")
    list_filter = ("status", "is_private")
    search_fields = ("metadata__title", "library__owner__username")
    inlines = [MetadataInline, VoiceStyleInline, LyricsInline]
    readonly_fields = ("created_at",)


# ---------------------------------------------------------------------------
# Library admin — shows how many songs are stored
# ---------------------------------------------------------------------------

@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin):
    list_display = ("owner", "song_count")
    search_fields = ("owner__username",)

    @admin.display(description="Songs")
    def song_count(self, obj):
        return obj.songs.count()


# ---------------------------------------------------------------------------
# Standalone admins for composed entities (allow lookup / edit individually)
# ---------------------------------------------------------------------------

@admin.register(Metadata)
class MetadataAdmin(admin.ModelAdmin):
    list_display = ("title", "mood", "occasion", "theme", "duration")
    search_fields = ("title",)
    list_filter = ("mood", "occasion")


@admin.register(VoiceStyle)
class VoiceStyleAdmin(admin.ModelAdmin):
    list_display = ("song", "style")
    list_filter = ("style",)


@admin.register(Lyrics)
class LyricsAdmin(admin.ModelAdmin):
    list_display = ("song", "mode")
    list_filter = ("mode",)


# ---------------------------------------------------------------------------
# SharedLink admin
# ---------------------------------------------------------------------------

@admin.register(SharedLink)
class SharedLinkAdmin(admin.ModelAdmin):
    list_display = ("song", "created_by", "token", "created_at")
    search_fields = ("song__metadata__title", "created_by__username")
    readonly_fields = ("token", "created_at")


# ---------------------------------------------------------------------------
# GenerationJob admin
# ---------------------------------------------------------------------------

@admin.register(GenerationJob)
class GenerationJobAdmin(admin.ModelAdmin):
    list_display = ("song", "strategy", "status", "task_id", "created_at", "updated_at")
    list_filter = ("strategy", "status")
    search_fields = ("task_id", "song__metadata__title")
    readonly_fields = ("task_id", "strategy", "created_at", "updated_at")
