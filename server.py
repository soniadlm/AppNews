"""FastAPI — Veille News.

Endpoints :
- GET  /api/themes                              → liste des thèmes prédéfinis + perso
- POST /api/themes                              → créer un thème perso
- DELETE /api/themes/{slug}                     → supprimer un thème perso
- GET  /api/feed?theme=...&lang=...&sort=...    → articles + résumés IA
- GET  /api/synthesis?theme=...&refresh=0|1     → synthèse globale (brief)
- GET  /api/favorites                           → favoris de l'utilisateur
- POST /api/favorites                           → ajouter
- DELETE /api/favorites?url=...                 → retirer
"""
import asyncio
import hashlib
import html
import os
import re
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from urllib.parse import urlparse

import feedparser
from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

import db
import summarizer
from rss_sources import PREDEFINED_THEMES, CUSTOM_POOL

# LLM activé dès qu'un token Hugging Face (ou autre provider OpenAI-compatible)
# est présent. Si VEILLE_PROD=1 est forcé, on désactive même avec une clé.
_has_llm_key = bool(
    os.environ.get("HF_TOKEN")
    or os.environ.get("HUGGINGFACE_API_KEY")
    or os.environ.get("OPENAI_API_KEY")
)
LLM_ENABLED = _has_llm_key and os.environ.get("VEILLE_PROD") != "1"

app = FastAPI(title="Veille News")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

_EXECUTOR = ThreadPoolExecutor(max_workers=8)
_FEED_CACHE: dict[str, tuple[float, list]] = {}
FEED_CACHE_TTL = 30 * 60  # 30 minutes


def _user_token_from_request(x_visitor_id: Optional[str], cookie_token: Optional[str]) -> str:
    """Préfère X-Visitor-Id injecté par le proxy ; sinon cookie ; sinon génère."""
    if x_visitor_id:
        return "v:" + x_visitor_id
    if cookie_token:
        return "c:" + cookie_token
    return "c:" + secrets.token_urlsafe(16)


# ---------- Helpers feed parsing ----------
def _clean(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _get_image(entry) -> Optional[str]:
    # enclosures / media_content / media_thumbnail / image dans content
    if hasattr(entry, "media_content"):
        for m in entry.media_content:
            if m.get("url"):
                return m["url"]
    if hasattr(entry, "media_thumbnail"):
        for m in entry.media_thumbnail:
            if m.get("url"):
                return m["url"]
    if hasattr(entry, "enclosures"):
        for enc in entry.enclosures:
            t = enc.get("type", "")
            if t.startswith("image/") and enc.get("href"):
                return enc["href"]
    # image dans description ou content
    desc = ""
    if hasattr(entry, "summary"):
        desc = entry.summary
    elif hasattr(entry, "description"):
        desc = entry.description
    if hasattr(entry, "content") and entry.content:
        desc += " " + entry.content[0].get("value", "")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
    if m:
        return m.group(1)
    return None


def _parse_feed_sync(name: str, url: str, lang: str) -> list:
    items = []
    try:
        parsed = feedparser.parse(url, request_headers={"User-Agent": "VeilleNews/1.0"})
        if parsed.bozo and not parsed.entries:
            return []
        for entry in parsed.entries[:25]:
            link = entry.get("link") or ""
            if not link:
                continue
            title = _clean(entry.get("title", ""))
            if not title:
                continue
            desc = entry.get("summary", "") or entry.get("description", "")
            published = entry.get("published", "") or entry.get("updated", "")
            published_ts = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published_ts = time.mktime(entry.published_parsed)
                except Exception:
                    pass
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                try:
                    published_ts = time.mktime(entry.updated_parsed)
                except Exception:
                    pass
            items.append({
                "url": link,
                "title": title,
                "description": desc,
                "source": name,
                "lang": lang,
                "published": published,
                "published_ts": published_ts or 0,
                "image": _get_image(entry),
            })
    except Exception as e:
        print(f"[feed:{name}] erreur: {e}")
    return items


async def _fetch_feed(name: str, url: str, lang: str) -> list:
    cache_key = url
    now = time.time()
    if cache_key in _FEED_CACHE:
        ts, items = _FEED_CACHE[cache_key]
        if now - ts < FEED_CACHE_TTL:
            return items
    loop = asyncio.get_event_loop()
    items = await loop.run_in_executor(_EXECUTOR, _parse_feed_sync, name, url, lang)
    if items:
        _FEED_CACHE[cache_key] = (now, items)
    return items


async def _fetch_many(feeds: list) -> list:
    results = await asyncio.gather(*(_fetch_feed(n, u, l) for (n, u, l) in feeds))
    all_items = [it for sub in results for it in sub]
    # déduplique par URL
    seen = set()
    out = []
    for it in all_items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        out.append(it)
    return out


def _filter_by_keywords(items: list, keywords: list) -> list:
    if not keywords:
        return items
    kws = [k.lower().strip() for k in keywords if k.strip()]
    if not kws:
        return items
    out = []
    for it in items:
        hay = (it.get("title", "") + " " + _clean(it.get("description", ""))).lower()
        if any(k in hay for k in kws):
            out.append(it)
    return out


# ---------- Lifecycle ----------
@app.on_event("startup")
async def on_startup():
    await db.init_db()


# ---------- Helpers de récupération de user_token ----------
def get_user_token(request: Request, response: Optional[Response] = None) -> str:
    x_visitor = request.headers.get("x-visitor-id")
    cookie_token = (
        request.cookies.get("__Host-veille-token")
        or request.cookies.get("veille-token")
    )
    token = _user_token_from_request(x_visitor, cookie_token)
    # si on a généré un cookie token et qu'il n'existe pas, on le pose
    if response is not None and not x_visitor and not cookie_token:
        # token format c:xxxx → extrait la partie
        # __Host- exige Secure + path=/ + pas de Domain. En HTTP local, on
        # retombe sur un nom non préfixé pour que le cookie soit accepté.
        is_https = (request.url.scheme == "https") or (
            request.headers.get("x-forwarded-proto", "").lower() == "https"
        )
        cookie_name = "__Host-veille-token" if is_https else "veille-token"
        response.set_cookie(
            cookie_name,
            token[2:],
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="lax",
            secure=is_https,
            path="/",
        )
    return token


# ---------- API ----------
@app.get("/api/themes")
async def list_themes(request: Request, response: Response):
    token = get_user_token(request, response)
    predefined = [
        {"slug": slug, "name": data["name"], "icon": data["icon"], "kind": "predefined"}
        for slug, data in PREDEFINED_THEMES.items()
    ]
    custom = await db.list_custom_themes(token)
    custom_out = [
        {"slug": c["slug"], "name": c["name"], "keywords": c["keywords"], "kind": "custom"}
        for c in custom
    ]
    return {"predefined": predefined, "custom": custom_out}


class NewTheme(BaseModel):
    name: str
    keywords: list[str]


@app.post("/api/themes")
async def create_theme(payload: NewTheme, request: Request, response: Response):
    token = get_user_token(request, response)
    name = payload.name.strip()
    if not name or len(name) > 60:
        raise HTTPException(400, "Nom invalide")
    kws = [k.strip()[:80] for k in payload.keywords if k and k.strip()][:30]
    if not kws:
        raise HTTPException(400, "Au moins un mot-clé requis")
    slug = await db.add_custom_theme(token, name, kws)
    return {"slug": slug, "name": name, "keywords": kws}


@app.delete("/api/themes/{slug}")
async def delete_theme(slug: str, request: Request, response: Response):
    token = get_user_token(request, response)
    await db.delete_custom_theme(token, slug)
    return {"ok": True}


async def _resolve_theme(token: str, theme_slug: str):
    """Renvoie (display_name, list_of_feeds, keyword_filter)."""
    if theme_slug in PREDEFINED_THEMES:
        t = PREDEFINED_THEMES[theme_slug]
        return t["name"], t["feeds"], None
    custom = await db.get_custom_theme(token, theme_slug)
    if custom:
        return custom["name"], CUSTOM_POOL, custom["keywords"]
    return None


@app.get("/api/feed")
async def get_feed(
    request: Request,
    response: Response,
    theme: str = Query(...),
    lang: str = Query("all"),
    sort: str = Query("recent"),
    limit: int = Query(24, ge=1, le=60),
):
    token = get_user_token(request, response)

    if theme == "favorites":
        favs = await db.list_favorites(token)
        if lang in ("fr", "en"):
            favs = [f for f in favs if (f.get("lang") or "").startswith(lang)]
        return {"theme": "Favoris", "articles": favs, "count": len(favs)}

    resolved = await _resolve_theme(token, theme)
    if not resolved:
        raise HTTPException(404, "Thème inconnu")
    display_name, feeds, kw_filter = resolved

    items = await _fetch_many(feeds)
    if kw_filter:
        items = _filter_by_keywords(items, kw_filter)
    if lang in ("fr", "en"):
        items = [it for it in items if it["lang"] == lang]

    if sort == "recent":
        items.sort(key=lambda x: x.get("published_ts", 0), reverse=True)
    items = items[:limit]

    # Résumés : cache d'abord, puis LLM si activé, sinon fallback description
    to_summarize_idx = []
    for i, it in enumerate(items):
        cached = await db.get_summary(it["url"])
        if cached:
            it["summary"] = cached
        else:
            to_summarize_idx.append(i)

    if to_summarize_idx:
        if LLM_ENABLED:
            # Mode dev : appel LLM pour générer les résumés manquants
            batch = [items[i] for i in to_summarize_idx]
            summaries = await summarizer.summarize_articles_batch(batch, concurrency=6)
            for i, s in zip(to_summarize_idx, summaries):
                items[i]["summary"] = s
                await db.save_summary(items[i]["url"], s)
        else:
            # Mode prod : pas de LLM — fallback sur description tronquée
            for i in to_summarize_idx:
                desc = _clean(items[i].get("description", ""))
                items[i]["summary"] = (desc[:200] + "…") if len(desc) > 200 else (desc or items[i].get("title", ""))

    # Favoris : marquage
    fav_set = await db.favorite_urls(token)
    for it in items:
        it["favorite"] = it["url"] in fav_set
        it.pop("description", None)
        it.pop("published_ts", None)

    return {"theme": display_name, "articles": items, "count": len(items)}


@app.get("/api/synthesis")
async def get_synthesis(
    request: Request,
    response: Response,
    theme: str = Query(...),
    refresh: int = Query(0),
):
    token = get_user_token(request, response)
    if theme == "favorites":
        return {"brief": "Sélection personnelle : retrouvez ici vos articles enregistrés.", "created_at": int(time.time()), "cached": False}
    resolved = await _resolve_theme(token, theme)
    if not resolved:
        raise HTTPException(404, "Thème inconnu")
    display_name, feeds, kw_filter = resolved

    cache_key = f"{theme}"

    if not refresh:
        # Cas normal (refresh=0) : retourne le cache si valide (TTL 30 min)
        # En prod, ignore le TTL pour toujours servir le cache
        max_age = 10**9 if not LLM_ENABLED else db.BRIEF_TTL
        cached = await db.get_brief(cache_key, max_age=max_age)
        if cached:
            return {"brief": cached["brief"], "created_at": cached["created_at"], "cached": True}

    if refresh and not LLM_ENABLED:
        # Mode prod avec refresh demandé : retourne le cache existant sans expiration
        cached = await db.get_brief(cache_key, max_age=10**9)
        if cached:
            return {
                "brief": cached["brief"],
                "created_at": cached["created_at"],
                "cached": True,
                "note": "Rafraîchissement non disponible en mode publié — contenu du cache servi.",
            }
        return {
            "brief": "Synthèse non disponible — ressources IA indisponibles en mode publié.",
            "created_at": int(time.time()),
            "cached": False,
        }

    # Mode dev ou refresh=0 sans cache valide : génère via LLM
    items = await _fetch_many(feeds)
    if kw_filter:
        items = _filter_by_keywords(items, kw_filter)
    items.sort(key=lambda x: x.get("published_ts", 0), reverse=True)
    items = items[:15]

    brief = await summarizer.generate_brief(display_name, items)
    await db.save_brief(cache_key, brief)
    return {"brief": brief, "created_at": int(time.time()), "cached": False}


class FavoriteIn(BaseModel):
    url: str
    title: str
    source: Optional[str] = None
    summary: Optional[str] = None
    image: Optional[str] = None
    published: Optional[str] = None
    lang: Optional[str] = None

    @classmethod
    def _is_safe_url(cls, v: Optional[str]) -> bool:
        if not v:
            return True
        return v.startswith("http://") or v.startswith("https://")

    def __init__(self, **data):
        super().__init__(**data)
        if not (self.url.startswith("http://") or self.url.startswith("https://")):
            raise ValueError("url must be http(s)")
        if self.image and not (self.image.startswith("http://") or self.image.startswith("https://") or self.image.startswith("data:image/")):
            self.image = None


@app.post("/api/favorites")
async def add_fav(payload: FavoriteIn, request: Request, response: Response):
    token = get_user_token(request, response)
    await db.add_favorite(token, payload.dict())
    return {"ok": True}


@app.delete("/api/favorites")
async def del_fav(url: str = Query(...), request: Request = None, response: Response = None):
    token = get_user_token(request, response)
    await db.remove_favorite(token, url)
    return {"ok": True}


@app.get("/api/favorites")
async def get_favs(request: Request, response: Response):
    token = get_user_token(request, response)
    favs = await db.list_favorites(token)
    return {"articles": favs, "count": len(favs)}


# ---------- Static (frontend) ----------
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@app.get("/")
async def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/{path:path}")
async def static_fallback(path: str):
    # Resolve to real path and reject any traversal outside STATIC_DIR
    candidate = os.path.realpath(os.path.join(STATIC_DIR, path))
    real_static = os.path.realpath(STATIC_DIR)
    if os.path.isfile(candidate) and candidate.startswith(real_static + os.sep):
        return FileResponse(candidate)
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
