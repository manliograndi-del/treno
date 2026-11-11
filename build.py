#!/usr/bin/env python3
"""Generatore del sito No TAV.

Legge le ricerche in ../ricerche/*.md (tabelle CSV, schede "### slug", sintesi,
bibliografie) e scrive:
  - public/            il sito statico multipagina (da pubblicare su GitHub Pages)
  - anteprima.html     lo stesso sito in un solo file, per l'anteprima

Uso:  python3 build.py [--out public] [--anteprima anteprima.html]
Richiede solo Python 3 e il pacchetto "markdown" (pip install markdown).
"""
import csv, io, re, json, html, sys, shutil, base64, argparse
from pathlib import Path
from collections import defaultdict, OrderedDict
import markdown

ROOT = Path(__file__).resolve().parent
RIC = ROOT.parent / "ricerche"
STATIC = ROOT / "static"

# ---------------------------------------------------------------- struttura
SEZIONI = OrderedDict([
    ("storia", dict(t="Storia", s="Dal 1989 a oggi, periodo per periodo", ic="i-clock", g="conoscere",
        intro="Qui raccontiamo la storia del movimento dal 1989 a oggi: le decisioni sull'opera, le giornate in piazza, i cantieri. Ogni evento ha la sua data, il suo luogo e le sue fonti.")),
    ("la-valle", dict(t="La valle", s="Paesi, luoghi della lotta, cantieri", ic="i-map", g="conoscere",
        intro="La Val di Susa: i paesi, i luoghi dove ci siamo ritrovati, i cantieri e le infrastrutture che la attraversano.")),
    ("perche-no", dict(t="Perché No", s="I dati sull'opera, tema per tema", ic="i-chart", g="conoscere",
        intro="Qui mettiamo in fila i dati sull'opera: traffico, costi, analisi costi-benefici, ambiente, alternative. Accanto a ogni dato indichiamo chi lo afferma e il documento da cui viene.")),
    ("la-scienza", dict(t="La scienza", s="Studi, tecnici, metodi, iter", ic="i-flask", g="conoscere",
        intro="Gli studi su geologia, acqua, aria, salute, energia e trasporti, e le persone che li hanno condotti. Per ogni studio riportiamo autori, metodo e conclusioni dichiarate.")),
    ("la-lotta", dict(t="La lotta", s="Presidi, marce, assemblee", ic="i-flag", g="lotta",
        intro="Le forme della mobilitazione: presidi, marce, assemblee, acquisti collettivi di terreni, comitati.")),
    ("le-persone", dict(t="Le persone", s="Persone e organizzazioni", ic="i-people", g="lotta",
        intro="Le persone e le organizzazioni che compaiono in questa storia, con il loro ruolo pubblico.")),
    ("arte-e-cultura", dict(t="Arte e cultura", s="Libri, film, musica, Alta Felicità", ic="i-note", g="lotta",
        intro="Libri, film, canzoni, concerti e festival nati intorno alla valle e al movimento.")),
    ("solidarieta", dict(t="Solidarietà", s="Dall'Italia, dalla Francia, dal mondo", ic="i-globe", g="lotta",
        intro="I legami con altri movimenti in Italia, con la Maurienne e la Savoia, con l'Europa e il mondo.")),
    ("diritti-e-repressione", dict(t="Diritti e repressione", s="Norme speciali, processi, costi", ic="i-scale", g="lotta",
        intro="Norme speciali, eventi di ordine pubblico, processi, misure di prevenzione e costi pubblici. Riportiamo i fatti e le versioni di ciascuna parte, ognuna attribuita a chi la sostiene.")),
    ("oggi-e-domani", dict(t="Oggi e domani", s="A che punto è l'opera", ic="i-cal", g="oggi",
        intro="A che punto è l'opera oggi: scavi, costi, cronoprogramma, cantieri aperti.")),
    ("archivio", dict(t="Archivio", s="Biblioteca e tutte le schede", ic="i-file", g="archivio",
        intro="Tutte le schede del sito in un solo posto: documenti da scaricare, eventi, luoghi, persone. Si possono filtrare e cercare.")),
])
GRUPPI = [("conoscere", "Conoscere"), ("lotta", "La lotta"), ("oggi", "Oggi"), ("archivio", "Archivio")]

FILE_SEZ = {
    "01": ["storia"], "01b": ["storia"], "02": ["perche-no"], "02b": ["perche-no", "oggi-e-domani"],
    "04a": ["la-valle"], "04b": ["la-valle", "la-lotta"], "04c": ["la-valle", "oggi-e-domani"],
    "04d": ["le-persone"], "04e": ["le-persone", "la-lotta"], "05a": ["arte-e-cultura"],
    "05b": ["solidarieta"], "05c": ["solidarieta"], "05d": ["solidarieta"],
    "06a": ["diritti-e-repressione"], "06b": ["diritti-e-repressione"], "06c": ["diritti-e-repressione"],
    "06d": ["diritti-e-repressione"], "06e": ["diritti-e-repressione"], "09": ["diritti-e-repressione"],
    "07a": ["la-scienza"], "07b": ["la-scienza"], "07c": ["la-scienza"], "07d": ["la-scienza"],
    "07e": ["la-scienza"], "07f": ["la-scienza"], "07g": ["la-scienza"],
    "08a": ["arte-e-cultura"], "08b": ["arte-e-cultura"], "08cde": ["arte-e-cultura"],
    "persone": ["le-persone"],
}
TIPO_SEZ = {"persona": ["le-persone"], "organizzazione": ["le-persone"], "luogo": ["la-valle"],
            "canzone": ["arte-e-cultura"], "concerto": ["arte-e-cultura"]}
SEZ_KEYWORDS = [("storia", "storia"), ("linea del tempo", "storia"), ("cronolog", "storia"),
    ("valle", "la-valle"), ("luoghi", "la-valle"), ("perch", "perche-no"), ("scienz", "la-scienza"),
    ("lotta", "la-lotta"), ("piazza", "la-lotta"), ("person", "le-persone"), ("protagonist", "le-persone"),
    ("arte", "arte-e-cultura"), ("cultura", "arte-e-cultura"), ("solidar", "solidarieta"),
    ("diritti", "diritti-e-repressione"), ("repress", "diritti-e-repressione"), ("oggi", "oggi-e-domani"),
    ("archivio", "archivio"), ("biblioteca", "archivio")]

TIPI = OrderedDict([
    ("evento", ("Evento", "Eventi")), ("luogo", ("Luogo", "Luoghi")), ("persona", ("Persona", "Persone")),
    ("organizzazione", ("Organizzazione", "Organizzazioni")), ("documento", ("Documento", "Documenti")),
    ("studio", ("Studio", "Studi")), ("dato", ("Dato", "Dati")), ("norma", ("Atto o norma", "Atti e norme")),
    ("procedimento", ("Procedimento", "Procedimenti")), ("costo", ("Costo pubblico", "Costi pubblici")),
    ("canzone", ("Canzone", "Canzoni")), ("concerto", ("Concerto", "Concerti")),
])
PREFISSO_TIPO = {"evento": "evento", "luogo": "luogo", "persona": "persona", "org": "organizzazione",
    "documento": "documento", "doc": "documento", "studio": "studio", "dato": "dato", "norma": "norma",
    "procedimento": "procedimento", "proc": "procedimento", "costo": "costo", "canzone": "canzone",
    "concerto": "concerto", "opera": "documento"}

LABEL = {"data": "Data", "precisione_data": "Precisione della data", "luogo_slug": "Luogo", "categoria": "Categoria",
    "cifre": "Cifre", "chi_dichiara_le_cifre": "Chi dichiara le cifre", "attori": "Attori", "fonti": "Fonti",
    "sezioni_sito": "Sezioni", "tipo": "Tipo", "comune": "Comune", "lat": "Latitudine", "lon": "Longitudine",
    "date": "Date", "ruolo": "Ruolo", "periodo": "Periodo", "gruppo": "Gruppo", "anni_attivita": "Anni di attività",
    "area": "Area", "sito": "Sito web", "autore_ente": "Autore o ente", "anno": "Anno", "pagine": "Pagine",
    "url_pdf": "PDF", "url_pagina": "Pagina web", "stato_link": "Stato del link", "copia_archive_org": "Copia su archive.org",
    "licenza": "Licenza", "autori_slug": "Autori", "ente": "Ente", "revisione_paritaria": "Revisione paritaria",
    "tema": "Tema", "metodo": "Metodo", "conclusioni": "Conclusioni dichiarate", "url": "Link",
    "grandezza": "Grandezza", "valore": "Valore", "unita": "Unità", "ufficio": "Ufficio giudiziario", "reati": "Reati",
    "data_inizio": "Inizio", "ultimo_grado": "Ultimo grado", "data_ultimo_grado": "Data dell'ultimo grado",
    "esito": "Esito", "n_imputati": "Imputati", "n_condannati": "Condannati", "n_assolti": "Assolti",
    "n_prescritti": "Prescritti", "eventi_slug": "Eventi collegati", "numero": "Numero", "oggetto": "Oggetto",
    "durata": "Durata", "ricorsi_esito": "Ricorsi ed esito", "voce": "Voce", "importo_euro": "Importo (euro)",
    "chi_dichiara": "Chi dichiara", "documento_slug": "Documento", "artista": "Artista", "album": "Album",
    "etichetta": "Etichetta", "url_youtube": "YouTube", "url_spotify": "Spotify", "url_testo": "Testo",
    "eseguita_a": "Eseguita a", "evento_slug": "Evento", "luogo": "Luogo", "palco": "Palco",
    "ordine_uscita": "Ordine di uscita", "completezza_scaletta": "Completezza della scaletta",
    "fonte_scaletta": "Fonte della scaletta", "nota_data": "Nota sulla data"}
NASCOSTI = {"slug", "titolo", "nome", "descrizione", "fonti", "sezioni_sito", "ricerche"}

PERIODI = [(1989, 1999, "Le origini"), (2000, 2004, "Accordi e primi presidi"), (2005, 2006, "Seghino e Venaus"),
           (2007, 2010, "L'Osservatorio"), (2011, 2012, "La Maddalena"), (2013, 2019, "Scavi, TELT, costi-benefici"),
           (2020, 2026, "San Didero e la Maurienne")]
MESI_L = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
SEGNAPOSTO_01 = {"1989-09-15", "1996-01-15", "2006-03-01", "2007-09-15", "2011-04-06", "2014-11-20", "2016-07-29", "2024-07-15"}

esc = lambda s: html.escape(str(s or ""), quote=True)
SLUG_RE = re.compile(r"(?<![\w/.-])([a-z]+(?:-[a-z0-9]+)+)(?![\w/-])")


def slugify(s, n=60):
    s = s.lower()
    for a, b in (("à", "a"), ("è", "e"), ("é", "e"), ("ì", "i"), ("ò", "o"), ("ù", "u"), ("’", ""), ("'", "")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:n].rstrip("-")


def fid_of(path):
    m = re.match(r"([0-9]{2}[a-z]*)-", path.name)
    return m.group(1) if m else path.stem.split("-")[0]


def clean_glued(text):
    """Toglie i rimandi numerici attaccati alle parole (ricerche esterne 01 e 02)."""
    text = text.replace("\\-", "-").replace("\\.", ".").replace("\\!", "!").replace("\\_", "_").replace("\\:", ":")
    def rep(m):
        i = m.start()
        if text[i - 1] in ",." and i >= 2 and text[i - 2].isdigit():
            return m.group(0)
        return ""
    return re.sub(r"(?<=[a-zàèéìòù\)\.»\"”,;:’'])(\d{1,2})(?=[\s,;.:)]|$)", rep, text)

# ---------------------------------------------------------------- lettura ricerche
class Ricerca:
    def __init__(self, path):
        self.path, self.fid = path, fid_of(path)
        self.text = path.read_text(encoding="utf-8")
        h1 = re.search(r"^# (.+)$", self.text, re.M)
        t = re.sub(r"\*", "", h1.group(1)) if h1 else path.stem
        t = re.sub(r"^.*?[–-]\s*Tappa\s+\w+:\s*", "", t)
        self.titolo = t[:1].upper() + t[1:]
        self.bib = self._bib()
        self.sez = FILE_SEZ.get(self.fid, [])

    def section(self, pattern, level=2):
        """Testo di una sezione '## ...' il cui titolo contiene pattern."""
        lines = self.text.split("\n"); out = None
        for ln in lines:
            m = re.match(r"^(#{1,%d}) (.*)" % level, ln)
            if m and out is not None:
                break
            if m and len(m.group(1)) == level and re.search(pattern, m.group(2), re.I):
                out = []; continue
            if out is not None:
                out.append(ln)
        return "\n".join(out).strip() if out is not None else ""

    def _bib(self):
        bib = {}; on = False
        for ln in self.text.split("\n"):
            if re.match(r"^#{2,4} .*(Bibliografia|Fonti \(|^#{2,4} Fonti)", ln) or re.match(r"^#{2,4} \**(Bibliografia|Fonti)", ln):
                on = True; continue
            if on and re.match(r"^## ", ln):
                break
            if on:
                m = re.match(r"^\s*>?\s*(?:\[(\d+)\]|(\d+)\.)\s+(.*)", ln)
                if m:
                    bib[int(m.group(1) or m.group(2))] = m.group(3).strip()
        return bib


def parse_csv_blocks(text):
    for m in re.finditer(r"```csv\s*\n(.*?)\n```", text, re.S):
        rows = list(csv.reader(io.StringIO(m.group(1))))
        if len(rows) < 2:
            continue
        yield [c.strip() for c in rows[0]], rows[1:]


def tipo_da_header(cols):
    s = set(cols)
    if cols[0] == "concerto_slug": return "scaletta"
    if cols[0] != "slug": return None
    if "palco" in s: return "concerto"
    if "precisione_data" in s and "titolo" in s: return "evento"
    if "lat" in s: return "luogo"
    if "anni_attivita" in s: return "organizzazione"
    if "url_pdf" in s: return "documento"
    if "revisione_paritaria" in s: return "studio"
    if "grandezza" in s: return "dato"
    if "reati" in s: return "procedimento"
    if "oggetto" in s and "numero" in s: return "norma"
    if "importo_euro" in s: return "costo"
    if "album" in s: return "canzone"
    if "ruolo" in s: return "persona"
    return None


class Scheda:
    def __init__(self, slug, tipo):
        self.slug, self.tipo = slug, tipo
        self.recs = []          # (campi, fid)
        self.corpi = []         # (titolo, markdown, fid)
        self.scaletta = []
        self.sez = set()
        self.verifica = False

    def add(self, row, fid):
        self.recs.append((row, fid))

    def get(self, k):
        for row, _ in self.recs:
            v = (row.get(k) or "").strip()
            if v: return v
        return ""

    @property
    def fids(self):
        return list(OrderedDict.fromkeys([f for _, f in self.recs] + [f for _, _, f in self.corpi]))

    @property
    def titolo(self):
        t = self.get("titolo") or self.get("nome") or self.get("grandezza") or self.get("voce")
        if not t and self.tipo == "norma":
            t = " ".join(x for x in (self.get("tipo"), self.get("numero"), self.get("ente")) if x) or self.get("oggetto")[:90]
        if not t and self.corpi: t = self.corpi[0][0]
        if not t:
            t = re.sub(r"^[a-z]+-", "", self.slug).replace("-", " ")
            t = t[:1].upper() + t[1:]
        return t

    @property
    def data(self):
        d = self.get("data") or self.get("data_inizio") or self.get("anno")
        if not d:
            m = re.match(r"[a-z]+-(\d{4}(?:-\d{2}(?:-\d{2})?)?)", self.slug)
            if m: d = m.group(1)
        m = re.match(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", d or "")
        return m.group(0) if m else ""

    @property
    def descr(self):
        out = []
        for row, f in self.recs:
            d = (row.get("descrizione") or row.get("conclusioni") or row.get("oggetto") or "").strip()
            if d and d not in [x for x, _ in out]: out.append((d, f))
        return out


def data_it(d, prec=""):
    if not d: return ""
    p = d.split("-")
    if len(p) == 3: return f"{int(p[2])} {MESI_L[int(p[1]) - 1]} {p[0]}"
    if len(p) == 2: return f"{MESI_L[int(p[1]) - 1]} {p[0]}"
    return p[0]


class Corpus:
    def __init__(self):
        self.ricerche = [Ricerca(p) for p in sorted(RIC.glob("*.md"))
                         if not p.name.startswith("00-") and p.name != "slug-usati.md"]
        # le correzioni (01b, 02b) hanno la precedenza sulle versioni precedenti
        pri = {"01b": 0, "02b": 0}
        self.ricerche.sort(key=lambda r: (pri.get(r.fid, 1), r.fid == "persone", r.path.name))
        self.by_fid = {r.fid: r for r in self.ricerche}
        self.schede = OrderedDict()
        for r in self.ricerche:
            self._load_csv(r)
        for r in self.ricerche:
            self._load_corpi(r)
        self._load_01()
        self._sezioni()

    def scheda(self, slug, tipo):
        if tipo is None:
            tipo = PREFISSO_TIPO.get(slug.split("-")[0], "documento")
        if slug not in self.schede:
            self.schede[slug] = Scheda(slug, tipo)
        return self.schede[slug]

    def _load_csv(self, r):
        for cols, rows in parse_csv_blocks(r.text):
            tipo = tipo_da_header(cols)
            if not tipo: continue
            for row in rows:
                d = {c: (row[i] if i < len(row) else "").strip() for i, c in enumerate(cols)}
                if tipo == "scaletta":
                    self.scheda(d["concerto_slug"], "concerto").scaletta.append(d); continue
                slug = d.get("slug", "")
                if not re.match(r"^[a-z]+(-[a-z0-9]+)+$", slug): continue
                self.scheda(slug, tipo).add(d, r.fid)

    def _load_corpi(self, r):
        lines = r.text.split("\n"); cur = None
        for ln in lines + ["## fine"]:
            m = re.match(r"^###\s+`?([a-z]+(?:-[a-z0-9]+)+)`?\s*(?:[–—:-]\s*(.*))?$", ln)
            if m or re.match(r"^#{1,3} ", ln):
                if cur and cur[0] in self.schede or (cur and PREFISSO_TIPO.get(cur[0].split("-")[0])):
                    s = self.scheda(cur[0], None)
                    s.corpi.append((cur[1], "\n".join(cur[2]).strip(), r.fid))
                cur = [m.group(1), (m.group(2) or "").strip(), []] if m else None
                continue
            if cur: cur[2].append(ln)

    def _load_01(self):
        r = self.by_fid.get("01")
        if not r: return
        tab = r.section("Cronologia Documentata")
        n_new = 0
        for ln in tab.split("\n"):
            if not ln.startswith("| ") or ln.startswith("| :") or ln.startswith("| Data"): continue
            c = [clean_glued(x.strip()) for x in ln.strip().strip("|").split(" | ")]
            if len(c) < 8 or not re.match(r"\d{4}", c[0]): continue
            md = re.match(r"(\d{4}(?:-\d{2}(?:-\d{2})?)?)", c[0])
            if not md: continue
            data = md.group(1)
            nota_data = re.sub(r"[*\[\]]", "", c[0][len(data):]).strip()
            ms = re.search(r"\(`([a-z]+(?:-[a-z0-9]+)+)`\)", c[1])
            tit = re.sub(r"\s*\(`[^`]*`\)", "", re.sub(r"\*\[[^\]]*\]\*", "", c[1]))
            tit = re.sub(r"\*", "", tit).strip()
            row = {"data": data, "titolo": tit, "luogo": c[2], "categoria": c[3], "descrizione": c[4],
                   "cifre": "" if re.match(r"(non applicabile|–|-)\.?$", c[5].lower()) else c[5], "attori": c[6], "fonti_md": c[7],
                   "affidabilita": c[8] if len(c) > 8 else ""}
            if nota_data: row["nota_data"] = nota_data
            target = self.schede.get(ms.group(1)) if ms else None
            if not target and not ms:
                target = self._match_evento(data, tit)
            if target:
                target.add(row, "01")
            else:
                s = self.scheda(ms.group(1) if ms else "evento-" + data + "-" + slugify(tit, 40), "evento")
                if data in SEGNAPOSTO_01 or "verific" in nota_data:
                    s.verifica = True
                s.add(row, "01"); n_new += 1
        self.n01 = n_new

    def _match_evento(self, data, tit):
        words = {w for w in re.findall(r"[a-zàèéìòù]{5,}", tit.lower())}
        best, bs = None, 0
        for s in self.schede.values():
            if s.tipo != "evento" or not s.data or s.data[:4] != data[:4]: continue
            w2 = {w for w in re.findall(r"[a-zàèéìòù]{5,}", (s.titolo + " " + s.slug.replace("-", " ")).lower())}
            sh = len(words & w2)
            sc = (3 if s.data == data else 1 if s.data[:7] == data[:7] else 0) + sh
            if (s.data == data and sh >= 1) or (s.data[:7] == data[:7] and sh >= 2) or (data in SEGNAPOSTO_01 and sh >= 2):
                if sc > bs: best, bs = s, sc
        return best

    def _sezioni(self):
        for s in self.schede.values():
            for row, f in s.recs:
                for part in re.split(r"[;,|]", row.get("sezioni_sito", "")):
                    p = part.strip().lower()
                    for k, v in SEZ_KEYWORDS:
                        if k in p: s.sez.add(v); break
                s.sez.update(FILE_SEZ.get(f, []))
            for _, _, f in s.corpi:
                s.sez.update(FILE_SEZ.get(f, []))
            s.sez.update(TIPO_SEZ.get(s.tipo, []))
            if s.tipo in ("documento", "studio"): s.sez.add("archivio")
            if any(x in (s.get("precisione_data") + s.get("data")).lower() for x in ("verific",)): s.verifica = True

    def eventi(self):
        return sorted([s for s in self.schede.values() if s.tipo == "evento" and s.data], key=lambda s: s.data)

# ---------------------------------------------------------------- rendering di testo
class Refs:
    """Rimandi [n] di una pagina, risolti sulla bibliografia del file di provenienza."""
    def __init__(self, corpus):
        self.c, self.used = corpus, OrderedDict()

    def sup(self, fid, n):
        r = self.c.by_fid.get(fid)
        txt = r.bib.get(n) if r else None
        if not txt: return f"[{n}]"
        self.used.setdefault(fid, OrderedDict())[n] = txt
        return f'<sup class="ref"><a href="#f-{fid}-{n}" title="{esc(re.sub(r"[*_]", "", txt)[:200])}">{n}</a></sup>'

    def html(self):
        if not self.used: return ""
        out = ['<section class="fonti" id="fonti"><h2 class="mono">Fonti</h2>']
        for fid, refs in self.used.items():
            r = self.c.by_fid[fid]
            out.append(f'<h3>{esc(r.titolo)}</h3><ol>')
            for n, t in refs.items():
                out.append(f'<li id="f-{fid}-{n}" value="{n}">{md_inline(t)}</li>')
            out.append("</ol>")
        out.append("</section>")
        return "".join(out)


def md_inline(t):
    t = clean_glued(t) if "\\" in t else t
    h = markdown.markdown(t)
    h = re.sub(r"^<p>(.*)</p>$", r"\1", h, flags=re.S)
    return autolink(h)


def autolink(h):
    parts = re.split(r"(<a\b.*?</a>|<[^>]+>)", h, flags=re.S)
    for i, p in enumerate(parts):
        if p.startswith("<"): continue
        parts[i] = re.sub(r"(https?://[^\s<>\"]+[^\s<>\".,;:)\]])", r'<a href="\1" rel="noopener" target="_blank">\1</a>', p)
    return "".join(parts)


class Render:
    def __init__(self, corpus):
        self.c = corpus

    def link_slugs(self, h, refs=None, fid=None, self_slug=None):
        parts = re.split(r"(<a\b.*?</a>|<[^>]+>)", h, flags=re.S)
        def rep(m):
            s = m.group(1)
            if s in self.c.schede and s != self_slug:
                return f'<a class="sl" href="~/schede/{s}/">{esc(self.c.schede[s].titolo)}</a>'
            return s
        for i, p in enumerate(parts):
            if p.startswith("<"): continue
            p = SLUG_RE.sub(rep, p)
            if refs is not None and fid:
                p = re.sub(r"\[(?:(\d{2}[a-z]*)-)?(\d{1,3})\](?!\()", lambda m: refs.sup(m.group(1) or fid, int(m.group(2))), p)
            parts[i] = p
        return "".join(parts)

    def md(self, text, refs=None, fid=None, self_slug=None):
        text = re.sub(r"`([a-z]+(?:-[a-z0-9]+)+)`", r"\1", text)
        text = re.sub(r"^((?:  )+)(?=[-*\d])", lambda m: m.group(1) * 2, text, flags=re.M)  # sottoelenchi a 2 spazi
        text = re.sub(r"^(?![ \t]*(?:[-*] |\d+\. |\|))(\S[^\n]*)\n(?=(?:[-*] |\d+\. ))", r"\1\n\n", text, flags=re.M)  # riga vuota prima degli elenchi
        text = re.sub(r"\[((?:\d{2}[a-z]*-)?\d{1,3})\](?!\()", r"&#91;\1&#93;", text)  # protegge i rimandi da markdown
        h = markdown.markdown(text, extensions=["tables", "sane_lists"])
        h = h.replace("&amp;#91;", "[").replace("&amp;#93;", "]").replace("&#91;", "[").replace("&#93;", "]")
        h = autolink(h)
        return self.link_slugs(h, refs, fid, self_slug)

    def txt(self, t, refs=None, fid=None, self_slug=None):
        return self.link_slugs(autolink(esc(t)), refs, fid, self_slug)

# ---------------------------------------------------------------- componenti
def card_item(s, extra=""):
    d = s.descr[0][0] if s.descr else (s.get("ruolo") or s.get("valore") or "")
    if len(d) > 180: d = d[:177].rsplit(" ", 1)[0] + "…"
    meta = [TIPI.get(s.tipo, (s.tipo,))[0]]
    if s.data: meta.append(data_it(s.data))
    elif s.get("periodo"): meta.append(s.get("periodo"))
    luogo = s.get("comune") or s.get("luogo")
    chk = '<span class="tag check">da verificare</span>' if s.verifica else ""
    yr = s.data[:4] if s.data else ""
    return (f'<a class="card" href="~/schede/{s.slug}/" data-t="{s.tipo}" data-y="{yr}" data-q="{esc((s.titolo + " " + d + " " + luogo).lower())}">'
            f'<span class="meta mono"><span>{esc(" · ".join(meta))}</span><span>{esc(luogo[:40])}</span></span>'
            f'<h3>{esc(s.titolo)}</h3>{f"<p>{esc(d)}</p>" if d else ""}{chk}{extra}</a>')


def card_grid(schede, filtro=True, gid="g"):
    if not schede: return ""
    tipi = OrderedDict()
    for s in schede: tipi[s.tipo] = tipi.get(s.tipo, 0) + 1
    chips = ""
    if filtro and len(schede) > 6:
        chips = (f'<div class="filterbar" data-for="{gid}"><input type="search" class="find" placeholder="Filtra queste {len(schede)} schede" aria-label="Filtra">'
                 + ('<div class="chips"><button class="chip" aria-pressed="true" data-f="">Tutte</button>' +
                    "".join(f'<button class="chip" aria-pressed="false" data-f="{t}">{TIPI.get(t, (t, t))[1]} <b>{n}</b></button>' for t, n in tipi.items()) + "</div>" if len(tipi) > 1 else "")
                 + "</div>")
    return chips + f'<div class="cards" id="{gid}">' + "".join(card_item(s) for s in schede) + "</div>"


def order(schede):
    tord = list(TIPI)
    return sorted(schede, key=lambda s: (tord.index(s.tipo) if s.tipo in tord else 99, s.data or "9999", s.titolo.lower()))

# ---------------------------------------------------------------- sito
class Sito:
    def __init__(self, corpus):
        self.c, self.R = corpus, Render(corpus)
        self.pages = OrderedDict()   # path -> (titolo, sezione, html)

    def add(self, path, titolo, sez, body):
        self.pages[path] = (titolo, sez, body)

    def build(self):
        self.home(); self.sezioni(); self.perche_no(); self.timeline(); self.schede(); self.archivio()

    # ---- home
    def home(self):
        c = self.c; cnt = defaultdict(int)
        for s in c.schede.values(): cnt[s.tipo] += 1
        nums = [(cnt["evento"], "eventi datati, dal 1989 al 2026"), (cnt["luogo"], "luoghi: paesi, presidi, cantieri"),
                (cnt["persona"] + cnt["organizzazione"], "persone e organizzazioni"),
                (cnt["documento"] + cnt["studio"], "documenti e studi, molti scaricabili"),
                (sum(len(r.bib) for r in c.ricerche), "fonti citate nelle schede")]
        r01 = c.by_fid.get("01")
        periodi = []
        for a, b, t in PERIODI:
            n = sum(1 for s in c.eventi() if a <= int(s.data[:4]) <= b)
            periodi.append(f'<a class="period{" hot" if t in ("Seghino e Venaus", "La Maddalena") else ""}" href="~/linea-del-tempo/#a{a}"><span class="py">{a} – {b if b < 2026 else "oggi"}</span><h3>{t}</h3><p>{n} eventi nella linea del tempo</p><span class="dot"></span></a>')
        sez = "".join(f'<a href="~/{k}/"><span class="ic"><svg><use href="#{v["ic"]}"/></svg></span><span><b>{v["t"]}</b><small>{v["s"]}</small><em class="mono">{sum(1 for s in c.schede.values() if k in s.sez)} schede</em></span></a>' for k, v in SEZIONI.items())
        momenti = [c.schede[k] for k in ("evento-2005-12-08-venaus-rioccupazione", "evento-2011-06-27-maddalena-sgombero", "evento-2023-06-17-maurienne-manifestazione") if k in c.schede]
        if len(momenti) < 3:
            momenti = [s for s in c.eventi() if s.corpi][:3]
        docs = [s for s in c.schede.values() if s.tipo == "documento" and s.get("url_pdf").startswith("http")]
        docs = sorted(docs, key=lambda s: s.get("anno"), reverse=True)[:6]
        body = f'''
<div class="hero"><canvas class="topo" aria-hidden="true"></canvas>
 <div class="coords mono" aria-hidden="true">Bassa Val di Susa<br>45,13° N · 7,13° E</div>
 <div class="wrap hero-in"><div class="hero-l"><span class="mono eyebrow">Val di Susa · dal 1989</span>
  <h1>Trentasette anni dalla parte della <em>valle</em>.</h1></div>
  <div class="hero-r"><p>Questo è l'archivio del movimento No TAV: la nostra storia, i dati sull'opera, le persone, i documenti. Ogni scheda ha le sue fonti.</p>
  <div class="row"><a class="btn" href="~/linea-del-tempo/">Apri la linea del tempo</a><a class="btn ghost" href="~/perche-no/">Perché No</a></div></div></div></div>
<div class="wrap"><div class="nums">{"".join(f'<div class="num"><strong>{n:,}</strong><p>{t}</p></div>'.replace(f"{n:,}", f"{n:,}".replace(",", ".")) for n, t in nums)}</div>
<p class="note mono">Numeri calcolati dalle schede del sito. Crescono a ogni nuova ricerca.</p></div>
<section class="night"><div class="wrap"><div class="sec-head"><div><span class="mono eyebrow">Storia</span><h2>Sette periodi, una sola lotta</h2></div>
 <p>Dalla prima ipotesi del 1989 ai cantieri di oggi. Ogni periodo apre la linea del tempo all'anno giusto.</p></div>
 <div class="periods" tabindex="0">{"".join(periodi)}</div></div></section>
<section><div class="wrap"><div class="sec-head"><div><span class="mono eyebrow">Il sito</span><h2>Undici sezioni</h2></div><p>Ogni sezione raccoglie le schede che la riguardano: la stessa scheda può stare in più sezioni.</p></div>
 <div class="sezgrid">{sez}</div></div></section>
<section class="pt0"><div class="wrap"><div class="sec-head"><div><span class="mono eyebrow">Le giornate</span><h2>Alcuni momenti</h2></div><p>Ogni giornata ha la sua scheda: luogo, numeri, versioni a confronto, fonti.</p></div>
 <div class="cards three">{"".join(card_item(s) for s in momenti)}</div></div></section>
<section class="pt0"><div class="wrap"><div class="sec-head"><div><span class="mono eyebrow">Archivio</span><h2>Dalla biblioteca</h2></div><p>Atti, studi, sentenze e dossier in PDF. <a href="~/archivio/">Tutta la biblioteca</a></p></div>
 <div class="docs">{"".join(self.doc_row(s) for s in docs)}</div></div></section>'''
        self.add("", "Ora e sempre No TAV", "", body)

    def doc_row(self, s):
        url = s.get("url_pdf") or s.get("url") or s.get("url_pagina")
        lab = "PDF ↗" if s.get("url_pdf") else "Link ↗"
        a = f'<a class="dl" href="{esc(url)}" target="_blank" rel="noopener">{lab}</a>' if url.startswith("http") else '<span></span>'
        return (f'<div class="doc" data-t="{esc(s.tipo)}" data-q="{esc((s.titolo + " " + s.get("autore_ente") + s.get("ente")).lower())}"><span class="y">{esc(s.get("anno") or s.data[:4])}</span>'
                f'<span><a href="~/schede/{s.slug}/"><b>{esc(s.titolo)}</b></a><small>{esc(s.get("autore_ente") or s.get("ente") or s.get("tipo"))}</small></span>{a}</div>')

    # ---- sezioni
    def page_head(self, eyebrow, titolo, intro, img=None):
        im = f'<img class="hero-img" src="~/static/{img}" alt="">' if img else '<canvas class="topo" aria-hidden="true"></canvas>'
        return (f'<div class="phead{" withimg" if img else ""}">{im}<div class="wrap"><span class="mono eyebrow">{eyebrow}</span>'
                f'<h1>{esc(titolo)}</h1><p class="intro">{intro}</p></div></div>')

    def sintesi(self, fids, refs):
        out = []
        for f in fids:
            r = self.c.by_fid.get(f)
            if not r: continue
            t = r.section(r"Sintesi")
            if not t and f == "01":
                continue
            if not t: continue
            t = clean_glued(t) if f in ("01", "02") else t
            out.append(f'<details class="sint"{" open" if not out else ""}><summary><span class="mono">In breve</span> {esc(r.titolo)}</summary><div class="prose">{self.R.md(t, refs, f)}</div></details>')
        return "".join(out)

    IMG = {"la-valle": "01-la-valle-header.svg", "la-lotta": "02-in-piazza-corteo-header.svg", "solidarieta": "02-in-piazza-corteo-header.svg",
           "storia": "03-presidio-di-notte-sfondo.svg"}

    def sezioni(self):
        c = self.c
        for k, v in SEZIONI.items():
            if k in ("perche-no", "archivio"): continue
            refs = Refs(c)
            fids = [f for f, ss in FILE_SEZ.items() if k in ss and f in c.by_fid]
            extra = ""
            if k == "storia":
                extra = self.storia_periodi(refs)
            if k == "oggi-e-domani" and "02b" in c.by_fid:
                t = c.by_fid["02b"].section(r"Cifre dell'opera")
                extra = f'<section class="pt0"><div class="wrap narrow"><h2 class="h2s">Le cifre dell\'opera al 2026</h2><div class="prose">{self.R.md(t, refs, "02b")}</div></div></section>'
            schede = order([s for s in c.schede.values() if k in s.sez and (k != "storia" or s.tipo != "evento")])
            sint = self.sintesi([f for f in fids if f not in ("02b",) or k == "oggi-e-domani"], refs)
            body = (self.page_head(dict(GRUPPI)[v["g"]], v["t"], esc(v["intro"]), self.IMG.get(k)) + extra +
                    (f'<section class="pt0"><div class="wrap narrow">{sint}</div></section>' if sint else "") +
                    (f'<section class="pt0"><div class="wrap"><h2 class="h2s">Le schede</h2>{card_grid(schede, gid="g-" + k)}</div></section>' if schede else "") +
                    f'<div class="wrap narrow">{refs.html()}</div>')
            self.add(k + "/", v["t"], k, body)

    def storia_periodi(self, refs):
        c = self.c; r = c.by_fid.get("01"); ev = c.eventi(); out = []
        testi = {}
        if r:
            sint = r.section(r"Sintesi Storico")
            for m in re.finditer(r"^### \**(\d{4})[–-](\d{4})[^\n]*\n(.*?)(?=^### |\Z)", sint, re.S | re.M):
                testi[int(m.group(1))] = clean_glued(m.group(3).strip())
        for a, b, t in PERIODI:
            evp = [s for s in ev if a <= int(s.data[:4]) <= b]
            txt = testi.get(a, "")
            out.append(f'<details class="periodo" id="p{a}"><summary><span class="py mono">{a} – {b}</span><b>{t}</b><span class="mono n">{len(evp)} eventi</span></summary>'
                       + (f'<div class="prose">{self.R.md(txt)}</div>' if txt else "")
                       + f'<div class="evlist">{"".join(self.ev_row(s) for s in evp)}</div>'
                       + f'<p><a class="btn ghost sm" href="~/linea-del-tempo/#a{a}">Apri {a} nella linea del tempo</a></p></details>')
        return (f'<section class="pt0"><div class="wrap narrow"><div class="sec-head"><h2 class="h2s">Sette periodi</h2>'
                f'<a class="btn" href="~/linea-del-tempo/">Linea del tempo interattiva</a></div>{"".join(out)}'
                f'<p class="note mono">Testi dei periodi dalla cronologia preliminare: in corso di verifica.</p></div></section>')

    def ev_row(self, s):
        chk = ' <span class="tag check">da verificare</span>' if s.verifica else ""
        return f'<a class="evrow" href="~/schede/{s.slug}/"><span class="mono">{esc(data_it(s.data))}</span><span>{esc(s.titolo)}{chk}</span></a>'

    # ---- perché no
    TEMI = [("traffico", "Il traffico", r"Traffico"), ("costi", "I costi", r"Costi e Finanz"), ("costi-benefici", "Costi e benefici", r"Costi-Benefici"),
            ("ambiente-e-salute", "Ambiente e salute", r"Ambiente e Salute"), ("alternative", "Le alternative", r"Alternative"),
            ("decisioni-e-territorio", "Decisioni e territorio", r"Decisioni e Territorio"), ("economia-e-lavoro", "Economia locale e lavoro", r"Economia Locale"),
            ("motivazioni-ufficiali", "Le motivazioni ufficiali", r"Motivazioni Ufficiali")]

    def perche_no(self):
        c = self.c; r = c.by_fid.get("02"); r2 = c.by_fid.get("02b")
        v = SEZIONI["perche-no"]; refs = Refs(c)
        temi = []
        for slug, t, pat in self.TEMI:
            txt = clean_glued(r.section(pat)) if r else ""
            first = re.sub(r"[*#]", "", txt.split("\n\n")[0])[:220].rsplit(" ", 1)[0] + "…" if txt else ""
            temi.append(f'<a href="~/perche-no/{slug}/"><span class="mono">Tema</span><span class="big">{t}</span><p>{esc(first)}</p></a>')
            prefs = Refs(c)
            extra = ""
            if slug == "traffico" and r2:
                extra = f'<h2 class="h2s">Aggiornamento al 2026</h2><div class="prose">{self.R.md(r2.section(r"Traffico"), prefs, "02b")}</div>'
            if slug == "costi" and r2:
                extra = f'<h2 class="h2s">Aggiornamento al 2026</h2><div class="prose">{self.R.md(r2.section(r"Cifre dell"), prefs, "02b")}</div>'
            body = (self.page_head(f'<a href="~/perche-no/">Perché No</a> · tema', t, "") +
                    f'<section class="pt0"><div class="wrap narrow"><div class="prose">{self.R.md(txt, prefs, "02")}</div>{extra}{prefs.html()}</div></section>')
            self.add(f"perche-no/{slug}/", t, "perche-no", body)
        superati = r2.section(r"superati") if r2 else ""
        schede = order([s for s in c.schede.values() if "perche-no" in s.sez])
        body = (self.page_head("Conoscere", v["t"], esc(v["intro"])) +
                f'<section class="pt0"><div class="wrap"><div class="why">{"".join(temi)}</div></div></section>' +
                f'<section class="pt0"><div class="wrap narrow">{self.sintesi(["02b"], refs)}' +
                (f'<details class="sint warn"><summary><span class="mono">Attenzione</span> Numeri superati dai dati del 2026</summary><div class="prose">{self.R.md(superati, refs, "02b")}</div></details>' if superati else "") +
                f'</div></section>' +
                (f'<section class="pt0"><div class="wrap"><h2 class="h2s">Le schede</h2>{card_grid(schede, gid="g-pn")}</div></section>' if schede else "") +
                f'<div class="wrap narrow">{refs.html()}</div>')
        self.add("perche-no/", v["t"], "perche-no", body)

    # ---- linea del tempo
    def timeline(self):
        E = []
        for s in self.c.eventi():
            d = s.data; p = d.split("-")
            luogo = s.get("luogo")
            ls = s.get("luogo_slug")
            if ls in self.c.schede: luogo = self.c.schede[ls].titolo
            cat = [x.strip().capitalize() for x in re.split(r"[;,]", s.get("categoria")) if x.strip()][:3]
            dsc = s.descr[0][0] if s.descr else ""
            E.append(dict(s=s.slug, y=int(p[0]), m=int(p[1]) if len(p) > 1 else 0, g=int(p[2]) if len(p) > 2 else 0,
                          t=s.titolo, l=luogo, c=cat, x=dsc[:400], n=s.get("cifre"), chk=s.verifica))
        body = (self.page_head("Storia · Linea del tempo", "1989 → oggi. Anno per anno.",
                "Scegliamo un anno sulla striscia: si aprono i mesi. Scegliamo un mese: compare quello che è successo. Ogni evento apre la sua scheda.") +
                '<div class="tl" data-tl><nav class="years-bar" aria-label="Anni"><div class="wrap"><div class="years"></div></div></nav>'
                '<div class="wrap tl-panel"></div>'
                f'<script type="application/json" class="tl-data">{json.dumps(E, ensure_ascii=False).replace("</", "<\\/")}</script></div>'
                '<div class="wrap"><p class="note mono">Gli eventi senza mese preciso compaiono sotto “mese non indicato”. Il bollino giallo segnala date o cifre da verificare.</p></div>')
        self.add("linea-del-tempo/", "Linea del tempo", "storia", body)

    # ---- schede
    def schede(self):
        back = defaultdict(set)
        for s in self.c.schede.values():
            blob = " ".join(" ".join(r.values()) for r, _ in s.recs) + " ".join(b for _, b, _ in s.corpi)
            for m in SLUG_RE.finditer(blob):
                if m.group(1) in self.c.schede and m.group(1) != s.slug:
                    back[m.group(1)].add(s.slug)
        for s in self.c.schede.values():
            self.add(f"schede/{s.slug}/", s.titolo, (sorted(s.sez) or [""])[0], self.scheda_page(s, back[s.slug]))

    def scheda_page(self, s, backs):
        R, refs = self.R, Refs(self.c)
        tipo = TIPI.get(s.tipo, (s.tipo,))[0]
        when = data_it(s.data) if s.data else s.get("periodo")
        rows = []; seen = set()
        for row, fid in s.recs:
            for k, v in row.items():
                if k in NASCOSTI or k in seen or not v or k in ("fonti_md", "affidabilita"): continue
                seen.add(k)
                if k.startswith("url") or k in ("sito", "copia_archive_org"):
                    val = f'<a href="{esc(v)}" target="_blank" rel="noopener">{esc(re.sub(r"^https?://(www\\.)?", "", v)[:48])}… ↗</a>' if v.startswith("http") else esc(v)
                else:
                    val = R.txt(v, refs, fid, s.slug)
                rows.append(f"<dt>{LABEL.get(k, k.replace('_', ' ').capitalize())}</dt><dd>{val}</dd>")
        fonti = []
        for row, fid in s.recs:
            if row.get("fonti"): fonti.append(R.txt(row["fonti"], refs, fid, s.slug))
            if row.get("fonti_md"): fonti.append(R.link_slugs(md_inline(row["fonti_md"]), refs, fid, s.slug))
        descr = "".join(f'<p class="lead">{R.txt(d, refs, f, s.slug)}</p>' for d, f in s.descr)
        corpi = "".join(f'<div class="prose corpo">{R.md(b, refs, f, s.slug)}</div>' for t, b, f in s.corpi)
        scal = ""
        if s.scaletta:
            scal = '<h2 class="h2s">Scaletta</h2><ol class="scaletta">' + "".join(f'<li>{esc(x.get("titolo"))} <small>{esc(x.get("artista"))}</small></li>' for x in sorted(s.scaletta, key=lambda x: int(x.get("posizione") or 0) if (x.get("posizione") or "").isdigit() else 0)) + "</ol>"
        rel = order([self.c.schede[b] for b in backs])
        sez = "".join(f'<a class="tag" href="~/{k}/">{SEZIONI[k]["t"]}</a>' for k in SEZIONI if k in s.sez)
        chk = '<p class="warnbox">Data o dati di questa scheda da verificare: le ricerche non li confermano ancora con una fonte primaria.</p>' if s.verifica else ""
        aff = "".join(f'<p class="small"><span class="mono">Affidabilità secondo la cronologia</span> {esc(r.get("affidabilita"))}</p>' for r, _ in s.recs if r.get("affidabilita"))
        return f'''<article class="scheda"><div class="wrap"><div class="sch-head">
<span class="mono eyebrow">{tipo}{" · " + esc(when) if when else ""}</span><h1>{esc(s.titolo)}</h1><div class="tags">{sez}</div></div>
<div class="sch-grid"><div class="sch-main">{chk}{descr}{corpi}{scal}
{f'<h2 class="h2s">Fonti indicate nella scheda</h2><p class="small">{"<br>".join(fonti)}</p>' if fonti else ""}{aff}
{refs.html()}</div>
<aside class="sch-side">{f'<dl>{"".join(rows)}</dl>' if rows else ""}
{f'<h2 class="mono">Collegata a</h2><div class="rel">{"".join(f"""<a href="~/schede/{r.slug}/"><small class="mono">{TIPI.get(r.tipo, (r.tipo,))[0]}{" · " + r.data[:4] if r.data else ""}</small>{esc(r.titolo)}</a>""" for r in rel[:40])}</div>' if rel else ""}
<p class="mono small slug">{s.slug}</p></aside></div></div></article>'''

    # ---- archivio
    def archivio(self):
        c = self.c; v = SEZIONI["archivio"]
        docs, visti = [], set()
        for s in sorted([s for s in c.schede.values() if s.tipo in ("documento", "studio")], key=lambda s: (s.get("anno") or s.data or "0"), reverse=True):
            k = slugify(s.titolo, 80)
            if k in visti: continue
            visti.add(k); docs.append(s)
        idx = [[s.slug, s.titolo, s.tipo, s.data[:4] if s.data else ""] for s in c.schede.values()]
        tipi = OrderedDict(); [tipi.__setitem__(s.tipo, tipi.get(s.tipo, 0) + 1) for s in c.schede.values()]
        body = (self.page_head("Archivio", v["t"], esc(v["intro"])) +
                f'''<section class="pt0"><div class="wrap"><h2 class="h2s">La biblioteca <small class="mono">{len(docs)} documenti e studi</small></h2>
<div class="filterbar" data-for="lib"><input type="search" class="find" placeholder="Cerca per titolo o autore" aria-label="Cerca nella biblioteca">
<div class="chips"><button class="chip" aria-pressed="true" data-f="">Tutti</button><button class="chip" aria-pressed="false" data-f="documento">Documenti</button><button class="chip" aria-pressed="false" data-f="studio">Studi</button></div></div>
<div class="docs" id="lib">{"".join(self.doc_row(s) for s in docs)}</div></div></section>
<section class="pt0"><div class="wrap"><h2 class="h2s">Tutte le schede <small class="mono">{len(c.schede)}</small></h2>
<div class="search-all"><input type="search" class="find" placeholder="Cerca un nome, un luogo, un evento" aria-label="Cerca in tutte le schede">
<div class="chips">{"".join(f'<button class="chip" aria-pressed="false" data-f="{t}">{TIPI.get(t, (t, t))[1]} <b>{n}</b></button>' for t, n in tipi.items())}</div>
<div class="results"></div><script type="application/json" class="idx">{json.dumps(idx, ensure_ascii=False)}</script></div></div></section>''')
        self.add("archivio/", v["t"], "archivio", body)

# ---------------------------------------------------------------- layout
def nav_html():
    mega = []
    for g, gt in GRUPPI:
        items = "".join(f'<a href="~/{k}/"><span class="ic"><svg><use href="#{v["ic"]}"/></svg></span><span><b>{v["t"]}</b><small>{v["s"]}</small></span></a>' for k, v in SEZIONI.items() if v["g"] == g)
        if g == "conoscere":
            items += '<a class="feat" href="~/linea-del-tempo/"><span class="mono">In evidenza</span><b>La linea del tempo</b><small>Anno per anno, ogni evento con le sue fonti</small></a>'
        mega.append(f'<div class="mega" data-menu="{g}" hidden><div class="wrap">{items}</div></div>')
    btns = "".join(f'<button type="button" aria-expanded="false" data-menu="{g}">{gt}</button>' for g, gt in GRUPPI)
    return btns, "".join(mega)


def footer_html():
    cols = "".join(f'<div><h4>{gt}</h4><ul>' + "".join(f'<li><a href="~/{k}/">{v["t"]}</a></li>' for k, v in SEZIONI.items() if v["g"] == g) +
                   ('<li><a href="~/linea-del-tempo/">Linea del tempo</a></li>' if g == "conoscere" else "") + "</ul></div>" for g, gt in GRUPPI)
    return f'<footer><div class="wrap"><div class="tree">{cols}</div><div class="fine mono"><span>Ora e sempre No TAV · Val di Susa</span><span>Bozza di lavoro · contenuti dalle ricerche del progetto</span></div></div></footer>'


ICONS = (ROOT / "static" / "icons.svg")


def layout(title, sez, body, css, js, head_extra=""):
    btns, mega = nav_html()
    return f'''<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{esc(title)}{" · No TAV" if title != "Ora e sempre No TAV" else ""}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
{css}{head_extra}</head><body data-sez="{sez}">
{ICONS.read_text(encoding="utf-8")}
<div class="draft mono">Bozza di lavoro · testi e numeri dalle ricerche, da verificare prima della pubblicazione</div>
<header class="site"><div class="wrap bar"><a class="logo" href="~/"><svg viewBox="0 0 64 44" aria-hidden="true"><path d="M2 4 C20 0 36 10 62 5 L62 37 C38 42 20 32 2 36 Z" fill="none" stroke="currentColor" stroke-width="2.5"/><path d="M12 27 L12 19 Q13 14 19 14 L44 14 Q52 14 54 22 L54 27 Z" fill="#C8102E"/><path d="M9 34 L57 8" stroke="#C8102E" stroke-width="4" stroke-linecap="round"/></svg>Ora e sempre No TAV</a>
<nav class="main" aria-label="Menu principale">{btns}</nav><div class="spacer"></div>
<a class="btn ghost sm" href="~/archivio/">Cerca</a><button class="btn ghost sm menu-toggle" type="button" aria-expanded="false">Menu</button></div>
{mega}<div class="mega" data-menu="mobile" hidden><div class="wrap"></div></div></header>
<main id="main">{body}</main>{footer_html()}{js}</body></html>'''


def rel_link(target, frm):
    depth = frm.count("/")
    pre = "../" * depth
    if "#" in target:
        t, h = target.split("#", 1); h = "#" + h
    else:
        t, h = target, ""
    if t.startswith("static/"): return pre + t + h
    return pre + t + ("index.html" if (t == "" or t.endswith("/")) else "") + h


def write_static(site, out):
    if out.exists(): shutil.rmtree(out)
    (out / "static").mkdir(parents=True)
    for f in STATIC.iterdir():
        if f.name != "icons.svg": shutil.copy(f, out / "static" / f.name)
    for path, (title, sez, body) in site.pages.items():
        frm = path
        css = f'<link rel="stylesheet" href="{"../" * frm.count("/")}static/style.css">'
        js = f'<script src="{"../" * frm.count("/")}static/app.js"></script>'
        h = layout(title, sez, body, css, js)
        h = re.sub(r'(href|src)="~/([^"]*)"', lambda m: f'{m.group(1)}="{rel_link(m.group(2), frm)}"', h)
        p = out / path / "index.html"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(h, encoding="utf-8")
    (out / ".nojekyll").write_text("")
    return len(site.pages)


def write_single(site, out):
    """Tutto il sito in un file: le pagine stanno in un oggetto JS, il router usa #/percorso."""
    def fix(h):
        def rep(m):
            attr, t = m.group(1), m.group(2)
            if t.startswith("static/"):
                f = STATIC / t[7:]
                return f'{attr}="data:image/svg+xml;base64,{base64.b64encode(f.read_bytes()).decode()}"'
            if "#" in t:
                t, a = t.split("#", 1)
                return f'{attr}="#/{t}?{a}"'
            return f'{attr}="#/{t}"'
        return re.sub(r'(href|src)="~/([^"]*)"', rep, h)
    pages = {p: [t, s, fix(b)] for p, (t, s, b) in site.pages.items()}
    css = f"<style>{(STATIC / 'style.css').read_text(encoding='utf-8')}</style>"
    data = json.dumps(pages, ensure_ascii=False).replace("</", "<\\/")
    js = f'<script>window.__PAGES={data};</script><script>{(STATIC / "app.js").read_text(encoding="utf-8")}</script>'
    h = layout("Ora e sempre No TAV", "", "", css, js)
    h = h.replace("<title>Ora e sempre No TAV</title>", "<title>Sito No TAV</title>")
    h = re.sub(r'(href|src)="~/([^"]*)"', lambda m: f'{m.group(1)}="#/{m.group(2)}"', h)
    # l'anteprima viene avvolta nello scheletro della pagina al momento della pubblicazione
    h = re.sub(r'^<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport"[^>]*>', '<meta name="claude:viewport-fit-sides" content="cover">', h)
    h = re.sub(r'</head><body data-sez="[^"]*">', '', h).replace("</body></html>", "")
    out.write_text(h, encoding="utf-8")
    return out.stat().st_size


def main():
    global RIC
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "public"))
    ap.add_argument("--anteprima", default=str(ROOT / "anteprima.html"))
    ap.add_argument("--ricerche", default=str(RIC), help="cartella con le ricerche .md")
    a = ap.parse_args()
    RIC = Path(a.ricerche)
    c = Corpus(); site = Sito(c); site.build()
    cnt = defaultdict(int)
    for s in c.schede.values(): cnt[s.tipo] += 1
    print("ricerche:", len(c.ricerche), "| schede:", len(c.schede), dict(cnt), "| eventi nuovi da 01:", getattr(c, "n01", 0))
    print("pagine statiche:", write_static(site, Path(a.out)))
    print("anteprima:", write_single(site, Path(a.anteprima)) // 1024, "KB")


if __name__ == "__main__":
    main()
