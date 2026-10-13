@echo off
chcp 65001 >nul
echo Instalando el motor de IA local de Prop Forge...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_ia.ps1" %*
if errorlevel 1 pause
