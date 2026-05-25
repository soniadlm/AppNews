"""Résumés d'articles et synthèses globales via Hugging Face Inference Providers.

On utilise le SDK `openai` pointé vers le router Hugging Face
(https://router.huggingface.co/v1) qui expose une API OpenAI-compatible pour
les modèles open-source. Cela évite de dépendre d'un compte Anthropic.

Authentification : un token HF (gratuit) — créé sur
https://huggingface.co/settings/tokens (login GitHub accepté), avec la
permission "Make calls to Inference Providers".
"""
import asyncio
import os
import re
from openai import AsyncOpenAI

_client = None

# Base par défaut : router Hugging Face. Surchargeable via env pour pointer
# vers n'importe quel provider OpenAI-compatible (Groq, OpenRouter, Together…).
DEFAULT_BASE_URL = "https://router.huggingface.co/v1"

# Modèle par défaut : Llama 3.3 70B Instruct — gratuit côté HF, multilingue,
# bonne qualité en français. Surchargeable via HF_MODEL.
DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct"


def _api_key() -> str | None:
    """Lit la clé d'API : HF_TOKEN en priorité, puis HUGGINGFACE_API_KEY,
    puis OPENAI_API_KEY (pour un provider générique)."""
    return (
        os.environ.get("HF_TOKEN")
        or os.environ.get("HUGGINGFACE_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )


def client():
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=_api_key() or "missing",
            base_url=os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL),
        )
    return _client


MODEL = os.environ.get("HF_MODEL") or os.environ.get("LLM_MODEL") or DEFAULT_MODEL


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1500]


async def summarize_article(title: str, description: str) -> str:
    desc = _strip_html(description) or "(pas de description disponible)"
    prompt = (
        "Tu es un éditeur de presse. Résume cet article en 2-3 phrases courtes "
        "et claires, en français, en gardant l'essentiel factuel. Pas d'opinion, "
        "pas de phrase d'introduction du type 'L'article parle de...'. Réponds "
        "uniquement par le résumé.\n\n"
        f"Titre: {title}\n"
        f"Description/contenu: {desc}"
    )
    try:
        resp = await client().chat.completions.create(
            model=MODEL,
            max_tokens=220,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        text = (resp.choices[0].message.content or "").strip()
        return text or _fallback(title, desc)
    except Exception as e:
        print(f"[summarize_article] erreur: {e}")
        return _fallback(title, desc)


def _fallback(title: str, desc: str) -> str:
    return (desc[:240] + "…") if desc else title


async def summarize_articles_batch(articles: list, concurrency: int = 4) -> list:
    """Renvoie un résumé pour chaque article (même ordre). Limite la concurrence."""
    sem = asyncio.Semaphore(concurrency)

    async def one(a):
        async with sem:
            return await summarize_article(a.get("title", ""), a.get("description", ""))

    return await asyncio.gather(*(one(a) for a in articles))


async def generate_brief(theme_name: str, articles: list) -> str:
    if not articles:
        return "Aucun article récent pour ce thème."
    lines = []
    for i, a in enumerate(articles[:15], 1):
        title = a.get("title", "").strip()
        desc = _strip_html(a.get("description", ""))[:280]
        lines.append(f"{i}. {title} — {desc}")
    listing = "\n".join(lines)
    prompt = (
        f'Tu es un analyste de presse. Voici les {len(lines)} derniers articles '
        f'sur le thème "{theme_name}". Produis une synthèse en 4-6 puces (•), '
        "en français, qui dégage les tendances, les faits marquants, et les "
        "angles complémentaires. Pas de phrase d'intro. Démarre directement "
        "par les puces.\n\n"
        f"Articles:\n{listing}"
    )
    try:
        resp = await client().chat.completions.create(
            model=MODEL,
            max_tokens=700,
            temperature=0.4,
            messages=[{"role": "user", "content": prompt}],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"[generate_brief] erreur: {e}")
        return "Synthèse temporairement indisponible. Consultez les articles ci-dessous."
