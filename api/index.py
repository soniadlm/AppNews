"""Entrypoint serverless Vercel — expose l'app FastAPI comme handler ASGI.

Vercel détecte ce module via vercel.json (routes → /api). On importe l'app
définie dans server.py à la racine du projet et on la ré-exporte sous le nom
`app` que le runtime Python de Vercel reconnaît automatiquement.
"""
import os
import sys

# Le bundle Vercel met /api/ comme cwd ; on ajoute la racine pour pouvoir
# importer server.py, db.py, summarizer.py, rss_sources.py.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from server import app  # noqa: E402  (FastAPI ASGI app)

# Vercel cherche un callable nommé `app` ou `handler` au niveau module.
handler = app
