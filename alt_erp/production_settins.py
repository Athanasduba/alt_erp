from pathlib import Path
from celery.schedules import crontab
import os
import dj_database_url
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Security ---
SECRET_KEY = config("DJANGO_SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = ["*"]  # or restrict to your Railway domain

# --- Celery configuration ---
CELERY_BROKER_URL = config("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL

CELERY_BEAT_SCHEDULE = {
    "check-overdue-invoices-every-midnight": {
        "task": "invoices.tasks.check_overdue_invoices",
        "schedule": crontab(hour=0, minute=0),
    },
    "generate-weekly-lease-invoices": {
        "task": "invoices.tasks.run_weekly_lease_generation",
        "schedule": crontab(day_of_week="monday", hour=8, minute=0),
    },
    "generate-installment-invoices": {
        "task": "invoices.tasks.run_installment_generation",
        "schedule": crontab(hour=8, minute=0),
    },
    "apply-account-balances": {
        "task": "accounting.tasks.apply_account_balances_to_invoices",
        "schedule": crontab(day_of_week="monday", hour=1, minute=0),
    },
}

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django_celery_results",
    "django_celery_beat",
    "customers.apps.CustomersConfig",
    "invoices.apps.InvoicesConfig",
    "motorcycles.apps.MotorcyclesConfig",
    "agents.apps.AgentsConfig",
    "warehouses.apps.WarehousesConfig",
    "users.apps.UsersConfig",
    "sales.apps.SalesConfig",
    "dashboard.apps.DashboardConfig",
    "accounting.apps.AccountingConfig",
    "payments.apps.PaymentsConfig",
    "reports.apps.ReportsConfig",
    "notifications",
    "monitoring",
    "widget_tweaks",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # ✅ added for static files
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "users.middleware.SessionSecurityMiddleware",
]

ROOT_URLCONF = "alt_erp.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "alt_erp" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "users.context_processors.role_flags",
                "reports.context_processors.reports_context",
            ],
        },
    },
]

WSGI_APPLICATION = "alt_erp.wsgi.application"

# --- Database (Railway injects DATABASE_URL) ---
DATABASES = {
    "default": dj_database_url.config(
        default=config("DATABASE_URL"),
        conn_max_age=600,
        ssl_require=True,
    )
}

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Dar_es_Salaam"
USE_I18N = True
USE_TZ = True

# --- Static files ---
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# --- Media files ---
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- Email (console for now, replace with SMTP in prod) ---
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}

# --- Session Security ---
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 1800
SESSION_SAVE_EVERY_REQUEST = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True

# --- Authentication Redirects ---
LOGIN_URL = "/users/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/users/login/"

# --- Logging (simplified for Railway) ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
