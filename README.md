# AppNews — Veille de presse multilingue

Application web de veille de presse : agrège des flux RSS sur 8 thèmes
prédéfinis (Tech & IA, Business, France, International, Science, Climat,
Startups, Sport), permet de créer des thèmes personnalisés par mots-clés,
et génère des résumés et synthèses via Claude (Anthropic).

- Stack : **FastAPI** (Python) + **SQLite** + **Anthropic Claude Haiku 4.5**
- Front : HTML/CSS/JS vanilla, responsive, mode sombre
- Cache : 256 résumés d'articles + 9 briefs déjà pré-générés dans `data.db`

## Démarrage local

```bash
# 1. Cloner et entrer dans le projet
git clone https://github.com/<votre-user>/AppNews.git
cd AppNews

# 2. Installer les dépendances
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Configurer la clé Anthropic
cp .env.example .env
# puis éditer .env et y mettre votre ANTHROPIC_API_KEY

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
   - `ANTHROPIC_API_KEY` = `sk-ant-...` (votre clé)
4. Cliquez sur **Deploy**. Vercel détecte `vercel.json` et configure automatiquement le runtime Python.

### Option B — Via la CLI Vercel

```bash
npm i -g vercel
vercel login
vercel link
vercel env add ANTHROPIC_API_KEY production
vercel --prod
```

## Variables d'environnement

| Variable            | Obligatoire | Description                                                        |
| ------------------- | ----------- | ------------------------------------------------------------------ |
| `ANTHROPIC_API_KEY` | Oui*        | Clé API Anthropic. Sans clé, l'app sert uniquement le cache.       |
| `ANTHROPIC_MODEL`   | Non         | Modèle Claude (défaut : `claude-haiku-4-5`).                       |
| `VEILLE_PROD`       | Non         | Mettre `1` pour forcer le mode cache strict (pas d'appels LLM).    |
| `VEILLE_DB_PATH`    | Non         | Chemin custom vers `data.db` (utile pour volumes persistants).     |

*Sans clé, l'app fonctionne quand même : elle sert les 256 résumés et 9 briefs
déjà présents en cache, mais ne génère pas de nouveau contenu.

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
├── summarizer.py         # Appels Anthropic Claude (résumés + briefs)
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
