"""
Ceas Mare - ceas pe tot ecranul, afișat/ascuns cu o tastă (Windows).

- Apasă tasta (implicit F9) oriunde în Windows -> ceasul apare pe tot ecranul.
- Apasă din nou aceeași tastă (sau Esc, sau click) -> ceasul dispare.
- Ctrl + tasta -> închide programul.
- Ora este sincronizată de pe internet (NTP), cu rezervă prin HTTP.
- Sub dată apare țara (din setarea de regiune a Windows), în culorile steagului ei.

Rulare:   pythonw ceas.py            (tasta implicită F9)
          pythonw ceas.py --tasta F8 (altă tastă: F1..F24, A..Z, 0..9)
          pythonw ceas.py --tara IT  (altă țară decât cea din Windows, cod din 2 litere)
Nu are nevoie de biblioteci externe (doar Python 3 standard).
"""

import argparse
import colorsys
import datetime
import email.utils
import queue
import socket
import struct
import sys
import threading
import time
import tkinter as tk
import urllib.request

# ----------------------------------------------------------------------------
# Setări
# ----------------------------------------------------------------------------
VERSIUNE = "1.4"
TASTA_IMPLICITA = "F9"
FORMAT_24H = True  # True: ora 00..23 (plus AM/PM); False: ora 01..12 (plus AM/PM)
INTERVAL_SINCRONIZARE = 10 * 60  # secunde între sincronizări cu internetul
INTERVAL_REINCERCARE = 30  # secunde, dacă nu a mers sincronizarea
SERVERE_NTP = ["time.windows.com", "pool.ntp.org", "time.google.com", "time.cloudflare.com"]
SERVERE_HTTP = ["https://www.google.com", "https://www.microsoft.com", "https://www.cloudflare.com"]

CULOARE_FUNDAL = "#000000"
CULOARE_ORA = "#FFFFFF"
CULOARE_AMPM = "#4FC3F7"
CULOARE_DATA = "#B0BEC5"
CULOARE_STARE = "#546E7A"

# Culori care se schimbă de la o oră la alta. Fiecare oră are culoarea ei; pe parcursul
# orei, culoarea trece treptat spre culoarea orei următoare.
CULORI_DINAMICE = True  # False: ora rămâne mereu CULOARE_ORA
PAS_NUANTA = 105  # grade pe roata culorilor între două ore (7 × 15°: toate 24 orele au culori diferite)
SATURATIE = 0.85
LUMINOZITATE = 0.62

ZILE = ["luni", "marți", "miercuri", "joi", "vineri", "sâmbătă", "duminică"]
LUNI = ["ianuarie", "februarie", "martie", "aprilie", "mai", "iunie", "iulie",
        "august", "septembrie", "octombrie", "noiembrie", "decembrie"]

# Țara utilizatorului, în culorile steagului național. Culorile sunt fixe (nu se
# schimbă cu ora) și se aplică pe litere, în benzi, în ordinea de pe steag.
ARATA_TARA = True  # False: nu se afișează țara
CONTRAST_MINIM = 4.5  # culorile prea închise (negru, bleumarin) se deschid până la acest contrast pe negru

# cod ISO din 2 litere -> (numele în română, culorile steagului)
TARI = {
    "RO": ("România", ["#002B7F", "#FCD116", "#CE1126"]),
    "MD": ("Republica Moldova", ["#0046AE", "#FFD200", "#CC092F"]),
    "DE": ("Germania", ["#000000", "#DD0000", "#FFCE00"]),
    "FR": ("Franța", ["#002654", "#FFFFFF", "#ED2939"]),
    "IT": ("Italia", ["#009246", "#FFFFFF", "#CE2B37"]),
    "ES": ("Spania", ["#AA151B", "#F1BF00", "#AA151B"]),
    "PT": ("Portugalia", ["#046A38", "#DA291C"]),
    "GB": ("Regatul Unit", ["#012169", "#FFFFFF", "#C8102E"]),
    "IE": ("Irlanda", ["#169B62", "#FFFFFF", "#FF883E"]),
    "NL": ("Țările de Jos", ["#AE1C28", "#FFFFFF", "#21468B"]),
    "BE": ("Belgia", ["#000000", "#FDDA24", "#EF3340"]),
    "LU": ("Luxemburg", ["#EF3340", "#FFFFFF", "#00A3E0"]),
    "AT": ("Austria", ["#ED2939", "#FFFFFF", "#ED2939"]),
    "CH": ("Elveția", ["#DA291C", "#FFFFFF", "#DA291C"]),
    "LI": ("Liechtenstein", ["#002B7F", "#CE1126"]),
    "MC": ("Monaco", ["#CE1126", "#FFFFFF"]),
    "AD": ("Andorra", ["#10069F", "#FEDF00", "#D50032"]),
    "SM": ("San Marino", ["#FFFFFF", "#5EB6E4"]),
    "MT": ("Malta", ["#FFFFFF", "#CF142B"]),
    "PL": ("Polonia", ["#FFFFFF", "#DC143C"]),
    "CZ": ("Cehia", ["#11457E", "#FFFFFF", "#D7141A"]),
    "SK": ("Slovacia", ["#FFFFFF", "#0B4EA2", "#EE1C25"]),
    "HU": ("Ungaria", ["#CD2A3E", "#FFFFFF", "#436F4D"]),
    "BG": ("Bulgaria", ["#FFFFFF", "#00966E", "#D62612"]),
    "RS": ("Serbia", ["#C6363C", "#0C4076", "#FFFFFF"]),
    "HR": ("Croația", ["#FF0000", "#FFFFFF", "#171796"]),
    "SI": ("Slovenia", ["#FFFFFF", "#005DA4", "#ED1C24"]),
    "BA": ("Bosnia și Herțegovina", ["#002395", "#FECB00", "#FFFFFF"]),
    "ME": ("Muntenegru", ["#C40308", "#D3AE3B"]),
    "MK": ("Macedonia de Nord", ["#D20000", "#FFE600"]),
    "AL": ("Albania", ["#E41E20", "#000000"]),
    "XK": ("Kosovo", ["#244AA5", "#D0A650"]),
    "GR": ("Grecia", ["#0D5EAF", "#FFFFFF", "#0D5EAF", "#FFFFFF"]),
    "CY": ("Cipru", ["#FFFFFF", "#D57800", "#4E5B31"]),
    "TR": ("Turcia", ["#E30A17", "#FFFFFF"]),
    "UA": ("Ucraina", ["#0057B7", "#FFD700"]),
    "BY": ("Belarus", ["#C8313E", "#4AA657"]),
    "RU": ("Rusia", ["#FFFFFF", "#0039A6", "#D52B1E"]),
    "GE": ("Georgia", ["#FFFFFF", "#FF0000"]),
    "AM": ("Armenia", ["#D90012", "#0033A0", "#F2A800"]),
    "AZ": ("Azerbaidjan", ["#0092BC", "#E4002B", "#00AF66"]),
    "KZ": ("Kazahstan", ["#00AFCA", "#FEC50C"]),
    "LT": ("Lituania", ["#FDB913", "#006A44", "#C1272D"]),
    "LV": ("Letonia", ["#9E3039", "#FFFFFF", "#9E3039"]),
    "EE": ("Estonia", ["#0072CE", "#000000", "#FFFFFF"]),
    "FI": ("Finlanda", ["#FFFFFF", "#002F6C", "#FFFFFF"]),
    "SE": ("Suedia", ["#006AA7", "#FECC02", "#006AA7"]),
    "NO": ("Norvegia", ["#BA0C2F", "#FFFFFF", "#00205B", "#FFFFFF", "#BA0C2F"]),
    "DK": ("Danemarca", ["#C8102E", "#FFFFFF", "#C8102E"]),
    "IS": ("Islanda", ["#02529C", "#FFFFFF", "#DC1E35", "#FFFFFF", "#02529C"]),
    "US": ("Statele Unite", ["#B22234", "#FFFFFF", "#3C3B6E"]),
    "CA": ("Canada", ["#D52B1E", "#FFFFFF", "#D52B1E"]),
    "MX": ("Mexic", ["#006847", "#FFFFFF", "#CE1126"]),
    "CU": ("Cuba", ["#002A8F", "#FFFFFF", "#CF142B"]),
    "BR": ("Brazilia", ["#009C3B", "#FFDF00", "#002776"]),
    "AR": ("Argentina", ["#74ACDF", "#FFFFFF", "#74ACDF"]),
    "CL": ("Chile", ["#0039A6", "#FFFFFF", "#D52B1E"]),
    "CO": ("Columbia", ["#FCD116", "#003893", "#CE1126"]),
    "PE": ("Peru", ["#D91023", "#FFFFFF", "#D91023"]),
    "VE": ("Venezuela", ["#FFCC00", "#00247D", "#CF142B"]),
    "AU": ("Australia", ["#012169", "#FFFFFF", "#E4002B"]),
    "NZ": ("Noua Zeelandă", ["#012169", "#FFFFFF", "#C8102E"]),
    "JP": ("Japonia", ["#FFFFFF", "#BC002D", "#FFFFFF"]),
    "CN": ("China", ["#EE1C25", "#FFFF00", "#EE1C25"]),
    "KR": ("Coreea de Sud", ["#CD2E3A", "#FFFFFF", "#0047A0"]),
    "IN": ("India", ["#FF9933", "#FFFFFF", "#138808"]),
    "ID": ("Indonezia", ["#FF0000", "#FFFFFF"]),
    "PH": ("Filipine", ["#0038A8", "#FFFFFF", "#CE1126"]),
    "TH": ("Thailanda", ["#A51931", "#F4F5F8", "#2D2A4A", "#F4F5F8", "#A51931"]),
    "VN": ("Vietnam", ["#DA251D", "#FFFF00"]),
    "IL": ("Israel", ["#0038B8", "#FFFFFF", "#0038B8"]),
    "EG": ("Egipt", ["#CE1126", "#FFFFFF", "#000000"]),
    "MA": ("Maroc", ["#C1272D", "#006233"]),
    "NG": ("Nigeria", ["#008751", "#FFFFFF", "#008751"]),
    "ZA": ("Africa de Sud", ["#007A4D", "#FFB612", "#DE3831", "#002395"]),
    "SA": ("Arabia Saudită", ["#006C35", "#FFFFFF"]),
    "AE": ("Emiratele Arabe Unite", ["#00732F", "#FFFFFF", "#000000", "#FF0000"]),
}


def luminanta(culoare):
    """Luminanța relativă (WCAG) a unei culori #RRGGBB."""
    def canal(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(culoare[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)


def lizibila_pe_negru(culoare, contrast=CONTRAST_MINIM):
    """Deschide culoarea (păstrând nuanța) până se citește bine pe fundal negru."""
    r, g, b = (int(culoare[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    for pas in range(101):
        rr, gg, bb = colorsys.hls_to_rgb(h, l + (1 - l) * pas / 100, s)
        c = f"#{round(rr * 255):02X}{round(gg * 255):02X}{round(bb * 255):02X}"
        if (luminanta(c) + 0.05) / 0.05 >= contrast:
            return c
    return "#FFFFFF"


def culori_litere(text, culori):
    """Culoarea fiecărui caracter: literele sunt împărțite în benzi egale, câte una
    pentru fiecare culoare a steagului (spațiile nu contează la împărțire)."""
    culori = [lizibila_pe_negru(c) for c in culori]
    litere = sum(1 for ch in text if not ch.isspace())
    rezultat, i = [], 0
    for ch in text:
        if ch.isspace():
            rezultat.append(culori[0])  # nu se vede, oricum
            continue
        if litere >= len(culori):
            rezultat.append(culori[i * len(culori) // litere])
        else:
            rezultat.append(culori[i % len(culori)])
        i += 1
    return rezultat


def tara_din_windows():
    """(cod ISO, nume) pentru țara setată în Windows (Setări → Oră și limbă → Regiune).
    Fără internet: se citește doar setarea locală. Întoarce (None, None) dacă nu se poate."""
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        buf = ctypes.create_unicode_buffer(128)
        cod = None
        try:  # Windows 10 1709+
            if k32.GetUserDefaultGeoName(buf, len(buf)) > 0:
                cod = buf.value.upper()
        except AttributeError:
            pass
        GEOCLASS_NATION, GEO_ISO2, GEO_FRIENDLYNAME = 16, 4, 8
        geo = k32.GetUserGeoID(GEOCLASS_NATION)
        if not cod or not cod.isalpha():  # „001” = „Lume”, adică nesetat
            cod = None
            if k32.GetGeoInfoW(geo, GEO_ISO2, buf, len(buf), 0) > 0:
                cod = buf.value.upper()
        nume = None
        if k32.GetGeoInfoW(geo, GEO_FRIENDLYNAME, buf, len(buf), 0) > 0:
            nume = buf.value
        return (cod if cod and cod.isalpha() else None), nume
    except Exception:
        return None, None


def tara_de_afisat(cod, nume_windows=None):
    """(text, culori pe caracter) pentru afișare, sau None dacă nu știm țara."""
    if cod and cod.upper() in TARI:
        nume, culori = TARI[cod.upper()]
    elif nume_windows:
        nume, culori = nume_windows, [CULOARE_DATA]  # țară fără steag definit: gri
    else:
        return None
    text = nume.upper()
    return text, culori_litere(text, culori)


def culoare_pentru(t, luminozitate=LUMINOZITATE, saturatie=SATURATIE):
    """Culoarea ceasului la momentul t (datetime).

    La începutul orei H culoarea e cea a orei H; până la sfârșitul orei se
    deplasează uniform pe roata culorilor până la culoarea orei H+1.
    După 23:59:59 se ajunge exact la culoarea orei 00, deci nu există salturi.
    """
    progres = (t.minute * 60 + t.second + t.microsecond / 1e6) / 3600
    nuanta = ((t.hour + progres) * PAS_NUANTA) % 360
    r, g, b = colorsys.hls_to_rgb(nuanta / 360, luminozitate, saturatie)
    return f"#{round(r * 255):02X}{round(g * 255):02X}{round(b * 255):02X}"


# ----------------------------------------------------------------------------
# Sincronizare oră de pe internet
# ----------------------------------------------------------------------------
NTP_EPOCH = 2208988800  # secunde între 1900-01-01 și 1970-01-01


def decalaj_ntp(server, timeout=3.0):
    """Întoarce diferența (secunde) dintre ora serverului NTP și ora PC-ului."""
    pachet = b"\x1b" + 47 * b"\0"  # LI=0, versiune 3, mod client
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)
        t0 = time.time()
        s.sendto(pachet, (server, 123))
        date, _ = s.recvfrom(48)
        t3 = time.time()
    if len(date) < 48:
        raise ValueError("răspuns NTP incomplet")

    def marca(b):
        sec, frac = struct.unpack("!II", b)
        return sec - NTP_EPOCH + frac / 2 ** 32

    t1 = marca(date[32:40])  # când a primit serverul cererea
    t2 = marca(date[40:48])  # când a trimis serverul răspunsul
    if t2 <= 0:
        raise ValueError("răspuns NTP invalid")
    return ((t1 - t0) + (t2 - t3)) / 2


def decalaj_http(url, timeout=5.0):
    """Rezervă: citește antetul 'Date' al unui site (precizie ~1 secundă)."""
    cerere = urllib.request.Request(url, method="HEAD")
    t0 = time.time()
    with urllib.request.urlopen(cerere, timeout=timeout) as r:
        antet = r.headers.get("Date")
    t3 = time.time()
    if not antet:
        raise ValueError("fără antet Date")
    ora_server = email.utils.parsedate_to_datetime(antet).timestamp()
    # antetul e trunchiat la secundă -> adăugăm 0.5 s în medie
    return ora_server + 0.5 - (t0 + t3) / 2


class SincronizareOra:
    """Ține decalajul față de ora exactă și îl actualizează periodic, în fundal."""

    def __init__(self):
        self._blocare = threading.Lock()
        self.decalaj = 0.0
        self.sursa = None  # serverul de la care s-a luat ultima dată ora
        self.ultima_sincronizare = None  # time.monotonic() la ultima reușită
        self._fir = threading.Thread(target=self._bucla, daemon=True)
        self._fir.start()

    def acum(self):
        with self._blocare:
            return time.time() + self.decalaj

    def stare(self):
        with self._blocare:
            return self.sursa, self.ultima_sincronizare, self.decalaj

    def sincronizeaza(self):
        for server in SERVERE_NTP:
            try:
                d = decalaj_ntp(server)
                self._salveaza(d, server)
                return True
            except (OSError, ValueError):
                continue
        for url in SERVERE_HTTP:
            try:
                d = decalaj_http(url)
                self._salveaza(d, url.split("//", 1)[-1])
                return True
            except Exception:
                continue
        return False

    def _salveaza(self, decalaj, sursa):
        with self._blocare:
            self.decalaj = decalaj
            self.sursa = sursa
            self.ultima_sincronizare = time.monotonic()

    def _bucla(self):
        while True:
            reusit = self.sincronizeaza()
            time.sleep(INTERVAL_SINCRONIZARE if reusit else INTERVAL_REINCERCARE)


# ----------------------------------------------------------------------------
# Tastă globală (funcționează oriunde în Windows, chiar dacă ceasul e ascuns)
# ----------------------------------------------------------------------------
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
ID_AFISARE = 1
ID_IESIRE = 2


def cod_tasta(nume):
    """Transformă un nume de tastă (F9, A, 5) în cod virtual Windows."""
    nume = nume.strip().upper()
    if nume.startswith("F") and nume[1:].isdigit() and 1 <= int(nume[1:]) <= 24:
        return 0x70 + int(nume[1:]) - 1
    if len(nume) == 1 and (nume.isalpha() or nume.isdigit()):
        return ord(nume)
    speciale = {"PAUSE": 0x13, "SCROLLLOCK": 0x91, "INSERT": 0x2D, "HOME": 0x24,
                "END": 0x23, "PAGEUP": 0x21, "PAGEDOWN": 0x22}
    if nume in speciale:
        return speciale[nume]
    raise ValueError(f"Tastă necunoscută: {nume}")


class TastaGlobala(threading.Thread):
    """Înregistrează tasta în Windows și pune evenimentele într-o coadă."""

    def __init__(self, vk, coada):
        super().__init__(daemon=True)
        self.vk = vk
        self.coada = coada
        self.gata = threading.Event()
        self.eroare = None

    def run(self):
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self.id_fir = kernel32.GetCurrentThreadId()

        if not user32.RegisterHotKey(None, ID_AFISARE, MOD_NOREPEAT, self.vk):
            self.eroare = "Tasta este deja folosită de alt program."
            self.gata.set()
            return
        user32.RegisterHotKey(None, ID_IESIRE, MOD_CONTROL | MOD_NOREPEAT, self.vk)
        self.gata.set()

        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    self.coada.put("iesire" if msg.wParam == ID_IESIRE else "comuta")
        finally:
            user32.UnregisterHotKey(None, ID_AFISARE)
            user32.UnregisterHotKey(None, ID_IESIRE)

    def opreste(self):
        import ctypes
        if self.is_alive():
            ctypes.windll.user32.PostThreadMessageW(self.id_fir, WM_QUIT, 0, 0)


# ----------------------------------------------------------------------------
# Fereastra ceasului
# ----------------------------------------------------------------------------
class CeasMare:
    def __init__(self, radacina, sincronizare, coada, nume_tasta, cerere_iesire=None,
                 tara=None):
        self.r = radacina
        self.cerere_iesire = cerere_iesire  # funcție: True dacă altă instanță ne cere să ieșim
        self.sinc = sincronizare
        self.coada = coada
        self.nume_tasta = nume_tasta
        self.vizibil = False
        self._actualizare = None

        r = self.r
        r.title("Ceas Mare")
        r.configure(bg=CULOARE_FUNDAL, cursor="none")
        r.overrideredirect(True)
        r.attributes("-topmost", True)

        l, h = r.winfo_screenwidth(), r.winfo_screenheight()
        r.geometry(f"{l}x{h}+0+0")

        # dimensiuni font (în pixeli; negativ = pixeli în Tk)
        marime_ora = int(min(l * 0.17, h * 0.40))
        marime_ampm = int(marime_ora * 0.32)
        marime_data = int(marime_ora * 0.16)
        marime_stare = max(12, int(h * 0.018))

        cadru = tk.Frame(r, bg=CULOARE_FUNDAL)
        cadru.place(relx=0.5, rely=0.47, anchor="center")

        rand = tk.Frame(cadru, bg=CULOARE_FUNDAL)
        rand.pack()
        self.eticheta_ora = tk.Label(rand, text="", fg=CULOARE_ORA, bg=CULOARE_FUNDAL,
                                     font=("Consolas", -marime_ora, "bold"))
        self.eticheta_ora.pack(side="left")
        self.eticheta_ampm = tk.Label(rand, text="", fg=CULOARE_AMPM, bg=CULOARE_FUNDAL,
                                      font=("Segoe UI", -marime_ampm, "bold"))
        self.eticheta_ampm.pack(side="left", anchor="s",
                                padx=(int(marime_ora * 0.08), 0),
                                pady=(0, int(marime_ora * 0.14)))

        self.eticheta_data = tk.Label(cadru, text="", fg=CULOARE_DATA, bg=CULOARE_FUNDAL,
                                      font=("Segoe UI", -marime_data))
        self.eticheta_data.pack(pady=(int(marime_ora * 0.05), 0))

        # țara: câte o etichetă pe literă, fiecare cu culoarea ei din steag
        self.rand_tara = tk.Frame(cadru, bg=CULOARE_FUNDAL)
        litere_tara = []
        if tara:
            text, culori = tara
            font_tara = ("Segoe UI", -int(marime_data * 0.85), "bold")
            for ch, culoare in zip(text, culori):
                e = tk.Label(self.rand_tara, text=ch, fg=culoare, bg=CULOARE_FUNDAL,
                             font=font_tara, bd=0, padx=0, pady=0, highlightthickness=0)
                e.pack(side="left")
                litere_tara.append(e)
            self.rand_tara.pack(pady=(int(marime_ora * 0.06), 0))

        self.eticheta_stare = tk.Label(r, text="", fg=CULOARE_STARE, bg=CULOARE_FUNDAL,
                                       font=("Segoe UI", -marime_stare))
        self.eticheta_stare.place(relx=0.5, rely=0.97, anchor="s")

        for w in (r, cadru, rand, self.eticheta_ora, self.eticheta_ampm,
                  self.eticheta_data, self.eticheta_stare, self.rand_tara, *litere_tara):
            w.bind("<Button-1>", lambda e: self.ascunde())
        r.bind("<Escape>", lambda e: self.ascunde())

        r.withdraw()
        self.r.after(50, self._citeste_coada)

    # --- afișare / ascundere ---------------------------------------------
    def comuta(self):
        self.ascunde() if self.vizibil else self.arata()

    def arata(self):
        self.vizibil = True
        self._deseneaza()
        self.r.deiconify()
        self.r.attributes("-topmost", True)
        self.r.lift()
        self.r.focus_force()

    def ascunde(self):
        self.vizibil = False
        if self._actualizare is not None:
            self.r.after_cancel(self._actualizare)
            self._actualizare = None
        self.r.withdraw()

    # --- desenare ---------------------------------------------------------
    def _deseneaza(self):
        if self._actualizare is not None:
            self.r.after_cancel(self._actualizare)
            self._actualizare = None
        if not self.vizibil:
            return

        acum = self.sinc.acum()
        t = datetime.datetime.fromtimestamp(acum)
        ora = t.hour if FORMAT_24H else (t.hour % 12 or 12)
        self.eticheta_ora.config(text=f"{ora:02d}:{t.minute:02d}:{t.second:02d}")
        self.eticheta_ampm.config(text="AM" if t.hour < 12 else "PM")
        self.eticheta_data.config(
            text=f"{ZILE[t.weekday()]}, {t.day} {LUNI[t.month - 1]} {t.year}")
        if CULORI_DINAMICE:
            self.eticheta_ora.config(fg=culoare_pentru(t))
            self.eticheta_ampm.config(fg=culoare_pentru(t))
            # data: aceeași nuanță, mai stinsă, ca ora să rămână în prim-plan
            self.eticheta_data.config(fg=culoare_pentru(t, luminozitate=0.75, saturatie=0.35))
        self.eticheta_stare.config(text=self._text_stare())

        # următoarea actualizare exact la schimbarea secundei
        pana_la_secunda = 1.0 - (acum % 1.0)
        self._actualizare = self.r.after(int(pana_la_secunda * 1000) + 5, self._deseneaza)

    def _text_stare(self):
        sursa, ultima, decalaj = self.sinc.stare()
        indicatii = (f"{self.nume_tasta} / Esc = ascunde   •   Ctrl+{self.nume_tasta} = închide"
                     f"   •   v{VERSIUNE}")
        if ultima is None:
            return f"Se sincronizează cu internetul… (ora PC-ului)   •   {indicatii}"
        minute = int((time.monotonic() - ultima) // 60)
        cand = "acum" if minute < 1 else f"acum {minute} min"
        return (f"Sincronizat cu {sursa} {cand} (PC-ul era {decalaj:+.2f} s)"
                f"   •   {indicatii}")

    # --- evenimente de la tasta globală -----------------------------------
    def _citeste_coada(self):
        try:
            while True:
                ev = self.coada.get_nowait()
                if ev == "comuta":
                    self.comuta()
                elif ev == "iesire":
                    self.r.destroy()
                    return
        except queue.Empty:
            pass
        if self.cerere_iesire is not None and self.cerere_iesire():
            self.r.destroy()  # a pornit o instanță nouă (de ex. o versiune mai nouă)
            return
        self.r.after(50, self._citeste_coada)


# ----------------------------------------------------------------------------
def mesaj_eroare(text):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, "Ceas Mare", 0x10)
    except Exception:
        print(text, file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Ceas mare pe tot ecranul, la apăsarea unei taste.")
    parser.add_argument("--tasta", default=TASTA_IMPLICITA,
                        help="tasta care afișează/ascunde ceasul (implicit F9)")
    parser.add_argument("--tara", default=None,
                        help="codul țării din 2 litere (implicit: regiunea din Windows)")
    args = parser.parse_args()

    if sys.platform != "win32":
        mesaj_eroare("Acest program funcționează doar pe Windows.")
        return 1

    import ctypes

    # O singură instanță: dacă rulează deja una (de ex. o versiune mai veche),
    # îi cerem să se închidă și îi luăm locul.
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = wintypes.HANDLE
    k32.CreateEventW.restype = wintypes.HANDLE
    k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k32.WaitForSingleObject.restype = wintypes.DWORD
    k32.SetEvent.argtypes = [wintypes.HANDLE]
    k32.ResetEvent.argtypes = [wintypes.HANDLE]

    mutex = k32.CreateMutexW(None, True, "CeasMare_instanta_unica_v2")
    exista_deja = ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS
    eveniment_iesire = k32.CreateEventW(None, True, False, "CeasMare_cerere_iesire")
    if exista_deja:
        k32.SetEvent(eveniment_iesire)
        rezultat = k32.WaitForSingleObject(mutex, 10000)
        k32.ResetEvent(eveniment_iesire)
        if rezultat not in (0x0, 0x80):  # WAIT_OBJECT_0, WAIT_ABANDONED
            mesaj_eroare("Ceasul rulează deja și nu s-a putut închide singur.\n"
                         "Închide CeasMare.exe din Task Manager și pornește-l din nou.")
            return 1

    def cerere_iesire():
        return k32.WaitForSingleObject(eveniment_iesire, 0) == 0

    # Ecran nețesut (fără scalare încețoșată pe monitoare 125%/150%)
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    try:
        vk = cod_tasta(args.tasta)
    except ValueError as e:
        mesaj_eroare(str(e))
        return 1
    nume_tasta = args.tasta.strip().upper()

    coada = queue.Queue()
    tasta = TastaGlobala(vk, coada)
    tasta.start()
    tasta.gata.wait(5)
    if tasta.eroare:
        mesaj_eroare(f"Nu pot folosi tasta {nume_tasta}: {tasta.eroare}\n\n"
                     f"Dacă rulează încă o versiune mai veche a ceasului, închide "
                     f"CeasMare.exe din Task Manager și pornește-l din nou.\n"
                     f"Altfel, pornește cu altă tastă, de ex.: --tasta F8")
        return 1

    tara = None
    if ARATA_TARA:
        cod, nume_windows = tara_din_windows()
        if args.tara:
            cod, nume_windows = args.tara.strip().upper(), None
        tara = tara_de_afisat(cod, nume_windows)

    sincronizare = SincronizareOra()
    radacina = tk.Tk()
    CeasMare(radacina, sincronizare, coada, nume_tasta, cerere_iesire, tara)
    try:
        radacina.mainloop()
    finally:
        tasta.opreste()
        tasta.join(2)  # tasta trebuie eliberată înainte ca o instanță nouă să o ia
    return 0


if __name__ == "__main__":
    sys.exit(main())
