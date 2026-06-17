from django.db.backends.sqlite3.features import DatabaseFeatures as SQLiteDatabaseFeatures


class DatabaseFeatures(SQLiteDatabaseFeatures):
    @property
    def max_query_params(self):
        return 999
