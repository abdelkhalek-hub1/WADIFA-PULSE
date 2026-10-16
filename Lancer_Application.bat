@echo off
title WadifaBot Maroc - Veille Emploi Public
color 0A
chcp 65001 >nul

echo ================================================================
echo    Lancement de l'Interface Web WadifaBot Maroc
echo ================================================================
echo.

cd /d "%~dp0"

echo [1/2] Verification des dependances...
python -m pip install -r requirements.txt >nul 2>&1

echo [2/2] Ouverture du tableau de bord dans votre navigateur...
start "" http://127.0.0.1:5000

echo.
echo Application en cours d'execution sur http://127.0.0.1:5000
echo Laissez cette fenetre ouverte pendant l'utilisation.
echo.
python app.py

pause
