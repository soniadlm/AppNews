"""Appels Anthropic Claude Haiku 4.5 pour résumés d'articles et synthèses globales."""
import asyncio
import os
import re
from anthropic import AsyncAnthropic

_client = None


def client():
    global _client
    if _client is None:
        _client = AsyncAnthropic()
    return _client


# Modèle Anthropic public (utilisé avec ANTHROPIC_API_KEY).
# Surchargeable via la variable d'env ANTHROPIC_MODEL.
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1500]


async def summarize_article(title: str, description: str) -> str:
    desc = _strip_html(description) or "(pas de description disponible)"
    prompt = (
        "Tu es un éditeur de presse. Résume cet article en 2-3 phrases courtes et claires, en français, "
        "en gardant l'essentiel factuel. Pas d'opinion, pas de phrase d'introduction du type 'L'article parle de...'. "
        "Réponds uniquement par le résumé.\n\n"
        f"Titre: {title}\n"
        f"Description/contenu: {desc}"
    )
    try:
        msg = await client().messages.create(
            model=MODEL,
            max_tokens=220,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in msg.content if hasattr(block, "text")).strip()
        return text or _fallback(title, desc)
    except Exception as e:
        print(f"[summarize_article] erreur: {e}")
        return _fallback(title, desc)


def _fallback(title: str, desc: str) -> str:
    return (desc[:240] + "…") if desc else title


async def summarize_articles_batch(articles: list, concurrency: int = 6) -> list:
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
        f'Tu es un analyste de presse. Voici les {len(lines)} derniers articles sur le thème "{theme_name}". '
        "Produis une synthèse en 4-6 puces (•), en français, qui dégage les tendances, les faits marquants, "
        "et les angles complémentaires. Pas de phrase d'intro. Démarre directement par les puces.\n\n"
        f"Articles:\n{listing}"
    )
    try:
        msg = await client().messages.create(
            model=MODEL,
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in msg.content if hasattr(block, "text")).strip()
    except Exception as e:
        print(f"[generate_brief] erreur: {e}")
        return "Synthèse temporairement indisponible. Consultez les articles ci-dessous."
