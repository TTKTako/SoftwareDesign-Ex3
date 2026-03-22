# Cithara AI Music Generator — Django Backend

Django 4.2 web application implementing the domain model for the Cithara AI Music Generator.

---

## Requirements

- Python 3.10+
- pip

---

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/TTKTako/SoftwareDesign-Ex3.git
cd Exercise3
```

### 2. Create and activate a virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```
or
```bash
pip3 install -r requirements.txt
```

### 4. Apply migrations

```bash
python manage.py migrate
```

### 5. Create a superuser (for Django Admin access)

```bash
python manage.py createsuperuser
```

### 6. Run the development server

```bash
python manage.py runserver
```

The application is available at **http://127.0.0.1:8000/**  
The admin interface is available at **http://127.0.0.1:8000/admin/**

---

## Project Structure

```
Exercise3/
├── config/                 # Django project configuration
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── music/                  # Core domain application
│   ├── migrations/
│   │   └── 0001_initial.py
│   ├── models.py           # Domain models
│   ├── admin.py            # Django Admin CRUD registrations
│   ├── views.py            # Simple JSON views
│   └── urls.py             # URL patterns
├── manage.py
└── db.sqlite3              # SQLite database (created after migrate)
```

---

## Domain Models

Implemented directly from the domain diagram:

| Model | Description | Key Constraints |
|---|---|---|
| `User` | Custom user (extends `AbstractUser`) | — |
| `Library` | Personal song library, one per user | Max 20 songs enforced on `Song.save()` |
| `Song` | Generated audio track | Default `is_private=True`; status lifecycle |
| `Metadata` | Title, mood, theme, occasion, duration | OneToOne composition of `Song` |
| `VoiceStyle` | Voice type (Male/Female/Robotic/Duet) | OneToOne composition of `Song` |
| `Lyrics` | Custom / AI-generated / Instrumental | OneToOne composition of `Song` |
| `SharedLink` | UUID-based secure share token | OneToOne with `Song`; FK to creator `User` |

> **Not persisted as models:**  
> `AudioPlayer` — pure UI component, no persistent state.  
> `AIGenerationAPI` — external third-party service; integration tracked via `Song.status` field.

---

## CRUD Operations

### Django Admin (full CRUD)

Log in at `/admin/` with the superuser credentials.  
All seven domain models are registered with search, filter, and inline editing.  
`Song` admin embeds `Metadata`, `VoiceStyle`, and `Lyrics` as inline forms.

### API Endpoints (Read)

| Endpoint | Auth required | Description |
|---|---|---|
| `GET /library/` | Yes | List all completed songs in the user's library |
| `GET /songs/<id>/` | Yes | Full detail for a specific song (owner only) |
| `GET /share/<uuid>/` | No* | Public metadata; audio URL only for logged-in users |

*Guests see metadata; must log in to receive the audio stream URL (FR-5.3).

---

## Security Notes

- `AUTH_USER_MODEL = 'music.User'` — custom user model, ready for Argon2 and OAuth integration.
- Private songs cannot be accessed via URL manipulation; `song_detail_view` filters by `library__owner`.
- `SharedLink.token` is a UUID generated server-side (`editable=False`).
- API keys for the AI service must be stored in environment variables (never committed).

---

## CRUD Functionality (Test)

> TA(s) Read this for The Submission

### How to Run (for TA)

```bash
# From the project root (with venv activated):
python manage.py test music --verbosity=2
```

Expected final output:
```
Ran 30 tests in ~3s
OK
```

Django creates a **temporary in-memory test database**, runs all tests, then destroys it — the production `db.sqlite3` is never touched.

---

### Test Groups and Expected Results

#### 1. `UserModelTests` — User model creation

| Test | What it does | Expected result |
|---|---|---|
| `test_create_user` | Creates a User and checks the record in DB | 1 user saved; password is hashed (not plain text) |
| `test_user_fields` | Sets first_name, last_name, email and re-reads from DB | All three fields persisted correctly |

---

#### 2. `LibraryModelTests` — Library ownership and capacity

| Test | What it does | Expected result |
|---|---|---|
| `test_library_created_and_owned` | Creates a Library linked to a User | `library.owner` matches the user; 0 songs |
| `test_library_is_not_full_below_limit` | Adds 19 songs directly | `is_full` returns `False` |
| `test_library_is_full_at_limit` | Adds exactly 20 songs directly | `is_full` returns `True` |

---

#### 3. `SongLimitTests` — 20-song hard cap (FR-2.1 / domain constraint)

| Test | What it does | Expected result |
|---|---|---|
| `test_song_created_within_limit` | Saves the 20th song via `song.save()` | Succeeds; library has 20 songs |
| `test_song_blocked_over_limit` | Tries to save a 21st song via `song.save()` | `ValidationError` raised; count stays at 20 |
| `test_song_private_by_default` | Creates a Song with no explicit privacy setting | `is_private == True` |

---

#### 4. `MetadataModelTests` — Metadata composition

| Test | What it does | Expected result |
|---|---|---|
| `test_metadata_created_and_linked` | Attaches Metadata (title, mood, occasion) to a Song | `song.metadata.title` readable; back-reference `meta.song` correct |
| `test_song_str_uses_metadata_title` | Calls `str(song)` after attaching Metadata | Returns `"Summer Vibes"` (the Metadata title) |

---

#### 5. `VoiceStyleModelTests` — Voice style choices

| Test | What it does | Expected result |
|---|---|---|
| `test_voice_style_choices` | Creates one Song per style: Male, Female, Robotic, Duet | Each `VoiceStyle` saved with the correct `style` value |

---

#### 6. `LyricsModelTests` — Lyrics modes

| Test | What it does | Expected result |
|---|---|---|
| `test_custom_lyrics` | Creates Lyrics with `mode=custom` and text content | Mode and content persisted correctly |
| `test_instrumental_lyrics_empty_content` | Creates Lyrics with `mode=instrumental` and empty content | Content is `""`, mode is `instrumental` |
| `test_ai_generated_lyrics_default` | Creates Lyrics without specifying mode | Default mode is `ai_generated` |

---

#### 7. `SharedLinkModelTests` — Secure share token

| Test | What it does | Expected result |
|---|---|---|
| `test_shared_link_token_is_uuid` | Creates a SharedLink | `token` is a valid `uuid.UUID` instance |
| `test_shared_link_tokens_are_unique` | Creates two SharedLinks | Both tokens are different |
| `test_shared_link_deletes_with_song` | Deletes a Song that owns a SharedLink | SharedLink is also removed (CASCADE) |

---

#### 8. `CRUDOperationsTests` — Full ORM Create / Read / Update / Delete

| Test | What it does | Expected result |
|---|---|---|
| `test_create_and_read_song` | Creates a Song with Metadata, VoiceStyle, Lyrics; re-reads from DB | All three composed entities readable via ORM |
| `test_update_song_metadata` | Changes Metadata title and saves | New title persisted when re-fetched |
| `test_delete_song` | Deletes a Song | Song and all composed records removed from DB |
| `test_update_song_privacy` | Flips `is_private` from True to False | `is_private == False` after DB re-read |

---

#### 9. `LibraryViewTests` — `GET /library/` authentication gate

| Test | What it does | Expected result |
|---|---|---|
| `test_library_redirects_unauthenticated` | Requests `/library/` without logging in | 302 redirect to `/accounts/login/` |
| `test_library_returns_200_for_authenticated_user` | Logs in and requests `/library/` | 200 OK; JSON contains `songs` list and correct `owner` |
| `test_library_shows_only_completed_songs` | Library has one completed and one pending song | Only the completed song appears in the response |

---

#### 10. `SongDetailViewTests` — `GET /songs/<id>/` ownership check

| Test | What it does | Expected result |
|---|---|---|
| `test_song_detail_returns_full_data_for_owner` | Owner requests their own song | 200 OK; metadata, voice_style, lyrics all in JSON |
| `test_song_detail_blocked_for_non_owner` | Different authenticated user requests a song they don't own | 404 Not Found (ownership enforced at DB query level) |
| `test_song_detail_redirects_unauthenticated` | Unauthenticated request | 302 redirect to login |

---

#### 11. `SharedLinkViewTests` — `GET /share/<uuid>/` guest vs authenticated access (FR-5.3)

| Test | What it does | Expected result |
|---|---|---|
| `test_guest_sees_metadata_no_audio` | Guest visits a public shared link | 200 OK; song title/mood present; `audio_url` is `null`; login prompt message included |
| `test_authenticated_user_receives_audio_url_field` | Logged-in user visits a shared link | 200 OK; `audio_url` key present; no login message |
| `test_private_song_hidden_from_guest` | Guest visits a shared link for a **private** song | 404 Not Found |

