from pathlib import Path
from datetime import timedelta
import dj_database_url
from environ import Env
import os

env = Env()
Env.read_env()
ENVIRONMENT = env('ENVIRONMENT', default='production')
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

import cloudinary
import cloudinary.uploader
import cloudinary.api

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'cloudinary_storage',
    'django.contrib.staticfiles',
    'channels',
    'cloudinary',
    'Account',
    'admin_panel',
    'newsletter',
    # 'notifications',
    "notifications.apps.NotificationsConfig",
    "django_filters",
    'order',
    'product',
    "debug_toolbar",

    
    'rest_framework',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'rest_framework.authtoken',

]

ASGI_APPLICATION = 'temmyCollection.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [env('CELERY_BROKER_URL')],
        },
    },
}

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "allauth.account.middleware.AccountMiddleware",
]

INTERNAL_IPS = [
    # ...
    "127.0.0.1",
    # ...
]

ROOT_URLCONF = 'temmyCollection.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'template'],
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

WSGI_APPLICATION = 'temmyCollection.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases


USE_RENDER_DB_LOCALLY = env.bool('USE_RENDER_DB_LOCALLY', default=False)
if ENVIRONMENT == 'development' and not USE_RENDER_DB_LOCALLY :
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': dj_database_url.parse(os.getenv('DATABASE_URL'))
    }

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'postgres',
#         'USER': 'postgres',
#         'PASSWORD': env('SUPABASE_DB_PASSWORD', default=''),
#         'HOST': 'db.ymkkxeaqopcgpvigqtlt.supabase.co',
#         'PORT': '5432',
#         'OPTIONS': {
#             'sslmode': 'require',  # <--- This is crucial for Supabase
#         },
#     }
# }




# DATABASES = {
#     "default": dj_database_url.parse(
#         env("DATABASE_URL"),
#         conn_max_age=600,
#         ssl_require=True,
#     ),
#     "sqlite_old": {
#         "ENGINE": "django.db.backends.sqlite3",
#         "NAME": BASE_DIR / "db.sqlite3",
#     },
# }







# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# MEDIA_URL = 'media/'
# MEDIA_ROOT = BASE_DIR / 'media/'

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

CLOUDINARY_URL = env('CLOUDINARY_URL')
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'


AUTH_USER_MODEL = "Account.Account"

CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:3001',
    "http://127.0.0.1:3000",
]

CORS_ALLOW_CREDENTIALS = True

SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
JWT_AUTH_SAMESITE = 'Lax'

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
]

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 8,

    "DEFAULT_AUTHENTICATION_CLASSES": [
        'Account.auth.CookieJWTAuthentication',
    ],

    "DEFAULT_PERMISSION_CLASSES": [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(seconds=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": [
            "openid",
            "email",
            "profile"
        ],
        "AUTH_PARAMS": {
            "access_type": "online",
            "prompt": "select_account"
        },
        "OAUTH_PKCE_ENABLED": True,
    }
}

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

from corsheaders.defaults import default_headers

# Keep the standard headers and append your custom cart_id header
CORS_ALLOW_HEADERS = list(default_headers) + [
    "cart_id",
    "formData",
]

# CORS_ALLOW_ALL_HEADERS = True

LOGIN_REDIRECT_URL = '/callback/'
# SOCIALACCOUNT_STORE_TOKENS = True
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_AUTO_SIGNUP = True


CELERY_BROKER_URL = env('CELERY_BROKER_URL')
# CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp-relay.brevo.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL')

FLUTTERWAVE_SECRET_KEY='FLWSECK_TEST-9e4517419bf700ba48ad2372d6e6c9b6-X'

BREVO_API_KEY = env("BREVO_API_KEY")
BREVO_LIST_ID = env("BREVO_LIST_ID")
BASE_URL = env('FRONTEND_BASEURL')
BREVO_SENDER_EMAIL = env("BREVO_SENDER_EMAIL", default="")
BREVO_SENDER_NAME = env("BREVO_SENDER_NAME",default="TemmyCollection",)
FRONTEND_URL = env("FRONTEND_URL",default="http://localhost:3000",)



# Keep your existing settings; add these variables separately.
VAPID_PUBLIC_KEY = os.environ.get(
    "VAPID_PUBLIC_KEY",
    "BBhyA5C9I8m-Xv0YJASAh8eaAR66kcGqHFcQgEl9sIpwbs-zHxUDvujHfgG2NuVmVS-8y6OoGR7s95bV-x3L7PE",
)

VAPID_PRIVATE_KEY = os.environ.get(
    "VAPID_PRIVATE_KEY",
    str(BASE_DIR / "private_key.pem"),
)

VAPID_ADMIN_EMAIL = os.environ.get(
    "VAPID_ADMIN_EMAIL",
    "mailto:admin@temmycollection.com",
)


# REST_FRAMEWORK = {
#     # Keep your existing DRF settings...
#     "DEFAULT_FILTER_BACKENDS": [
#         "django_filters.rest_framework.DjangoFilterBackend",
#         "rest_framework.filters.SearchFilter",
#         "rest_framework.filters.OrderingFilter",
#     ],
# }