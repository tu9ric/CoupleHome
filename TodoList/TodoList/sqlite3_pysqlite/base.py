import sys

from django.core.exceptions import ImproperlyConfigured

try:
    import pysqlite3
except ImportError as exc:
    raise ImproperlyConfigured('Install pysqlite3-binary or set USE_PYSQLITE3=False.') from exc

sys.modules['sqlite3'] = pysqlite3

from django.db.backends.sqlite3.base import DatabaseWrapper as SQLiteDatabaseWrapper

from .features import DatabaseFeatures


class DatabaseWrapper(SQLiteDatabaseWrapper):
    features_class = DatabaseFeatures
