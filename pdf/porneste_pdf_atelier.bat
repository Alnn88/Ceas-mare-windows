@echo off
rem Porneste PDF Atelier. La prima rulare instaleaza bibliotecile necesare.
cd /d "%~dp0"
python -c "import pymupdf, pdf2docx, openpyxl" 2>nul || python -m pip install -r requirements.txt
start "" pythonw pdf_atelier.py %*
