@echo off
rem Windows programini (.exe) derler. Gereken: Python 3.11+  ->  pip install -r requirements.txt
cd /d "%~dp0"
python -m PyInstaller --noconfirm --onefile --windowed --name "OgulTarimMuhasebe" --icon "%~dp0logo.ico" ^
  --add-data "%~dp0logo.jpg;." --hidden-import excel_aktar --hidden-import ekstre --hidden-import bulut --hidden-import db_tarama ^
  --distpath ..\dist --workpath ..\build\pyinstaller --specpath ..\build muhasebe.py
echo Hazir: ..\dist\OgulTarimMuhasebe.exe
