# Starts a live Tavily-backed demo on port 8001. The key is held in this process only.
$ErrorActionPreference = 'Stop'
$promptedForKey = $false
$loadedLocalKeys = @()
$localEnv = Join-Path $PSScriptRoot '.env.local'
if (Test-Path -LiteralPath $localEnv) {
    foreach ($line in Get-Content -LiteralPath $localEnv) {
        if ($line -match '^\s*(TAVILY_API_KEY|OPENAI_API_KEY|OPENAI_BASE_URL|OPENAI_MODEL)\s*=(.*)$') {
            $name = $matches[1]
            $value = $matches[2].Trim().Trim('"', "'")
            if ($value -and -not [Environment]::GetEnvironmentVariable($name, 'Process')) {
                [Environment]::SetEnvironmentVariable($name, $value, 'Process')
                $loadedLocalKeys += $name
            }
        }
    }
}
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
    foreach ($name in $loadedLocalKeys) {
        Remove-Item -LiteralPath ("Env:" + $name) -ErrorAction SilentlyContinue
    }
}
