from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-(6phaoex5!way0xb%whxu+%xr4d_jcxsfg$p9edrtyt0mlci)^'

DEBUG = True

ALLOWED_HOSTS = ['*']

# Настройка кастомной модели пользователя
AUTH_USER_MODEL = 'RateApp.User'

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'channels',
    'rest_framework',
    'rest_framework_simplejwt',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'RateApp',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'Rate.urls'

# Настройки статических файлов
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / "Rate" / "config" / "wwwroot",
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / "RateApp" / "templates",
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'Rate.wsgi.application'
ASGI_APPLICATION = 'Rate.asgi.application'

# Настройка Channels (WebSocket)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Настройки JWT (на основе настроек Ивана)
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# Настройки REST Framework для использования JWT по умолчанию
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'RateApp.middleware.CookieJWTAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    )
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'