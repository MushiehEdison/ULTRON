# Build ULTRON.exe on Windows with PyInstaller.
# Run from the repo root:  powershell -File build/windows/build.ps1
$ErrorActionPreference = "Stop"

pip install -r requirements.txt

$iconArgs = @()
if (Test-Path "build/windows/icon.ico") {
    $iconArgs = @("--icon", "build/windows/icon.ico")
}

pyinstaller `
  --name ULTRON `
  --onefile `
  --windowed `
  @iconArgs `
  --add-data "app/gui/assets;app/gui/assets" `
  --hidden-import faster_whisper `
  --hidden-import qtawesome `
  --collect-data qtawesome `
  --distpath build/windows/dist `
  --workpath build/windows/work `
  --specpath build/windows `
  app/main.py

Write-Host "Done: build/windows/dist/ULTRON.exe"
