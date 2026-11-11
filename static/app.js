/* Sito No TAV: menu, filtri, ricerca, linea del tempo, curve di livello.
   Funziona sia nel sito statico sia nell'anteprima a file unico (window.__PAGES). */
(function () {
  "use strict";
  var SPA = !!window.__PAGES;
  var anchor = "";
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var TIPI = { evento: "Evento", luogo: "Luogo", persona: "Persona", organizzazione: "Organizzazione", documento: "Documento", studio: "Studio", dato: "Dato", norma: "Atto o norma", procedimento: "Procedimento", costo: "Costo pubblico", canzone: "Canzone", concerto: "Concerto" };
  function href(p) { return SPA ? "#/" + p : (document.querySelector('link[rel=stylesheet][href$="static/style.css"]').getAttribute("href").replace("static/style.css", "") + p + "index.html"); }

  /* ---------- menu */
  var header = document.querySelector("header.site");
  var btns = [].slice.call(header.querySelectorAll("nav.main button"));
  var panels = [].slice.call(header.querySelectorAll(".mega"));
  var mt = header.querySelector(".menu-toggle");
  function closeAll() { panels.forEach(function (p) { p.hidden = true; }); btns.concat([mt]).forEach(function (b) { b.setAttribute("aria-expanded", "false"); }); }
  function toggle(b, name) {
    var open = b.getAttribute("aria-expanded") === "true"; closeAll();
    if (!open) { b.setAttribute("aria-expanded", "true"); header.querySelector('.mega[data-menu="' + name + '"]').hidden = false; }
  }
  btns.forEach(function (b) { b.addEventListener("click", function (e) { toggle(b, b.dataset.menu); e.stopPropagation(); }); });
  var mob = header.querySelector('.mega[data-menu="mobile"] .wrap');
  header.querySelectorAll(".mega:not([data-menu=mobile]) a").forEach(function (a) { mob.appendChild(a.cloneNode(true)); });
  mt.addEventListener("click", function (e) { toggle(mt, "mobile"); e.stopPropagation(); });
  document.addEventListener("click", function (e) { if (!header.contains(e.target) || e.target.closest(".mega a")) closeAll(); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeAll(); });

  /* ---------- curve di livello */
  function topo(cv) {
    var ctx = cv.getContext("2d"), P = [], seed = 7;
    var rnd = function () { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    for (var i = 0; i < 60; i++) P.push([rnd() * 1.3, rnd() * 1.3, rnd() * .5 + .3, rnd() * .08 + .04]);
    var f = function (x, y) { var v = 0; for (var k = 0; k < P.length; k++) { var dx = x - P[k][0], dy = y - P[k][1]; v += P[k][2] * Math.exp(-(dx * dx + dy * dy) / (P[k][3] * 1.6)); } return v; };
    function draw() {
      var r = cv.getBoundingClientRect(); if (!r.width) return;
      var dpr = window.devicePixelRatio || 1; cv.width = r.width * dpr; cv.height = r.height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, r.width, r.height);
      ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue("--contour"); ctx.lineWidth = 1;
      var S = 9, W = Math.ceil(r.width / S) + 1, H = Math.ceil(r.height / S) + 1, g = [], mn = Infinity, mx = -Infinity;
      for (var j = 0; j < H; j++) for (var i = 0; i < W; i++) { var v = f(i * S / r.width * 1.2, j * S / r.width * 1.2 + .3); g[j * W + i] = v; if (v < mn) mn = v; if (v > mx) mx = v; }
      ctx.beginPath();
      for (var k = 1; k < 18; k++) {
        var t = mn + (mx - mn) * k / 18;
        for (j = 0; j < H - 1; j++) for (i = 0; i < W - 1; i++) {
          var a = g[j * W + i], b = g[j * W + i + 1], c = g[(j + 1) * W + i + 1], d = g[(j + 1) * W + i], pts = [];
          var L = function (p, q, x1, y1, x2, y2) { var u = (t - p) / (q - p); pts.push([(x1 + (x2 - x1) * u) * S, (y1 + (y2 - y1) * u) * S]); };
          if ((a < t) !== (b < t)) L(a, b, i, j, i + 1, j); if ((b < t) !== (c < t)) L(b, c, i + 1, j, i + 1, j + 1);
          if ((c < t) !== (d < t)) L(c, d, i + 1, j + 1, i, j + 1); if ((d < t) !== (a < t)) L(d, a, i, j + 1, i, j);
          for (var z = 0; z + 1 < pts.length; z += 2) { ctx.moveTo(pts[z][0], pts[z][1]); ctx.lineTo(pts[z + 1][0], pts[z + 1][1]); }
        }
      }
      ctx.stroke();
    }
    draw(); var to; window.addEventListener("resize", function () { clearTimeout(to); to = setTimeout(draw, 150); });
  }

  /* ---------- filtri sulle griglie */
  function filterbar(bar) {
    var box = document.getElementById(bar.dataset.for); if (!box) return;
    var input = bar.querySelector(".find"), chips = [].slice.call(bar.querySelectorAll(".chip")), tipo = "";
    function apply() {
      var q = (input.value || "").toLowerCase().trim();
      [].forEach.call(box.children, function (el) {
        var ok = (!tipo || el.dataset.t === tipo) && (!q || (el.dataset.q || el.textContent.toLowerCase()).indexOf(q) > -1);
        el.hidden = !ok;
      });
    }
    input.addEventListener("input", apply);
    chips.forEach(function (c) { c.addEventListener("click", function () { tipo = c.dataset.f; chips.forEach(function (x) { x.setAttribute("aria-pressed", x === c); }); apply(); }); });
  }

  /* ---------- ricerca in tutte le schede */
  function searchAll(box) {
    var idx = JSON.parse(box.querySelector(".idx").textContent), input = box.querySelector(".find"), out = box.querySelector(".results");
    var chips = [].slice.call(box.querySelectorAll(".chip")), tipo = "";
    function run() {
      var q = input.value.toLowerCase().trim();
      if (!q && !tipo) { out.innerHTML = "<p>Scriviamo almeno una parola, oppure scegliamo un tipo di scheda.</p>"; return; }
      var r = idx.filter(function (x) { return (!tipo || x[2] === tipo) && (!q || (x[1] + " " + x[0]).toLowerCase().indexOf(q) > -1); });
      out.innerHTML = r.slice(0, 200).map(function (x) { return '<a href="' + href("schede/" + x[0] + "/") + '"><span class="mono">' + esc(TIPI[x[2]] || x[2]) + '</span><b>' + esc(x[1]) + '</b><span class="mono">' + esc(x[3]) + "</span></a>"; }).join("") + (r.length > 200 ? "<p>Altri " + (r.length - 200) + " risultati: restringiamo la ricerca.</p>" : "") + (r.length ? "" : "<p>Nessuna scheda trovata.</p>");
    }
    input.addEventListener("input", run);
    chips.forEach(function (c) { c.addEventListener("click", function () { var on = c.getAttribute("aria-pressed") !== "true"; chips.forEach(function (x) { x.setAttribute("aria-pressed", "false"); }); c.setAttribute("aria-pressed", on); tipo = on ? c.dataset.f : ""; run(); }); });
    run();
  }

  /* ---------- linea del tempo */
  var MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"];
  var MESI_L = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"];
  function timeline(root) {
    var E = JSON.parse(root.querySelector(".tl-data").textContent);
    var Y0 = 1989, Y1 = 2026, yearsEl = root.querySelector(".years"), panel = root.querySelector(".tl-panel"), state = { y: null, m: null };
    var byYear = function (y) { return E.filter(function (e) { return e.y === y; }); };
    for (var y = Y0; y <= Y1; y++) (function (y) {
      if (y % 10 === 0 && y !== Y0) { var d = document.createElement("span"); d.className = "decade"; yearsEl.appendChild(d); }
      var n = byYear(y).length, b = document.createElement("button"), h = Math.min(n, 14);
      b.className = "yr" + (n ? " has" : ""); b.dataset.y = y; b.setAttribute("aria-pressed", "false");
      b.setAttribute("aria-label", n ? y + ", " + n + " eventi" : y + ", nessun evento");
      if (!n) b.tabIndex = -1;
      var ticks = ""; for (var i = 0; i < h; i++) ticks += '<i style="height:' + (4 + i * 1.3) + 'px"></i>';
      b.innerHTML = '<span class="ticks">' + (n ? ticks : '<i class="none"></i>') + "</span>" + y;
      if (n) b.onclick = function () { pick(y); };
      yearsEl.appendChild(b);
    })(y);
    function pick(y) {
      state = { y: y, m: null };
      var ms = uniq(byYear(y).map(function (e) { return e.m; })); if (ms.length === 1) state.m = ms[0];
      render(true);
      var b = yearsEl.querySelector('.yr[data-y="' + y + '"]'); if (b) yearsEl.scrollLeft = b.offsetLeft - yearsEl.clientWidth / 2;
      if (!SPA) try { history.replaceState(null, "", "#a" + y); } catch (_) { }
    }
    function uniq(a) { return a.filter(function (x, i) { return a.indexOf(x) === i; }).sort(function (a, b) { return a - b; }); }
    function render(fresh) {
      [].forEach.call(yearsEl.querySelectorAll(".yr"), function (b) { b.setAttribute("aria-pressed", +b.dataset.y === state.y); });
      var evs = byYear(state.y), cnt = function (m) { return evs.filter(function (e) { return e.m === m; }).length; };
      var months = uniq(evs.map(function (e) { return e.m; }));
      var head = '<div class="year-head"><div class="big">' + state.y + '</div><div class="year-meta"><strong>' + evs.length + (evs.length === 1 ? " evento" : " eventi") + "</strong><p>" + months.map(function (m) { return m ? MESI_L[m - 1] : "mese non indicato"; }).join(", ") + "</p></div></div>";
      var mo = '<div class="months" role="group" aria-label="Mesi del ' + state.y + '"' + (fresh ? "" : ' style="animation:none"') + ">" +
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 0].map(function (m) { var c = cnt(m); if (m === 0 && !c) return ""; return '<button class="mo" ' + (c ? "" : "disabled") + ' aria-pressed="' + (state.m === m) + '" data-m="' + m + '">' + (m ? MESI[m - 1] : "s.d.") + "<b>" + (c || "·") + "</b></button>"; }).join("") + "</div>";
      var list;
      if (state.m === null) list = '<p class="hint">Scegliamo un mese tra quelli accesi.</p>';
      else {
        var sel = evs.filter(function (e) { return e.m === state.m; }).sort(function (a, b) { return a.g - b.g; });
        list = '<p class="hint">' + (state.m ? MESI_L[state.m - 1] : "Mese non indicato,") + " " + state.y + '</p><div class="tl-events">' + sel.map(function (e, i) {
          return '<a class="tl-ev" href="' + href("schede/" + e.s + "/") + '" style="animation-delay:' + i * 50 + 'ms"><div class="day">' + (e.g || "–") + "<small>" + (e.m ? MESI[e.m - 1] + " " : "") + e.y + '</small></div><div><h3>' + esc(e.t) + "</h3>" + (e.l ? '<p class="place">' + esc(e.l) + "</p>" : "") +
            '<div class="tags">' + e.c.map(function (c) { return '<span class="tag">' + esc(c) + "</span>"; }).join("") + (e.chk ? '<span class="tag check">Da verificare</span>' : "") + "</div>" +
            (e.x ? '<p class="desc">' + esc(e.x) + "</p>" : "") + (e.n ? '<div class="numrow"><span>Numeri</span>' + esc(e.n) + "</div>" : "") + "</div></a>";
        }).join("") + "</div>";
      }
      panel.innerHTML = head + mo + list;
      [].forEach.call(panel.querySelectorAll(".mo:not(:disabled)"), function (b) { b.onclick = function () { state.m = +b.dataset.m; render(false); }; });
    }
    var want = parseInt((SPA ? anchor : location.hash.slice(1)).replace("a", ""), 10);
    var start = byYear(want).length ? want : 2005;
    pick(start);
    var ms = uniq(byYear(start).map(function (e) { return e.m; })); state.m = ms[ms.length - 1]; render(true);
  }

  function init(root) {
    [].forEach.call(root.querySelectorAll("canvas.topo"), topo);
    [].forEach.call(root.querySelectorAll(".filterbar"), filterbar);
    [].forEach.call(root.querySelectorAll(".search-all"), searchAll);
    [].forEach.call(root.querySelectorAll("[data-tl]"), timeline);
  }

  /* ---------- anteprima a file unico: router su #/percorso */
  if (SPA) {
    var main = document.getElementById("main");
    var go = function () {
      var h = location.hash;
      if (h && h.indexOf("#/") !== 0) { var el = document.getElementById(h.slice(1)); if (el) el.scrollIntoView(); return; }
      var p = decodeURIComponent((h || "#/").slice(2)), q = p.indexOf("?");
      anchor = q > -1 ? p.slice(q + 1) : ""; p = q > -1 ? p.slice(0, q) : p;
      var pg = window.__PAGES[p] || window.__PAGES[p + "/"];
      if (!pg) { main.innerHTML = '<div class="wrap" style="padding:80px 16px"><h1>Pagina non trovata</h1><p><a href="#/">Torna alla home</a></p></div>'; return; }
      main.innerHTML = pg[2]; document.body.dataset.sez = pg[1];
      document.title = pg[0] + (p ? " · No TAV" : "");
      window.scrollTo(0, 0); closeAll(); init(main);
      if (anchor && !/^a\d{4}$/.test(anchor)) { var t = document.getElementById(anchor); if (t) { if (t.tagName === "DETAILS") t.open = true; t.scrollIntoView(); } }
    };
    window.addEventListener("hashchange", go); go();
  } else {
    init(document);
  }
})();
