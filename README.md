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
cd SoftwareDesign-Ex3
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

### 4. Configure environment variables

Create a `.env` file in the project root by copying the sample below:

```env
SECRET_KEY="django-insecure-your-secret-key-here"
```

> **Note:** Never commit your real `.env` file to version control. Add it to `.gitignore`.

### 5. Apply migrations

```bash
python manage.py migrate
```

### 6. Create a superuser (for Django Admin access)

```bash
python manage.py createsuperuser
```

### 7. Run the development server

```bash
python manage.py runserver
```

The application is available at **http://127.0.0.1:8000/**  
The admin interface is available at **http://127.0.0.1:8000/admin/**

---

## Project Structure

```
SoftwareDesign-Ex3/
├── config/                 # Django project configuration
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── music/                  # Core domain application
│   ├── migrations/
│   │   └── 0001_initial.py
│   ├── models/             # Domain models (one file per entity)
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── library.py
│   │   ├── song.py
│   │   ├── metadata.py
│   │   ├── voice_style.py
│   │   ├── lyrics.py
│   │   └── shared_link.py
│   ├── admin.py            # Django Admin CRUD registrations
│   ├── views.py            # Simple JSON views
│   └── urls.py             # URL patterns
├── manage.py
└── db.sqlite3              # SQLite database (created after migrate)
```

---

## Domain Models

Adapted from the Exercise 2 domain diagram with implementation-driven refinements
(see [Domain Model Changes from Exercise 2](#domain-model-changes-from-exercise-2) below):

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
> `AIGenerationAPI` — external third-party service; interaction tracked via `Song.status`.

---

## Domain Model Changes from Exercise 2

The following diagram reflects the **implemented** model. Differences from the Exercise 2 submission are explained in the table below.

![domain diagram](https://github.com/TTKTako/SoftwareDesign-Ex3/diagram.png)

### Change Log vs Exercise 2

| # | Exercise 2 Entity | Change | Justification |
|---|---|---|---|
| 1 | `AuthenticatedUser` / `Guest` (two subtypes of `User`) | Merged into a single `User` model | Django's built-in session framework already distinguishes authenticated vs. unauthenticated requests at the view layer via `request.user.is_authenticated`. A separate `Guest` DB row has no persistent attributes and would be empty; an inheritance table adds schema complexity with zero benefit. |
| 2 | `AudioPlayer` | Removed from DB layer | `AudioPlayer` is a front-end UI component (HTML5 `<audio>` element). It holds no data that needs to be persisted — playback position, volume, etc. are ephemeral browser state. |
| 3 | `AIGenerationAPI` | Removed from DB layer | The AI service is an external third-party API. It has no persistent attributes of its own in our schema. Its interaction is represented by the `Song.status` lifecycle (`PENDING → GENERATING → COMPLETED / FAILED`), which gives the UI all the feedback described in FR-2.6 and FR-2.7. |
| 4 | `Song` (no status) | Added `status` field (`TextChoices`: PENDING, GENERATING, COMPLETED, FAILED) | Required to implement background generation (FR-2.7), visual loading feedback (FR-2.6), and to filter the library view to show only completed songs (FR-3.3). |
| 5 | `Song` (no file) | Added `audio_file` (FileField) and `created_at` (DateTime) | `audio_file` stores the path to the generated audio on disk, required for playback (FR-4.x) and download (FR-5.1). `created_at` is needed for the library listing which displays creation date (FR-3.3). |
| 6 | `Metadata` (generic attributes) | Made `mood` and `occasion` concrete `TextChoices` enums | FR-2.2 lists specific valid values for mood and occasion. Using enums enforces data integrity at the DB level and drives the UI drop-downs deterministically. |
| 7 | `Lyrics` (implicit) | Added explicit `mode` (`TextChoices`: CUSTOM, AI_GENERATED, INSTRUMENTAL) and `content` | FR-2.4 and FR-2.5 require distinguishing between user-provided, AI-generated, and instrumental songs. The original diagram named the class but did not specify how these three cases were differentiated. |
| 8 | `VoiceStyle` (generic) | Added `style` as `TextChoices` (MALE, FEMALE, ROBOTIC, DUET) | FR-2.3 defines exactly four voice options. Enumerating them in code prevents invalid values and drives UI selection. |

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

## CRUD Functionality

### How to Run

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

