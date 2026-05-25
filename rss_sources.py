"""Sources RSS organisées par thème prédéfini, plus un pool généraliste pour les thèmes perso."""

PREDEFINED_THEMES = {
    "tech-ia": {
        "name": "Tech & IA",
        "icon": "circuit",
        "feeds": [
            ("The Verge", "https://www.theverge.com/rss/index.xml", "en"),
            ("TechCrunch", "https://techcrunch.com/feed/", "en"),
            ("Le Monde — Pixels", "https://www.lemonde.fr/pixels/rss_full.xml", "fr"),
            ("L'Usine Digitale", "https://www.usine-digitale.fr/rss", "fr"),
        ],
    },
    "business": {
        "name": "Business & Économie",
        "icon": "bars",
        "feeds": [
            ("Les Echos", "https://services.lesechos.fr/rss/les-echos-economie.xml", "fr"),
            ("Bloomberg Markets", "https://feeds.bloomberg.com/markets/news.rss", "en"),
            ("Financial Times", "https://www.ft.com/rss/home", "en"),
            ("La Tribune", "https://www.latribune.fr/feed.rss", "fr"),
        ],
    },
    "france": {
        "name": "France",
        "icon": "hexagone",
        "feeds": [
            ("Le Monde", "https://www.lemonde.fr/rss/une.xml", "fr"),
            ("Franceinfo", "https://www.francetvinfo.fr/titres.rss", "fr"),
            ("Libération", "https://www.liberation.fr/arc/outboundfeeds/rss/?outputType=xml", "fr"),
        ],
    },
    "international": {
        "name": "International",
        "icon": "globe",
        "feeds": [
            ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml", "en"),
            ("NYT World", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "en"),
            ("France 24", "https://www.france24.com/fr/rss", "fr"),
            ("Le Monde — International", "https://www.lemonde.fr/international/rss_full.xml", "fr"),
        ],
    },
    "science": {
        "name": "Science & Recherche",
        "icon": "atom",
        "feeds": [
            ("Nature", "https://www.nature.com/nature.rss", "en"),
            ("Science (AAAS)", "https://www.science.org/rss/news_current.xml", "en"),
            ("Pour la Science", "https://www.pourlascience.fr/rss", "fr"),
            ("Le Monde — Sciences", "https://www.lemonde.fr/sciences/rss_full.xml", "fr"),
        ],
    },
    "climat": {
        "name": "Climat & Environnement",
        "icon": "leaf",
        "feeds": [
            ("The Guardian — Environment", "https://www.theguardian.com/environment/rss", "en"),
            ("Reporterre", "https://reporterre.net/spip.php?page=backend", "fr"),
            ("Le Monde — Planète", "https://www.lemonde.fr/planete/rss_full.xml", "fr"),
        ],
    },
    "startups": {
        "name": "Startups & Innovation",
        "icon": "rocket",
        "feeds": [
            ("Maddyness", "https://www.maddyness.com/feed/", "fr"),
            ("FrenchWeb", "https://www.frenchweb.fr/feed", "fr"),
            ("TechCrunch — Startups", "https://techcrunch.com/category/startups/feed/", "en"),
        ],
    },
    "sport": {
        "name": "Sport",
        "icon": "trophy",
        "feeds": [
            ("L'Équipe", "https://www.lequipe.fr/rss/actu_rss.xml", "fr"),
            ("Franceinfo Sport", "https://www.francetvinfo.fr/sports.rss", "fr"),
            ("BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml", "en"),
        ],
    },
}

# Pool généraliste pour les thèmes personnalisés (filtrés par mots-clés).
CUSTOM_POOL = [
    ("Le Monde", "https://www.lemonde.fr/rss/une.xml", "fr"),
    ("Le Monde — International", "https://www.lemonde.fr/international/rss_full.xml", "fr"),
    ("Le Monde — Économie", "https://www.lemonde.fr/economie/rss_full.xml", "fr"),
    ("Le Monde — Pixels", "https://www.lemonde.fr/pixels/rss_full.xml", "fr"),
    ("Le Monde — Planète", "https://www.lemonde.fr/planete/rss_full.xml", "fr"),
    ("Franceinfo", "https://www.francetvinfo.fr/titres.rss", "fr"),
    ("Libération", "https://www.liberation.fr/arc/outboundfeeds/rss/?outputType=xml", "fr"),
    ("Les Echos", "https://services.lesechos.fr/rss/les-echos-economie.xml", "fr"),
    ("La Tribune", "https://www.latribune.fr/feed.rss", "fr"),
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml", "en"),
    ("NYT World", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "en"),
    ("The Guardian — World", "https://www.theguardian.com/world/rss", "en"),
    ("The Verge", "https://www.theverge.com/rss/index.xml", "en"),
    ("TechCrunch", "https://techcrunch.com/feed/", "en"),
    ("Bloomberg Markets", "https://feeds.bloomberg.com/markets/news.rss", "en"),
]
