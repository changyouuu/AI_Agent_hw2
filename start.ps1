$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    & py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        throw 'Python 3.12 is required. Run: py install 3.12'
    }
}

# Missing packages must produce only an exit code. Windows PowerShell can
# treat native stderr as a terminating error before this branch runs.
& $python -c 'import importlib.util, sys; sys.exit(0 if all(importlib.util.find_spec(name) for name in sys.argv[1:]) else 1)' streamlit pdfplumber
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install --only-binary=:all: -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        throw 'Dependency installation failed. Check the pip output above.'
    }
}

& $python -m streamlit run app.py --server.address=127.0.0.1 --server.maxUploadSize=30 --browser.gatherUsageStats=false
