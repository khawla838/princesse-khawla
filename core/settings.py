from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
env.read_env(env_file=str(BASE_DIR / ".env"))

SECRET_KEY = env("SECRET_KEY")

DEBUG = env.bool("DEBUG", default=True)

ASGI_APPLICATION = 'core.asgi.application'

INSTALLED_APPS = [
    "modeltranslation",
    "cities_light",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "strawberry.django",
    "strawberry_django",
    "tinymce",
    "fcm_django",
    "channels",
    "api",
    "guard",
    "shared",
    "partners",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

ASGI_APPLICATION = 'core.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

WSGI_APPLICATION = "core.wsgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"

LANGUAGES = [
    ("en", "English"),
    ("fr", "Français"),
]

LOCALE_PATHS = [
    BASE_DIR / "locale",
]

TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = "/static/"
MEDIA_URL = "/upload/"
MEDIA_ROOT = BASE_DIR / "upload"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOW_CREDENTIALS = True
CORS_PREFLIGHT_MAX_AGE = 86400
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

TINYMCE_DEFAULT_CONFIG = {
    "height": 360,
    "width": "100%",
    "cleanup_on_startup": True,
    "custom_undo_redo_levels": 20,
    "selector": "textarea",
    "plugins": "link lists code",
    "toolbar": "undo redo | bold italic | bullist numlist | link code",
}

CITIES_LIGHT_TRANSLATION_LANGUAGES = ["en", "fr", "ar"]
CITIES_LIGHT_INCLUDE_COUNTRIES = ["TN", "MA", "DZ", "LY", "EG", "LB", "YE", "SY"]
CITIES_LIGHT_INCLUDE_CITY_TYPES = ["PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLC"]

LOGIN_URL = "/auth/login/"
LOGIN_REDIRECT_URL = "/partners/dashboard/"
LOGOUT_REDIRECT_URL = "/auth/login/"

SITE_URL_BASE = env("SITE_URL", default="http://localhost:8000")

if DEBUG:
    SITE_URL = "http://localhost:8000"
    CORS_ALLOW_ALL_ORIGINS = DEBUG
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "127.0.0.1:8000"]
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("EMAIL_HOST")
    EMAIL_PORT = env.int("EMAIL_PORT")
    EMAIL_HOST_USER = env("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS")
    EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL")
    DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="FielMedina <noreply@fielmedina.com>")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
    STATICFILES_DIRS = [
        BASE_DIR / "static",
    ]
    STATIC_ROOT = BASE_DIR / "staticfiles"

else:
    SITE_URL = env("SITE_URL")
    CORS_ALLOWED_ORIGINS = [
        "https://fielmedina.com",
        "https://www.fielmedina.com",
    ]
    ALLOWED_HOSTS = ["mystory.fielmedina.com"]
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("EMAIL_HOST")
    EMAIL_PORT = env.int("EMAIL_PORT")
    EMAIL_HOST_USER = env("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS")
    EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL")
    DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="FielMedina <noreply@fielmedina.com>")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME"),
            "USER": env("DB_USER"),
            "PASSWORD": env("DB_PASSWORD"),
            "HOST": env("DB_HOST"),
            "PORT": env("DB_PORT"),
        }
    }
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    STATIC_ROOT = BASE_DIR / "static"


PUBLIC_GROQ_API_KEI = env("PUBLIC_GROQ_API_KEI")
PUBLIC_SHORT_API = env("PUBLIC_SHORT_API")
SHORT_IO_DOMAIN = env("SHORT_IO_DOMAIN")
SHORT_IO_FOLDER_ID = env("SHORT_IO_FOLDER_ID")
DJANGO_ADMIN_URL = env("DJANGO_ADMIN_URL")

# ── Firebase ──────────────────────────────────────────────────────────────────
GOOGLE_APPLICATION_CREDENTIALS = env(
    "GOOGLE_APPLICATION_CREDENTIALS",
    default=str(BASE_DIR / "fielmedinasousse-firebase-adminsdk-fbsvc-32939c9c5a.json"),
)

FCM_DJANGO_SETTINGS = {
    "FCM_SERVER_KEY": env("FCM_SERVER_KEY", default=None),
    "ONE_DEVICE_PER_USER": False,
    "DELETE_INACTIVE_DEVICES": False,
    "UPDATE_ON_DUPLICATE_REG_ID": True,
    "APP_VERBOSE_NAME": "FielMedina",
}

FIREBASE_CLIENT_CONFIG = {
    "apiKey": env("FIREBASE_API_KEY", default="AIzaSyC7ddaaSc5fo_o8vqShhyf2D9e5fCXJvso"),
    "authDomain": env("FIREBASE_AUTH_DOMAIN", default="fielmedinasousse.firebaseapp.com"),
    "projectId": env("FIREBASE_PROJECT_ID", default="fielmedinasousse"),
    "storageBucket": env("FIREBASE_STORAGE_BUCKET", default="fielmedinasousse.firebasestorage.app"),
    "messagingSenderId": env("FIREBASE_MESSAGING_SENDER_ID", default="797838304877"),
    "appId": env("FIREBASE_APP_ID", default="1:797838304877:web:e586351927c5dd38954164"),
    "measurementId": env("FIREBASE_MEASUREMENT_ID", default="G-KMEWT7N3ND"),
}

# ── Konnect ───────────────────────────────────────────────────────────────────
KONNECT_API_KEY = env("KONNECT_API_KEY", default="")
KONNECT_WALLET_ID = env("KONNECT_WALLET_ID", default="")
KONNECT_BASE_URL = env(
    "KONNECT_BASE_URL",
    default="https://api.sandbox.konnect.network/api/v2",
)
KONNECT_RECEIVER_WALLET_ID = env("KONNECT_RECEIVER_WALLET_ID", default="")