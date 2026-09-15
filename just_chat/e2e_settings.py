from .settings import *  # noqa: F403


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / ".e2e.sqlite3",  # noqa: F405
    }
}

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
