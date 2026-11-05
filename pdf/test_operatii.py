"""Test rapid: rulează fiecare operație pe PDF-uri generate și verifică rezultatul.

python test_operatii.py
"""
import sys
import tempfile
import warnings
import zipfile
from pathlib import Path

import openpyxl
import pymupdf
from docx import Document

import operatii as op

warnings.filterwarnings("ignore")


def pdf_de_test(cale, nume, pagini=5):
    d = pymupdf.open()
    for i in range(pagini):
        p = d.new_page()
        p.insert_text((72, 72), f"{nume} pagina {i + 1}")
        y = 120
        for rand in [["Nume", "Cant", "Pret"], ["Ciment", "10", "1.234,50"], ["Nisip", "3", "12,5"]]:
            for j, c in enumerate(rand):
                p.insert_text((72 + j * 120, y), c)
            p.draw_line((60, y + 5), (440, y + 5))
            y += 20
    d.save(cale)
    return str(cale)


def pagini(cale):
    with pymupdf.open(cale) as d:
        return d.page_count


def main():
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        a = pdf_de_test(t / "a.pdf", "A")
        b = pdf_de_test(t / "b.pdf", "B", 3)
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 400, 300), False)
        pix.set_rect(pix.irect, (20, 120, 200))
        pix.save(t / "img.png")

        assert pagini(op.uneste([a, b], t)[0]) == 8
        assert [pagini(f) for f in op.imparte(a, t, "intervale", "1-2, 3-5")] == [2, 3]
        assert len(op.imparte(a, t, "fiecare")) == 5
        assert [pagini(f) for f in op.imparte(a, t, "la_n", la_fiecare=2)] == [2, 2, 1]
        assert pagini(op.extrage_pagini(a, t, "2, 4")[0]) == 2
        assert pagini(op.sterge_pagini(a, t, "1-2")[0]) == 3
        org = op.organizeaza(a, t, "5, 1-4")[0]
        assert pymupdf.open(org)[0].get_text().startswith("A pagina 5")
        assert pymupdf.open(op.roteste([a], t, 90)[0])[0].rotation == 90
        assert op.comprima([a], t)[0].exists()
        assert op.repara([a], t)[0].exists()

        docx = op.pdf_in_word([a], t)[0]
        assert "A pagina 1" in "\n".join(p.text for p in Document(docx).paragraphs)
        ws = openpyxl.load_workbook(op.pdf_in_excel([a], t)[0]).worksheets[0]
        assert list(ws.values)[1] == ("Ciment", 10, 1234.5), list(ws.values)
        assert "A pagina 3" in op.pdf_in_text([a], t)[0].read_text(encoding="utf-8")
        with zipfile.ZipFile(op.pdf_in_imagini([a], t)[0]) as z:
            assert len(z.namelist()) == 5

        img_pdf = op.imagini_in_pdf([t / "img.png", t / "img.png"], t, format_pagina="A4")[0]
        assert pagini(img_pdf) == 2
        with zipfile.ZipFile(op.extrage_imagini([img_pdf], t)[0]) as z:
            assert len(z.namelist()) == 1

        nr = op.numere_pagini([a], t, format_="Pagina {n} din {total}")[0]
        assert "Pagina 2 din 5" in pymupdf.open(nr)[1].get_text()
        assert op.filigran([a], t, "CONFIDENȚIAL")[0].exists()

        prot = op.protejeaza([a], t, "secret")[0]
        assert pymupdf.open(prot).needs_pass
        try:
            op.deblocheaza([prot], t, "gresit")
            raise AssertionError("parola greșită a fost acceptată")
        except ValueError:
            pass
        assert not pymupdf.open(op.deblocheaza([prot], t, "secret")[0]).needs_pass

        assert op.interval_pagini("1-3, 5, 8-", 10) == [0, 1, 2, 4, 7, 8, 9]
    print("Toate testele au trecut.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
