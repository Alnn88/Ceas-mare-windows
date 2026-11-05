"""Operațiile PDF folosite de PDF Atelier (fără interfață grafică).

Fiecare funcție primește căi de fișiere și scrie rezultatul pe disc.
Întoarce lista fișierelor create.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import pymupdf

# ---------------------------------------------------------------- utilitare


def _deschide(cale, parola: str | None = None) -> pymupdf.Document:
    doc = pymupdf.open(cale)
    if doc.needs_pass:
        if not parola or not doc.authenticate(parola):
            doc.close()
            raise ValueError(f"„{Path(cale).name}” este protejat cu parolă. "
                             "Folosește mai întâi „Deblochează PDF”.")
    return doc


def interval_pagini(text: str, total: int) -> list[int]:
    """Transformă „1-3, 5, 8-” în indici 0-based. Gol = toate paginile."""
    text = (text or "").strip()
    if not text:
        return list(range(total))
    rezultat: list[int] = []
    for bucata in text.replace(";", ",").split(","):
        bucata = bucata.strip()
        if not bucata:
            continue
        if "-" in bucata:
            a, b = bucata.split("-", 1)
            start = int(a) if a.strip() else 1
            stop = int(b) if b.strip() else total
        else:
            start = stop = int(bucata)
        if start < 1 or stop > total or start > stop:
            raise ValueError(f"Interval invalid: „{bucata}” (documentul are {total} pagini).")
        rezultat.extend(range(start - 1, stop))
    return rezultat


def grupuri_pagini(text: str, total: int) -> list[list[int]]:
    """„1-3, 4-6, 7” → [[0,1,2],[3,4,5],[6]] (fiecare grup devine un PDF)."""
    grupuri = []
    for bucata in text.replace(";", ",").split(","):
        if bucata.strip():
            grupuri.append(interval_pagini(bucata, total))
    if not grupuri:
        raise ValueError("Scrie cel puțin un interval, de exemplu 1-3, 4-6.")
    return grupuri


def _nume(folder, baza: str, sufix: str, ext: str) -> Path:
    cale = Path(folder) / f"{baza}{sufix}{ext}"
    i = 2
    while cale.exists():
        cale = Path(folder) / f"{baza}{sufix} ({i}){ext}"
        i += 1
    return cale


def _salveaza(doc: pymupdf.Document, cale: Path, **optiuni) -> Path:
    doc.save(cale, garbage=3, deflate=True, **optiuni)
    return cale


# ---------------------------------------------------------------- organizare


def uneste(fisiere: list, folder) -> list[Path]:
    if len(fisiere) < 2:
        raise ValueError("Alege cel puțin două fișiere PDF.")
    rezultat = pymupdf.open()
    for f in fisiere:
        with _deschide(f) as d:
            rezultat.insert_pdf(d)
    cale = _salveaza(rezultat, _nume(folder, "unit", "", ".pdf"))
    rezultat.close()
    return [cale]


def imparte(fisier, folder, mod: str = "fiecare", intervale: str = "", la_fiecare: int = 1) -> list[Path]:
    """mod: „fiecare” (o pagină/fișier), „intervale” (ex. 1-3,4-6), „la_n” (câte N pagini)."""
    baza = Path(fisier).stem
    create = []
    with _deschide(fisier) as doc:
        total = doc.page_count
        if mod == "intervale":
            grupuri = grupuri_pagini(intervale, total)
        else:
            n = 1 if mod == "fiecare" else max(1, int(la_fiecare))
            grupuri = [list(range(i, min(i + n, total))) for i in range(0, total, n)]
        for grup in grupuri:
            nou = pymupdf.open()
            for p in grup:
                nou.insert_pdf(doc, from_page=p, to_page=p)
            eticheta = f"{grup[0] + 1}" if len(grup) == 1 else f"{grup[0] + 1}-{grup[-1] + 1}"
            create.append(_salveaza(nou, _nume(folder, baza, f"_pag_{eticheta}", ".pdf")))
            nou.close()
    return create


def extrage_pagini(fisier, folder, pagini: str) -> list[Path]:
    with _deschide(fisier) as doc:
        idx = interval_pagini(pagini, doc.page_count)
        nou = pymupdf.open()
        for p in idx:
            nou.insert_pdf(doc, from_page=p, to_page=p)
        cale = _salveaza(nou, _nume(folder, Path(fisier).stem, "_extras", ".pdf"))
        nou.close()
    return [cale]


def sterge_pagini(fisier, folder, pagini: str) -> list[Path]:
    if not pagini.strip():
        raise ValueError("Scrie paginile de șters, de exemplu 2, 5-7.")
    with _deschide(fisier) as doc:
        de_sters = set(interval_pagini(pagini, doc.page_count))
        if len(de_sters) >= doc.page_count:
            raise ValueError("Nu poți șterge toate paginile.")
        doc.select([i for i in range(doc.page_count) if i not in de_sters])
        cale = _salveaza(doc, _nume(folder, Path(fisier).stem, "_fara_pagini", ".pdf"))
    return [cale]


def organizeaza(fisier, folder, ordine: str) -> list[Path]:
    """Ordinea nouă a paginilor, ex. „3, 1, 2, 4-10”. Paginile pot fi și repetate."""
    with _deschide(fisier) as doc:
        idx = interval_pagini(ordine, doc.page_count)
        doc.select(idx)
        cale = _salveaza(doc, _nume(folder, Path(fisier).stem, "_organizat", ".pdf"))
    return [cale]


def roteste(fisiere: list, folder, grade: int = 90, pagini: str = "") -> list[Path]:
    create = []
    for f in fisiere:
        with _deschide(f) as doc:
            for p in interval_pagini(pagini, doc.page_count):
                pag = doc[p]
                pag.set_rotation((pag.rotation + grade) % 360)
            create.append(_salveaza(doc, _nume(folder, Path(f).stem, "_rotit", ".pdf")))
    return create


# ---------------------------------------------------------------- optimizare


def comprima(fisiere: list, folder, nivel: str = "recomandat") -> list[Path]:
    """nivel: „mic” (calitate mare), „recomandat”, „extrem” (fișier cât mai mic)."""
    setari = {"mic": (200, 85), "recomandat": (150, 70), "extrem": (96, 45)}
    dpi, calitate = setari.get(nivel, setari["recomandat"])
    create = []
    for f in fisiere:
        with _deschide(f) as doc:
            try:
                doc.rewrite_images(dpi_threshold=int(dpi * 1.3), dpi_target=dpi,
                                   quality=calitate, lossy=True, lossless=True, bitonal=True,
                                   color=True, gray=True, set_to_gray=False)
            except Exception:
                pass  # PDF fără imagini sau imagini nesuportate: comprimăm doar structura
            try:
                doc.subset_fonts()
            except Exception:
                pass
            doc.scrub(metadata=False, xml_metadata=True, thumbnails=True, reset_fields=False,
                      reset_responses=False, javascript=False, embedded_files=False,
                      attached_files=False, clean_pages=True, hidden_text=False,
                      redactions=False, redact_images=0, remove_links=False)
            cale = _nume(folder, Path(f).stem, "_comprimat", ".pdf")
            doc.save(cale, garbage=4, deflate=True, deflate_images=True,
                     deflate_fonts=True, clean=True, use_objstms=1)
        # nu întoarcem un fișier mai mare decât originalul
        if cale.stat().st_size >= Path(f).stat().st_size:
            shutil.copyfile(f, cale)
        create.append(cale)
    return create


def repara(fisiere: list, folder) -> list[Path]:
    create = []
    for f in fisiere:
        doc = pymupdf.open(f)  # MuPDF reconstruiește automat tabela xref stricată
        create.append(_salveaza(doc, _nume(folder, Path(f).stem, "_reparat", ".pdf"), clean=True))
        doc.close()
    return create


# ---------------------------------------------------------------- conversie DIN PDF


def pdf_in_word(fisiere: list, folder) -> list[Path]:
    from pdf2docx import Converter

    create = []
    for f in fisiere:
        cale = _nume(folder, Path(f).stem, "", ".docx")
        conv = Converter(str(f))
        try:
            conv.convert(str(cale), multi_processing=False)
        finally:
            conv.close()
        create.append(cale)
    return create


def pdf_in_excel(fisiere: list, folder, o_foaie_per_tabel: bool = True) -> list[Path]:
    """Extrage tabelele (pe fiecare pagină) într-un registru Excel.

    Dacă o pagină nu are tabele detectate, textul ei e pus rând cu rând,
    împărțit în coloane după spațiile mari dintre cuvinte.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter

    create = []
    for f in fisiere:
        wb = Workbook()
        wb.remove(wb.active)
        with _deschide(f) as doc:
            foaie_comuna = None
            for nr, pag in enumerate(doc, start=1):
                tabele = []
                try:
                    tabele = [_extrage_tabel(pag, t) for t in pag.find_tables().tables]
                except Exception:
                    pass
                tabele = [t for t in tabele if t and any(any(c for c in r) for r in t)]
                if not tabele:
                    randuri = _text_pe_coloane(pag)
                    if randuri:
                        tabele = [randuri]
                for ti, tabel in enumerate(tabele, start=1):
                    if o_foaie_per_tabel:
                        titlu = f"Pag {nr}" + (f" - T{ti}" if len(tabele) > 1 else "")
                        ws = wb.create_sheet(titlu[:31])
                    else:
                        if foaie_comuna is None:
                            foaie_comuna = wb.create_sheet("Date")
                        ws = foaie_comuna
                        if ws.max_row > 1:
                            ws.append([])
                    for rand in tabel:
                        ws.append([_valoare_excel(c) for c in rand])
            if not wb.sheetnames:
                ws = wb.create_sheet("Gol")
                ws.append(["Nu am găsit text sau tabele în PDF (poate fi scanat)."])
            for ws in wb.worksheets:
                for col in ws.columns:
                    lungime = max((len(str(c.value)) for c in col if c.value is not None), default=8)
                    ws.column_dimensions[get_column_letter(col[0].column)].width = min(60, max(8, lungime + 2))
                for c in ws[1]:
                    c.font = Font(bold=True)
                for rand in ws.iter_rows():
                    for c in rand:
                        c.alignment = Alignment(vertical="top", wrap_text=True)
        cale = _nume(folder, Path(f).stem, "", ".xlsx")
        wb.save(cale)
        create.append(cale)
    return create


def _extrage_tabel(pag, tabel) -> list[list]:
    """Citește textul fiecărei celule din dreptunghiul ei (mai sigur decât extract())."""
    randuri = []
    for rand in tabel.rows:
        celule = []
        for bbox in rand.cells:
            if bbox is None:
                celule.append(None)
            else:
                text = pag.get_textbox(pymupdf.Rect(bbox))
                celule.append(" ".join(text.split()) if text else None)
        randuri.append(celule)
    return randuri


def _valoare_excel(celula):
    if celula is None:
        return None
    text = str(celula).strip()
    curat = re.sub(r"\s", "", text)
    # numere în format românesc (1.234,56 / 12,5) sau internațional (1,234.56 / 12.5)
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?|-?\d+,\d+", curat):
        return float(curat.replace(".", "").replace(",", "."))
    if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?|-?\d+\.\d+", curat):
        return float(curat.replace(",", ""))
    if re.fullmatch(r"-?(0|[1-9]\d{0,14})", curat):
        return int(curat)
    return text


def _text_pe_coloane(pag) -> list[list[str]]:
    cuvinte = pag.get_text("words")  # x0, y0, x1, y1, cuvânt, bloc, linie, nr
    if not cuvinte:
        return []
    linii: dict[tuple, list] = {}
    for w in cuvinte:
        linii.setdefault((w[5], w[6]), []).append(w)
    randuri = []
    for cheie in sorted(linii, key=lambda k: (min(w[1] for w in linii[k]), min(w[0] for w in linii[k]))):
        ws = sorted(linii[cheie], key=lambda w: w[0])
        celule, curent, ultim_x1 = [], [], None
        for w in ws:
            inaltime = w[3] - w[1]
            if ultim_x1 is not None and w[0] - ultim_x1 > inaltime * 1.5:
                celule.append(" ".join(curent))
                curent = []
            curent.append(w[4])
            ultim_x1 = w[2]
        celule.append(" ".join(curent))
        randuri.append(celule)
    return randuri


def pdf_in_text(fisiere: list, folder) -> list[Path]:
    create = []
    for f in fisiere:
        with _deschide(f) as doc:
            text = "\n\n".join(f"--- Pagina {i} ---\n{p.get_text()}" for i, p in enumerate(doc, 1))
        cale = _nume(folder, Path(f).stem, "", ".txt")
        cale.write_text(text, encoding="utf-8")
        create.append(cale)
    return create


def pdf_in_imagini(fisiere: list, folder, format_: str = "jpg", dpi: int = 150) -> list[Path]:
    create = []
    for f in fisiere:
        baza = Path(f).stem
        with _deschide(f) as doc:
            if doc.page_count == 1:
                pix = doc[0].get_pixmap(dpi=dpi)
                cale = _nume(folder, baza, "", f".{format_}")
                pix.save(cale, jpg_quality=90) if format_ == "jpg" else pix.save(cale)
                create.append(cale)
                continue
            cale_zip = _nume(folder, baza, "_imagini", ".zip")
            with zipfile.ZipFile(cale_zip, "w", zipfile.ZIP_DEFLATED) as z:
                for i, pag in enumerate(doc, 1):
                    pix = pag.get_pixmap(dpi=dpi)
                    z.writestr(f"{baza}_pag_{i:03d}.{format_}",
                               pix.tobytes("jpeg" if format_ == "jpg" else "png", jpg_quality=90))
            create.append(cale_zip)
    return create


def extrage_imagini(fisiere: list, folder) -> list[Path]:
    """Scoate imaginile originale încorporate în PDF, într-o arhivă ZIP."""
    create = []
    for f in fisiere:
        baza = Path(f).stem
        cale_zip = _nume(folder, baza, "_imagini_extrase", ".zip")
        n = 0
        with _deschide(f) as doc, zipfile.ZipFile(cale_zip, "w") as z:
            vazute = set()
            for i, pag in enumerate(doc, 1):
                for img in pag.get_images(full=True):
                    xref = img[0]
                    if xref in vazute:
                        continue
                    vazute.add(xref)
                    info = doc.extract_image(xref)
                    if not info:
                        continue
                    n += 1
                    z.writestr(f"{baza}_pag{i}_img{n}.{info['ext']}", info["image"])
        if n == 0:
            cale_zip.unlink()
            raise ValueError(f"„{Path(f).name}” nu conține imagini.")
        create.append(cale_zip)
    return create


# ---------------------------------------------------------------- conversie ÎN PDF

EXT_IMAGINI = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp"}
EXT_OFFICE = {".doc", ".docx", ".odt", ".rtf", ".txt",
              ".xls", ".xlsx", ".ods", ".csv",
              ".ppt", ".pptx", ".odp"}


def imagini_in_pdf(fisiere: list, folder, orientare: str = "auto", margine: int = 0,
                   format_pagina: str = "imagine", un_singur_pdf: bool = True) -> list[Path]:
    """format_pagina: „imagine” (pagina are mărimea pozei), „A4”, „Letter”."""
    def pagina_pentru(rezultat, cale_img):
        with pymupdf.open(cale_img) as img_doc:
            r = img_doc[0].rect
        if format_pagina == "imagine":
            latime, inaltime = r.width + 2 * margine, r.height + 2 * margine
        else:
            dim = pymupdf.paper_size("a4" if format_pagina == "A4" else "letter")
            latime, inaltime = dim
            peisaj = orientare == "peisaj" or (orientare == "auto" and r.width > r.height)
            if peisaj:
                latime, inaltime = inaltime, latime
        pag = rezultat.new_page(width=latime, height=inaltime)
        zona = pymupdf.Rect(margine, margine, latime - margine, inaltime - margine)
        pag.insert_image(zona, filename=str(cale_img), keep_proportion=True)

    if not fisiere:
        raise ValueError("Alege cel puțin o imagine.")
    create = []
    if un_singur_pdf:
        rezultat = pymupdf.open()
        for f in fisiere:
            pagina_pentru(rezultat, f)
        create.append(_salveaza(rezultat, _nume(folder, Path(fisiere[0]).stem if len(fisiere) == 1 else "imagini", "", ".pdf")))
        rezultat.close()
    else:
        for f in fisiere:
            rezultat = pymupdf.open()
            pagina_pentru(rezultat, f)
            create.append(_salveaza(rezultat, _nume(folder, Path(f).stem, "", ".pdf")))
            rezultat.close()
    return create


def office_in_pdf(fisiere: list, folder) -> list[Path]:
    """Word / Excel / PowerPoint → PDF.

    Pe Windows folosește Microsoft Office (dacă e instalat), altfel LibreOffice.
    """
    create = []
    for f in fisiere:
        f = Path(f).resolve()
        cale = _nume(folder, f.stem, "", ".pdf").resolve()
        eroare_office = None
        if sys.platform == "win32":
            try:
                _office_com(f, cale)
                create.append(cale)
                continue
            except Exception as e:  # Office lipsă sau eroare: încercăm LibreOffice
                eroare_office = e
        soffice = _gaseste_libreoffice()
        if not soffice:
            mesaj = ("Pentru Word/Excel/PowerPoint → PDF e nevoie de Microsoft Office "
                     "sau de LibreOffice (gratuit, libreoffice.org) instalat pe calculator.")
            if eroare_office:
                mesaj += f"\n(Office: {eroare_office})"
            raise RuntimeError(mesaj)
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", tmp, str(f)],
                           check=True, capture_output=True, timeout=300,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            produs = Path(tmp) / f"{f.stem}.pdf"
            if not produs.exists():
                raise RuntimeError(f"LibreOffice nu a putut converti „{f.name}”.")
            shutil.move(str(produs), cale)
        create.append(cale)
    return create


def _gaseste_libreoffice() -> str | None:
    for nume in ("soffice", "libreoffice"):
        gasit = shutil.which(nume)
        if gasit:
            return gasit
    for baza in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
        cand = Path(baza) / "LibreOffice" / "program" / "soffice.exe"
        if cand.exists():
            return str(cand)
    return None


def _office_com(sursa: Path, destinatie: Path) -> None:
    import pythoncom
    import win32com.client

    ext = sursa.suffix.lower()
    pythoncom.CoInitialize()
    try:
        if ext in {".doc", ".docx", ".odt", ".rtf", ".txt"}:
            app = win32com.client.DispatchEx("Word.Application")
            app.Visible = False
            app.DisplayAlerts = 0
            try:
                d = app.Documents.Open(str(sursa), ReadOnly=True, ConfirmConversions=False)
                d.ExportAsFixedFormat(str(destinatie), 17)  # wdExportFormatPDF
                d.Close(False)
            finally:
                app.Quit()
        elif ext in {".xls", ".xlsx", ".ods", ".csv"}:
            app = win32com.client.DispatchEx("Excel.Application")
            app.Visible = False
            app.DisplayAlerts = False
            try:
                wb = app.Workbooks.Open(str(sursa), ReadOnly=True)
                wb.ExportAsFixedFormat(0, str(destinatie))  # xlTypePDF
                wb.Close(False)
            finally:
                app.Quit()
        elif ext in {".ppt", ".pptx", ".odp"}:
            app = win32com.client.DispatchEx("PowerPoint.Application")
            try:
                p = app.Presentations.Open(str(sursa), ReadOnly=True, WithWindow=False)
                p.SaveAs(str(destinatie), 32)  # ppSaveAsPDF
                p.Close()
            finally:
                app.Quit()
        else:
            raise ValueError(f"Tip de fișier nesuportat: {ext}")
    finally:
        pythoncom.CoUninitialize()


# ---------------------------------------------------------------- editare


def _pozitie(rect: pymupdf.Rect, pozitie: str, w: float, h: float, margine: float = 24):
    """Întoarce colțul stânga-sus pentru un text de mărime w×h."""
    vert, oriz = pozitie.split("-")  # ex. „jos-centru”
    x = {"stanga": rect.x0 + margine, "centru": rect.x0 + (rect.width - w) / 2,
         "dreapta": rect.x1 - margine - w}[oriz]
    y = {"sus": rect.y0 + margine, "jos": rect.y1 - margine - h}[vert]
    return x, y


def numere_pagini(fisiere: list, folder, pozitie: str = "jos-centru", format_: str = "{n}",
                  incepe_de_la: int = 1, marime: int = 11, pagini: str = "") -> list[Path]:
    """format_: „{n}”, „Pagina {n}”, „Pagina {n} din {total}”, „{n}/{total}”."""
    create = []
    for f in fisiere:
        with _deschide(f) as doc:
            total = doc.page_count
            for i in interval_pagini(pagini, total):
                pag = doc[i]
                text = format_.format(n=i + incepe_de_la, total=total + incepe_de_la - 1)
                w = pymupdf.get_text_length(text, fontname="helv", fontsize=marime)
                x, y = _pozitie(pag.rect, pozitie, w, marime)
                punct = pymupdf.Point(x, y + marime) * pag.derotation_matrix
                pag.insert_text(punct, text, fontname="helv", fontsize=marime,
                                color=(0.15, 0.15, 0.15), rotate=pag.rotation)
            create.append(_salveaza(doc, _nume(folder, Path(f).stem, "_numerotat", ".pdf")))
    return create


def filigran(fisiere: list, folder, text: str = "CONFIDENȚIAL", marime: int = 60,
             opacitate: float = 0.25, culoare=(0.8, 0.1, 0.1), diagonal: bool = True,
             imagine: str | None = None) -> list[Path]:
    if not text.strip() and not imagine:
        raise ValueError("Scrie un text sau alege o imagine pentru filigran.")
    create = []
    for f in fisiere:
        with _deschide(f) as doc:
            for pag in doc:
                r = pag.rect
                if imagine:
                    lat = r.width * 0.5
                    zona = pymupdf.Rect(r.x0 + (r.width - lat) / 2, r.y0 + (r.height - lat) / 2,
                                        r.x0 + (r.width + lat) / 2, r.y0 + (r.height + lat) / 2)
                    pag.insert_image(zona, filename=imagine, keep_proportion=True, overlay=True)
                    # opacitatea imaginii nu e controlată aici; se folosește imaginea ca atare
                else:
                    font = _font_unicode()
                    w = font.text_length(text, fontsize=marime)
                    centru = pymupdf.Point(r.width / 2, r.height / 2)
                    unghi = 45 if diagonal else 0
                    m = pymupdf.Matrix(unghi)
                    tw = pymupdf.TextWriter(pag.rect, opacity=opacitate, color=culoare)
                    tw.append(pymupdf.Point(centru.x - w / 2, centru.y + marime / 3), text,
                              font=font, fontsize=marime)
                    tw.write_text(pag, morph=(centru, m), overlay=True)
            create.append(_salveaza(doc, _nume(folder, Path(f).stem, "_filigran", ".pdf")))
    return create


def _font_unicode() -> pymupdf.Font:
    """Un font care are diacriticele românești (ș, ț, ă, î, â)."""
    for cale in (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(cale):
            return pymupdf.Font(fontfile=cale)
    return pymupdf.Font("notos")  # Noto Sans inclus în PyMuPDF


# ---------------------------------------------------------------- securitate


def protejeaza(fisiere: list, folder, parola: str, permite_tiparire: bool = True,
               permite_copiere: bool = False) -> list[Path]:
    if not parola:
        raise ValueError("Scrie o parolă.")
    perm = pymupdf.PDF_PERM_ACCESSIBILITY
    if permite_tiparire:
        perm |= pymupdf.PDF_PERM_PRINT | pymupdf.PDF_PERM_PRINT_HQ
    if permite_copiere:
        perm |= pymupdf.PDF_PERM_COPY
    create = []
    for f in fisiere:
        with _deschide(f) as doc:
            cale = _nume(folder, Path(f).stem, "_protejat", ".pdf")
            doc.save(cale, garbage=3, deflate=True, encryption=pymupdf.PDF_ENCRYPT_AES_256,
                     user_pw=parola, owner_pw=parola + "_proprietar", permissions=perm)
        create.append(cale)
    return create


def deblocheaza(fisiere: list, folder, parola: str = "") -> list[Path]:
    create = []
    for f in fisiere:
        doc = pymupdf.open(f)
        if doc.needs_pass and not doc.authenticate(parola):
            doc.close()
            raise ValueError(f"Parola pentru „{Path(f).name}” nu este corectă.")
        cale = _nume(folder, Path(f).stem, "_deblocat", ".pdf")
        doc.save(cale, garbage=3, deflate=True, encryption=pymupdf.PDF_ENCRYPT_NONE)
        doc.close()
        create.append(cale)
    return create


def informatii(fisier) -> str:
    with pymupdf.open(fisier) as doc:
        rand = [f"Fișier: {Path(fisier).name}",
                f"Mărime: {Path(fisier).stat().st_size / 1024:.1f} KB",
                f"Protejat cu parolă: {'da' if doc.needs_pass else 'nu'}"]
        if not doc.needs_pass:
            rand.append(f"Pagini: {doc.page_count}")
            for k, v in (doc.metadata or {}).items():
                if v and k not in ("format", "encryption"):
                    rand.append(f"{k}: {v}")
        return "\n".join(rand)


def numar_pagini(fisier) -> int | None:
    try:
        with pymupdf.open(fisier) as doc:
            return None if doc.needs_pass else doc.page_count
    except Exception:
        return None
