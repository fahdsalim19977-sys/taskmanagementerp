"""Production WSGI entry point.

The legacy app module assigns a development secret after loading Config.
This wrapper restores the environment-provided production secret before the
Gunicorn worker starts serving requests.
"""

import os

from app import app


secret_key = os.environ.get("SECRET_KEY")
if not secret_key:
    raise RuntimeError("SECRET_KEY must be set before starting the production server")

app.secret_key = secret_key
