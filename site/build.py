"""Génère le site statique du carnet à partir des fiches .md.

Usage : python site/build.py            -> écrit le site dans _site/
Dépendances : pyyaml, markdown, pillow
"""
import hashlib
import html
import json
import re
import shutil
import unicodedata
from urllib.parse import quote
from pathlib import Path

import markdown
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(__file__).resolve().parent
OUT = ROOT / "_site"
RECIPES = ROOT / "recettes"
ADMIN = "admin/#/collections/recettes"  # éditeur en ligne (Sveltia CMS)

# Ordre et libellés des catégories (la valeur stockée dans les fiches reste inchangée)
CATEGORIES = [
    ("Entrée", "Entrées", "Pour ouvrir le bal"),
    ("Salade", "Salades", "Fraîcheur et croquant"),
    ("Soupe", "Soupes", "Chaudes ou glacées"),
    ("Italien", "Italie", "Pâtes, risottos et compagnie"),
    ("Mediterranéen", "Méditerranée", "Soleil et épices douces"),
    ("Asiat", "Asie", "Nouilles, bols et raviolis"),
    ("Indien", "Inde", "Currys, dahls et pains"),
    ("Plat en sauce", "Plats mijotés", "Le temps fait le travail"),
    ("Plat au four", "Plats au four", "On enfourne et on attend"),
    ("Plat à la poelle", "À la poêle", "Rapide et doré"),
    ("Street-food", "Street-food", "Burgers, tacos et sandwichs"),
    ("Accompagnement", "Accompagnements", "Tout ce qui va à côté"),
    ("Sauce et condiment", "Sauces & condiments", "Le petit plus qui change tout"),
    ("Dessert", "Desserts", "Pour finir en douceur"),
]
CAT_LABEL = {k: v for k, v, _ in CATEGORIES}
CAT_TAGLINE = {k: t for k, _, t in CATEGORIES}
# Photo de la vignette de catégorie sur la page d'accueil (sinon : la première recette illustrée)
TILE_PICK = {"Sauce et condiment": "Sauce chimichurri et entrecôte.md", "Dessert": "Tarte au citron meringuée.md"}
SAISONS = ["printemps", "été", "automne-hiver", "toute saison"]
TEMPS = ["< 30 min", "30 min – 1 h", "1 h – 2 h", "2 h +"]


def slugify(s):
    s = unicodedata.normalize("NFKD", s.replace("œ", "oe").replace("Œ", "oe"))
    s = s.encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def norm(s):
    """Texte simplifié pour la recherche (sans accents, minuscules)."""
    s = unicodedata.normalize("NFKD", s.replace("œ", "oe")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower())


def esc(s):
    return html.escape(str(s), quote=True)


def read_recipes():
    recipes = []
    for f in sorted(RECIPES.glob("*.md")):
        text = f.read_text()
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
        if not m:
            print("sans en-tête :", f.name)
            continue
        meta = yaml.safe_load(m.group(1))
        meta["body"] = m.group(2)
        meta["file"] = f.name
        meta["stem"] = f.stem
        meta["image"] = (meta.get("image") or "").lstrip("/")
        meta.setdefault("source", "Perso")
        meta["slug"] = slugify(f.stem)
        recipes.append(meta)
    return recipes


def split_sections(body):
    """Découpe le corps en sections '## ...' -> liste de (titre, texte)."""
    parts = re.split(r"^## +(.+)$", body, flags=re.M)
    intro = parts[0].strip()
    secs = [(parts[i].strip(), parts[i + 1].strip()) for i in range(1, len(parts), 2)]
    return intro, secs


LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+\.)\s")


def md(text):
    # Les fiches enchaînent souvent « **Sous-titre** » et une liste sans ligne vide :
    # on ajoute la ligne vide attendue par Markdown.
    out = []
    for line in text.split("\n"):
        if LIST_ITEM.match(line) and out and out[-1].strip() and not LIST_ITEM.match(out[-1]) and not out[-1].startswith((" ", "\t")):
            out.append("")
        out.append(line)
    return markdown.markdown("\n".join(out), extensions=["sane_lists", "tables"])


# ---------- images ----------

def build_images(recipes):
    """Copie les couvertures en WebP réduites (1400 px et 640 px)."""
    for r in recipes:
        img = r.get("image") or ""
        if img.startswith("http"):
            r["img_big"] = r["img_small"] = img
            continue
        src = ROOT / img
        if not img or not src.exists():
            r["img_big"] = r["img_small"] = ""
            continue
        h = hashlib.md5(src.read_bytes()).hexdigest()[:8]  # nom lié au contenu : une photo changée = nouveau fichier
        base = f"img/{r['slug']}-{h}"
        for size, suffix in ((1400, "big"), (640, "small")):
            dst = OUT / f"{base}-{suffix}.webp"
            if not dst.exists():
                im = Image.open(src).convert("RGB")
                im.thumbnail((size, size))
                dst.parent.mkdir(parents=True, exist_ok=True)
                im.save(dst, "WEBP", quality=80)
            r[f"img_{suffix}"] = f"{base}-{suffix}.webp"


def img_url(path, prefix):
    if not path:
        return ""
    return path if path.startswith("http") else prefix + path


# ---------- gabarits ----------

def temps_court(t):
    return (t or "").split(" (")[0]


def repos(t):
    m = re.search(r"\(repos (.+)\)", t or "")
    return m.group(1) if m else ""


ICON_LEAF = '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 19c0-8 5-13 15-14-1 10-6 15-14 15H5v-1Zm0 0 8-8" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>'
ICON_CLOCK = '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M12 7.5V12l3 2" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>'
ICON_PLAY = '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l11-6.5-11-6.5Z" fill="currentColor"/></svg>'
ICON_SEARCH = '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="m16 16 4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'


def card(r, prefix):
    search = norm(" ".join([r["titre"], CAT_LABEL.get(r["categorie"], ""), r["body"]]))
    search = re.sub(r"https?://\S+", "", search)
    img = img_url(r.get("img_small"), prefix)
    veg = f'<span class="tag veg">{ICON_LEAF}Végé</span>' if r.get("vegetarien") else ""
    return f"""<a class="card" href="{prefix}recette/{r['slug']}/"
 data-cat="{esc(r['categorie'])}" data-saison="{esc(r['saison'])}" data-temps="{esc(temps_court(r['temps']))}"
 data-veg="{1 if r.get('vegetarien') else 0}" data-src="{esc(r['source'])}" data-q="{esc(search)}" data-t="{esc(norm(r['titre']))}">
  <div class="card-img">{f'<img loading="lazy" src="{esc(img)}" alt="">' if img else '<div class="noimg"></div>'}</div>
  <div class="card-body">
    <span class="card-cat">{esc(CAT_LABEL.get(r['categorie'], r['categorie']))}</span>
    <h3>{esc(r['titre'])}</h3>
    <div class="card-meta"><span class="tag">{ICON_CLOCK}{esc(temps_court(r['temps']))}</span>{veg}</div>
  </div>
</a>"""


ICON_PLUS = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>'
ICON_EDIT = '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16v4Zm10-14 4 4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>'


def new_card(prefix, cat=None):
    q = f"?categorie={quote(cat)}" if cat else ""
    return f"""<a class="card-new" href="{prefix}{ADMIN}/new{q}">
  <span class="plus">{ICON_PLUS}</span><span>Nouvelle recette</span></a>"""


def filters(show_cat):
    cat = ""
    if show_cat:
        opts = "".join(f'<option value="{esc(k)}">{esc(v)}</option>' for k, v, _ in CATEGORIES)
        cat = f'<label class="sel"><span>Catégorie</span><select data-f="cat"><option value="">Toutes</option>{opts}</select></label>'
    chips = lambda name, vals: "".join(
        f'<button type="button" class="chip" data-f="{name}" data-v="{esc(v)}">{esc(v)}</button>' for v in vals)
    return f"""<div class="filters">
  <div class="search">{ICON_SEARCH}<input type="search" id="q" placeholder="Rechercher une recette, un ingrédient…" autocomplete="off"></div>
  <div class="frow">
    {cat}
    <div class="fgroup"><span class="flabel">Saison</span>{chips('saison', SAISONS)}</div>
    <div class="fgroup"><span class="flabel">Temps</span>{chips('temps', TEMPS)}</div>
    <div class="fgroup"><button type="button" class="chip" data-f="veg" data-v="1">{ICON_LEAF}Végétarien</button>
</div>
  </div>
  <div class="fstatus"><span id="count"></span><button type="button" id="reset">Effacer les filtres</button></div>
</div>"""


def page(title, body, prefix, active="", desc="Mon carnet de recettes"):
    nav = "".join(
        f'<a href="{prefix}categorie/{slugify(k)}/"{" aria-current=page" if k == active else ""}>{esc(v)}</a>'
        for k, v, _ in CATEGORIES)
    return f"""<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(desc)}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,650&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{prefix}style.css">
</head><body>
<header class="top">
  <div class="top-in">
    <a class="logo" href="{prefix}"><span class="logo-mark">C</span><span>Le carnet</span></a>
    <form class="top-search" action="{prefix}" method="get">{ICON_SEARCH}<input name="q" type="search" placeholder="Rechercher…" aria-label="Rechercher"></form>
  </div>
  <nav class="cats">{nav}</nav>
</header>
<main>{body}</main>
<footer class="foot">Carnet de recettes perso · recettes tirées en grande partie des vidéos de <a href="https://www.youtube.com/@Whoogys">Whoogy's</a> · <a href="{prefix}admin/">Gérer les recettes</a></footer>
<script src="{prefix}app.js"></script>
</body></html>"""


def home(recipes):
    prefix = ""
    by_cat = {}
    for r in recipes:
        by_cat.setdefault(r["categorie"], []).append(r)
    tiles = []
    for k, label, tag in CATEGORIES:
        rs = by_cat.get(k, [])
        if not rs:
            continue
        pick = next((r for r in rs if r["file"] == TILE_PICK.get(k)), None) or \
            next((r for r in rs if r.get("img_small") and not r["img_small"].startswith("http")), rs[0])
        tiles.append(f"""<a class="tile" href="categorie/{slugify(k)}/">
  <img loading="lazy" src="{esc(img_url(pick.get('img_small'), prefix))}" alt="">
  <span class="tile-txt"><strong>{esc(label)}</strong><em>{len(rs)} recettes</em></span></a>""")
    cards = "\n".join(card(r, prefix) for r in sorted(recipes, key=lambda r: norm(r["titre"])))
    body = f"""
<section class="hero">
  <p class="eyebrow">{len(recipes)} recettes · {len(by_cat)} catégories</p>
  <h1>Qu'est-ce qu'on mange&nbsp;?</h1>
  <p class="lead">Les recettes testées, notées et illustrées. Cherchez par plat, par ingrédient ou selon le temps que vous avez.</p>
</section>
<section class="tiles">{''.join(tiles)}</section>
<section class="list" id="toutes">
  <h2 class="sec-title">Toutes les recettes</h2>
  {filters(True)}
  <div class="grid">{new_card(prefix)}{cards}</div>
  <p class="empty" hidden>Aucune recette ne correspond. Essayez d'enlever un filtre.</p>
</section>"""
    return page("Le carnet de recettes", body, prefix)


def category_page(key, recipes):
    prefix = "../../"
    rs = sorted([r for r in recipes if r["categorie"] == key], key=lambda r: norm(r["titre"]))
    cover = next((r for r in rs if r["file"] == TILE_PICK.get(key) and r.get("img_big")), None) or \
        next((r for r in rs if r.get("img_big") and r.get("source") != "Perso"), None)
    style = f' style="--cover:url(\'{esc(prefix + cover["img_big"])}\')"' if cover else ""
    body = f"""
<section class="cat-hero"{style}>
  <div class="cat-hero-in">
    <a class="crumb" href="{prefix}">Toutes les recettes</a>
    <h1>{esc(CAT_LABEL[key])}</h1>
    <p>{esc(CAT_TAGLINE[key])} · {len(rs)} recettes</p>
  </div>
</section>
<section class="list">
  {filters(False)}
  <div class="grid">{new_card(prefix, key)}{''.join(card(r, prefix) for r in rs)}</div>
  <p class="empty" hidden>Aucune recette ne correspond. Essayez d'enlever un filtre.</p>
</section>"""
    return page(f"{CAT_LABEL[key]} · Le carnet", body, prefix, active=key)


def recipe_page(r, recipes):
    prefix = "../../"
    intro, secs = split_sections(r["body"])
    video_html, pres, ingr, steps, other = "", "", "", "", []
    for title, txt in secs:
        t = title.lower()
        if "vidéo" in t:
            link = re.search(r"\[([^\]]+)\]\((https://www\.youtube\.com/[^)]+)\)", txt)
            note = re.sub(r"\[[^\]]+\]\([^)]+\)", "", txt).strip()
            if link:
                video_html = f"""<a class="video" href="{esc(link.group(2))}" target="_blank" rel="noopener">
  <span class="video-play">{ICON_PLAY}</span><span><strong>Voir la vidéo</strong><em>{esc(link.group(1))}</em></span></a>"""
                if note:
                    video_html += f'<div class="video-note">{md(note)}</div>'
        elif "présentation" in t:
            pres = md(txt)
        elif "ingrédient" in t:
            ingr = md(txt)
        elif "étape" in t:
            steps = md(txt)
        else:
            other.append(f"<h2>{esc(re.sub(r'^[0-9]+\\. ', '', title))}</h2>{md(txt)}")
    if not ingr and not steps:
        steps = md(r["body"])
    big = img_url(r.get("img_big"), prefix)
    chips = [f'<a class="tag" href="{prefix}categorie/{slugify(r["categorie"])}/">{esc(CAT_LABEL.get(r["categorie"], r["categorie"]))}</a>',
             f'<span class="tag">{ICON_CLOCK}{esc(temps_court(r["temps"]))}</span>']
    if repos(r["temps"]):
        chips.append(f'<span class="tag">+ repos {esc(repos(r["temps"]))}</span>')
    chips.append(f'<span class="tag">{esc(r["saison"])}</span>')
    if r.get("vegetarien"):
        chips.append(f'<span class="tag veg">{ICON_LEAF}Végétarien</span>')
    if r.get("source") == "Perso":
        chips.append('<span class="tag perso">Recette perso</span>')
    same = [x for x in recipes if x["categorie"] == r["categorie"] and x["slug"] != r["slug"]][:4]
    more = "".join(card(x, prefix) for x in same)
    body = f"""
<article class="recipe">
  <header class="r-head">
    <a class="crumb" href="{prefix}categorie/{slugify(r['categorie'])}/">{esc(CAT_LABEL.get(r['categorie'], r['categorie']))}</a>
    <h1>{esc(r['titre'])}</h1>
    <div class="r-tags">{''.join(chips)}</div>
    <a class="edit" href="{prefix}{ADMIN}/entries/{quote(r['stem'])}">{ICON_EDIT}Modifier la recette</a>
  </header>
  {f'<figure class="r-img"><img src="{esc(big)}" alt="{esc(r["titre"])}"></figure>' if big else ''}
  <div class="r-intro">{intro and md(intro)}{pres}{video_html}</div>
  <div class="r-cols">
    {f'<aside class="r-ingr"><h2>Ingrédients</h2><p class="hint">Touchez un ingrédient pour le cocher.</p>{ingr}</aside>' if ingr else ''}
    <section class="r-steps">{'<h2>Étapes</h2>' if steps else ''}{steps}{''.join(other)}</section>
  </div>
</article>
{f'<section class="list more"><h2 class="sec-title">Dans la même catégorie</h2><div class="grid">{more}</div></section>' if more else ''}"""
    return page(f"{r['titre']} · Le carnet", body, prefix, active=r["categorie"])


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def main():
    recipes = read_recipes()
    OUT.mkdir(exist_ok=True)
    build_images(recipes)
    for f in ("style.css", "app.js"):
        shutil.copy(SRC / f, OUT / f)
    shutil.copytree(SRC / "admin", OUT / "admin", dirs_exist_ok=True)
    # originaux, pour l'aperçu des photos dans l'éditeur
    shutil.copytree(ROOT / "images", OUT / "images", dirs_exist_ok=True)
    write(OUT / "index.html", home(recipes))
    for k, _, _ in CATEGORIES:
        if any(r["categorie"] == k for r in recipes):
            write(OUT / "categorie" / slugify(k) / "index.html", category_page(k, recipes))
    for r in recipes:
        write(OUT / "recette" / r["slug"] / "index.html", recipe_page(r, recipes))
    (OUT / ".nojekyll").write_text("")
    unknown = {r["categorie"] for r in recipes} - set(CAT_LABEL)
    if unknown:
        print("catégories inconnues :", unknown)
    print(f"{len(recipes)} recettes -> {OUT}")


if __name__ == "__main__":
    main()
