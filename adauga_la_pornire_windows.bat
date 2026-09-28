@echo off
rem Face ca ceasul sa porneasca automat la fiecare pornire a Windows-ului.
set "CE_DIR=%~dp0"
set "CE_TINTA="
set "CE_SCRIPT="
if exist "%~dp0CeasMare.exe" goto exe
for %%P in (pythonw.exe) do set "CE_TINTA=%%~$PATH:P"
set "CE_SCRIPT=%~dp0ceas.py"
goto verifica
:exe
set "CE_TINTA=%~dp0CeasMare.exe"
:verifica
if "%CE_TINTA%"=="" (
    echo Nu am gasit nici CeasMare.exe, nici Python ^(pythonw.exe^).
    pause
    exit /b 1
)
powershell -NoProfile -Command "$d=[Environment]::GetFolderPath('Startup'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'Ceas Mare.lnk')); $s.TargetPath=$env:CE_TINTA; if($env:CE_SCRIPT){$s.Arguments='\"'+$env:CE_SCRIPT+'\"'}; $s.WorkingDirectory=$env:CE_DIR; $s.Save()"
echo Gata! Ceasul va porni automat cu Windows-ul.
pause
