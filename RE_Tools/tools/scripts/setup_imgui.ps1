# Clone Dear ImGui into ThirdParty/imgui for optional ModLoader build.
$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Dest = Join-Path $Root "ThirdParty\imgui"
if (Test-Path (Join-Path $Dest "imgui.h")) {
    Write-Host "OK: $Dest already exists"
    exit 0
}
New-Item -ItemType Directory -Force -Path (Split-Path $Dest) | Out-Null
git clone --depth 1 --branch v1.91.8 https://github.com/ocornut/imgui.git $Dest
Write-Host "Cloned imgui to $Dest"
Write-Host "Next: cmake -S ModLoader -B build/modloader -DHORSE_ENABLE_IMGUI=ON"
