"""Production WSGI entry point for Railway/Gunicorn."""

import os

from app import app

secret_key = os.environ.get("SECRET_KEY")
if not secret_key:
    raise RuntimeError("SECRET_KEY must be set before starting the production server")

# app.py currently assigns a legacy hard-coded key; override it at the final
# production entry point until that assignment is removed in the next refactor.
app.secret_key = secret_key
