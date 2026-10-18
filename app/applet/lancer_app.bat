@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title Sign Language AI Studio - Lanceur Windows

REM ================================================================
REM        SIGN LANGUAGE AI STUDIO - LANCEUR WINDOWS PRO
REM ================================================================
cls
echo ================================================================
echo        SIGN LANGUAGE AI STUDIO - LANCEUR AUTOMATIQUE
echo ================================================================
echo.

REM 1. Recherche intelligente de Python compatible (Python 3.10 ou 3.11 recommande pour l'IA)
set "PYTHON_EXE="

REM Test 1 : Lanceur py officiel de Windows avec version 3.10 ou 3.11 (ideal)
py -3.10 --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_EXE=py -3.10"
    goto PYTHON_FOUND
)

py -3.11 --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_EXE=py -3.11"
    goto PYTHON_FOUND
)

REM Test 2 : Dossiers standards d'installation de Python 3.10 et 3.11
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python310;%LOCALAPPDATA%\Programs\Python\Python310\Scripts;!PATH!"
    goto PYTHON_FOUND
)

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;!PATH!"
    goto PYTHON_FOUND
)

if exist "C:\Python310\python.exe" (
    set "PYTHON_EXE=C:\Python310\python.exe"
    set "PATH=C:\Python310;C:\Python310\Scripts;!PATH!"
    goto PYTHON_FOUND
)

if exist "C:\Python311\python.exe" (
    set "PYTHON_EXE=C:\Python311\python.exe"
    set "PATH=C:\Python311;C:\Python311\Scripts;!PATH!"
    goto PYTHON_FOUND
)

if exist "%ProgramFiles%\Python310\python.exe" (
    set "PYTHON_EXE=%ProgramFiles%\Python310\python.exe"
    set "PATH=%ProgramFiles%\Python310;%ProgramFiles%\Python310\Scripts;!PATH!"
    goto PYTHON_FOUND
)

if exist "%ProgramFiles%\Python311\python.exe" (
    set "PYTHON_EXE=%ProgramFiles%\Python311\python.exe"
    set "PATH=%ProgramFiles%\Python311;%ProgramFiles%\Python311\Scripts;!PATH!"
    goto PYTHON_FOUND
)

if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python39;%LOCALAPPDATA%\Programs\Python\Python39\Scripts;!PATH!"
    goto PYTHON_FOUND
)

REM Test 3 : Commande python dans le PATH (on verifie que ce n'est PAS Python 3.13+)
python --version >nul 2>&1
if !errorlevel! equ 0 (
    python -c "import sys; exit(1 if sys.version_info >= (3, 13) else 0)" >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_EXE=python"
        goto PYTHON_FOUND
    ) else (
        REM Python est 3.13 ou plus recent -> incompatible avec TensorFlow/MediaPipe
        goto PYTHON_TOO_NEW
    )
)

REM Test 4 : py standard
py --version >nul 2>&1
if !errorlevel! equ 0 (
    py -c "import sys; exit(1 if sys.version_info >= (3, 13) else 0)" >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_EXE=py"
        goto PYTHON_FOUND
    ) else (
        goto PYTHON_TOO_NEW
    )
)

REM -----------------------------------------------------------------
REM Si Python n'est pas trouve du tout
REM -----------------------------------------------------------------
cls
echo ================================================================
echo   [ERREUR] Python n'est pas detecte sur votre ordinateur !
echo ================================================================
echo.
echo Deux solutions simples et rapides pour installer la bonne version :
echo.
echo ----------------------------------------------------------------
echo OPTION 1 (Automatique en 1 seule commande) :
echo   Ouvrez un terminal CMD et tapez :
echo   winget install Python.Python.3.10
echo.
echo OPTION 2 (Installation manuelle via l'installateur officiel) :
echo   1. Telechargez l'installateur direct Python 3.10 :
echo      https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe
echo   2. IMPORTANT : Au debut de l'installation, cochez imperativement :
echo      [x] Add Python to PATH (tout en bas de la premiere fenetre)
echo   3. Cliquez sur "Install Now"
echo ----------------------------------------------------------------
echo.
echo Une fois installe, fermez cette fenetre et relancez lancer_app.bat !
echo.
pause
exit /b 1

REM -----------------------------------------------------------------
REM Si l'utilisateur a Python 3.13+ (incompatible avec l'IA)
REM -----------------------------------------------------------------
:PYTHON_TOO_NEW
cls
echo ================================================================
echo   [INCOMPATIBILITE DETECTEE] Python 3.13 n'est pas compatible IA
echo ================================================================
echo.
echo Vous avez actuellement Python 3.13 installe sur votre PC.
echo.
echo Les bibliotheques d'intelligence artificielle et de vision :
echo   - TensorFlow
echo   - MediaPipe (Google)
echo   - OpenCV
echo NE SONT PAS ENCORE COMPATIBLES avec Python 3.13 (erreur de build).
echo.
echo La version standard mondiale pour l'IA est Python 3.10 (ou 3.11).
echo.
echo ----------------------------------------------------------------
echo COMMENT REGLER CELA EN 1 MINUTE :
echo.
echo 1. Installez Python 3.10 via cette commande dans un terminal CMD :
echo      winget install Python.Python.3.10
echo.
echo    OU telechargez directement l'installateur officiel 3.10 :
echo      https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe
echo    (en cochant bien la case [x] Add Python to PATH)
echo.
echo 2. Relancez ensuite ce script lancer_app.bat !
echo    Il detectera automatiquement Python 3.10 sans conflit.
echo ----------------------------------------------------------------
echo.
pause
exit /b 1

:PYTHON_FOUND
echo [OK] Python compatible detecte !
echo Executable : !PYTHON_EXE!
!PYTHON_EXE! --version
echo.

REM Verifier si un ancien venv existe avec Python 3.13 et le regenerer si besoin
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe -c "import sys; exit(1 if sys.version_info >= (3, 13) else 0)" >nul 2>&1
    if !errorlevel! neq 0 (
        echo [INFO] Ancien environnement venv base sur Python 3.13 detecte.
        echo [INFO] Nettoyage et recreation avec Python compatible...
        rmdir /s /q venv >nul 2>&1
    )
)

REM 2. Verification / Creation de l'environnement virtuel venv
if not exist "venv\Scripts\activate.bat" (
    echo [INFO] Creation de l'environnement virtuel Python (venv)...
    !PYTHON_EXE! -m venv venv
    if !errorlevel! neq 0 (
        echo [ERREUR] Impossible de creer le venv.
        pause
        exit /b 1
    )
    echo [OK] Environnement venv cree avec succes !
    echo.
    echo [INFO] Installation des dependances du projet (requirements.txt)...
    echo Cela peut prendre 1 a 2 minutes la premiere fois...
    echo.
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    if !errorlevel! neq 0 (
        echo.
        echo [INFO] Ajustement automatique des bibliotheques...
        pip install mediapipe opencv-python "numpy<2" tensorflow scikit-learn pyttsx3 pywin32
    )
    echo.
    echo [OK] Toutes les dependances sont installees !
    timeout /t 2 >nul
) else (
    call venv\Scripts\activate.bat
)

:MENU
cls
echo ================================================================
echo        SIGN LANGUAGE AI STUDIO - MENU PRINCIPAL
echo ================================================================
echo.
echo   [1] Lancer la reconnaissance en direct (realtime.py) [RECOMMANDE]
echo   [2] Re-entrainer le modele d'IA (train.py)
echo   [3] Collecter de nouveaux gestes / signes (collect.py)
echo   [4] Gerer / Supprimer des donnees (delete.py)
echo   [5] Verifier / Reinstaller les dependances (pip install)
echo   [6] Quitter
echo.
echo ================================================================
set /p CHOIX="Choisissez une option (1-6) puis appuyez sur Entree : "

if "%CHOIX%"=="1" goto RUN_REALTIME
if "%CHOIX%"=="2" goto RUN_TRAIN
if "%CHOIX%"=="3" goto RUN_COLLECT
if "%CHOIX%"=="4" goto RUN_DELETE
if "%CHOIX%"=="5" goto RUN_REINSTALL
if "%CHOIX%"=="6" exit /b 0

echo Choix invalide. Veuillez reessayer.
timeout /t 2 >nul
goto MENU

:RUN_REALTIME
cls
echo ================================================================
echo   LANCEMENT DU STUDIO PRO DE RECONNAISSANCE EN DIRECT
echo ================================================================
echo.
echo [CONSEIL] Assurez-vous que la webcam n'est pas utilisee par
echo           le navigateur web (fermez la camera dans le navigateur).
echo.
echo [RACCOURCIS CLAVIER DANS LA FENETRE CAMERA] :
echo   - Appuyez sur [C] pour effacer la phrase courante
echo   - Appuyez sur [S] pour repeter la phrase au haut-parleur
echo   - Appuyez sur [M] pour activer/couper la synthese vocale
echo   - Appuyez sur [Q] pour quitter la camera
echo.
echo Demarrage en cours...
python realtime.py
echo.
echo Application fermee.
pause
goto MENU

:RUN_TRAIN
cls
echo ================================================================
echo   ENTRAINEMENT DU MODELE DE RECONNAISSANCE DES SIGNES
echo ================================================================
echo.
python train.py
echo.
echo Entrainement termine !
pause
goto MENU

:RUN_COLLECT
cls
echo ================================================================
echo   COLLECTE DE DONNEES (NOUVEAUX SIGNES)
echo ================================================================
echo.
python collect.py
echo.
echo Collecte terminee !
pause
goto MENU

:RUN_DELETE
cls
echo ================================================================
echo   GESTION ET SUPPRESSION DE DONNEES
echo ================================================================
echo.
python delete.py
echo.
pause
goto MENU

:RUN_REINSTALL
cls
echo ================================================================
echo   REINSTALLATION DES DEPENDANCES
echo ================================================================
echo.
python -m pip install --upgrade pip
pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo.
    echo [INFO] Ajustement automatique pour votre version de Python...
    pip install mediapipe opencv-python "numpy<2" tensorflow scikit-learn pyttsx3 pywin32
)
echo.
echo Verification terminee !
pause
goto MENU
