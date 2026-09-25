"""Isolated local browser-test API. Never starts a paid model/crawler worker."""

import os

import psycopg
import uvicorn

os.environ["DATABASE_URL"] = "postgresql://brief:brief-local-only@localhost:55432/brief_browser"
os.environ["BRIEF_SECURE_COOKIES"] = "false"
os.environ["BRIEF_EMBEDDED_WORKER"] = "false"
os.environ["FRONTEND_ORIGINS"] = "http://127.0.0.1:5175"
with psycopg.connect("postgresql://brief:brief-local-only@localhost:55432/postgres", autocommit=True) as connection:
    if not connection.execute("SELECT 1 FROM pg_database WHERE datname='brief_browser'").fetchone():
        connection.execute("CREATE DATABASE brief_browser")
from brief.db import Database

Database().migrate()
uvicorn.run("brief.api:app", host="127.0.0.1", port=8001)
