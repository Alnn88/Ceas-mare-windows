"""
Ceas Mare - ceas pe tot ecranul, afișat/ascuns cu o tastă (Windows).

- Apasă tasta (implicit F9) oriunde în Windows -> ceasul apare pe tot ecranul.
- Apasă din nou aceeași tastă (sau Esc, sau click) -> ceasul dispare.
- Ctrl + tasta -> închide programul.
- Ora este sincronizată de pe internet (NTP), cu rezervă prin HTTP.

Rulare:   pythonw ceas.py            (tasta implicită F9)
          pythonw ceas.py --tasta F8 (altă tastă: F1..F24, A..Z, 0..9)
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
VERSIUNE = "1.3"
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
    def __init__(self, radacina, sincronizare, coada, nume_tasta, cerere_iesire=None):
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

        self.eticheta_stare = tk.Label(r, text="", fg=CULOARE_STARE, bg=CULOARE_FUNDAL,
                                       font=("Segoe UI", -marime_stare))
        self.eticheta_stare.place(relx=0.5, rely=0.97, anchor="s")

        for w in (r, cadru, rand, self.eticheta_ora, self.eticheta_ampm,
                  self.eticheta_data, self.eticheta_stare):
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

    sincronizare = SincronizareOra()
    radacina = tk.Tk()
    CeasMare(radacina, sincronizare, coada, nume_tasta, cerere_iesire)
    try:
        radacina.mainloop()
    finally:
        tasta.opreste()
        tasta.join(2)  # tasta trebuie eliberată înainte ca o instanță nouă să o ia
    return 0


if __name__ == "__main__":
    sys.exit(main())
