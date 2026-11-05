# PDF Atelier

Program pentru Windows cu toate uneltele PDF uzuale. Lucrează **pe calculatorul tău**:
fișierele nu sunt încărcate pe internet, nu ai limită de mărime sau de număr de fișiere.

| Categorie | Unelte |
|---|---|
| Organizare | Unește PDF · Împarte PDF (fiecare pagină / pe intervale / la N pagini) · Extrage pagini · Șterge pagini · Organizează (schimbă ordinea) · Rotește |
| Optimizare | Comprimă PDF (3 niveluri) · Repară PDF |
| Conversie din PDF | PDF în Word (.docx) · PDF în Excel (.xlsx, tabele) · PDF în JPG/PNG · Extrage imagini · PDF în text |
| Conversie în PDF | Word / Excel / PowerPoint în PDF · Imagini (JPG, PNG…) în PDF |
| Editare | Numere de pagină · Filigran (text sau imagine) |
| Securitate | Protejează cu parolă (AES-256) · Deblochează PDF |

## Cum îl folosești

1. Alegi unealta din ecranul principal (sau o cauți după nume).
2. Adaugi fișierele – cu butonul **Adaugă fișiere** sau trăgându-le în fereastră.
   La „Unește” le poți pune în ordine cu ▲ ▼.
3. Alegi opțiunile din dreapta și apeși butonul mare.
4. Rezultatul se salvează lângă fișierul original (sau în folderul ales) –
   fișierul original nu este modificat niciodată.

Paginile se scriu așa: `1-3, 5, 8-` (1 până la 3, pagina 5, de la 8 până la final).

## Instalare

**Fără Python (PdfAtelier.exe):** pe GitHub, la **Actions → Construieste PdfAtelier.exe**,
deschide ultima rulare și descarcă arhiva **PdfAtelier-windows** de la *Artifacts*.
Dezarhivează și pornește `PdfAtelier.exe`. (SmartScreen poate avertiza la prima
pornire: „Mai multe informații” → „Rulează oricum”.)

**Cu Python 3:** dublu-click pe `porneste_pdf_atelier.bat` – la prima pornire instalează
singur bibliotecile (`pip install -r requirements.txt`).

## De știut

- **Word / Excel / PowerPoint → PDF** folosește Microsoft Office dacă e instalat;
  altfel LibreOffice (gratuit, <https://www.libreoffice.org>).
- **PDF → Word / Excel** funcționează pe PDF-uri cu text. Un PDF scanat (doar poză)
  nu are text de extras.
- **PDF → Excel** detectează tabelele de pe fiecare pagină; numerele scrise
  românește (`1.234,50`) devin numere în Excel. Pe paginile fără tabel, textul e
  împărțit în coloane după spațiile dintre cuvinte.
