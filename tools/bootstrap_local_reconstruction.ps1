param(
  [string]$Bundle = "site_gy_qyhx_gsh20260310",
  [string]$PythonPath = "",
  [string]$OutputRoot = "outputs/local_reconstruction_setup",
  [switch]$RunAssetValidation,
  [switch]$RunPointcloudSmoke,
  [string]$RunName = "local_setup_pointcloud_smoke",
  [string]$HandoffRootUri = "local-only"
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
  $scriptDir = Split-Path -Parent $MyInvocation.ScriptName
  return (Resolve-Path (Join-Path $scriptDir "..")).Path
}

function Test-PythonExecutable {
  param([string]$Candidate)

  if ([string]::IsNullOrWhiteSpace($Candidate)) {
    return $false
  }
  if (-not (Test-Path -LiteralPath $Candidate)) {
    return $false
  }
  try {
    $output = & $Candidate -c "import sys; print(sys.executable)" 2>$null
    return -not [string]::IsNullOrWhiteSpace(($output | Select-Object -First 1))
  } catch {
    return $false
  }
}

function Find-Python {
  param(
    [string]$RepoRoot,
    [string]$ExplicitPythonPath
  )

  $candidates = New-Object System.Collections.Generic.List[string]
  if (-not [string]::IsNullOrWhiteSpace($ExplicitPythonPath)) {
    $candidates.Add($ExplicitPythonPath)
  }

  $venvPython = Join-Path $RepoRoot ".venv/Scripts/python.exe"
  if (Test-Path -LiteralPath $venvPython) {
    $candidates.Add((Resolve-Path $venvPython).Path)
  }

  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($null -ne $python) {
    $candidates.Add($python.Source)
  }

  $codexPython = Join-Path $env:USERPROFILE ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"
  if (Test-Path -LiteralPath $codexPython) {
    $candidates.Add((Resolve-Path $codexPython).Path)
  }

  foreach ($candidate in $candidates) {
    if (Test-PythonExecutable -Candidate $candidate) {
      return $candidate
    }
  }
  return $null
}

function Invoke-Step {
  param(
    [string]$Name,
    [scriptblock]$Body
  )

  $started = Get-Date
  try {
    $output = & $Body 2>&1
    return [ordered]@{
      name = $Name
      passed = $true
      started_at = $started.ToString("s")
      finished_at = (Get-Date).ToString("s")
      output = @($output | ForEach-Object { "$_" })
    }
  } catch {
    return [ordered]@{
      name = $Name
      passed = $false
      started_at = $started.ToString("s")
      finished_at = (Get-Date).ToString("s")
      error = "$($_.Exception.Message)"
      output = @()
    }
  }
}

function Set-RepoPythonPath {
  param([string]$RepoRoot)

  $entries = New-Object System.Collections.Generic.List[string]
  $entries.Add((Resolve-Path (Join-Path $RepoRoot "src")).Path)
  $legacySitePackages = Join-Path $RepoRoot ".venv/Lib/site-packages"
  if (Test-Path -LiteralPath $legacySitePackages) {
    $entries.Add((Resolve-Path $legacySitePackages).Path)
  }
  if (-not [string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $entries.Add($env:PYTHONPATH)
  }
  $env:PYTHONPATH = ($entries -join [IO.Path]::PathSeparator)
}

function Add-LocalToolPath {
  param([string]$RepoRoot)

  $paths = @(
    (Join-Path $RepoRoot ".local_tools/ffmpeg/bin"),
    (Join-Path $RepoRoot ".local_tools/colmap/bin"),
    (Join-Path $RepoRoot ".local_tools/colmap")
  )
  foreach ($path in $paths) {
    if (Test-Path -LiteralPath $path) {
      $resolved = (Resolve-Path $path).Path
      if (($env:Path -split [IO.Path]::PathSeparator) -notcontains $resolved) {
        $env:Path = $resolved + [IO.Path]::PathSeparator + $env:Path
      }
    }
  }
}

function New-MarkdownReport {
  param($Report)

  $lines = New-Object System.Collections.Generic.List[string]
  $lines.Add("# Local Reconstruction Bootstrap")
  $lines.Add("")
  $lines.Add("- verdict: $($Report.verdict)")
  $lines.Add("- repo_root: ``$($Report.repo_root)``")
  $lines.Add("- bundle: ``$($Report.bundle)``")
  $lines.Add("- python: ``$($Report.python)``")
  $lines.Add("- generated_at: ``$($Report.generated_at)``")
  $lines.Add("")
  $lines.Add("## Directories")
  foreach ($dir in $Report.directories) {
    $lines.Add("- ``$dir``")
  }
  $lines.Add("")
  $lines.Add("## Steps")
  foreach ($step in $Report.steps) {
    $lines.Add("- $($step.name): passed=$($step.passed)")
    if ($step.error) {
      $lines.Add("  - error: ``$($step.error)``")
    }
  }
  $lines.Add("")
  $lines.Add("## Next Actions")
  foreach ($action in $Report.next_actions) {
    $lines.Add("- $action")
  }
  $lines.Add("")
  return ($lines -join [Environment]::NewLine)
}

$repoRoot = Get-RepoRoot
Set-Location $repoRoot
Add-LocalToolPath -RepoRoot $repoRoot

$outDir = Join-Path $repoRoot $OutputRoot
$rawImageDir = Join-Path $repoRoot "data/raw/qiyu_loop/images"
$rawVideoDir = Join-Path $repoRoot "data/raw/qiyu_loop/video"
$pointcloudOut = Join-Path $repoRoot "outputs/pointcloud_reconstruction"
$colmapOut = Join-Path $repoRoot "outputs/colmap_smoke/qiyu_loop"

foreach ($dir in @($outDir, $rawImageDir, $rawVideoDir, $pointcloudOut, $colmapOut)) {
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

$python = Find-Python -RepoRoot $repoRoot -ExplicitPythonPath $PythonPath
if ($python) {
  Set-RepoPythonPath -RepoRoot $repoRoot
}

$steps = New-Object System.Collections.Generic.List[object]
$extraPythonPath = @((Join-Path $repoRoot ".venv/Lib/site-packages"))
$checkArgs = @("-ExecutionPolicy", "Bypass", "-File", ".\tools\check_local_env.ps1", "-OutputRoot", $OutputRoot)
if ($python) {
  $checkArgs += @("-PythonPath", $python, "-ExtraPythonPath")
  $checkArgs += $extraPythonPath
}
$steps.Add((Invoke-Step -Name "environment_check" -Body { powershell @checkArgs }))

if ($python -and $RunAssetValidation) {
  $steps.Add((Invoke-Step -Name "asset_validation" -Body {
    & $python ".\tools\validate_reconstruction_assets.py" --bundle $Bundle
  }))
}

$smokeRunDir = $null
if ($python -and $RunPointcloudSmoke) {
  $steps.Add((Invoke-Step -Name "pointcloud_smoke" -Body {
    & $python ".\tools\reconstruct_pointcloud_map.py" --bundle $Bundle --selection center --max-tiles 16 --max-points 50000 --split-ground --clean-ground --run-name $RunName
  }))
  $smokeRunDir = Join-Path $repoRoot "outputs/pointcloud_reconstruction/$Bundle/$RunName"
  $cleanGroundPly = Join-Path $smokeRunDir "site_proxy_ground_clean.ply"
  if (Test-Path -LiteralPath $cleanGroundPly) {
    $steps.Add((Invoke-Step -Name "ground_heightmap" -Body {
      & $python ".\tools\build_ground_heightmap.py" --input-ply $cleanGroundPly --cell-size 1.0 --min-points-per-cell 2
    }))
    $steps.Add((Invoke-Step -Name "handoff_manifest" -Body {
      & $python ".\tools\build_reconstruction_handoff_manifest.py" --run-dir $smokeRunDir --site-id $Bundle --handoff-root-uri $HandoffRootUri
    }))
  }
}

$nextActions = New-Object System.Collections.Generic.List[string]
if (-not $python) {
  $nextActions.Add("Install Python 3.11/3.12 and recreate .venv, or pass -PythonPath to an existing python.exe.")
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  $nextActions.Add("Install FFmpeg before COLMAP image/video smoke tests.")
}
if (-not (Get-Command colmap -ErrorAction SilentlyContinue)) {
  $nextActions.Add("External colmap.exe is not installed; use pycolmap smoke first, and install COLMAP CUDA build only if CLI/GUI workflow is required.")
}
if (-not $RunPointcloudSmoke) {
  $nextActions.Add("Run again with -RunPointcloudSmoke to produce a pointcloud smoke run and handoff manifest.")
}
$nextActions.Add("Keep generated outputs under outputs/ or artifacts/; do not commit heavy reconstruction artifacts.")

$failed = @($steps | Where-Object { -not $_.passed })
$pycolmapReady = $false
if ($python) {
  try {
    & $python -c "import pycolmap" 2>$null
    $pycolmapReady = ($LASTEXITCODE -eq 0)
  } catch {
    $pycolmapReady = $false
  }
}
$verdict = if (-not $python) {
  "blocked"
} elseif ($failed.Count -gt 0) {
  "partial"
} elseif ((Get-Command ffmpeg -ErrorAction SilentlyContinue) -and ((Get-Command colmap -ErrorAction SilentlyContinue) -or $pycolmapReady)) {
  "ready"
} else {
  "partial"
}

$report = New-Object System.Collections.Specialized.OrderedDictionary
$report.Add("generated_at", (Get-Date).ToString("s"))
$report.Add("repo_root", $repoRoot)
$report.Add("bundle", $Bundle)
$report.Add("verdict", $verdict)
$report.Add("python", $python)
$report.Add("directories", @($rawImageDir, $rawVideoDir, $pointcloudOut, $colmapOut, $outDir))
$report.Add("steps", @($steps | ForEach-Object { $_ }))
$report.Add("next_actions", @($nextActions | ForEach-Object { $_ }))

$jsonPath = Join-Path $outDir "bootstrap_local_reconstruction.json"
$mdPath = Join-Path $outDir "bootstrap_local_reconstruction.md"
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding UTF8
New-MarkdownReport -Report $report | Set-Content -LiteralPath $mdPath -Encoding UTF8

Write-Host "verdict=$verdict"
Write-Host "json=$jsonPath"
Write-Host "markdown=$mdPath"
if ($smokeRunDir) {
  Write-Host "smoke_run_dir=$smokeRunDir"
}
