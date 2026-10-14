# Instalador del motor de IA local (Stable Fast 3D) para Prop Forge. Solo ASCII a proposito (PowerShell 5.1).
# Uso: doble clic en instalar_ia.bat. Tarda 15-30 minutos y descarga unos 6 GB. Se puede repetir sin problema.
param([switch]$ConTripoSR)
$ErrorActionPreference = "Stop"
$Base = Join-Path $env:LOCALAPPDATA "PiratePropForge"
$Venv = Join-Path $Base "venv"
$Py = Join-Path $Venv "Scripts\python.exe"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
New-Item -ItemType Directory -Force -Path $Base | Out-Null
Start-Transcript -Path (Join-Path $Base "install.log") -Force | Out-Null

Write-Host "Instalador de Prop Forge, version 0.2.6 (carpeta: $Here)" -ForegroundColor Green
function Paso($n, $texto) { Write-Host ""; Write-Host ("[{0}/8] {1}" -f $n, $texto) -ForegroundColor Cyan }
function Falla($texto) { Write-Host ""; Write-Host ("ERROR: " + $texto) -ForegroundColor Red; Write-Host "Registro: $Base\install.log"; Stop-Transcript | Out-Null; Read-Host "Pulsa Enter para cerrar"; exit 1 }
function Ejecuta($exe, $argumentos) {
    & $exe @argumentos
    if ($LASTEXITCODE -ne 0) { Falla ("fallo el comando: " + $exe + " " + ($argumentos -join " ")) }
}

Paso 1 "Comprobando la tarjeta NVIDIA"
if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) { Falla "No encuentro nvidia-smi. Instala el driver de NVIDIA (geforce.com/drivers) y repite." }
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader

Paso 2 "Buscando Python 3.11"
function Busca-Python311 {
    $cands = @()
    try { $p = & py -3.11 -c "import sys;print(sys.executable)" 2>$null; if ($LASTEXITCODE -eq 0 -and $p) { $cands += $p } } catch {}
    $cands += (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe")
    $cands += "C:\Program Files\Python311\python.exe"
    foreach ($c in $cands) { if ($c -and (Test-Path $c)) { return $c } }
    return $null
}
$Sys = Busca-Python311
if (-not $Sys) {
    Write-Host "No esta Python 3.11. Lo instalo con winget (si te pide permiso, acepta)..."
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { Falla "No tengo winget. Instala Python 3.11 desde python.org (marca 'Add to PATH') y repite." }
    winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
    $Sys = Busca-Python311
    if (-not $Sys) { Falla "Instale Python 3.11 pero no lo encuentro. Cierra esta ventana y ejecuta de nuevo instalar_ia.bat." }
}
Write-Host "Python: $Sys"

Paso 3 "Creando el entorno aislado (no toca tu Python ni el de Blender)"
if (-not (Test-Path $Py)) { Ejecuta $Sys @("-m", "venv", $Venv) }
Ejecuta $Py @("-m", "pip", "install", "--upgrade", "pip", "wheel", "setuptools==69.5.1")

Paso 4 "Instalando PyTorch 2.6 con CUDA 12.4 (compatible con GTX 1080 Ti)"
Ejecuta $Py @("-m", "pip", "install", "torch==2.6.0", "torchvision==0.21.0", "--index-url", "https://download.pytorch.org/whl/cu124")

Paso 5 "Descargando Stable Fast 3D"
$Sf3dRoot = Join-Path $Base "sf3d"
$Zip = Join-Path $Base "sf3d.zip"
if (-not (Test-Path (Join-Path $Sf3dRoot "stable-fast-3d-main\sf3d"))) {
    Invoke-WebRequest -Uri "https://github.com/Stability-AI/stable-fast-3d/archive/refs/heads/main.zip" -OutFile $Zip
    if (Test-Path $Sf3dRoot) { Remove-Item -Recurse -Force $Sf3dRoot }
    Expand-Archive -Path $Zip -DestinationPath $Sf3dRoot -Force
    Remove-Item $Zip
}
$Sf3d = Join-Path $Sf3dRoot "stable-fast-3d-main"
if (-not (Test-Path (Join-Path $Sf3d "sf3d"))) { Falla "La descarga de SF3D no trae la carpeta sf3d." }

Paso 6 "Instalando dependencias (rembg en CPU para dejar la GPU libre)"
$deps = @("einops==0.7.0", "jaxtyping==0.2.31", "omegaconf==2.3.0", "transformers==4.42.3", "open_clip_torch==2.24.0",
          "trimesh==4.4.1", "numpy==1.26.4", "huggingface-hub==0.23.4", "rembg==2.0.57", "onnxruntime", "pynanoinstantmeshes==0.0.3",
          "gpytoolbox==0.2.0", "pillow", "ninja")
Ejecuta $Py (@("-m", "pip", "install") + $deps)
# Compilador de C++ para texture_baker y uv_unwrapper
$vsw = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
$tieneVC = $false
if (Test-Path $vsw) { $r = & $vsw -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath; if ($r) { $tieneVC = $true } }
if (-not $tieneVC) {
    Write-Host "Falta el compilador de C++ (Build Tools de Visual Studio, ~5 GB). SF3D lo necesita para dos piezas pequenas." -ForegroundColor Yellow
    $resp = Read-Host "Instalarlo ahora con winget? (s/n)"
    if ($resp -match "^[sSyY]") {
        winget install -e --id Microsoft.VisualStudio.2022.BuildTools --accept-package-agreements --accept-source-agreements --override "--quiet --wait --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
    } else { Falla "Sin Build Tools no se puede compilar texture_baker/uv_unwrapper. Instala 'Build Tools para Visual Studio' (carga de trabajo C++) y repite." }
}
# Sin aislamiento: el compilador necesita ver el torch ya instalado. Version CPU de texture_baker (no exige CUDA Toolkit);
# el plugin ejecuta ese paso en CPU, lo que cuesta solo unos segundos por malla.
$env:USE_CUDA = "0"; $env:USE_NATIVE_ARCH = "0"
Ejecuta $Py @("-m", "pip", "install", "--no-build-isolation", (Join-Path $Sf3d "texture_baker"))
Ejecuta $Py @("-m", "pip", "install", "--no-build-isolation", (Join-Path $Sf3d "uv_unwrapper"))
# hace visible el paquete sf3d sin instalarlo
$site = & $Py -c "import sysconfig;print(sysconfig.get_paths()['purelib'])"
Set-Content -Path (Join-Path $site "pf_sf3d.pth") -Value $Sf3d -Encoding ASCII

if ($ConTripoSR) {
    Write-Host "TripoSR (experimental, opcional)..." -ForegroundColor Yellow
    try {
        $tz = Join-Path $Base "triposr.zip"; $tr = Join-Path $Base "triposr"
        Invoke-WebRequest -Uri "https://github.com/VAST-AI-Research/TripoSR/archive/refs/heads/main.zip" -OutFile $tz
        if (Test-Path $tr) { Remove-Item -Recurse -Force $tr }
        Expand-Archive -Path $tz -DestinationPath $tr -Force; Remove-Item $tz
        & $Py -m pip install imageio xatlas moderngl git+https://github.com/tatsy/torchmcubes.git
        Set-Content -Path (Join-Path $site "pf_triposr.pth") -Value (Join-Path $tr "TripoSR-main") -Encoding ASCII
    } catch { Write-Host "TripoSR no se pudo instalar (no pasa nada, SF3D funciona sin el): $_" -ForegroundColor Yellow }
}

Paso 7 "Acceso al modelo (Hugging Face)"
Write-Host "SF3D es gratuito pero pide aceptar su licencia con tu cuenta (una sola vez):"
Write-Host "  1) Crea/entra en tu cuenta en https://huggingface.co"
Write-Host "  2) Abre https://huggingface.co/stabilityai/stable-fast-3d y pulsa 'Agree and access repository'"
Write-Host "  3) Crea un token de lectura en https://huggingface.co/settings/tokens (tipo Read)"
Start-Process "https://huggingface.co/stabilityai/stable-fast-3d"
$tok = Read-Host "Pega aqui el token (hf_...) y pulsa Enter (o Enter vacio para hacerlo despues)" -AsSecureString
$plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($tok))
if ($plain) { Ejecuta $Py @("-c", "from huggingface_hub import login; login(token='$plain', add_to_git_credential=False)") }

Paso 8 "Guardando configuracion y comprobando"
$cfg = @{ python = $Py; sf3d = $Sf3d; installed = (Get-Date -Format "yyyy-MM-dd HH:mm") } | ConvertTo-Json
Set-Content -Path (Join-Path $Base "worker_env.json") -Value $cfg -Encoding ASCII
Write-Host ""
& $Py (Join-Path $Here "doctor.py")
Write-Host ""
Write-Host "Listo. Abre Blender > N > Prop Forge > IA local > Iniciar motor de IA." -ForegroundColor Green
Stop-Transcript | Out-Null
Read-Host "Pulsa Enter para cerrar"
