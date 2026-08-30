"use strict";

const form = document.getElementById("searchForm");
const input = document.getElementById("q");
const limitChips = document.querySelectorAll(".limitchip");
const results = document.getElementById("results");
const hint = document.getElementById("hint");
const statText = document.getElementById("statText");
const refreshBtn = document.getElementById("refreshBtn");
const modal = document.getElementById("modal");
const modalClose = document.getElementById("modalClose");
const modalVideo = document.getElementById("modalVideo");
const modalTitle = document.getElementById("modalTitle");
const modalSub = document.getElementById("modalSub");

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
}

function fmtDauer(d) {
  if (!d) return "";
  const p = String(d).split(":");
  if (p.length === 3 && !isNaN(+p[0])) return `${+p[0]} Std. ${+p[1]} Min.`;
  return d;
}

// Formate kommen als {label, url} bereits vom Server (Resolver-Plugin).
function formatsOf(item) {
  return (item.formats || []).filter(f => f && f.url);
}

function bestVideoUrl(item) {
  const f = formatsOf(item);
  // möglichst hohe Qualität zuletzt: Standard als sichere Wahl
  return (f.find(x => x.label === "Standard") || f[f.length - 1] || {}).url || "";
}

// URL-Validierung (HEAD) — asynchron, deaktiviert defekte Formate global
const checkCache = {};
async function isValid(url) {
  if (url in checkCache) return checkCache[url];
  try {
    const r = await (await fetch(`/api/check?url=${encodeURIComponent(url)}`)).json();
    checkCache[url] = r.ok;
    return r.ok;
  } catch { return true; } // unsicher ⇒ erstmal erlauben
}

function openPreview(item, videoUrl) {
  modal.classList.add("open");
  modalTitle.textContent = item.titel || "";
  modalSub.textContent = [item.sender, item.datum].filter(Boolean).join("  •  ");
  modalVideo.src = `/api/stream?url=${encodeURIComponent(videoUrl)}`;
  modalVideo.load();
  modalVideo.play().catch(() => {});
}

function closePreview() {
  modal.classList.remove("open");
  modalVideo.pause();
  modalVideo.removeAttribute("src");
  modalVideo.load();
}

modalClose.addEventListener("click", closePreview);
modal.addEventListener("click", (e) => { if (e.target === modal) closePreview(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePreview(); });

function render(r) {
  results.innerHTML = "";
  if (!r.results || r.results.length === 0) {
    hint.textContent = "Keine Treffer. Versuche andere Schreibweise oder einen kürzeren Begriff.";
    return;
  }
  hint.textContent = `${r.count} Treffer`;
  for (const item of r.results) {
    const card = el("div", "card");
    card.appendChild(el("span", "sender", item.sender));
    card.appendChild(el("h3", "", item.titel));
    if (item.thema) card.appendChild(el("div", "thema", item.thema));
    if (item.beschreibung) card.appendChild(el("div", "desc", item.beschreibung));
    card.appendChild(el("div", "meta",
      [item.datum, fmtDauer(item.dauer),
       item.groesse_mb ? `${item.groesse_mb} MB` : ""].filter(Boolean).join("  •  ")));

    // Format-Auswahl (vom Resolver geliefert) + Validierung im Hintergrund
    const fmtBox = el("div", "fmts");
    const videoUrl = bestVideoUrl(item);
    const fmts = formatsOf(item);
    if (!videoUrl && fmts.length === 0) {
      fmtBox.appendChild(el("span", "muted", "Kein Video verfügbar"));
    } else {
      for (const f of fmts) {
        const b = el("button", "fmt", f.label);
        b.addEventListener("click", () => openPreview(item, f.url));
        fmtBox.appendChild(b);
        isValid(f.url).then(ok => {
          if (!ok) { b.disabled = true; b.title = "nicht erreichbar"; }
        });
      }
      if (fmts.length === 0 && videoUrl) {
        const b = el("button", "fmt", "Abspielen");
        b.addEventListener("click", () => openPreview(item, videoUrl));
        fmtBox.appendChild(b);
      }
    }

    // Untertitel + Download-Links
    const subBox = el("div", "subbox");
    if (item.url_untertitel) {
      const a = el("a", "", "📄 Untertitel bestellen");
      a.href = `/api/download?url=${encodeURIComponent(item.url_untertitel)}`;
      subBox.appendChild(a);
    }
    for (const f of fmts) {
      const a = el("a", "", `⬇ ${f.label} als Datei`);
      a.href = `/api/download?url=${encodeURIComponent(f.url)}`;
      a.download = "";
      subBox.appendChild(a);
    }
    if (item.website) {
      const w = el("a", "", "Webseite");
      w.href = item.website; w.target = "_blank"; w.rel = "noopener";
      subBox.appendChild(w);
    }

    card.appendChild(fmtBox);
    if (subBox.children.length) card.appendChild(subBox);
    results.appendChild(card);
  }
}

let currentLimit = "20";

function setLimit(n) {
  currentLimit = String(n);
  limitChips.forEach(c => c.classList.toggle("active", c.dataset.n === currentLimit));
}

async function doSearch(q) {
  if (!q) { results.innerHTML = ""; hint.textContent = ""; return; }
  hint.textContent = "Suche…";
  results.replaceChildren(el("div", "skeleton"), el("div", "skeleton"), el("div", "skeleton"));
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&n=${currentLimit}`);
    render(await res.json());
  } catch (e) {
    results.innerHTML = "";
    hint.textContent = "Fehler bei der Suche: " + e.message;
  }
}

async function refreshStats() {
  try {
    const s = await (await fetch("/api/stats")).json();
    if (s.fehlt) {
      statText.textContent = "Keine Datenbank vorhanden → ‚Neu laden‘.";
      statText.title = "Noch keine Filmliste indexiert.";
    } else {
      statText.textContent = `${s.eintraege.toLocaleString("de-DE")} Einträge • Stand ${new Date(s.stand_ts * 1000).toLocaleString("de-DE")}`;
      statText.title = "Lokale SQLite-Datenbank (offline). " + s.db_datei;
    }
  } catch (e) {
    statText.textContent = "Status nicht erreichbar.";
  }
}

refreshBtn.addEventListener("click", async () => {
  refreshBtn.disabled = true;
  statText.classList.add("busy");
  statText.textContent = "Neu laden dauert eine Weile…";
  try {
    await fetch("/api/refresh", { method: "POST" });
    let i = 0;
    const timer = setInterval(async () => {
      i++;
      try {
        const s = await (await fetch("/api/stats")).json();
        if (s.eintraege > 0 || i > 900) {
          clearInterval(timer);
          refreshBtn.disabled = false;
          statText.classList.remove("busy");
          await refreshStats();
        } else {
          statText.textContent = "Indexierung läuft…";
        }
      } catch (e) { /* dranbleiben */ }
    }, 4000);
  } catch (e) {
    refreshBtn.disabled = false;
    statText.classList.remove("busy");
    statText.textContent = "Fehler: " + e.message;
  }
});

form.addEventListener("submit", (e) => {
  e.preventDefault();
  doSearch(input.value.trim());
});

// Trefferzahl anklicken → sofort neu suchen (falls ein Suchbegriff da ist)
limitChips.forEach(chip => {
  chip.addEventListener("click", () => {
    setLimit(chip.dataset.n);
    const q = input.value.trim();
    if (q) doSearch(q);
  });
});
setLimit(currentLimit);

refreshStats();