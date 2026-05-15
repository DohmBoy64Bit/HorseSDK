@echo off
setlocal
cd /d "%~dp0"

if not exist "build" mkdir build

g++ -shared -o build\steam_api64.dll src\steam_api64.cpp exports.def ^
    -std=c++17 -O2 -s ^
    -static-libgcc -static-libstdc++ ^
    -Wl,--enable-stdcall-fixup

if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

echo Built: %cd%\build\steam_api64.dll
copy /Y build\steam_api64.dll "..\Game\steam_api64.dll" >nul
copy /Y steam_appid.txt "..\Game\steam_appid.txt" >nul 2>nul
echo Deployed to ..\Game\
