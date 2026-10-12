import os
import sys

# Resolve the project root (one level up from api/)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add root to sys.path so `import app` works
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Import the Flask app instance from the root-level app.py
from app import app  # noqa: F401 — Vercel looks for `app` in this module

# Vercel invokes this module as a WSGI handler; no app.run() needed
