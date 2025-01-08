
@echo off
:: Verificar si el script tiene permisos de administrador
openfiles >nul 2>nul
if %errorlevel% neq 0 (
    echo Este script debe ejecutarse con permisos de administrador.
    echo Por favor, reinicie este archivo como administrador.
    pause
    exit /b
)

:: Título del script
echo Instalando dependencias para MonkeBot...

:: Verificar instalación de Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python no está instalado. Descargando ahora...

    :: Descargar Python
    mkdir python_temp
    cd python_temp
    curl -LO https://www.python.org/ftp/python/3.11.5/python-3.11.5-amd64.exe

    :: Instalar Python de forma silenciosa
    python-3.11.5-amd64.exe /quiet InstallAllUsers=1 PrependPath=1

    :: Eliminar instalador temporal
    cd ..
    rmdir /s /q python_temp
    echo Python instalado y agregado al PATH.
) else (
    echo Python detectado en el sistema.
)

:: Crear un entorno virtual (opcional pero recomendado)
python -m venv venv
call venv\Scripts\activate

:: Instalar dependencias principales
echo Instalando discord.py...
pip install discord.py

echo Instalando yt-dlp...
pip install yt-dlp

echo Instalando python-dotenv...
pip install python-dotenv

:: Verificar instalación de FFmpeg
where ffmpeg >nul 2>nul
if %errorlevel% neq 0 (
    echo FFmpeg no está instalado. Descargando ahora...

    :: Crear una carpeta temporal
    mkdir ffmpeg_temp
    cd ffmpeg_temp

    :: Descargar FFmpeg
    curl -LO https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip

    :: Extraer FFmpeg
    powershell -Command "Expand-Archive -Path ffmpeg-release-essentials.zip -DestinationPath ."

    :: Mover FFmpeg a una ubicación permanente
    move ffmpeg-* ..\ffmpeg
    cd ..
    rmdir /s /q ffmpeg_temp

    :: Agregar FFmpeg al PATH
    setx /M PATH "%PATH%;%cd%\ffmpeg\bin"

    echo FFmpeg instalado y agregado al PATH.
) else (
    echo FFmpeg detectado en el sistema.
)

:: Finalización
echo Todas las dependencias y herramientas han sido instaladas correctamente.
pause
