import sqlite3
from contextlib import closing, contextmanager


@contextmanager
def connect(path, **kwargs):
    with closing(sqlite3.connect(path, **kwargs)) as db:
        with db:
            yield db
