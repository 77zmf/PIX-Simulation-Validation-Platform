param(
  [string]$WorkspaceRoot,
  [string]$AssetRoot,
  [switch]$Execute
)

$checks = @(
  @{ Name = "Git"; Command = "git --version" },
  @{ Name = "Python"; Command = "python --version" },
  @{ Name = "OpenSSH"; Command = "ssh -V" }
)

Write-Host "WorkspaceRoot: $WorkspaceRoot"
Write-Host "AssetRoot: $AssetRoot"
Write-Host "Execute: $Execute"

foreach ($check in $checks) {
  Write-Host "Checking $($check.Name)..."
  try {
    Invoke-Expression $check.Command | Out-Host
  } catch {
    Write-Warning "$($check.Name) check failed: $($_.Exception.Message)"
  }
}

if ($Execute) {
  New-Item -ItemType Directory -Force -Path $AssetRoot | Out-Null
  Write-Host "Ensured asset root exists: $AssetRoot"
  Write-Host "WSL2, Ubuntu 22.04, CARLA 0.9.15, and self-hosted runner installation remain operator-controlled."
} else {
  Write-Host "Dry run only. Re-run with -Execute to create directories and apply host changes."
}
