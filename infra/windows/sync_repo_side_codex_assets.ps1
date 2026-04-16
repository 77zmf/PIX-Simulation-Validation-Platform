param(
  [string]$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path,
  [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }),
  [switch]$SyncAgents,
  [switch]$SyncSkills,
  [switch]$Execute
)

$ErrorActionPreference = "Stop"

if (-not $SyncAgents -and -not $SyncSkills) {
  $SyncAgents = $true
  $SyncSkills = $true
}

function Get-NormalizedPath([string]$PathValue) {
  return [System.IO.Path]::GetFullPath($PathValue)
}

function Assert-IsChildPath([string]$ParentPath, [string]$ChildPath) {
  $parent = Get-NormalizedPath($ParentPath)
  $child = Get-NormalizedPath($ChildPath)
  if (-not $child.StartsWith($parent, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to write outside target root. Parent='$parent' Child='$child'"
  }
}

$repoAgentsPath = Join-Path $WorkspaceRoot "AGENTS.md"
$repoSkillsRoot = Join-Path $WorkspaceRoot "ops\\skills"
$targetAgentsPath = Join-Path $CodexHome "AGENTS.md"
$targetSkillsRoot = Join-Path $CodexHome "skills"
$backupRoot = Join-Path $CodexHome ("repo_sync_backups\\" + (Get-Date -Format "yyyyMMdd_HHmmss"))

if (-not (Test-Path $repoAgentsPath)) {
  throw "Repo AGENTS.md not found: $repoAgentsPath"
}

if (-not (Test-Path $repoSkillsRoot)) {
  throw "Repo skills root not found: $repoSkillsRoot"
}

$skillDirectories = Get-ChildItem $repoSkillsRoot -Directory | Sort-Object Name

Write-Host "WorkspaceRoot: $WorkspaceRoot"
Write-Host "CodexHome: $CodexHome"
Write-Host "SyncAgents: $SyncAgents"
Write-Host "SyncSkills: $SyncSkills"
Write-Host "Execute: $Execute"
Write-Host ""

if ($SyncAgents) {
  Write-Host "[Plan] Sync AGENTS.md"
  Write-Host "  Source: $repoAgentsPath"
  Write-Host "  Target: $targetAgentsPath"
}

if ($SyncSkills) {
  Write-Host "[Plan] Sync repo-side skills"
  foreach ($skill in $skillDirectories) {
    $targetSkillPath = Join-Path $targetSkillsRoot $skill.Name
    Write-Host "  $($skill.Name)"
    Write-Host "    Source: $($skill.FullName)"
    Write-Host "    Target: $targetSkillPath"
  }
}

if (-not $Execute) {
  Write-Host ""
  Write-Host "Dry run only. Re-run with -Execute to apply changes."
  exit 0
}

New-Item -ItemType Directory -Force -Path $CodexHome | Out-Null
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

if ($SyncAgents) {
  Assert-IsChildPath -ParentPath $CodexHome -ChildPath $targetAgentsPath
  if (Test-Path $targetAgentsPath) {
    Copy-Item -LiteralPath $targetAgentsPath -Destination (Join-Path $backupRoot "AGENTS.md") -Force
    Write-Host "Backed up existing AGENTS.md to $(Join-Path $backupRoot 'AGENTS.md')"
  }
  Copy-Item -LiteralPath $repoAgentsPath -Destination $targetAgentsPath -Force
  Write-Host "Synced AGENTS.md -> $targetAgentsPath"
}

if ($SyncSkills) {
  New-Item -ItemType Directory -Force -Path $targetSkillsRoot | Out-Null
  $backupSkillsRoot = Join-Path $backupRoot "skills"
  New-Item -ItemType Directory -Force -Path $backupSkillsRoot | Out-Null

  foreach ($skill in $skillDirectories) {
    $targetSkillPath = Join-Path $targetSkillsRoot $skill.Name
    $backupSkillPath = Join-Path $backupSkillsRoot $skill.Name

    Assert-IsChildPath -ParentPath $targetSkillsRoot -ChildPath $targetSkillPath

    if (Test-Path $targetSkillPath) {
      Copy-Item -LiteralPath $targetSkillPath -Destination $backupSkillPath -Recurse -Force
      Remove-Item -LiteralPath $targetSkillPath -Recurse -Force
      Write-Host "Backed up existing skill '$($skill.Name)' to $backupSkillPath"
    }

    Copy-Item -LiteralPath $skill.FullName -Destination $targetSkillPath -Recurse -Force
    Write-Host "Synced skill '$($skill.Name)' -> $targetSkillPath"
  }
}

Write-Host ""
Write-Host "Repo-side Codex assets sync completed."
Write-Host "BackupRoot: $backupRoot"
