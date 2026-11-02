# Crea l'installer di Trip YTD per Windows: dist\Trip-YTD-Windows-Setup.exe
# Serve Inno Setup 6 (https://jrsoftware.org/isinfo.php). Uso: powershell -File src\windows\build.ps1
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-Location (Resolve-Path "$PSScriptRoot\..\..")

# Python "embeddable" per Windows 64 bit (python.org), con il suo SHA-256 ufficiale
$pyVersion = '3.14.10'
$pySha256 = '90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159'
$pyZip = "python-$pyVersion-embed-amd64.zip"

$version = [regex]::Match((Get-Content src\trip_ytd.py -Raw), '(?m)^VERSION = "([^"]+)"').Groups[1].Value
New-Item -ItemType Directory -Force build\cache, dist | Out-Null

$cached = "build\cache\$pyZip"
if (-not (Test-Path $cached)) {
    Invoke-WebRequest "https://www.python.org/ftp/python/$pyVersion/$pyZip" -OutFile "$cached.part"
    Move-Item "$cached.part" $cached
}
if ((Get-FileHash $cached -Algorithm SHA256).Hash -ne $pySha256) {
    Remove-Item $cached
    throw "Checksum di $pyZip non valido"
}

$stage = 'build\windows\Trip YTD'
if (Test-Path build\windows) { Remove-Item -Recurse -Force build\windows }
New-Item -ItemType Directory -Force "$stage\app", "$stage\runtime" | Out-Null
Expand-Archive $cached "$stage\runtime"
Copy-Item src\trip_ytd.py, src\ui.html, src\icon.svg, src\icon.ico "$stage\app"

$iscc = @(
    (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source,
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $iscc) { throw 'Inno Setup 6 non trovato: installalo da https://jrsoftware.org/isinfo.php' }

& $iscc /Qp "/DAppVersion=$version" src\windows\trip-ytd.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup ha restituito il codice $LASTEXITCODE" }
Write-Host "Creato: dist\Trip-YTD-Windows-Setup.exe (Trip YTD $version)"
