"""
Test suite for the Cithara AI Music Generator domain layer.

Covers:
  - Model creation and persistence (CRUD)
  - Domain constraints (20-song library limit, private-by-default)
  - Relationship integrity (Library ↔ Song, Song ↔ Metadata/VoiceStyle/Lyrics)
  - SharedLink UUID generation and uniqueness
  - View access control (authentication gates, ownership checks)
  - Shared-link guest restrictions (metadata visible, audio gated)
"""

import uuid

from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from .models import Library, Lyrics, Metadata, SharedLink, Song, User, VoiceStyle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username="testuser", password="testpass123"):
    return User.objects.create_user(username=username, password=password)


def make_library(user):
    return Library.objects.create(owner=user)


def make_song(library, status=Song.Status.COMPLETED):
    return Song.objects.create(library=library, status=status)


def make_full_song(library, title="My Song", status=Song.Status.COMPLETED):
    """Create a Song with all three composed entities attached."""
    song = Song.objects.create(library=library, status=status)
    Metadata.objects.create(
        song=song, title=title, mood="happy", theme="adventure", occasion="general"
    )
    VoiceStyle.objects.create(song=song, style=VoiceStyle.Style.MALE)
    Lyrics.objects.create(song=song, mode=Lyrics.Mode.AI_GENERATED, content="")
    return song


# ===========================================================================
# 1. User model
# ===========================================================================

class UserModelTests(TestCase):
    """Test: custom User model creation and persistence."""

    def test_create_user(self):
        """
        Create a User with username and password.
        Expect: user saved to DB with correct username; password is hashed (not plain text).
        """
        user = make_user("alice", "s3cur3pass")
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(User.objects.get(pk=user.pk).username, "alice")
        self.assertNotEqual(user.password, "s3cur3pass")  # must be hashed

    def test_user_fields(self):
        """
        AbstractUser provides first_name, last_name, email — required by FR-1.3.
        Expect: all three fields are writable and persisted.
        """
        user = User.objects.create_user(
            username="bob",
            password="pass",
            first_name="Bob",
            last_name="Smith",
            email="bob@example.com",
        )
        fetched = User.objects.get(pk=user.pk)
        self.assertEqual(fetched.first_name, "Bob")
        self.assertEqual(fetched.last_name, "Smith")
        self.assertEqual(fetched.email, "bob@example.com")


# ===========================================================================
# 2. Library model
# ===========================================================================

class LibraryModelTests(TestCase):
    """Test: Library ownership, is_full property, and song counting."""

    def test_library_created_and_owned(self):
        """
        Create a Library linked to a User.
        Expect: Library exists with correct owner and 0 songs.
        """
        user = make_user()
        library = make_library(user)
        self.assertEqual(library.owner, user)
        self.assertEqual(library.songs.count(), 0)

    def test_library_is_not_full_below_limit(self):
        """
        Add 19 songs to a library.
        Expect: is_full returns False.
        """
        user = make_user()
        lib = make_library(user)
        for _ in range(19):
            Song.objects.create(library=lib)
        self.assertFalse(lib.is_full)

    def test_library_is_full_at_limit(self):
        """
        Add exactly 20 songs (bypassing clean() via objects.create directly on Song).
        Expect: is_full returns True.
        """
        user = make_user()
        lib = make_library(user)
        for _ in range(20):
            # Use objects.create to bypass the 20-limit ValidationError so we
            # can test is_full in isolation
            Song.objects.create(library=lib)
        self.assertTrue(lib.is_full)


# ===========================================================================
# 3. Song model — 20-song limit constraint
# ===========================================================================

class SongLimitTests(TestCase):
    """Test: domain constraint that a Library cannot exceed 20 songs."""

    def _fill_library(self, library, count=20):
        for _ in range(count):
            Song.objects.create(library=library)

    def test_song_created_within_limit(self):
        """
        Create the 20th song via save() (which calls clean()).
        Expect: Song saved successfully, library has 20 songs.
        """
        user = make_user()
        lib = make_library(user)
        self._fill_library(lib, count=19)
        song = Song(library=lib)
        song.save()  # 20th — should succeed
        self.assertEqual(lib.songs.count(), 20)

    def test_song_blocked_over_limit(self):
        """
        Attempt to create a 21st song via save() on a full library.
        Expect: ValidationError is raised; song count remains 20.
        """
        user = make_user()
        lib = make_library(user)
        self._fill_library(lib, count=20)
        song = Song(library=lib)
        with self.assertRaises(ValidationError):
            song.save()
        self.assertEqual(lib.songs.count(), 20)

    def test_song_private_by_default(self):
        """
        Create a Song without specifying is_private.
        Expect: is_private is True (FR-3.2 — private by default).
        """
        user = make_user()
        lib = make_library(user)
        song = Song.objects.create(library=lib)
        self.assertTrue(song.is_private)


# ===========================================================================
# 4. Metadata model
# ===========================================================================

class MetadataModelTests(TestCase):
    """Test: Metadata composition on Song (title, mood, theme, occasion)."""

    def test_metadata_created_and_linked(self):
        """
        Attach Metadata to a Song.
        Expect: song.metadata accessible; title, mood, occasion saved correctly.
        """
        user = make_user()
        lib = make_library(user)
        song = make_song(lib)
        meta = Metadata.objects.create(
            song=song, title="Summer Vibes", mood="happy",
            theme="beach", occasion="party"
        )
        self.assertEqual(song.metadata.title, "Summer Vibes")
        self.assertEqual(song.metadata.mood, "happy")
        self.assertEqual(meta.song, song)

    def test_song_str_uses_metadata_title(self):
        """
        Song.__str__ should return the Metadata title once attached.
        Expect: str(song) == "Summer Vibes".
        """
        user = make_user()
        lib = make_library(user)
        song = make_song(lib)
        Metadata.objects.create(
            song=song, title="Summer Vibes", mood="calm",
            theme="sea", occasion="relaxation"
        )
        self.assertEqual(str(song), "Summer Vibes")


# ===========================================================================
# 5. VoiceStyle model
# ===========================================================================

class VoiceStyleModelTests(TestCase):
    """Test: VoiceStyle composition on Song with correct choices."""

    def test_voice_style_choices(self):
        """
        Create one Song per voice style.
        Expect: each VoiceStyle persisted with the correct style value.
        """
        user = make_user()
        lib = make_library(user)
        for style in VoiceStyle.Style:
            song = make_song(lib)
            vs = VoiceStyle.objects.create(song=song, style=style)
            self.assertEqual(vs.style, style)
            self.assertEqual(vs.song, song)


# ===========================================================================
# 6. Lyrics model
# ===========================================================================

class LyricsModelTests(TestCase):
    """Test: Lyrics modes — custom, AI-generated, instrumental."""

    def test_custom_lyrics(self):
        """
        Create Lyrics with custom content.
        Expect: mode == 'custom', content preserved.
        """
        user = make_user()
        lib = make_library(user)
        song = make_song(lib)
        lyrics = Lyrics.objects.create(
            song=song, mode=Lyrics.Mode.CUSTOM, content="La la la"
        )
        self.assertEqual(lyrics.mode, Lyrics.Mode.CUSTOM)
        self.assertEqual(lyrics.content, "La la la")

    def test_instrumental_lyrics_empty_content(self):
        """
        Create Lyrics in instrumental mode with no content.
        Expect: mode == 'instrumental', content is empty string.
        """
        user = make_user()
        lib = make_library(user)
        song = make_song(lib)
        lyrics = Lyrics.objects.create(
            song=song, mode=Lyrics.Mode.INSTRUMENTAL, content=""
        )
        self.assertEqual(lyrics.mode, Lyrics.Mode.INSTRUMENTAL)
        self.assertEqual(lyrics.content, "")

    def test_ai_generated_lyrics_default(self):
        """
        Create Lyrics without specifying mode.
        Expect: default mode is 'ai_generated' (FR-2.5).
        """
        user = make_user()
        lib = make_library(user)
        song = make_song(lib)
        lyrics = Lyrics.objects.create(song=song)
        self.assertEqual(lyrics.mode, Lyrics.Mode.AI_GENERATED)


# ===========================================================================
# 7. SharedLink model
# ===========================================================================

class SharedLinkModelTests(TestCase):
    """Test: SharedLink UUID token generation, uniqueness, and ownership."""

    def test_shared_link_token_is_uuid(self):
        """
        Create a SharedLink.
        Expect: token is a valid UUID, auto-generated server-side.
        """
        user = make_user()
        lib = make_library(user)
        song = make_song(lib)
        link = SharedLink.objects.create(song=song, created_by=user)
        self.assertIsInstance(link.token, uuid.UUID)

    def test_shared_link_tokens_are_unique(self):
        """
        Create two SharedLinks for two different songs.
        Expect: their tokens are different (uniqueness constraint).
        """
        user = make_user()
        lib = make_library(user)
        song1 = make_song(lib)
        song2 = make_song(lib)
        link1 = SharedLink.objects.create(song=song1, created_by=user)
        link2 = SharedLink.objects.create(song=song2, created_by=user)
        self.assertNotEqual(link1.token, link2.token)

    def test_shared_link_deletes_with_song(self):
        """
        Delete a Song that has a SharedLink.
        Expect: SharedLink is also deleted (CASCADE).
        """
        user = make_user()
        lib = make_library(user)
        song = make_song(lib)
        SharedLink.objects.create(song=song, created_by=user)
        self.assertEqual(SharedLink.objects.count(), 1)
        song.delete()
        self.assertEqual(SharedLink.objects.count(), 0)


# ===========================================================================
# 8. CRUD operations via ORM
# ===========================================================================

class CRUDOperationsTests(TestCase):
    """Test: Create, Read, Update, Delete on core domain entities via ORM."""

    def test_create_and_read_song(self):
        """
        Create a full Song (with Metadata, VoiceStyle, Lyrics).
        Expect: Song retrievable from DB with all composed entities intact.
        """
        user = make_user()
        lib = make_library(user)
        song = make_full_song(lib, title="CRUD Test Song")
        fetched = Song.objects.select_related(
            "metadata", "voice_style", "lyrics"
        ).get(pk=song.pk)
        self.assertEqual(fetched.metadata.title, "CRUD Test Song")
        self.assertEqual(fetched.voice_style.style, VoiceStyle.Style.MALE)
        self.assertEqual(fetched.lyrics.mode, Lyrics.Mode.AI_GENERATED)

    def test_update_song_metadata(self):
        """
        Update a Song's Metadata title.
        Expect: new title persisted and readable.
        """
        user = make_user()
        lib = make_library(user)
        song = make_full_song(lib, title="Old Title")
        song.metadata.title = "New Title"
        song.metadata.save()
        self.assertEqual(Metadata.objects.get(pk=song.metadata.pk).title, "New Title")

    def test_delete_song(self):
        """
        Delete a Song.
        Expect: Song removed from DB; composed Metadata/VoiceStyle/Lyrics also removed.
        """
        user = make_user()
        lib = make_library(user)
        song = make_full_song(lib)
        song_pk = song.pk
        song.delete()
        self.assertFalse(Song.objects.filter(pk=song_pk).exists())
        self.assertFalse(Metadata.objects.filter(song_id=song_pk).exists())
        self.assertFalse(VoiceStyle.objects.filter(song_id=song_pk).exists())
        self.assertFalse(Lyrics.objects.filter(song_id=song_pk).exists())

    def test_update_song_privacy(self):
        """
        Flip a Song from private to public.
        Expect: is_private is False after save.
        """
        user = make_user()
        lib = make_library(user)
        song = make_song(lib)
        self.assertTrue(song.is_private)
        song.is_private = False
        song.save()
        self.assertFalse(Song.objects.get(pk=song.pk).is_private)


# ===========================================================================
# 9. View — /library/ access control
# ===========================================================================

class LibraryViewTests(TestCase):
    """Test: GET /library/ authentication gate and correct response payload."""

    def test_library_redirects_unauthenticated(self):
        """
        Request GET /library/ without logging in.
        Expect: 302 redirect to the login page (FR-1.4).
        """
        response = self.client.get(reverse("music:library"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_library_returns_200_for_authenticated_user(self):
        """
        Log in and request GET /library/.
        Expect: 200 OK with JSON containing 'songs' list.
        """
        user = make_user()
        make_library(user)
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("music:library"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("songs", data)
        self.assertEqual(data["owner"], "testuser")

    def test_library_shows_only_completed_songs(self):
        """
        Library has one completed and one pending song.
        Expect: only the completed song appears in the response.
        """
        user = make_user()
        lib = make_library(user)
        completed = make_full_song(lib, title="Done Song", status=Song.Status.COMPLETED)
        make_full_song(lib, title="Pending Song", status=Song.Status.PENDING)
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("music:library"))
        data = response.json()
        self.assertEqual(data["song_count"], 1)
        self.assertEqual(data["songs"][0]["title"], "Done Song")


# ===========================================================================
# 10. View — /songs/<id>/ ownership check
# ===========================================================================

class SongDetailViewTests(TestCase):
    """Test: GET /songs/<id>/ returns detail for owner; blocks other users."""

    def test_song_detail_returns_full_data_for_owner(self):
        """
        Owner requests their song's detail.
        Expect: 200 OK with metadata, voice_style, and lyrics in JSON.
        """
        user = make_user()
        lib = make_library(user)
        song = make_full_song(lib, title="Owner Song")
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("music:song_detail", args=[song.pk]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["metadata"]["title"], "Owner Song")
        self.assertIn("voice_style", data)
        self.assertIn("lyrics", data)

    def test_song_detail_blocked_for_non_owner(self):
        """
        Another authenticated user requests a song they don't own.
        Expect: 404 Not Found (ownership enforced at query level).
        """
        owner = make_user("owner", "pass1")
        other = make_user("other", "pass2")
        lib = make_library(owner)
        song = make_full_song(lib)
        self.client.login(username="other", password="pass2")
        response = self.client.get(reverse("music:song_detail", args=[song.pk]))
        self.assertEqual(response.status_code, 404)

    def test_song_detail_redirects_unauthenticated(self):
        """
        Unauthenticated request to song detail.
        Expect: 302 redirect to login (FR-1.4).
        """
        response = self.client.get(reverse("music:song_detail", args=[999]))
        self.assertEqual(response.status_code, 302)


# ===========================================================================
# 11. View — /share/<uuid>/ guest vs authenticated access
# ===========================================================================

class SharedLinkViewTests(TestCase):
    """Test: shared link enforces metadata-only for guests, audio for auth users."""

    def _setup_shared_song(self):
        user = make_user()
        lib = make_library(user)
        song = make_full_song(lib, title="Shared Song")
        song.is_private = False
        song.save()
        link = SharedLink.objects.create(song=song, created_by=user)
        return user, song, link

    def test_guest_sees_metadata_no_audio(self):
        """
        Unauthenticated user visits a shared link.
        Expect: 200 OK, metadata fields present, audio_url is None, login message shown (FR-5.3).
        """
        _, _, link = self._setup_shared_song()
        response = self.client.get(reverse("music:shared_link", args=[link.token]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["title"], "Shared Song")
        self.assertIsNone(data["audio_url"])
        self.assertIn("Log in", data["message"])

    def test_authenticated_user_receives_audio_url_field(self):
        """
        Authenticated user visits a shared link.
        Expect: 200 OK, metadata present, audio_url key present (may be None if no file uploaded).
        """
        user, _, link = self._setup_shared_song()
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("music:shared_link", args=[link.token]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("audio_url", data)
        self.assertNotIn("message", data)

    def test_private_song_hidden_from_guest(self):
        """
        A private song has a SharedLink but the visitor is unauthenticated.
        Expect: 404 Not Found — private songs are not exposed via direct URL to guests.
        """
        user = make_user()
        lib = make_library(user)
        song = make_full_song(lib, title="Private Song")
        # is_private remains True (default)
        link = SharedLink.objects.create(song=song, created_by=user)
        response = self.client.get(reverse("music:shared_link", args=[link.token]))
        self.assertEqual(response.status_code, 404)
