# AppNews — Veille de presse multilingue

Application web de veille de presse : agrège des flux RSS sur 8 thèmes
prédéfinis (Tech & IA, Business, France, International, Science, Climat,
Startups, Sport), permet de créer des thèmes personnalisés par mots-clés,
et génère des résumés et synthèses via des modèles open-source servis par
**Hugging Face Inference Providers**.

- Stack : **FastAPI** (Python) + **SQLite** + **Llama 3.3 70B** via [Hugging Face](https://huggingface.co/)
- Front : HTML/CSS/JS vanilla, responsive, mode sombre
- Cache : 256 résumés d'articles + 9 briefs déjà pré-générés dans `data.db`

## Pourquoi Hugging Face ?

- **Pas besoin de carte bancaire** ni de création de compte spécifique :
  on se connecte à [huggingface.co](https://huggingface.co/) avec un compte
  GitHub ou Google.
- **Quota gratuit** généreux sur l'API d'inférence.
- **API OpenAI-compatible** : on peut basculer vers d'autres providers
  (OpenRouter, Groq, Together…) sans changer le code, en surchargeant juste
  `LLM_BASE_URL` et `OPENAI_API_KEY`.

## Obtenir un token Hugging Face (2 min)

1. Allez sur [huggingface.co/join](https://huggingface.co/join) et cliquez
   sur **Sign in with GitHub** (ou Google).
2. Une fois connecté, allez sur
   [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).
3. Cliquez sur **Create new token** → type **Fine-grained**.
4. Cochez la permission **"Make calls to Inference Providers"**.
5. Copiez le token (`hf_...`).

## Démarrage local

```bash
# 1. Cloner et entrer dans le projet
git clone https://github.com/soniadlm/AppNews.git
cd AppNews

# 2. Installer les dépendances
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Configurer le token Hugging Face
cp .env.example .env
# puis éditer .env et y mettre votre HF_TOKEN

# 4. Lancer le serveur
export $(cat .env | xargs)  # charge les variables d'env
uvicorn server:app --reload --port 5000
```

Ouvrez ensuite [http://localhost:5000](http://localhost:5000).

## Déploiement sur Vercel

### Option A — Via le dashboard Vercel (recommandé)

1. Allez sur [vercel.com/new](https://vercel.com/new) et connectez votre compte GitHub.
2. Importez le dépôt `AppNews`.
3. Dans **Settings → Environment Variables**, ajoutez :
   - `HF_TOKEN` = `hf_...` (votre token Hugging Face)
4. Cliquez sur **Deploy**. Vercel détecte `vercel.json` et configure
   automatiquement le runtime Python.

### Option B — Via la CLI Vercel

```bash
npm i -g vercel
vercel login
vercel link
vercel env add HF_TOKEN production
vercel --prod
```

## Variables d'environnement

| Variable         | Obligatoire | Description                                                       |
| ---------------- | ----------- | ----------------------------------------------------------------- |
| `HF_TOKEN`       | Oui*        | Token Hugging Face. Sans clé, l'app sert uniquement le cache.     |
| `HF_MODEL`       | Non         | Modèle (défaut : `meta-llama/Llama-3.3-70B-Instruct`).            |
| `LLM_BASE_URL`   | Non         | URL d'un autre provider OpenAI-compatible (OpenRouter, Groq…).    |
| `OPENAI_API_KEY` | Non         | Clé pour un provider tiers si `LLM_BASE_URL` est défini.          |
| `VEILLE_PROD`    | Non         | Mettre `1` pour forcer le mode cache strict (pas d'appels LLM).   |
| `VEILLE_DB_PATH` | Non         | Chemin custom vers `data.db` (utile pour volumes persistants).    |

*Sans clé, l'app fonctionne quand même : elle sert les 256 résumés et 9 briefs
déjà présents en cache, mais ne génère pas de nouveau contenu.

## Changer de modèle ou de provider

Le code utilise le SDK `openai` pointé sur le router Hugging Face. Pour
basculer vers un autre fournisseur compatible OpenAI :

```bash
# Exemple : OpenRouter (login GitHub aussi)
LLM_BASE_URL=https://openrouter.ai/api/v1
OPENAI_API_KEY=sk-or-v1-...
HF_MODEL=meta-llama/llama-3.3-70b-instruct:free
```

## Architecture

```
appnews/
├── api/
│   └── index.py          # Entrypoint serverless Vercel (handler ASGI)
├── static/
│   ├── index.html        # SPA
│   ├── app.js
│   └── styles.css
├── server.py             # Routes FastAPI (/api/themes, /api/feed, /api/synthesis, /api/favorites)
├── db.py                 # Couche SQLite asynchrone (aiosqlite)
├── summarizer.py         # Appels LLM (HF Inference Providers via SDK openai)
├── rss_sources.py        # 8 thèmes prédéfinis + pool générique pour thèmes perso
├── data.db               # Cache pré-généré (résumés + briefs)
├── requirements.txt
├── vercel.json
└── README.md
```

## ⚠️ Limites du stockage sur Vercel

Vercel est **serverless** : le filesystem est en lecture seule sauf `/tmp`,
qui est éphémère et **par instance lambda**. Concrètement :

- Le cache `data.db` est livré en lecture seule dans le bundle.
- Au premier appel d'une lambda froide, `data.db` est copié dans `/tmp/data.db`
  pour permettre les écritures (nouveaux résumés générés, favoris, thèmes perso).
- **Les favoris et thèmes personnalisés créés par les utilisateurs ne persistent
  pas durablement** — ils peuvent disparaître quand l'instance est recyclée.

Pour de la **vraie persistance** côté utilisateur, migrer vers :

- **Vercel Postgres** (`@vercel/postgres`) — recommandé, intégré au dashboard
- **Turso** (libSQL/SQLite hébergé) — change minimal de code
- **Supabase** ou **Neon** (Postgres)

Cette migration ne touche que `db.py`.

## API

| Méthode | Route                                  | Description                                         |
| ------- | -------------------------------------- | --------------------------------------------------- |
| GET     | `/api/themes`                          | Liste des thèmes (prédéfinis + perso)              |
| POST    | `/api/themes`                          | Créer un thème perso (`{name, keywords: []}`)       |
| DELETE  | `/api/themes/{slug}`                   | Supprimer un thème perso                            |
| GET     | `/api/feed?theme=...&lang=...&sort=`   | Articles + résumés IA                               |
| GET     | `/api/synthesis?theme=...&refresh=0|1` | Synthèse globale (brief)                            |
| GET     | `/api/favorites`                       | Favoris de l'utilisateur                            |
| POST    | `/api/favorites`                       | Ajouter un favori                                   |
| DELETE  | `/api/favorites?url=...`               | Retirer un favori                                   |

## Sécurité

- Cookie `__Host-veille-token` (httpOnly, Secure, SameSite=Lax) en HTTPS,
  fallback `veille-token` en HTTP local.
- Validation stricte des URLs sur les favoris (http(s) uniquement, images
  http(s) ou `data:image/`).
- Mots-clés des thèmes limités à 80 chars × 30 max.
- Protection contre la traversée de répertoires sur le servage des fichiers statiques.

## Licence

MIT
