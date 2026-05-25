"""Couche SQLite asynchrone : thèmes personnalisés, cache résumés/synthèses, favoris.

Gestion du filesystem :
- En local : data.db reste à la racine du projet (lecture + écriture).
- Sur Vercel : le FS est read-only sauf /tmp. On copie data.db dans /tmp au
  premier accès pour permettre l'écriture (favoris, thèmes perso, nouveaux
  résumés). ⚠️ /tmp est éphémère et par-instance : les données utilisateur
  ne persistent pas entre invocations. Pour de la vraie persistance, brancher
  Vercel Postgres ou Turso (cf. README).
"""
import aiosqlite
import hashlib
import json
import os
import shutil
import time

_BUNDLED_DB = os.path.join(os.path.dirname(__file__), "data.db")


def _resolve_db_path() -> str:
    """Renvoie un chemin DB inscriptible.

    - VEILLE_DB_PATH (env) prioritaire si défini (ex. volume monté).
    - Sinon, sur Vercel/serverless (FS read-only), on copie data.db dans /tmp.
    - Sinon, on utilise le data.db local.
    """
    override = os.environ.get("VEILLE_DB_PATH")
    if override:
        return override

    # Heuristique serverless : Vercel/AWS Lambda exposent /var/task en read-only.
    on_vercel = os.environ.get("VERCEL") == "1" or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
    if on_vercel:
        tmp_db = "/tmp/data.db"
        if not os.path.exists(tmp_db) and os.path.exists(_BUNDLED_DB):
            try:
                shutil.copyfile(_BUNDLED_DB, tmp_db)
            except Exception as e:
                print(f"[db] copie data.db vers /tmp échouée: {e}")
        return tmp_db

    return _BUNDLED_DB


DB_PATH = _resolve_db_path()

SCHEMA = """
CREATE TABLE IF NOT EXISTS custom_themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_token TEXT NOT NULL,
    slug TEXT NOT NULL,
    name TEXT NOT NULL,
    keywords TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_custom_user ON custom_themes(user_token);

CREATE TABLE IF NOT EXISTS article_summaries (
    url_hash TEXT PRIMARY KEY,
    summary TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS theme_briefs (
    theme_key TEXT PRIMARY KEY,
    brief TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_token TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT,
    summary TEXT,
    image TEXT,
    published TEXT,
    lang TEXT,
    created_at INTEGER NOT NULL,
    UNIQUE(user_token, url)
);
CREATE INDEX IF NOT EXISTS idx_fav_user ON favorites(user_token);
"""


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


# ---------- Résumés d'articles ----------
async def get_summary(url: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT summary FROM article_summaries WHERE url_hash = ?",
            (url_hash(url),),
        )
        row = await cur.fetchone()
        return row[0] if row else None


async def save_summary(url: str, summary: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO article_summaries (url_hash, summary, created_at) VALUES (?, ?, ?)",
            (url_hash(url), summary, int(time.time())),
        )
        await db.commit()


# ---------- Synthèses globales (briefs) ----------
BRIEF_TTL = 30 * 60  # 30 minutes


async def get_brief(theme_key: str, max_age: int = BRIEF_TTL):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT brief, created_at FROM theme_briefs WHERE theme_key = ?",
            (theme_key,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        brief, created_at = row
        if int(time.time()) - created_at > max_age:
            return None
        return {"brief": brief, "created_at": created_at}


async def save_brief(theme_key: str, brief: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO theme_briefs (theme_key, brief, created_at) VALUES (?, ?, ?)",
            (theme_key, brief, int(time.time())),
        )
        await db.commit()


# ---------- Thèmes personnalisés ----------
async def list_custom_themes(user_token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, slug, name, keywords, created_at FROM custom_themes WHERE user_token = ? ORDER BY created_at DESC",
            (user_token,),
        )
        rows = await cur.fetchall()
        return [
            {"id": r[0], "slug": r[1], "name": r[2], "keywords": json.loads(r[3]), "created_at": r[4]}
            for r in rows
        ]


async def add_custom_theme(user_token: str, name: str, keywords: list):
    slug = "custom-" + hashlib.sha256(f"{user_token}:{name}:{time.time()}".encode()).hexdigest()[:10]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO custom_themes (user_token, slug, name, keywords, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_token, slug, name, json.dumps(keywords), int(time.time())),
        )
        await db.commit()
    return slug


async def get_custom_theme(user_token: str, slug: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT slug, name, keywords FROM custom_themes WHERE user_token = ? AND slug = ?",
            (user_token, slug),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {"slug": row[0], "name": row[1], "keywords": json.loads(row[2])}


async def delete_custom_theme(user_token: str, slug: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM custom_themes WHERE user_token = ? AND slug = ?",
            (user_token, slug),
        )
        await db.commit()


# ---------- Favoris ----------
async def list_favorites(user_token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """SELECT url, title, source, summary, image, published, lang, created_at
               FROM favorites WHERE user_token = ? ORDER BY created_at DESC""",
            (user_token,),
        )
        rows = await cur.fetchall()
        return [
            {
                "url": r[0],
                "title": r[1],
                "source": r[2],
                "summary": r[3],
                "image": r[4],
                "published": r[5],
                "lang": r[6],
                "saved_at": r[7],
                "favorite": True,
            }
            for r in rows
        ]


async def add_favorite(user_token: str, article: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO favorites
               (user_token, url, title, source, summary, image, published, lang, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_token,
                article["url"],
                article["title"],
                article.get("source"),
                article.get("summary"),
                article.get("image"),
                article.get("published"),
                article.get("lang"),
                int(time.time()),
            ),
        )
        await db.commit()


async def remove_favorite(user_token: str, url: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM favorites WHERE user_token = ? AND url = ?",
            (user_token, url),
        )
        await db.commit()


async def favorite_urls(user_token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT url FROM favorites WHERE user_token = ?",
            (user_token,),
        )
        rows = await cur.fetchall()
        return {r[0] for r in rows}
