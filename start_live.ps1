# Starts a live Tavily-backed demo on port 8001. The key is held in this process only.
$ErrorActionPreference = 'Stop'
$promptedForKey = $false
if (-not $env:TAVILY_API_KEY) {
    $secureKey = Read-Host 'Enter your Tavily API key (input hidden)' -AsSecureString
    $keyPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    try {
        $env:TAVILY_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPtr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPtr)
    }
    $promptedForKey = $true
}
if (-not $env:TAVILY_API_KEY) { throw 'Tavily API key is required.' }
$env:SEARCH_PROVIDER = 'tavily'
Push-Location -LiteralPath $PSScriptRoot
try {
    Write-Host 'Live search will be available at http://127.0.0.1:8001'
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
} finally {
    Pop-Location
    if ($promptedForKey) { Remove-Item Env:TAVILY_API_KEY -ErrorAction SilentlyContinue }
}
