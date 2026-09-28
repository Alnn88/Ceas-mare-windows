# Ceas Mare pentru Windows

Un ceas pe **tot ecranul**, afișat la cerere cu o tastă:

- apeși **F9** (oriunde în Windows, în orice program) → ceasul apare pe tot ecranul;
- apeși din nou **F9** (sau `Esc`, sau un click) → ceasul dispare;
- **Ctrl + F9** → închide programul.

Ora e afișată în format de 24 de ore, `HH:mm:ss` (ora de la 00 la 23), cu
AM/PM alături (AM pentru 00–11, PM pentru 12–23) și data dedesubt (în română), și este
**sincronizată de pe internet** (servere NTP: time.windows.com, pool.ntp.org,
time.google.com; dacă UDP e blocat, se folosește ora de la un site prin HTTPS).
Se resincronizează la fiecare 10 minute. Dacă nu ai internet, folosește ora PC-ului
și scrie asta jos pe ecran.

## Varianta 1 – fără Python (CeasMare.exe)

1. Pe GitHub, intră la **Actions → Construieste CeasMare.exe**, deschide ultima rulare
   și descarcă arhiva **CeasMare-windows** de la *Artifacts*.
2. Dezarhivează într-un folder (de ex. `C:\CeasMare`) și pornește `CeasMare.exe`.
   Nu apare nicio fereastră – programul așteaptă tasta F9.
3. (Opțional) rulează `adauga_la_pornire_windows.bat` ca să pornească automat cu Windows-ul.

> Windows SmartScreen poate avertiza la prima pornire („Mai multe informații” → „Rulează oricum”),
> pentru că exe-ul nu este semnat digital.

## Varianta 2 – cu Python

1. Instalează Python 3 de pe <https://www.python.org> (bifează *Add Python to PATH*).
2. Dublu-click pe `porneste_ceas.bat`.
3. (Opțional) `adauga_la_pornire_windows.bat` pentru pornire automată.

Nu are nevoie de alte biblioteci.

## Altă tastă

```
porneste_ceas.bat --tasta F8
CeasMare.exe --tasta F10
```

Taste acceptate: `F1`…`F24`, litere `A`…`Z`, cifre `0`…`9`, `Pause`, `ScrollLock`,
`Insert`, `Home`, `End`, `PageUp`, `PageDown`. Dacă tasta e deja folosită de alt
program, apare un mesaj și poți alege alta.

Pentru formatul de 12 ore (01–12), pune `FORMAT_24H = False` în `ceas.py`.

Culorile, serverele de timp și intervalul de sincronizare se pot schimba în partea de
sus a fișierului `ceas.py` (secțiunea *Setări*).
