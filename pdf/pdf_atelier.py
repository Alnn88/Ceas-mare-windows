"""PDF Atelier – unelte PDF pe calculatorul tău (fără internet, fără încărcări).

Pornire:  python pdf_atelier.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import operatii as op

VERSIUNE = "1.0"

try:  # trage-și-plasează (opțional)
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception:  # pragma: no cover
    TkinterDnD = None
    DND_FILES = None

# ---------------------------------------------------------------- aspect

FUNDAL = "#f4f6fb"
CARD = "#ffffff"
TEXT = "#1d2433"
TEXT_SECUNDAR = "#5b6475"
ACCENT = "#2f5bea"
ACCENT_HOVER = "#2149c9"
BORDURA = "#dfe3ec"

CULORI_CATEGORII = {
    "Organizare": "#2f5bea",
    "Optimizare": "#1aa179",
    "Conversie din PDF": "#e8590c",
    "Conversie în PDF": "#d6336c",
    "Editare": "#7048e8",
    "Securitate": "#495057",
}

PDF = [("Fișiere PDF", "*.pdf")]
IMAGINI = [("Imagini", "*.jpg *.jpeg *.png *.bmp *.gif *.tif *.tiff *.webp")]
OFFICE = [("Documente Office", "*.doc *.docx *.odt *.rtf *.txt *.xls *.xlsx *.ods *.csv *.ppt *.pptx *.odp")]

# ---------------------------------------------------------------- definirea uneltelor
# Fiecare opțiune: (cheie, eticheta, tip, implicit, [valori])
# tipuri: text, parola, numar, alegere, bifa

POZITII = ["jos-centru", "jos-dreapta", "jos-stanga", "sus-centru", "sus-dreapta", "sus-stanga"]

UNELTE = [
    dict(id="uneste", titlu="Unește PDF", icon="⧉", cat="Organizare",
         desc="Combină mai multe PDF-uri într-unul singur, în ordinea dorită.",
         tipuri=PDF, multiple=True, minim=2,
         rulare=lambda f, d, o: op.uneste(f, d)),
    dict(id="imparte", titlu="Împarte PDF", icon="✂", cat="Organizare",
         desc="Separă paginile în fișiere PDF independente.",
         tipuri=PDF, multiple=False,
         optiuni=[("mod", "Mod de împărțire", "alegere", "fiecare pagină",
                   ["fiecare pagină", "pe intervale", "la fiecare N pagini"]),
                  ("intervale", "Intervale (ex. 1-3, 4-6, 7)", "text", ""),
                  ("la_fiecare", "N pagini", "numar", 2)],
         rulare=lambda f, d, o: op.imparte(f[0], d,
                                           {"fiecare pagină": "fiecare", "pe intervale": "intervale"}
                                           .get(o["mod"], "la_n"), o["intervale"], o["la_fiecare"])),
    dict(id="extrage", titlu="Extrage pagini", icon="⇱", cat="Organizare",
         desc="Păstrează doar paginile alese, într-un PDF nou.",
         tipuri=PDF, multiple=False,
         optiuni=[("pagini", "Pagini (ex. 1, 3, 5-8)", "text", "")],
         rulare=lambda f, d, o: op.extrage_pagini(f[0], d, o["pagini"])),
    dict(id="sterge", titlu="Șterge pagini", icon="🗑", cat="Organizare",
         desc="Elimină paginile de care nu ai nevoie.",
         tipuri=PDF, multiple=False,
         optiuni=[("pagini", "Pagini de șters (ex. 2, 5-7)", "text", "")],
         rulare=lambda f, d, o: op.sterge_pagini(f[0], d, o["pagini"])),
    dict(id="organizeaza", titlu="Organizează PDF", icon="⇅", cat="Organizare",
         desc="Schimbă ordinea paginilor (le poți și repeta).",
         tipuri=PDF, multiple=False, ordine_pagini=True,
         optiuni=[("ordine", "Ordinea nouă (ex. 3, 1, 2, 4-10)", "text", "")],
         rulare=lambda f, d, o: op.organizeaza(f[0], d, o["ordine"])),
    dict(id="roteste", titlu="Rotește PDF", icon="⟳", cat="Organizare",
         desc="Rotește toate paginile sau doar unele.",
         tipuri=PDF, multiple=True,
         optiuni=[("grade", "Rotire", "alegere", "90° dreapta", ["90° dreapta", "180°", "90° stânga"]),
                  ("pagini", "Doar paginile (gol = toate)", "text", "")],
         rulare=lambda f, d, o: op.roteste(f, d, {"90° dreapta": 90, "180°": 180}.get(o["grade"], 270),
                                           o["pagini"])),

    dict(id="comprima", titlu="Comprimă PDF", icon="⇲", cat="Optimizare",
         desc="Micșorează fișierul păstrând o calitate bună.",
         tipuri=PDF, multiple=True,
         optiuni=[("nivel", "Compresie", "alegere", "recomandată",
                   ["mică (calitate mare)", "recomandată", "extremă (fișier minim)"])],
         rulare=lambda f, d, o: op.comprima(f, d, {"mică (calitate mare)": "mic",
                                                   "extremă (fișier minim)": "extrem"}
                                            .get(o["nivel"], "recomandat"))),
    dict(id="repara", titlu="Repară PDF", icon="✚", cat="Optimizare",
         desc="Încearcă să recupereze un PDF deteriorat.",
         tipuri=PDF, multiple=True,
         rulare=lambda f, d, o: op.repara(f, d)),

    dict(id="pdf_word", titlu="PDF în Word", icon="W", cat="Conversie din PDF",
         desc="Transformă PDF-ul într-un document Word (.docx) editabil.",
         tipuri=PDF, multiple=True,
         rulare=lambda f, d, o: op.pdf_in_word(f, d)),
    dict(id="pdf_excel", titlu="PDF în Excel", icon="X", cat="Conversie din PDF",
         desc="Scoate tabelele din PDF într-un fișier Excel (.xlsx).",
         tipuri=PDF, multiple=True,
         optiuni=[("foi", "Fiecare tabel pe o foaie separată", "bifa", True)],
         rulare=lambda f, d, o: op.pdf_in_excel(f, d, o["foi"])),
    dict(id="pdf_jpg", titlu="PDF în imagini", icon="▣", cat="Conversie din PDF",
         desc="Fiecare pagină devine o imagine JPG sau PNG.",
         tipuri=PDF, multiple=True,
         optiuni=[("format", "Format", "alegere", "jpg", ["jpg", "png"]),
                  ("dpi", "Calitate (DPI)", "alegere", "150", ["72", "150", "200", "300"])],
         rulare=lambda f, d, o: op.pdf_in_imagini(f, d, o["format"], int(o["dpi"]))),
    dict(id="extrage_img", titlu="Extrage imagini", icon="⛶", cat="Conversie din PDF",
         desc="Salvează pozele originale conținute în PDF.",
         tipuri=PDF, multiple=True,
         rulare=lambda f, d, o: op.extrage_imagini(f, d)),
    dict(id="pdf_text", titlu="PDF în text", icon="T", cat="Conversie din PDF",
         desc="Extrage tot textul într-un fișier .txt.",
         tipuri=PDF, multiple=True,
         rulare=lambda f, d, o: op.pdf_in_text(f, d)),

    dict(id="office_pdf", titlu="Word / Excel / PPT în PDF", icon="⇪", cat="Conversie în PDF",
         desc="Transformă documente Office în PDF (folosește Office sau LibreOffice instalat).",
         tipuri=OFFICE, multiple=True,
         rulare=lambda f, d, o: op.office_in_pdf(f, d)),
    dict(id="jpg_pdf", titlu="Imagini în PDF", icon="▤", cat="Conversie în PDF",
         desc="Pune imagini JPG/PNG într-un PDF.",
         tipuri=IMAGINI, multiple=True,
         optiuni=[("pagina", "Mărimea paginii", "alegere", "A4", ["A4", "Letter", "imagine"]),
                  ("orientare", "Orientare", "alegere", "auto", ["auto", "portret", "peisaj"]),
                  ("margine", "Margine", "alegere", "mică", ["fără", "mică", "mare"]),
                  ("unul", "Toate imaginile într-un singur PDF", "bifa", True)],
         rulare=lambda f, d, o: op.imagini_in_pdf(f, d, o["orientare"],
                                                  {"fără": 0, "mică": 20, "mare": 50}[o["margine"]],
                                                  o["pagina"], o["unul"])),

    dict(id="numere", titlu="Numere de pagină", icon="#", cat="Editare",
         desc="Adaugă numărul paginii pe fiecare pagină.",
         tipuri=PDF, multiple=True,
         optiuni=[("pozitie", "Poziție", "alegere", "jos-centru", POZITII),
                  ("format", "Format", "alegere", "{n}",
                   ["{n}", "Pagina {n}", "Pagina {n} din {total}", "{n} / {total}"]),
                  ("start", "Începe numerotarea de la", "numar", 1),
                  ("marime", "Mărime font", "numar", 11),
                  ("pagini", "Doar paginile (gol = toate)", "text", "")],
         rulare=lambda f, d, o: op.numere_pagini(f, d, o["pozitie"], o["format"], o["start"],
                                                 o["marime"], o["pagini"])),
    dict(id="filigran", titlu="Filigran", icon="◈", cat="Editare",
         desc="Scrie un text (sau pune o imagine) peste toate paginile.",
         tipuri=PDF, multiple=True,
         optiuni=[("text", "Text", "text", "CONFIDENȚIAL"),
                  ("marime", "Mărime font", "numar", 60),
                  ("opacitate", "Transparență", "alegere", "25%", ["10%", "25%", "50%", "75%", "100%"]),
                  ("culoare", "Culoare", "alegere", "roșu", ["roșu", "gri", "albastru", "negru"]),
                  ("diagonal", "Pe diagonală", "bifa", True),
                  ("imagine", "Imagine în loc de text (opțional)", "imagine", "")],
         rulare=lambda f, d, o: op.filigran(
             f, d, o["text"], o["marime"], int(o["opacitate"].rstrip("%")) / 100,
             {"roșu": (0.8, 0.1, 0.1), "gri": (0.5, 0.5, 0.5), "albastru": (0.1, 0.3, 0.8),
              "negru": (0, 0, 0)}[o["culoare"]], o["diagonal"], o["imagine"] or None)),

    dict(id="protejeaza", titlu="Protejează PDF", icon="🔒", cat="Securitate",
         desc="Pune parolă pe PDF (criptare AES-256).",
         tipuri=PDF, multiple=True,
         optiuni=[("parola", "Parolă", "parola", ""),
                  ("parola2", "Repetă parola", "parola", ""),
                  ("tiparire", "Permite tipărirea", "bifa", True),
                  ("copiere", "Permite copierea textului", "bifa", False)],
         rulare=lambda f, d, o: _protejeaza(f, d, o)),
    dict(id="deblocheaza", titlu="Deblochează PDF", icon="🔓", cat="Securitate",
         desc="Scoate parola de pe un PDF (trebuie să știi parola).",
         tipuri=PDF, multiple=True,
         optiuni=[("parola", "Parola actuală", "parola", "")],
         rulare=lambda f, d, o: op.deblocheaza(f, d, o["parola"])),
]


def _protejeaza(f, d, o):
    if o["parola"] != o["parola2"]:
        raise ValueError("Parolele nu coincid.")
    return op.protejeaza(f, d, o["parola"], o["tiparire"], o["copiere"])


def deschide(cale) -> None:
    cale = str(cale)
    if sys.platform == "win32":
        os.startfile(cale)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", cale])
    else:
        subprocess.Popen(["xdg-open", cale])


def arata_in_folder(cale) -> None:
    cale = Path(cale)
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(cale)])
    else:
        deschide(cale.parent)


# ---------------------------------------------------------------- interfața


class Aplicatie:
    def __init__(self, radacina: tk.Tk):
        self.r = radacina
        self.r.title(f"PDF Atelier {VERSIUNE}")
        self.r.geometry("1060x720")
        self.r.minsize(820, 560)
        self.r.configure(bg=FUNDAL)
        self._stil()
        self.continut = tk.Frame(self.r, bg=FUNDAL)
        self.continut.pack(fill="both", expand=True)
        self.acasa()

    # ---------------------------------------------------- stiluri
    def _stil(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure(".", background=FUNDAL, foreground=TEXT, font=("Segoe UI", 10))
        s.configure("Card.TFrame", background=CARD)
        s.configure("TCheckbutton", background=CARD)
        s.configure("TCombobox", padding=4)
        s.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=BORDURA, thickness=8)

    def _goleste(self):
        for w in self.continut.winfo_children():
            w.destroy()

    def _buton(self, parinte, text, comanda, principal=True, **kw):
        b = tk.Button(parinte, text=text, command=comanda, relief="flat", cursor="hand2",
                      bd=0, padx=kw.pop("padx", 18), pady=kw.pop("pady", 8),
                      font=kw.pop("font", ("Segoe UI", 10, "bold" if principal else "normal")),
                      bg=kw.pop("bg", ACCENT if principal else CARD), fg="white" if principal else TEXT,
                      activebackground=kw.pop("activebackground", ACCENT_HOVER if principal else BORDURA),
                      activeforeground="white" if principal else TEXT,
                      highlightthickness=0 if principal else 1, highlightbackground=BORDURA, **kw)
        return b

    # ---------------------------------------------------- ecranul principal
    def acasa(self):
        self._goleste()
        antet = tk.Frame(self.continut, bg=FUNDAL)
        antet.pack(fill="x", padx=32, pady=(24, 4))
        tk.Label(antet, text="PDF Atelier", font=("Segoe UI", 24, "bold"), bg=FUNDAL,
                 fg=TEXT).pack(anchor="w")
        tk.Label(antet, text="Toate uneltele PDF de care ai nevoie, pe calculatorul tău. "
                             "Fișierele nu pleacă nicăieri.",
                 font=("Segoe UI", 11), bg=FUNDAL, fg=TEXT_SECUNDAR).pack(anchor="w")

        cautare_var = tk.StringVar()
        rand_cautare = tk.Frame(self.continut, bg=FUNDAL)
        rand_cautare.pack(fill="x", padx=32, pady=(10, 4))
        tk.Label(rand_cautare, text="🔍", bg=FUNDAL).pack(side="left")
        intrare = ttk.Entry(rand_cautare, textvariable=cautare_var, width=40)
        intrare.pack(side="left", padx=6)
        intrare.focus_set()

        # zonă derulabilă cu carduri
        cadru = tk.Frame(self.continut, bg=FUNDAL)
        cadru.pack(fill="both", expand=True, padx=20, pady=8)
        panza = tk.Canvas(cadru, bg=FUNDAL, highlightthickness=0)
        bara = ttk.Scrollbar(cadru, orient="vertical", command=panza.yview)
        interior = tk.Frame(panza, bg=FUNDAL)
        fereastra = panza.create_window((0, 0), window=interior, anchor="nw")
        panza.configure(yscrollcommand=bara.set)
        panza.pack(side="left", fill="both", expand=True)
        bara.pack(side="right", fill="y")
        interior.bind("<Configure>", lambda e: panza.configure(scrollregion=panza.bbox("all")))

        def rotita(e):
            if panza.winfo_exists():
                panza.yview_scroll(int(-e.delta / 120) if e.delta else (-1 if e.num == 4 else 1), "units")
        self.r.bind_all("<MouseWheel>", rotita)
        self.r.bind_all("<Button-4>", rotita)
        self.r.bind_all("<Button-5>", rotita)

        stare = {"latime": 0}

        def deseneaza(*_):
            for w in interior.winfo_children():
                w.destroy()
            filtru = cautare_var.get().strip().lower()
            latime = max(panza.winfo_width(), 400)
            coloane = max(2, latime // 235)
            unelte = [u for u in UNELTE if not filtru or filtru in u["titlu"].lower()
                      or filtru in u["desc"].lower() or filtru in u["cat"].lower()]
            categorii = list(dict.fromkeys(u["cat"] for u in unelte))
            rand = 0
            for cat in categorii:
                tk.Label(interior, text=cat.upper(), font=("Segoe UI", 9, "bold"), bg=FUNDAL,
                         fg=CULORI_CATEGORII[cat]).grid(row=rand, column=0, columnspan=coloane,
                                                        sticky="w", padx=12, pady=(14, 2))
                rand += 1
                for i, u in enumerate([u for u in unelte if u["cat"] == cat]):
                    self._card(interior, u).grid(row=rand + i // coloane, column=i % coloane,
                                                 padx=10, pady=8, sticky="nsew")
                rand += (len([u for u in unelte if u["cat"] == cat]) + coloane - 1) // coloane
            for c in range(coloane):
                interior.grid_columnconfigure(c, weight=1, uniform="c", minsize=210)
            if not unelte:
                tk.Label(interior, text="Nicio unealtă găsită.", bg=FUNDAL, fg=TEXT_SECUNDAR).grid(padx=12)

        def la_redimensionare(e):
            panza.itemconfigure(fereastra, width=e.width)
            if abs(e.width - stare["latime"]) > 60:
                stare["latime"] = e.width
                deseneaza()
        panza.bind("<Configure>", la_redimensionare)
        cautare_var.trace_add("write", deseneaza)

        def enter(_):
            gasite = [u for u in UNELTE if cautare_var.get().strip().lower() in u["titlu"].lower()]
            if len(gasite) >= 1 and cautare_var.get().strip():
                self.unealta(gasite[0])
        intrare.bind("<Return>", enter)

    def _card(self, parinte, u):
        culoare = CULORI_CATEGORII[u["cat"]]
        card = tk.Frame(parinte, bg=CARD, highlightthickness=1, highlightbackground=BORDURA,
                        cursor="hand2", height=165)
        card.grid_propagate(False)
        card.pack_propagate(False)
        icon = tk.Label(card, text=u["icon"], font=("Segoe UI Symbol", 18, "bold"), fg="white",
                        bg=culoare, width=3, height=1)
        icon.pack(anchor="w", padx=16, pady=(16, 8))
        titlu = tk.Label(card, text=u["titlu"], font=("Segoe UI", 12, "bold"), bg=CARD, fg=TEXT,
                         anchor="w")
        titlu.pack(fill="x", padx=16)
        desc = tk.Label(card, text=u["desc"], font=("Segoe UI", 9), bg=CARD, fg=TEXT_SECUNDAR,
                        justify="left", anchor="nw", wraplength=190)
        desc.pack(fill="both", expand=True, padx=16, pady=(2, 12))

        def peste(_):
            card.configure(highlightbackground=culoare, highlightthickness=2)

        def afara(_):
            card.configure(highlightbackground=BORDURA, highlightthickness=1)

        for w in (card, icon, titlu, desc):
            w.bind("<Button-1>", lambda e, u=u: self.unealta(u))
            w.bind("<Enter>", peste)
            w.bind("<Leave>", afara)
        card.bind("<Configure>", lambda e: desc.configure(wraplength=max(120, e.width - 32)))
        return card

    # ---------------------------------------------------- ecranul unei unelte
    def unealta(self, u, fisiere_initiale=None):
        self._goleste()
        self.r.unbind_all("<MouseWheel>")
        self.r.unbind_all("<Button-4>")
        self.r.unbind_all("<Button-5>")
        self.u = u
        self.fisiere: list[str] = []
        culoare = CULORI_CATEGORII[u["cat"]]

        bara = tk.Frame(self.continut, bg=FUNDAL)
        bara.pack(fill="x", padx=24, pady=(16, 0))
        self._buton(bara, "← Toate uneltele", self.acasa, principal=False, padx=12, pady=4).pack(side="left")

        antet = tk.Frame(self.continut, bg=FUNDAL)
        antet.pack(fill="x", padx=32, pady=(12, 8))
        tk.Label(antet, text=u["icon"], font=("Segoe UI Symbol", 20, "bold"), fg="white", bg=culoare,
                 width=3).pack(side="left", padx=(0, 14))
        texte = tk.Frame(antet, bg=FUNDAL)
        texte.pack(side="left", fill="x")
        tk.Label(texte, text=u["titlu"], font=("Segoe UI", 20, "bold"), bg=FUNDAL, fg=TEXT).pack(anchor="w")
        tk.Label(texte, text=u["desc"], font=("Segoe UI", 10), bg=FUNDAL, fg=TEXT_SECUNDAR).pack(anchor="w")

        corp = tk.Frame(self.continut, bg=FUNDAL)
        corp.pack(fill="both", expand=True, padx=32, pady=8)
        corp.grid_columnconfigure(0, weight=3)
        corp.grid_columnconfigure(1, weight=2, minsize=300)
        corp.grid_rowconfigure(0, weight=1)

        # --- stânga: fișierele
        stanga = tk.Frame(corp, bg=CARD, highlightthickness=1, highlightbackground=BORDURA)
        stanga.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        sus = tk.Frame(stanga, bg=CARD)
        sus.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(sus, text="Fișiere", font=("Segoe UI", 11, "bold"), bg=CARD).pack(side="left")
        self.eticheta_nr = tk.Label(sus, text="", bg=CARD, fg=TEXT_SECUNDAR)
        self.eticheta_nr.pack(side="left", padx=8)

        self.lista = tk.Listbox(stanga, font=("Segoe UI", 10), bd=0, highlightthickness=0,
                                selectbackground=culoare, activestyle="none", bg=CARD)
        self.lista.pack(fill="both", expand=True, padx=16, pady=4)
        self.gol = tk.Label(stanga, bg=CARD, fg=TEXT_SECUNDAR, font=("Segoe UI", 11), cursor="hand2",
                            text=("Trage fișierele aici\nsau\n" if TkinterDnD else "") + "apasă „Adaugă fișiere”")
        self.gol.bind("<Button-1>", lambda e: self.adauga())
        self.lista.bind("<Double-Button-1>", lambda e: self._deschide_selectat())

        butoane = tk.Frame(stanga, bg=CARD)
        butoane.pack(fill="x", padx=16, pady=(4, 14))
        self._buton(butoane, "+ Adaugă fișiere", self.adauga).pack(side="left")
        if u.get("multiple"):
            self._buton(butoane, "▲", lambda: self._muta(-1), principal=False, padx=10).pack(side="left", padx=(8, 0))
            self._buton(butoane, "▼", lambda: self._muta(1), principal=False, padx=10).pack(side="left", padx=4)
            self._buton(butoane, "A→Z", self._sorteaza, principal=False, padx=10).pack(side="left")
        self._buton(butoane, "Elimină", self._elimina, principal=False, padx=10).pack(side="left", padx=4)

        if TkinterDnD:
            for w in (self.lista, self.gol, stanga):
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", lambda e: self._adauga_cai(self.r.tk.splitlist(e.data)))

        # --- dreapta: opțiuni + acțiune
        dreapta = tk.Frame(corp, bg=CARD, highlightthickness=1, highlightbackground=BORDURA)
        dreapta.grid(row=0, column=1, sticky="nsew")
        tk.Label(dreapta, text="Opțiuni", font=("Segoe UI", 11, "bold"), bg=CARD).pack(anchor="w", padx=16, pady=(14, 6))
        self.valori = {}
        optiuni = tk.Frame(dreapta, bg=CARD)
        optiuni.pack(fill="x", padx=16)
        for cheie, eticheta, tip, implicit, *rest in u.get("optiuni", []):
            self._optiune(optiuni, cheie, eticheta, tip, implicit, rest[0] if rest else None)
        if not u.get("optiuni"):
            tk.Label(optiuni, text="Nu sunt opțiuni – adaugă fișierele și apasă butonul.",
                     bg=CARD, fg=TEXT_SECUNDAR, wraplength=260, justify="left").pack(anchor="w")

        tk.Label(dreapta, text="Salvează în", font=("Segoe UI", 9), bg=CARD, fg=TEXT_SECUNDAR).pack(
            anchor="w", padx=16, pady=(16, 0))
        rand_folder = tk.Frame(dreapta, bg=CARD)
        rand_folder.pack(fill="x", padx=16)
        self.folder = tk.StringVar(value="")
        ttk.Entry(rand_folder, textvariable=self.folder).pack(side="left", fill="x", expand=True)
        self._buton(rand_folder, "…", self._alege_folder, principal=False, padx=8, pady=2).pack(side="left", padx=(4, 0))
        tk.Label(dreapta, text="(gol = lângă fișierul original)", font=("Segoe UI", 8), bg=CARD,
                 fg=TEXT_SECUNDAR).pack(anchor="w", padx=16)

        jos = tk.Frame(dreapta, bg=CARD)
        jos.pack(side="bottom", fill="x", padx=16, pady=16)
        self.progres = ttk.Progressbar(jos, mode="indeterminate")
        self.stare = tk.Label(jos, text="", bg=CARD, fg=TEXT_SECUNDAR, wraplength=280, justify="left")
        self.stare.pack(fill="x", pady=(0, 6))
        self.rezultate = tk.Frame(jos, bg=CARD)
        self.rezultate.pack(fill="x")
        self.buton_start = self._buton(jos, f"{u['titlu']}  →", self.porneste,
                                       font=("Segoe UI", 12, "bold"), pady=12, bg=culoare,
                                       activebackground=culoare)
        self.buton_start.pack(fill="x", pady=(8, 0))

        self._actualizeaza_lista()
        if fisiere_initiale:
            self._adauga_cai(fisiere_initiale)

    def _optiune(self, parinte, cheie, eticheta, tip, implicit, valori):
        rand = tk.Frame(parinte, bg=CARD)
        rand.pack(fill="x", pady=4)
        if tip == "bifa":
            var = tk.BooleanVar(value=implicit)
            ttk.Checkbutton(rand, text=eticheta, variable=var).pack(anchor="w")
        else:
            tk.Label(rand, text=eticheta, bg=CARD, fg=TEXT_SECUNDAR, font=("Segoe UI", 9)).pack(anchor="w")
            if tip == "alegere":
                var = tk.StringVar(value=implicit)
                ttk.Combobox(rand, textvariable=var, values=valori, state="readonly").pack(fill="x")
            elif tip == "numar":
                var = tk.IntVar(value=implicit)
                ttk.Spinbox(rand, textvariable=var, from_=1, to=999, width=8).pack(anchor="w")
            elif tip == "imagine":
                var = tk.StringVar(value=implicit)
                r2 = tk.Frame(rand, bg=CARD)
                r2.pack(fill="x")
                ttk.Entry(r2, textvariable=var).pack(side="left", fill="x", expand=True)
                self._buton(r2, "…", lambda: var.set(filedialog.askopenfilename(filetypes=IMAGINI) or var.get()),
                            principal=False, padx=8, pady=2).pack(side="left", padx=(4, 0))
            else:
                var = tk.StringVar(value=implicit)
                ttk.Entry(rand, textvariable=var, show="•" if tip == "parola" else "").pack(fill="x")
        self.valori[cheie] = var

    # ---------------------------------------------------- lista de fișiere
    def adauga(self):
        tipuri = self.u["tipuri"] + [("Toate fișierele", "*.*")]
        if self.u.get("multiple"):
            cai = filedialog.askopenfilenames(filetypes=tipuri)
        else:
            c = filedialog.askopenfilename(filetypes=tipuri)
            cai = [c] if c else []
        self._adauga_cai(cai)

    def _adauga_cai(self, cai):
        extensii = {e.lstrip("*").lower() for _, t in self.u["tipuri"] for e in t.split()}
        respinse = []
        for c in cai:
            if os.path.isdir(c):
                continue
            if Path(c).suffix.lower() not in extensii:
                respinse.append(Path(c).name)
                continue
            if not self.u.get("multiple"):
                self.fisiere = []
            if c not in self.fisiere:
                self.fisiere.append(c)
        if respinse:
            messagebox.showwarning("Fișiere ignorate",
                                   "Aceste fișiere nu sunt de tipul potrivit:\n" + "\n".join(respinse))
        self._actualizeaza_lista()

    def _actualizeaza_lista(self):
        self.lista.delete(0, "end")
        for i, f in enumerate(self.fisiere, 1):
            extra = ""
            if f.lower().endswith(".pdf"):
                n = op.numar_pagini(f)
                extra = "   🔒 protejat" if n is None else f"   ({n} pag.)"
            self.lista.insert("end", f"  {i}.  {Path(f).name}{extra}")
        if self.fisiere:
            self.gol.place_forget()
            self.eticheta_nr.configure(text=f"{len(self.fisiere)} selectat(e)")
        else:
            self.gol.place(in_=self.lista, relx=0.5, rely=0.45, anchor="center")
            self.eticheta_nr.configure(text="")

    def _selectat(self):
        s = self.lista.curselection()
        return s[0] if s else None

    def _muta(self, directie):
        i = self._selectat()
        if i is None:
            return
        j = i + directie
        if 0 <= j < len(self.fisiere):
            self.fisiere[i], self.fisiere[j] = self.fisiere[j], self.fisiere[i]
            self._actualizeaza_lista()
            self.lista.selection_set(j)

    def _sorteaza(self):
        self.fisiere.sort(key=lambda f: Path(f).name.lower())
        self._actualizeaza_lista()

    def _elimina(self):
        i = self._selectat()
        if i is not None:
            del self.fisiere[i]
            self._actualizeaza_lista()

    def _deschide_selectat(self):
        i = self._selectat()
        if i is not None:
            deschide(self.fisiere[i])

    def _alege_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.folder.set(d)

    # ---------------------------------------------------- rulare
    def porneste(self):
        u = self.u
        minim = u.get("minim", 1)
        if len(self.fisiere) < minim:
            messagebox.showinfo(u["titlu"], "Adaugă cel puțin " +
                                ("un fișier." if minim == 1 else f"{minim} fișiere."))
            return
        try:
            optiuni = {k: v.get() for k, v in self.valori.items()}
        except tk.TclError:
            messagebox.showerror(u["titlu"], "Verifică valorile numerice din opțiuni.")
            return
        folder = self.folder.get().strip() or str(Path(self.fisiere[0]).parent)
        if not os.path.isdir(folder):
            messagebox.showerror(u["titlu"], f"Folderul nu există:\n{folder}")
            return
        if not os.access(folder, os.W_OK):
            messagebox.showerror(u["titlu"], f"Nu pot scrie în folderul:\n{folder}\nAlege alt folder.")
            return

        for w in self.rezultate.winfo_children():
            w.destroy()
        self.buton_start.configure(state="disabled", text="Se lucrează…")
        self.stare.configure(text="Se procesează, te rog așteaptă…", fg=TEXT_SECUNDAR)
        self.progres.pack(fill="x", before=self.stare, pady=(0, 6))
        self.progres.start(12)
        fisiere = list(self.fisiere)

        def lucreaza():
            try:
                rezultat = u["rulare"](fisiere, folder, optiuni)
                self.r.after(0, lambda: self._gata(rezultat, None))
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                mesaj = str(e) or e.__class__.__name__
                self.r.after(0, lambda: self._gata(None, mesaj))

        threading.Thread(target=lucreaza, daemon=True).start()

    def _gata(self, rezultat, eroare):
        if not self.buton_start.winfo_exists():
            return
        self.progres.stop()
        self.progres.pack_forget()
        self.buton_start.configure(state="normal", text=f"{self.u['titlu']}  →")
        if eroare:
            self.stare.configure(text="Nu a mers: " + eroare, fg="#c92a2a")
            messagebox.showerror(self.u["titlu"], eroare)
            return
        n = len(rezultat)
        self.stare.configure(text=f"✔ Gata! {n} fișier{'e' if n != 1 else ''} creat{'e' if n != 1 else ''}:",
                             fg="#2b8a3e")
        for cale in rezultat[:6]:
            rand = tk.Frame(self.rezultate, bg=CARD)
            rand.pack(fill="x", pady=1)
            marime = Path(cale).stat().st_size / 1024
            tk.Label(rand, text=f"{Path(cale).name}  ({marime:,.0f} KB)", bg=CARD, fg=TEXT,
                     anchor="w").pack(side="left", fill="x", expand=True)
            self._buton(rand, "Deschide", lambda c=cale: deschide(c), principal=False,
                        padx=8, pady=1, font=("Segoe UI", 9)).pack(side="right")
        if n > 6:
            tk.Label(self.rezultate, text=f"… și încă {n - 6}", bg=CARD, fg=TEXT_SECUNDAR).pack(anchor="w")
        self._buton(self.rezultate, "Arată în folder", lambda: arata_in_folder(rezultat[0]),
                    principal=False, pady=4).pack(anchor="w", pady=(6, 0))


def main():
    radacina = TkinterDnD.Tk() if TkinterDnD else tk.Tk()
    if sys.platform == "win32":
        try:  # text clar pe ecrane cu scalare
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    app = Aplicatie(radacina)
    # PDF-uri date ca argumente (ex. trase peste .exe) → deschide direct „Unește” sau „Comprimă”
    argumente = [a for a in sys.argv[1:] if os.path.isfile(a)]
    if argumente:
        u = next(x for x in UNELTE if x["id"] == ("uneste" if len(argumente) > 1 else "comprima"))
        app.unealta(u, argumente)
    radacina.mainloop()


if __name__ == "__main__":
    main()
