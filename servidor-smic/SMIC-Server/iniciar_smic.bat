@echo off
title SMIC - Iniciando...

REM ================================
REM Crear carpeta de clips si no existe
REM ================================
if not exist "%USERPROFILE%\Desktop\SMIC_clips" (
    mkdir "%USERPROFILE%\Desktop\SMIC_clips"
)

REM ================================
REM Descargar clips nuevos de la RPi
REM ================================
title SMIC - Descargando clips...
scp -r proyecto-smic@SMIC.local:/home/proyecto-smic/SMIC/eventos/* "%USERPROFILE%\Desktop\SMIC_clips\" 2>nul

REM ================================
REM Levantar Flask en segundo plano
REM ================================
title SMIC - Levantando servidor...
cd /d "C:\Users\fnmov\OneDrive\Documentos\GitHub\SMIC\servidor-smic\SMIC-Server"
call venv\Scripts\activate

start /B python app.py > "%TEMP%\smic_flask.log" 2>&1

REM Esperar que Flask levante
timeout /t 3 /nobreak > nul

REM ================================
REM Abrir el navegador
REM ================================
start http://127.0.0.1:5000/panel

exit
