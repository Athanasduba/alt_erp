from pathlib import Path
from celery.schedules import crontab
import os
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import platform
import dj_database_url   # ✅ added for Railway Postgres

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-qsgk^n1$-x4^m*zu(kj3#*^$o0*bj4glfg8l^9esky7&ywc%kd'
DEBUG = True
ALLOWED_HOSTS = []

# Celery configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
#CELERY_RESULT_BACKEND = 'redis://localhost:6379/0' #this is for local development
CELERY_RESULT_BACKEND = 'django-db'#this is for production hosting in railways

CELERY_BEAT_SCHEDULE = {
    # Nightly overdue invoice check
    'check-overdue-invoices-every-midnight': {
        'task': 'invoices.tasks.check_overdue_invoices',
        'schedule': crontab(hour=0, minute=0),
    },

    # Weekly invoice generation for leasing customers
    'generate-weekly-lease-invoices': {
        'task': 'invoices.tasks.run_weekly_lease_generation',
        'schedule': crontab(day_of_week='monday', hour=8, minute=0),
        
    },

    # Installment invoice generation (runs daily, task handles schedule internally)
    'generate-installment-invoices': {
        'task': 'invoices.tasks.run_installment_generation',
        'schedule': crontab(hour=8, minute=0),  # every day at 8 AM
    },

    # Weekly accounting balances application
    'apply-account-balances': {
        'task': 'accounting.tasks.apply_account_balances_to_invoices',
        'schedule': crontab(day_of_week='monday', hour=1, minute=0),
    },
}

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    "django_celery_results",   # ✅ required for TaskResult logs
    "django_celery_beat",      # ✅ required for beat schedule management

    # Custom apps with AppConfig
    'customers.apps.CustomersConfig',     # ✅ ensures signals are loaded
    'invoices.apps.InvoicesConfig',
    'motorcycles.apps.MotorcyclesConfig',
    'agents.apps.AgentsConfig',
    'warehouses.apps.WarehousesConfig',
    'users.apps.UsersConfig',
    'sales.apps.SalesConfig',
    'dashboard.apps.DashboardConfig',
    'accounting.apps.AccountingConfig',
    'payments.apps.PaymentsConfig',
    'reports.apps.ReportsConfig',  # ✅ add this line
    "notifications",
    "monitoring",
    "widget_tweaks",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'users.middleware.SessionSecurityMiddleware',
]

ROOT_URLCONF = 'alt_erp.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'alt_erp' / 'templates'],  # global templates folder
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'users.context_processors.role_flags',
                "reports.context_processors.reports_context",# my contex for motorcycle and customer
            ],
        },
    },
]

WSGI_APPLICATION = 'alt_erp.wsgi.application'

# ✅ Updated database config for Railway
raw_db_url = os.environ.get("DATABASE_URL")
if raw_db_url and raw_db_url.startswith("postgresql://"):
    raw_db_url = raw_db_url.replace("postgresql://", "postgres://", 1)

DATABASES = {
    'default': dj_database_url.parse(
        raw_db_url,
        conn_max_age=600,
        ssl_require=False
    )
}

AUTH_USER_MODEL = 'users.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Dar_es_Salaam'   # ✅ proper timezone for Tanzania
USE_I18N = True
USE_TZ = True

# --- Static files setup ---
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / "static",   # your custom CSS/JS/images
]
STATIC_ROOT = BASE_DIR / "staticfiles"  # for collectstatic in production

# --- Media files ---
MEDIA_URL = '/media/'
#MEDIA_ROOT = BASE_DIR / "media"/"contracts"
MEDIA_ROOT = BASE_DIR / "media"

# --- Email ---
MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}

# --- Session Security ---
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 1800
SESSION_SAVE_EVERY_REQUEST = False
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True

# --- Authentication Redirects ---
LOGIN_URL = '/users/login/'           # where unauthenticated users are sent
LOGIN_REDIRECT_URL = '/dashboard/'    # where users go after successful login
LOGOUT_REDIRECT_URL = '/users/login/' # where users go after logout

# --- Logging ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "signals_file_size": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "erp_signals.log"),
            "maxBytes": 5 * 1024 * 1024,  # 5 MB
            "backupCount": 5,
            "formatter": "verbose",
            "delay": True,  # ✅ prevents file lock issues on Windows
        },
        "signals_file_time": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "erp_signals_daily.log"),
            "when": "midnight",
            "interval": 1,
            "backupCount": 7,
            "formatter": "verbose",
            "delay": True,  # ✅ prevents PermissionError during rollover
        },
    },
    "loggers": {
        "": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "customers.signals": {
            "handlers": ["console", "signals_file_size", "signals_file_time"],
            "level": "INFO",
            "propagate": False,
        },
        "payments.signals": {
            "handlers": ["console", "signals_file_size", "signals_file_time"],
            "level": "INFO",
            "propagate": False,
        },
        "invoices.signals": {
            "handlers": ["console", "signals_file_size", "signals_file_time"],
            "level": "INFO",
            "propagate": False,
        },
        "notifications.signals": {
            "handlers": ["console", "signals_file_size", "signals_file_time"],
            "level": "INFO",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console", "signals_file_size", "signals_file_time"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# --- Celery Windows Compatibility ---
if platform.system() == "Windows":
    CELERYD_POOL = "solo"
    CELERY_WORKER_POOL = "solo"
    CELERY_WORKER_CONCURRENCY = 1
