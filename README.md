# Sito No TAV – generatore

Il sito è statico: solo HTML, CSS e JavaScript. Si genera dalle ricerche in `../ricerche/`.

## Come si rigenera

    pip install markdown
    python3 build.py --ricerche CARTELLA_RICERCHE --out docs

GitHub Pages pubblica la cartella `docs/` del ramo `main`: https://manliograndi-del.github.io/treno/
Le ricerche di partenza (file .md) non sono in questo repository: stanno nella cartella del progetto.

Scrive:
- `docs/` (o la cartella indicata con `--out`): il sito multipagina pubblicato su GitHub Pages (una pagina per ogni sezione, per ogni tema di Perché No, per la linea del tempo, per l'archivio e per ogni scheda);
- `anteprima.html`: lo stesso sito in un solo file, per l'anteprima privata.

## Da dove prende i contenuti

- **Schede**: le tabelle CSV di ogni ricerca (eventi, luoghi, persone, organizzazioni, documenti, studi, dati, norme, procedimenti, costi, canzoni, concerti). Schede con lo stesso slug in file diversi vengono unite.
- **Testo esteso della scheda**: i blocchi `### slug – Titolo` delle ricerche.
- **Fonti**: i rimandi `[n]` sono risolti sulla bibliografia del file da cui viene il testo; `[01b-15]` rimanda alla bibliografia di un altro file.
- **Testi di sezione**: le sintesi (`## 1. Sintesi`) di ogni ricerca, i periodi della cronologia 01, i temi della ricerca 02 con gli aggiornamenti della 02b.
- **Linea del tempo**: tutti gli eventi con data; quelli della tabella della cronologia 01 vengono uniti agli eventi con lo stesso slug.
- Le sezioni del sito vengono dal campo `sezioni_sito` e dal file di provenienza (tabella `FILE_SEZ` in build.py).

## File

- `build.py`: generatore (struttura delle sezioni, testi introduttivi, regole di unione);
- `static/style.css`, `static/app.js`, `static/icons.svg`, illustrazioni SVG.
