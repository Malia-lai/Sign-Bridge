# Sign Language AI Studio - Lanceur PowerShell Windows
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "       SIGN LANGUAGE AI STUDIO - LANCEUR WINDOWS PRO" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Detection de Python (priorite a Python 3.10 ou 3.11 pour l'IA)
$pythonCmd = $null
$possiblePaths = @(
    "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "C:\Python310\python.exe",
    "C:\Python311\python.exe",
    "C:\Program Files\Python310\python.exe",
    "C:\Program Files\Python311\python.exe",
    "python"
)

foreach ($path in $possiblePaths) {
    try {
        $p = Start-Process -FilePath $path -ArgumentList "-c", "import sys; exit(0 if sys.version_info < (3, 13) and sys.version_info >= (3, 9) else 1)" -NoNewWindow -PassThru -Wait -ErrorAction SilentlyContinue
        if ($p.ExitCode -eq 0) {
            $pythonCmd = $path
            break
        }
    } catch {}
}

if (-not $pythonCmd) {
    Write-Host "[ERREUR] Version de Python compatible (3.10 ou 3.11) non detectee !" -ForegroundColor Red
    Write-Host "Si vous avez Python 3.13, les bibliotheques IA (MediaPipe/TensorFlow/OpenCV) ne fonctionnent pas encore dessus." -ForegroundColor Yellow
    Write-Host "Installez Python 3.10 en tapant dans un terminal :" -ForegroundColor Cyan
    Write-Host "   winget install Python.Python.3.10" -ForegroundColor Green
    Write-Host ""
    Write-Host "Ou telechargez l'installateur officiel :" -ForegroundColor Yellow
    Write-Host "   https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe" -ForegroundColor Cyan
    Write-Host ""
    Read-Host "Appuyez sur Entree pour quitter..."
    exit
}

Write-Host "[OK] Python detecte : $pythonCmd" -ForegroundColor Green
& $pythonCmd --version
Write-Host ""

# 2. Gestion de l'environnement virtuel venv
if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
    Write-Host "[INFO] Creation de l'environnement virtuel (venv)..." -ForegroundColor Yellow
    & $pythonCmd -m venv venv
    Write-Host "[INFO] Installation des dependances (requirements.txt)..." -ForegroundColor Yellow
    & .\venv\Scripts\python.exe -m pip install --upgrade pip
    try {
        & .\venv\Scripts\pip.exe install -r requirements.txt
    } catch {
        Write-Host "[INFO] Ajustement automatique pour votre version de Python..." -ForegroundColor Yellow
        & .\venv\Scripts\pip.exe install mediapipe opencv-python "numpy<2" tensorflow scikit-learn pyttsx3 pywin32
    }
    Write-Host "[OK] Dependances installees !" -ForegroundColor Green
}

$venvPython = ".\venv\Scripts\python.exe"

# 3. Menu Interactif
function Show-Menu {
    Clear-Host
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "       SIGN LANGUAGE AI STUDIO - MENU WINDOWS" -ForegroundColor Green
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  [1] Lancer la Reconnaissance en Direct (realtime.py)" -ForegroundColor White
    Write-Host "  [2] Entrainer le Modele IA LSTM (train.py)" -ForegroundColor White
    Write-Host "  [3] Enregistrer de Nouveaux Gestes (collect.py)" -ForegroundColor White
    Write-Host "  [4] Diagnostiquer les Donnees (samplenum.py)" -ForegroundColor White
    Write-Host "  [5] Supprimer un Geste (delete.py)" -ForegroundColor White
    Write-Host "  [6] Lancer l'Application Web Studio React (npm run dev)" -ForegroundColor White
    Write-Host "  [7] Reinstaller les Dependances (pip install)" -ForegroundColor White
    Write-Host "  [Q] Quitter" -ForegroundColor Gray
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
}

while ($true) {
    Show-Menu
    $choice = Read-Host "Votre choix (1-7 ou Q)"

    switch ($choice.ToUpper()) {
        "1" {
            Clear-Host
            Write-Host "[CONSEIL WEBCAM] Desactivez la webcam du navigateur si elle est active !" -ForegroundColor Yellow
            Write-Host "Lancement de realtime.py..." -ForegroundColor Green
            & $venvPython realtime.py
            Read-Host "Appuyez sur Entree pour revenir au menu..."
        }
        "2" {
            Clear-Host
            Write-Host "Entrainement du modele LSTM..." -ForegroundColor Green
            & $venvPython train.py
            Read-Host "Appuyez sur Entree pour revenir au menu..."
        }
        "3" {
            Clear-Host
            Write-Host "Collecte de gestes..." -ForegroundColor Green
            & $venvPython collect.py
            Read-Host "Appuyez sur Entree pour revenir au menu..."
        }
        "4" {
            Clear-Host
            & $venvPython samplenum.py
            Read-Host "Appuyez sur Entree pour revenir au menu..."
        }
        "5" {
            Clear-Host
            & $venvPython delete.py
            Read-Host "Appuyez sur Entree pour revenir au menu..."
        }
        "6" {
            Clear-Host
            npm run dev
            Read-Host "Appuyez sur Entree pour revenir au menu..."
        }
        "7" {
            Clear-Host
            & $venvPython -m pip install --upgrade pip
            & .\venv\Scripts\pip.exe install -r requirements.txt
            Read-Host "Appuyez sur Entree pour revenir au menu..."
        }
        "Q" {
            Write-Host "Au revoir !" -ForegroundColor Green
            exit
        }
        default {
            Write-Host "Choix invalide." -ForegroundColor Red
            Start-Sleep -Seconds 1
        }
    }
}
