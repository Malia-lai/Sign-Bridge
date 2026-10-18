@echo off
setlocal enabledelayedexpansion
title Sign Language AI Studio - Lanceur Windows

REM ================================================================
REM        SIGN LANGUAGE AI STUDIO - LANCEUR WINDOWS PRO
REM ================================================================
echo.
echo ================================================================
echo        SIGN LANGUAGE AI STUDIO - LANCEUR AUTOMATIQUE
echo ================================================================
echo.

REM 1. Recherche intelligente de Python
set "PYTHON_EXE="

REM Test 1 : Commande python standard
where python >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_EXE=python"
    goto PYTHON_FOUND
)

REM Test 2 : Commande py (lanceur officiel Windows)
where py >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_EXE=py"
    goto PYTHON_FOUND
)

REM Test 3 : Chemins d installation standards Windows
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python310;%LOCALAPPDATA%\Programs\Python\Python310\Scripts;!PATH!"
    goto PYTHON_FOUND
)
if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python39;%LOCALAPPDATA%\Programs\Python\Python39\Scripts;!PATH!"
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
if exist "C:\Python39\python.exe" (
    set "PYTHON_EXE=C:\Python39\python.exe"
    set "PATH=C:\Python39;C:\Python39\Scripts;!PATH!"
    goto PYTHON_FOUND
)
if exist "%ProgramFiles%\Python310\python.exe" (
    set "PYTHON_EXE=%ProgramFiles%\Python310\python.exe"
    set "PATH=%ProgramFiles%\Python310;%ProgramFiles%\Python310\Scripts;!PATH!"
    goto PYTHON_FOUND
)
if exist "%ProgramFiles%\Python39\python.exe" (
    set "PYTHON_EXE=%ProgramFiles%\Python39\python.exe"
    set "PATH=%ProgramFiles%\Python39;%ProgramFiles%\Python39\Scripts;!PATH!"
    goto PYTHON_FOUND
)

REM Si Python n est pas trouve
cls
echo ================================================================
echo   [ERREUR] Python n est pas detecte sur votre ordinateur !
echo ================================================================
echo.
echo Pour faire fonctionner cette application sur Windows :
echo.
echo 1. Telechargez Python 3.10 ou 3.9 depuis le site officiel :
echo    https://www.python.org/downloads/
echo.
echo 2. TRES IMPORTANT : Lors de l installation, cochez impérativement
echo    la case tout en bas :
echo    [x] Add Python to PATH  (ou Add python.exe to PATH)
echo.
echo 3. Une fois installe, relancez simplement ce fichier lancer_app.bat !
echo ================================================================
echo.
pause
exit /b 1

:PYTHON_FOUND
echo [OK] Python detecte : !PYTHON_EXE!
!PYTHON_EXE! --version
echo.

REM 2. Gestion de l environnement virtuel (venv)
if not exist "venv\Scripts\activate.bat" (
    echo [INFO] Creation de l environnement virtuel Python (venv)...
    !PYTHON_EXE! -m venv venv
    if !errorlevel! neq 0 (
        echo [ERREUR] Echec lors de la creation du venv.
        pause
        exit /b 1
    )
    echo [OK] Environnement venv cree avec succes !
    echo.
    echo [INFO] Installation des dependances depuis requirements.txt...
    echo (Cette operation peut prendre 2 a 3 minutes la premiere fois)
    echo.
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    echo.
    echo [OK] Toutes les dependances sont pretes !
    echo.
) else (
    call venv\Scripts\activate.bat
)

:MENU
cls
echo ================================================================
echo        SIGN LANGUAGE AI STUDIO - MENU WINDOWS
echo ================================================================
echo.
echo   [1] Lancer la Reconnaissance en Direct Webcam (realtime.py)
echo   [2] Entrainer le Modele IA LSTM (train.py)
echo   [3] Enregistrer de Nouveaux Gestes (collect.py)
echo   [4] Verifier et Diagnostiquer le Dataset (samplenum.py)
echo   [5] Supprimer un Geste Invalide (delete.py)
echo   [6] Lancer l Interface Web Studio (npm run dev)
echo   [7] Reinstaller les Dependances (pip install)
echo   [Q] Quitter
echo.
echo ================================================================
set /p CHOIX="Votre choix (1-7 ou Q) puis Entree : "

if /i "%CHOIX%"=="1" goto RUN_REALTIME
if /i "%CHOIX%"=="2" goto RUN_TRAIN
if /i "%CHOIX%"=="3" goto RUN_COLLECT
if /i "%CHOIX%"=="4" goto RUN_SAMPLES
if /i "%CHOIX%"=="5" goto RUN_DELETE
if /i "%CHOIX%"=="6" goto RUN_WEB
if /i "%CHOIX%"=="7" goto RUN_REINSTALL
if /i "%CHOIX%"=="Q" goto QUIT
if /i "%CHOIX%"=="q" goto QUIT

echo Choix invalide.
timeout /t 2 >nul
goto MENU

:RUN_REALTIME
cls
echo ================================================================
echo   LANCEMENT DE LA RECONNAISSANCE EN DIRECT (realtime.py)
echo ================================================================
echo.
echo [CONSEIL WEBCAM] : Si votre camera est allumee dans votre navigateur
echo web (AI Studio), desactivez-la d abord pour liberer le flux Windows !
echo.
echo Raccourcis dans la fenetre video :
echo   [Q] Quitter  |  [C] Effacer phrase  |  [S] Rejouer voix  |  [M] Muet
echo ================================================================
echo.
python realtime.py
echo.
pause
goto MENU

:RUN_TRAIN
cls
echo ================================================================
echo   ENTRAINEMENT DU MODELE IA LSTM (train.py)
echo ================================================================
echo.
python train.py
echo.
pause
goto MENU

:RUN_COLLECT
cls
echo ================================================================
echo   COLLECTE DE GESTES (collect.py)
echo ================================================================
echo.
python collect.py
echo.
pause
goto MENU

:RUN_SAMPLES
cls
echo ================================================================
echo   DIAGNOSTIC DU JEU DE DONNEES (samplenum.py)
echo ================================================================
echo.
python samplenum.py
echo.
pause
goto MENU

:RUN_DELETE
cls
echo ================================================================
echo   SUPPRESSION D UN GESTE (delete.py)
echo ================================================================
echo.
python delete.py
echo.
pause
goto MENU

:RUN_WEB
cls
echo ================================================================
echo   LANCEMENT DE L INTERFACE WEB STUDIO (Vite / React)
echo ================================================================
echo.
npm run dev
pause
goto MENU

:RUN_REINSTALL
cls
echo ================================================================
echo   REINSTALLATION DES DEPENDANCES PYTHON
echo ================================================================
echo.
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
pause
goto MENU

:QUIT
echo Au revoir !
timeout /t 1 >nul
exit /b 0
