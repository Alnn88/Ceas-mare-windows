@echo off
rem Porneste ceasul in fundal (fara fereastra neagra). Tasta implicita: F9
rem Pentru alta tasta:  porneste_ceas.bat --tasta F8
start "" pythonw "%~dp0ceas.py" %*
