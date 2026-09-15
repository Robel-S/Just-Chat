# AGENTS.md

## Project shape

Just-Chat is a Django 6 application with Django REST Framework APIs, Django Channels WebSockets, and React page entry points built by Vite.

- `manage.py`: Django command entry point.
- `just_chat/`: project-wide Django configuration and top-level routing.
- `accounts/`: custom user model and registration/profile behavior.
- `pages/`: chat, message, friendship, attachment, REST API, and WebSocket behavior.
- `assets/`: editable React/Vite source.
- `templates/`: Django page shells and authentication templates.
- `static/css/`: editable page styles.
- `static/js/` and `static/manifest.json`: Vite build output; prefer editing `assets/`.
- `media/`: local uploaded/user content; do not treat it as source code.
- `node_modules/`, `.venv/`, and `__pycache__/`: dependencies/generated state; skip when searching.

## Backend routing map

Start at `just_chat/urls.py` for HTTP routes. It delegates account routes to `accounts/urls.py` and application/API routes to `pages/urls.py`.

For an API change, follow this path:

`pages/urls.py` -> `pages/views.py` -> `pages/serializers.py` -> `pages/models.py`

- `pages/models.py`: friendships, friend requests, chats, memberships/unread counts, messages, and attachments.
- `pages/views.py`: DRF list/create/update/delete endpoints plus the `chats` and `friends` template views.
- `pages/serializers.py`: API payload shapes and read-only/computed fields.
- `pages/tests.py`: model, API, and WebSocket tests.
- `pages/migrations/`: schema history; create a new migration after model changes rather than editing applied migrations.
- `accounts/models.py`: `CustomUser` (configured by `AUTH_USER_MODEL`).
- `accounts/forms.py` and `accounts/views.py`: signup and profile-edit flows.
- `accounts/tests.py`: account model/view tests.

## Real-time message routing

For WebSocket behavior, follow:

`just_chat/asgi.py` -> `pages/routing.py` -> `pages/consumers.py`

- `/ws/chat/<chat_id>/`: chat connection and message delivery through `ChatConsumer`.
- `/ws/notifications/`: unread-count notifications through `NotificationConsumer`.
- `pages/message_composition.py`: Message creation, membership authorization, unread accounting, canonical projection, and post-commit live publication.
- `pages/apps.py`: Django application configuration.

When changing message payloads, inspect the consumer, corresponding serializer/model, and `assets/pages/chats.jsx` together.

## Frontend routing map

- `templates/chats.html` mounts `assets/pages/chats.jsx` into `#root`; styles are in `static/css/chats.css`.
- `templates/friends.html` mounts `assets/pages/friends.jsx` into `#root`; styles are in `static/css/friends.css`.
- `templates/loginbase.html`: shared authenticated-page shell/navigation.
- `templates/base.html`: shared authentication-page shell.
- `templates/registration/`: login, signup, and profile-edit pages; shared auth styles are in `static/css/registration.css`.
- `vite.config.js`: Vite inputs, dev server, manifest, and build-output configuration.

The React page files currently contain their components, fetch calls, and local state in the same file, so begin searches in the page entry point rather than looking for a separate component tree.

## Configuration and local services

- `just_chat/settings.py`: installed apps, PostgreSQL, cache/channel layer, templates, static/media, authentication, and Vite settings.
- `docker-compose.yml`: Django (`web`), PostgreSQL (`db`), Vite (`react`), and Redis services.
- `requirements.txt`: Python dependencies.
- `package.json`: frontend dependencies and `npm run dev` / `npm run build` scripts.
- `Dockerfile` and `assets/Dockerfile`: backend and frontend container definitions.

## Useful commands

Run these from the directory containing `manage.py`:

```powershell
python manage.py test
python manage.py check
python manage.py makemigrations
python manage.py migrate
npm run dev
npm run build
docker compose up --build
```

Because the default database host is the Docker service name `db`, Django commands run directly on the host may require local settings or the Compose stack.

## Search shortcuts

Prefer scoped searches that exclude generated and uploaded content:

```powershell
rg "search term" pages accounts assets templates static/css just_chat
rg --files pages accounts assets templates static/css just_chat
```

Before editing, check `git status --short` and preserve unrelated existing work. Do not edit generated bundles, dependency folders, uploaded media, or existing migrations unless the task specifically calls for it.

## Agent skills

### Issue tracker

Issues are tracked in this repository's GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

The default five-label triage vocabulary is used. See `docs/agents/triage-labels.md`.

### Domain docs

This repository uses a single-context domain-doc layout. See `docs/agents/domain.md`.
