# Build ULTRON.exe on Windows with PyInstaller.
# Run from the repo root:  powershell -File build/windows/build.ps1
$ErrorActionPreference = "Stop"

pip install -r requirements.txt

pyinstaller `
  --name ULTRON `
  --onefile `
  --windowed `
  --icon build/windows/icon.ico `
  --add-data "app/gui/assets;app/gui/assets" `
  --hidden-import faster_whisper `
  --hidden-import qtawesome `
  --collect-data qtawesome `
  --distpath build/windows/dist `
  --workpath build/windows/work `
  --specpath build/windows `
  app/main.py

Write-Host "Done: build/windows/dist/ULTRON.exe"
