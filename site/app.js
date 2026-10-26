// Recherche, filtres et petites interactions du carnet
(function () {
  const norm = s => s.normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/œ/g, "oe").toLowerCase();

  // Numérotation continue des étapes (listes qui reprennent à 6, 10…)
  document.querySelectorAll(".r-steps ol[start]").forEach(ol => {
    ol.style.counterReset = "s " + (parseInt(ol.getAttribute("start"), 10) - 1);
  });

  // Ingrédients à cocher
  document.querySelectorAll(".r-ingr li").forEach(li => li.addEventListener("click", () => li.classList.toggle("done")));

  const grid = document.querySelector(".filters + .grid");
  if (!grid) return;
  const cards = [...grid.querySelectorAll(".card")];
  const q = document.getElementById("q");
  const count = document.getElementById("count");
  const reset = document.getElementById("reset");
  const empty = grid.parentElement.querySelector(".empty");
  const catSel = document.querySelector('select[data-f="cat"]');
  const state = { saison: new Set(), temps: new Set(), veg: false };

  function apply() {
    const words = norm(q.value.trim()).split(/\s+/).filter(Boolean);
    const cat = catSel ? catSel.value : "";
    let n = 0;
    for (const c of cards) {
      const d = c.dataset;
      const ok = (!cat || d.cat === cat)
        && (!state.saison.size || state.saison.has(d.saison))
        && (!state.temps.size || state.temps.has(d.temps))
        && (!state.veg || d.veg === "1")
        && words.every(w => d.q.includes(w));
      c.hidden = !ok;
      if (ok) n++;
    }
    // les titres qui correspondent d'abord
    if (words.length) {
      const score = c => words.every(w => c.dataset.t.includes(w)) ? 0 : 1;
      cards.slice().sort((a, b) => score(a) - score(b) || a.dataset.t.localeCompare(b.dataset.t)).forEach(c => grid.appendChild(c));
    }
    count.textContent = n + (n > 1 ? " recettes" : " recette");
    const active = words.length || cat || state.saison.size || state.temps.size || state.veg;
    reset.hidden = !active;
    if (empty) empty.hidden = n > 0;
  }

  document.querySelectorAll(".filters .chip").forEach(b => b.addEventListener("click", () => {
    const f = b.dataset.f, v = b.dataset.v;
    if (f === "veg") state.veg = !state.veg;
    else state[f].has(v) ? state[f].delete(v) : state[f].add(v);
    b.classList.toggle("on");
    apply();
  }));
  q.addEventListener("input", apply);
  if (catSel) catSel.addEventListener("change", apply);
  reset.addEventListener("click", () => {
    q.value = ""; if (catSel) catSel.value = "";
    state.saison.clear(); state.temps.clear(); state.veg = false;
    document.querySelectorAll(".filters .chip.on").forEach(b => b.classList.remove("on"));
    cards.slice().sort((a, b) => a.dataset.t.localeCompare(b.dataset.t)).forEach(c => grid.appendChild(c));
    apply();
  });

  // Recherche lancée depuis l'en-tête (?q=…)
  const p = new URLSearchParams(location.search).get("q");
  if (p) {
    q.value = p;
    document.getElementById("toutes")?.scrollIntoView();
  }
  apply();
})();
