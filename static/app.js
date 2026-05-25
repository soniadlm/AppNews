// API base : __PORT_5000__ est remplacé au déploiement par /port/5000.
// En local, on parle directement au serveur uvicorn (même origine si servi par FastAPI).
const PORT_PLACEHOLDER = "__PORT_5000__";
const API_BASE = PORT_PLACEHOLDER.startsWith("__") ? "" : PORT_PLACEHOLDER;

const ICONS = {
  circuit: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v4M15 3v4M9 17v4M15 17v4M3 9h4M3 15h4M17 9h4M17 15h4M9 9h6v6H9z"/></svg>',
  bars: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 20V10M10 20V4M16 20v-8M22 20V8"/></svg>',
  hexagone: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M12 2l9 5v10l-9 5-9-5V7z"/></svg>',
  globe: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>',
  atom: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="1.6"/><ellipse cx="12" cy="12" rx="10" ry="4"/><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(60 12 12)"/><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(120 12 12)"/></svg>',
  leaf: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 4c-9 1-15 6-15 14 0 2 1 2 2 2 8 0 13-6 14-14 0-1-0-2-1-2zM5 20c6-6 10-10 14-14"/></svg>',
  rocket: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 19c0-4 4-12 9-14 5 2 9 10 9 14 0 1-1 1-2 0l-2-2c-2 2-5 2-5 2s0-3 2-5l-2-2c-1-1-1-2 0-2-4 1-9 5-9 9z"/></svg>',
  trophy: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 4h12v4a6 6 0 0 1-12 0V4zM6 6H3a3 3 0 0 0 3 3M18 6h3a3 3 0 0 1-3 3M9 16h6M12 14v4M9 20h6"/></svg>',
  tag: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12V3h9l9 9-9 9z"/><circle cx="7.5" cy="7.5" r="1"/></svg>',
};

const state = {
  themes: { predefined: [], custom: [] },
  currentTheme: null,    // slug
  currentName: "",
  currentKind: "predefined",
  lang: "all",
  sort: "recent",
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function showToast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(showToast._tid);
  showToast._tid = setTimeout(() => { t.hidden = true; }, 2400);
}

async function api(path, opts = {}) {
  const url = API_BASE + path;
  const res = await fetch(url, { credentials: "include", ...opts });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${text}`);
  }
  return res.json();
}

// ====== Thèmes ======
async function loadThemes() {
  const data = await api("/api/themes");
  state.themes = data;
  renderThemes();
}

function renderThemes() {
  const pre = $("#predefined-list");
  pre.innerHTML = state.themes.predefined.map((t) => themeItem(t, "predefined")).join("");
  const custom = $("#custom-list");
  if (state.themes.custom.length === 0) {
    custom.innerHTML = '<li class="empty-hint">Aucun thème pour l\'instant.</li>';
  } else {
    custom.innerHTML = state.themes.custom.map((t) => themeItem(t, "custom")).join("");
  }
  attachThemeHandlers();
  highlightActive();
}

function themeItem(t, kind) {
  const icon = ICONS[t.icon] || ICONS.tag;
  const del = kind === "custom"
    ? `<span class="delete-x" data-del="${t.slug}" role="button" title="Supprimer" aria-label="Supprimer"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></span>`
    : "";
  return `
    <li>
      <button class="theme-link" data-theme="${t.slug}" data-kind="${kind}" data-name="${escapeAttr(t.name)}">
        <span class="theme-icon">${icon}</span>
        <span class="theme-name">${escapeHtml(t.name)}</span>
        ${del}
      </button>
    </li>`;
}

function attachThemeHandlers() {
  $$(".theme-link").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      if (e.target.closest(".delete-x")) return;
      const slug = btn.dataset.theme;
      const kind = btn.dataset.kind;
      const name = btn.dataset.name || (kind === "favorites" ? "Favoris" : slug);
      selectTheme(slug, name, kind);
    });
  });
  $$(".delete-x").forEach((b) => {
    b.addEventListener("click", async (e) => {
      e.stopPropagation();
      const slug = b.dataset.del;
      if (!confirm("Supprimer ce thème personnalisé ?")) return;
      await api(`/api/themes/${slug}`, { method: "DELETE" });
      if (state.currentTheme === slug) state.currentTheme = null;
      await loadThemes();
      if (!state.currentTheme) selectTheme("tech-ia", "Tech & IA", "predefined");
    });
  });
}

function highlightActive() {
  $$(".theme-link").forEach((b) => b.classList.toggle("active", b.dataset.theme === state.currentTheme));
}

// ====== Sélection / fil ======
async function selectTheme(slug, name, kind) {
  state.currentTheme = slug;
  state.currentName = name;
  state.currentKind = kind;
  highlightActive();
  // Sidebar : fermer sur mobile
  $("#sidebar").classList.remove("open");

  $("#page-eyebrow").textContent = kind === "favorites" ? "Bibliothèque" : (kind === "custom" ? "Thème personnalisé" : "Veille du jour");
  $("#page-title").textContent = name;

  // Brief
  const brief = $("#brief");
  brief.style.display = kind === "favorites" ? "none" : "";

  if (kind !== "favorites") {
    renderBriefSkeleton();
    loadBrief(false);
  }

  renderFeedSkeleton();
  loadFeed();
}

function renderBriefSkeleton() {
  $("#brief-body").innerHTML = '<div class="skeleton-line"></div><div class="skeleton-line"></div><div class="skeleton-line short"></div>';
  $("#brief-meta").textContent = "Synthèse IA des derniers articles";
}

function renderFeedSkeleton() {
  $("#feed").innerHTML = '<div class="article-skel"></div><div class="article-skel"></div><div class="article-skel"></div>';
}

async function loadBrief(refresh) {
  if (!state.currentTheme || state.currentTheme === "null") {
    $("#brief-body").innerHTML = '<p style="color:var(--text-mute)">Sélectionnez un thème pour afficher la synthèse.</p>';
    return;
  }
  try {
    const data = await api(`/api/synthesis?theme=${encodeURIComponent(state.currentTheme)}&refresh=${refresh ? 1 : 0}`);
    $("#brief-body").innerHTML = formatBrief(data.brief);
    const date = new Date((data.created_at || 0) * 1000);
    const dStr = isNaN(date) ? "" : date.toLocaleString("fr-FR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
    $("#brief-meta").textContent = `Synthèse · ${dStr}${data.cached ? " (cache)" : ""}`;
  } catch (e) {
    $("#brief-body").innerHTML = '<p style="color:var(--text-mute)">Synthèse indisponible pour le moment.</p>';
  }
}

function renderInline(text) {
  // **bold** → <strong>, sans HTML brut (on escape d'abord)
  let s = escapeHtml(text);
  s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/(^|[\s(])_([^_]+)_/g, '$1<em>$2</em>');
  return s;
}

function formatBrief(text) {
  if (!text) return "";
  const lines = text.split("\n").map(l => l.trim()).filter(Boolean);
  const bullets = lines.filter(l => /^[•\-\*]/.test(l));
  if (bullets.length >= 3) {
    const items = lines.map(l => l.replace(/^[•\-\*]\s*/, "")).filter(Boolean);
    return "<ul>" + items.map(i => `<li>${renderInline(i)}</li>`).join("") + "</ul>";
  }
  return `<p>${renderInline(text).replace(/\n/g, "<br>")}</p>`;
}

async function loadFeed() {
  if (!state.currentTheme || state.currentTheme === "null") {
    $("#feed").innerHTML = '<div class="empty-state"><h3>Aucun thème sélectionné</h3><p>Choisissez un thème dans la barre latérale pour commencer.</p></div>';
    return;
  }
  try {
    const url = state.currentTheme === "favorites"
      ? "/api/feed?theme=favorites"
      : `/api/feed?theme=${encodeURIComponent(state.currentTheme)}&lang=${state.lang}&sort=${state.sort}`;
    const data = await api(url);
    renderFeed(data.articles || []);
  } catch (e) {
    $("#feed").innerHTML = `<div class="empty-state"><h3>Impossible de charger</h3><p>${escapeHtml(String(e.message || e))}</p></div>`;
  }
}

function renderFeed(articles) {
  if (!articles.length) {
    const msg = state.currentTheme === "favorites"
      ? "Cliquez sur l'étoile d'un article pour l'ajouter à vos favoris."
      : "Aucun article ne correspond à vos critères pour l'instant.";
    $("#feed").innerHTML = `<div class="empty-state"><h3>Rien à afficher</h3><p>${msg}</p></div>`;
    return;
  }
  $("#feed").innerHTML = articles.map(articleHtml).join("");
  $$(".fav-btn").forEach((b) => b.addEventListener("click", onToggleFavorite));
}

function articleHtml(a) {
  const dt = a.published ? formatDate(a.published) : "";
  const langLabel = (a.lang || "").toUpperCase();
  const img = a.image
    ? `<div class="article-image"><img src="${escapeAttr(a.image)}" alt="" loading="lazy" onerror="this.parentNode.innerHTML='';this.parentNode.classList.add('empty');"></div>`
    : `<div class="article-image empty"></div>`;
  return `
    <article class="article">
      <div>
        <div class="article-meta">
          <span class="article-source">${escapeHtml(a.source || "")}</span>
          ${dt ? `<span>·</span><span>${escapeHtml(dt)}</span>` : ""}
          ${langLabel ? `<span class="lang-badge">${escapeHtml(langLabel)}</span>` : ""}
        </div>
        <h2 class="article-title"><a href="${escapeAttr(a.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(a.title)}</a></h2>
        <p class="article-summary">${escapeHtml(a.summary || "")}</p>
        <div class="article-actions">
          <a class="read-link" href="${escapeAttr(a.url)}" target="_blank" rel="noopener noreferrer">
            Lire l'article
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17L17 7M9 7h8v8"/></svg>
          </a>
          <button class="fav-btn ${a.favorite ? "active" : ""}" data-url="${escapeAttr(a.url)}" data-payload='${escapeAttr(JSON.stringify(serializeForFav(a)))}' title="Ajouter aux favoris" aria-label="Ajouter aux favoris">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><polygon points="12 2 15 8.6 22 9.5 17 14.4 18.2 21.5 12 18.1 5.8 21.5 7 14.4 2 9.5 9 8.6 12 2"/></svg>
          </button>
        </div>
      </div>
      ${img}
    </article>`;
}

function serializeForFav(a) {
  return {
    url: a.url, title: a.title, source: a.source, summary: a.summary,
    image: a.image, published: a.published, lang: a.lang,
  };
}

async function onToggleFavorite(e) {
  const btn = e.currentTarget;
  const url = btn.dataset.url;
  const active = btn.classList.toggle("active");
  try {
    if (active) {
      const payload = JSON.parse(btn.dataset.payload);
      await api("/api/favorites", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      showToast("Ajouté aux favoris");
    } else {
      await api("/api/favorites?url=" + encodeURIComponent(url), { method: "DELETE" });
      showToast("Retiré des favoris");
      if (state.currentTheme === "favorites") loadFeed();
    }
  } catch (err) {
    btn.classList.toggle("active");
    showToast("Erreur");
  }
}

function formatDate(s) {
  const d = new Date(s);
  if (isNaN(d)) return s;
  return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "short" });
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function escapeAttr(s) { return escapeHtml(s); }

// ====== Filtres ======
$("#lang-select").addEventListener("change", (e) => { state.lang = e.target.value; loadFeed(); });
$("#sort-select").addEventListener("change", (e) => { state.sort = e.target.value; loadFeed(); });
$("#refresh-btn").addEventListener("click", () => {
  renderFeedSkeleton();
  loadFeed();
});
$("#brief-refresh").addEventListener("click", () => {
  renderBriefSkeleton();
  loadBrief(true);
});

// ====== Modal nouveau thème ======
$("#new-theme-btn").addEventListener("click", () => { $("#modal-overlay").hidden = false; $("#theme-name").focus(); });
$("#modal-close").addEventListener("click", closeModal);
$("#modal-cancel").addEventListener("click", closeModal);
$("#modal-overlay").addEventListener("click", (e) => { if (e.target.id === "modal-overlay") closeModal(); });
function closeModal() {
  $("#modal-overlay").hidden = true;
  $("#new-theme-form").reset();
}
$("#new-theme-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = $("#theme-name").value.trim();
  const kwRaw = $("#theme-keywords").value.trim();
  const keywords = kwRaw.split(",").map(k => k.trim()).filter(Boolean);
  if (!name || !keywords.length) return;
  try {
    const created = await api("/api/themes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, keywords }),
    });
    closeModal();
    await loadThemes();
    selectTheme(created.slug, created.name, "custom");
    showToast("Thème créé");
  } catch (err) {
    showToast("Erreur : " + err.message);
  }
});

// ====== Menu mobile ======
$("#menu-btn").addEventListener("click", () => $("#sidebar").classList.toggle("open"));
$("#brand-link").addEventListener("click", (e) => { e.preventDefault(); selectTheme("tech-ia", "Tech & IA", "predefined"); });

// ====== Thème clair / sombre ======
const themeToggle = $("#theme-toggle");
function applyTheme(t) {
  document.documentElement.setAttribute("data-theme", t);
}
function initTheme() {
  // Pas de localStorage (sandbox iframe) → on suit prefers-color-scheme et le toggle vit en mémoire.
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme(prefersDark ? "dark" : "light");
}
themeToggle.addEventListener("click", () => {
  const cur = document.documentElement.getAttribute("data-theme") || "light";
  applyTheme(cur === "dark" ? "light" : "dark");
});
initTheme();

// ====== Boot ======
(async function init() {
  // Affichage initial pour éviter l'état "Chargement..." bloqué
  $("#page-title").textContent = "Veille";
  $("#page-eyebrow").textContent = "Veille du jour";
  try {
    await loadThemes();
    // Sélection du premier thème prédéfini disponible, fallback tech-ia
    const first = (state.themes.predefined && state.themes.predefined[0]) || { slug: "tech-ia", name: "Tech & IA" };
    await selectTheme(first.slug, first.name, "predefined");
  } catch (e) {
    console.error("Init failed:", e);
    $("#page-title").textContent = "Hors ligne";
    $("#feed").innerHTML = `<div class="empty-state"><h3>Connexion au serveur impossible</h3><p>${escapeHtml(String(e.message || e))}</p><p style="margin-top:12px;color:var(--text-mute);font-size:13px">Réessayez dans quelques secondes ou rechargez la page.</p></div>`;
    $("#brief-body").innerHTML = '<p style="color:var(--text-mute)">Synthèse indisponible — backend injoignable.</p>';
  }
})();
