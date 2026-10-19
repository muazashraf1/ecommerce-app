from .base import *

DEBUG = True

# In local mode, default to SQLite unless explicitly configured otherwise
if os.environ.get('USE_SQLITE', 'True').lower() in ('true', '1'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
