@echo off
REM Export gameplay decompiles via Ghidra analyzeHeadless.
REM Set GHIDRA_INSTALL to your Ghidra folder (contains support\analyzeHeadless.bat).

setlocal
if "%GHIDRA_INSTALL%"=="" set "GHIDRA_INSTALL=C:\Program Files\Ghidra\ghidra_11.3_PUBLIC"
set "REPO=%~dp0..\.."
set "PROJECT=%REPO%\ghidra_project"
set "OUT=%REPO%\RE_Tools\docs\ghidra_exports"

if not exist "%GHIDRA_INSTALL%\support\analyzeHeadless.bat" (
  echo GHIDRA_INSTALL not found: %GHIDRA_INSTALL%
  echo Set GHIDRA_INSTALL to Ghidra install path.
  exit /b 1
)

if not exist "%REPO%\Game\Horsey.exe" (
  echo Missing %REPO%\Game\Horsey.exe
  exit /b 1
)

mkdir "%OUT%" 2>nul
mkdir "%PROJECT%" 2>nul

echo Project: %PROJECT%
echo Output:  %OUT%

call "%GHIDRA_INSTALL%\support\analyzeHeadless.bat" ^
  "%PROJECT%" HorseSDK ^
  -import "%REPO%\Game\Horsey.exe" ^
  -overwrite ^
  -scriptPath "%REPO%\RE_Tools\ghidra_scripts" ^
  -postScript ExportGameplayDecompile.java "%OUT%"

exit /b %ERRORLEVEL%
