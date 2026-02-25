"""Database connection helper for the API service."""
from contextlib import contextmanager
import psycopg2
import psycopg2.extras
from api import config


def get_connection():
    conn = psycopg2.connect(config.DATABASE_URL)
    conn.autocommit = False
    return conn


@contextmanager
def db_connection():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
