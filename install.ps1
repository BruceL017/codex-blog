$ErrorActionPreference = "Stop"
$RepoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Candidates = @()

if ($env:CODEX_BLOG_PYTHON) {
    $Candidates += @{ Exe = $env:CODEX_BLOG_PYTHON; Args = @() }
}

$Candidates += @(
    @{ Exe = "py"; Args = @("-3") },
    @{ Exe = "python3.14"; Args = @() },
    @{ Exe = "python3.13"; Args = @() },
    @{ Exe = "python3.12"; Args = @() },
    @{ Exe = "python3.11"; Args = @() },
    @{ Exe = "python3.10"; Args = @() },
    @{ Exe = "python3"; Args = @() },
    @{ Exe = "python"; Args = @() }
)

foreach ($Candidate in $Candidates) {
    if (Get-Command $Candidate.Exe -ErrorAction SilentlyContinue) {
        $Probe = & $Candidate.Exe @($Candidate.Args) (Join-Path $RepoDir "scripts/python_probe.py") 2>&1
        $StoreStub = $Probe -match "Microsoft Store|WindowsApps|App execution alias|was not found"
        if ($LASTEXITCODE -eq 0 -and -not $StoreStub) {
            & $Candidate.Exe @($Candidate.Args) (Join-Path $RepoDir "scripts/install.py") install @args
            exit $LASTEXITCODE
        }
    }
}

throw "Codex Blog requires Python 3.10 or newer."
