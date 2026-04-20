param(
  [string]$OutputRoot = "outputs/env",
  [string]$PythonPath = "",
  [string[]]$ExtraPythonPath = @(),
  [switch]$JsonOnly
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
  $scriptDir = Split-Path -Parent $MyInvocation.ScriptName
  return (Resolve-Path (Join-Path $scriptDir "..")).Path
}

function Get-CommandInfo {
  param([string]$Name)

  $cmd = Get-Command $Name -ErrorAction SilentlyContinue
  if ($null -eq $cmd) {
    return [ordered]@{
      name = $Name
      present = $false
      path = $null
    }
  }

  return [ordered]@{
    name = $Name
    present = $true
    path = $cmd.Source
  }
}

function Invoke-Capture {
  param(
    [string]$FilePath,
    [string[]]$Arguments
  )

  try {
    $output = & $FilePath @Arguments 2>&1 | Select-Object -First 8
    return [ordered]@{
      ok = $true
      output = @($output | ForEach-Object { "$_" })
    }
  } catch {
    return [ordered]@{
      ok = $false
      output = @("$($_.Exception.Message)")
    }
  }
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

function Get-PythonPath {
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

function Test-PythonModules {
  param([string]$PythonPath)

  if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    return [ordered]@{
      ok = $false
      python = $null
      modules = @()
      error = "python not found"
    }
  }

  $code = @"
import importlib
import json
import sys

names = ["yaml", "numpy", "open3d", "cv2", "trimesh", "pycolmap", "matplotlib"]
rows = []
ok = True
for name in names:
    try:
        mod = importlib.import_module(name)
        rows.append({
            "name": name,
            "present": True,
            "version": getattr(mod, "__version__", "unknown"),
        })
    except Exception as exc:
        ok = False
        rows.append({
            "name": name,
            "present": False,
            "version": None,
            "error": str(exc),
        })
print(json.dumps({
    "ok": ok,
    "python": sys.executable,
    "modules": rows,
}, ensure_ascii=False))
"@

  try {
    $oldPythonPath = $env:PYTHONPATH
    $pythonPathEntries = New-Object System.Collections.Generic.List[string]
    foreach ($entry in $ExtraPythonPath) {
      if (-not [string]::IsNullOrWhiteSpace($entry) -and (Test-Path -LiteralPath $entry)) {
        $pythonPathEntries.Add((Resolve-Path $entry).Path)
      }
    }
    if (-not [string]::IsNullOrWhiteSpace($oldPythonPath)) {
      $pythonPathEntries.Add($oldPythonPath)
    }
    if ($pythonPathEntries.Count -gt 0) {
      $env:PYTHONPATH = ($pythonPathEntries -join [IO.Path]::PathSeparator)
    }
    $output = @($code | & $PythonPath - 2>&1)
    $env:PYTHONPATH = $oldPythonPath
    $json = $output | Where-Object { "$_".TrimStart().StartsWith("{") } | Select-Object -Last 1
    if ([string]::IsNullOrWhiteSpace($json)) {
      throw "python module probe did not emit JSON: $($output -join '; ')"
    }
    return ($json | ConvertFrom-Json)
  } catch {
    $env:PYTHONPATH = $oldPythonPath
    return [ordered]@{
      ok = $false
      python = $PythonPath
      modules = @()
      error = "$($_.Exception.Message)"
    }
  }
}

function New-MarkdownReport {
  param($Report)

  $lines = New-Object System.Collections.Generic.List[string]
  $lines.Add("# Local Reconstruction Tool Check")
  $lines.Add("")
  $lines.Add("- verdict: $($Report.verdict)")
  $lines.Add("- repo_root: $($Report.repo_root)")
  $lines.Add("- generated_at: $($Report.generated_at)")
  $lines.Add("")
  $lines.Add("## Core Commands")
  foreach ($item in $Report.commands) {
    $lines.Add("- $($item.name): present=$($item.present), path=$($item.path)")
  }
  $lines.Add("")
  $lines.Add("## Versions")
  $lines.Add("### nvidia-smi")
  foreach ($line in $Report.versions.nvidia_smi.output) {
    $lines.Add("- $line")
  }
  $lines.Add("")
  $lines.Add("### ffmpeg")
  foreach ($line in $Report.versions.ffmpeg.output) {
    $lines.Add("- $line")
  }
  $lines.Add("")
  $lines.Add("### colmap")
  foreach ($line in $Report.versions.colmap.output) {
    $lines.Add("- $line")
  }
  $lines.Add("")
  $lines.Add("## Python Modules")
  if ($Report.python.error) {
    $lines.Add("- error: $($Report.python.error)")
  }
  foreach ($mod in $Report.python.modules) {
    $lines.Add("- $($mod.name): present=$($mod.present), version=$($mod.version)")
  }
  $lines.Add("")
  $lines.Add("## Next Commands")
  $lines.Add('```powershell')
  $lines.Add(".\.venv\Scripts\Activate.ps1")
  $lines.Add("python .\tools\validate_reconstruction_assets.py --bundle site_gy_qyhx_gsh20260310")
  $lines.Add('```')
  return ($lines -join [Environment]::NewLine)
}

$repoRoot = Get-RepoRoot
Set-Location $repoRoot

$pythonPath = Get-PythonPath -RepoRoot $repoRoot -ExplicitPythonPath $PythonPath
$commands = @(
  (Get-CommandInfo -Name "git"),
  (Get-CommandInfo -Name "python"),
  (Get-CommandInfo -Name "ffmpeg"),
  (Get-CommandInfo -Name "colmap"),
  (Get-CommandInfo -Name "nvidia-smi"),
  (Get-CommandInfo -Name "wsl")
)

$pythonModules = Test-PythonModules -PythonPath $pythonPath

$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
$colmap = Get-Command colmap -ErrorAction SilentlyContinue
$nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue

$versions = [ordered]@{
  ffmpeg = if ($ffmpeg) { Invoke-Capture -FilePath $ffmpeg.Source -Arguments @("-version") } else { [ordered]@{ ok = $false; output = @("ffmpeg not found") } }
  colmap = if ($colmap) { Invoke-Capture -FilePath $colmap.Source -Arguments @("-h") } else { [ordered]@{ ok = $false; output = @("colmap not found") } }
  nvidia_smi = if ($nvidiaSmi) { Invoke-Capture -FilePath $nvidiaSmi.Source -Arguments @() } else { [ordered]@{ ok = $false; output = @("nvidia-smi not found") } }
}

$coreReady = $true
foreach ($name in @("git", "ffmpeg", "colmap")) {
  $found = $false
  foreach ($cmd in $commands) {
    if ($cmd.name -eq $name -and $cmd.present) {
      $found = $true
    }
  }
  if (-not $found) {
    $coreReady = $false
  }
}

if (-not $pythonModules.ok) {
  $coreReady = $false
}

$gpuReady = $false
foreach ($cmd in $commands) {
  if ($cmd.name -eq "nvidia-smi" -and $cmd.present) {
    $gpuReady = $true
  }
}

$verdict = if ($coreReady -and $gpuReady) {
  "ready"
} elseif ($coreReady) {
  "partial"
} else {
  "blocked"
}

$report = [ordered]@{
  generated_at = (Get-Date).ToString("s")
  repo_root = $repoRoot
  verdict = $verdict
  commands = $commands
  python = $pythonModules
  versions = $versions
  install_hint = [ordered]@{
    python_venv = "python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -U pip; .\.venv\Scripts\python.exe -m pip install PyYAML numpy open3d opencv-python trimesh pycolmap matplotlib"
    ffmpeg = "winget install --id Gyan.FFmpeg.Essentials -e --accept-package-agreements --accept-source-agreements --scope user"
    colmap = "Download colmap-x64-windows-cuda.zip from https://github.com/colmap/colmap/releases and add its bin directory to PATH"
  }
}

$outDir = Join-Path $repoRoot $OutputRoot
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$jsonPath = Join-Path $outDir "reconstruction_tool_check.json"
$mdPath = Join-Path $outDir "reconstruction_tool_check.md"

$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding UTF8
New-MarkdownReport -Report $report | Set-Content -LiteralPath $mdPath -Encoding UTF8

if ($JsonOnly) {
  $report | ConvertTo-Json -Depth 8
} else {
  Write-Host "verdict=$verdict"
  Write-Host "json=$jsonPath"
  Write-Host "markdown=$mdPath"
  Write-Host "next=powershell -ExecutionPolicy Bypass -File .\tools\check_local_env.ps1"
}
