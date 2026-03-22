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
