# Zarsaman Analyzer launcher (English only). The API key is read via hidden input,
# lives only in this process environment, and is removed afterwards.
Set-Location -Path $PSScriptRoot
$ErrorActionPreference = "Stop"

$py = $null
foreach ($c in @("python", "py")) {
    if (Get-Command $c -ErrorAction SilentlyContinue) { $py = $c; break }
}
if (-not $py) { Write-Host "ERROR: Python 3.11+ was not found in PATH." -ForegroundColor Red; exit 1 }

& $py -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Python 3.11 or newer is required." -ForegroundColor Red; exit 1 }

if (-not $env:ZAR_STATE_ENDPOINT) { $env:ZAR_STATE_ENDPOINT = "https://zarsaman.ir/api/state.json.php" }

Write-Host "Zarsaman Analyzer"
Write-Host "Enter the state API key (input is hidden). Leave empty for offline/local-cache mode."
$secure = Read-Host -AsSecureString "API key"
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
$plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

$extra = @()
if ([string]::IsNullOrEmpty($plain)) {
    Write-Host "WARNING: no key entered. Running OFFLINE: state is NOT live; cached values are never treated as fresh." -ForegroundColor Yellow
    $extra += "--offline"
} else {
    $env:ZAR_STATE_API_KEY = $plain
}
$plain = $null

try {
    & $py -m zarsaman_analyzer doctor @extra
    & $py -m zarsaman_analyzer run --stage http @extra
} finally {
    Remove-Item Env:ZAR_STATE_API_KEY -ErrorAction SilentlyContinue
}
Write-Host "Finished. Reports are in zarsaman_workspace\output\source_analysis"
