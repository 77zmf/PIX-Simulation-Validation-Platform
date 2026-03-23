param(
  [switch]$Execute
)

Write-Host "Stopping CarlaUE4.exe"
if ($Execute) {
  Get-Process CarlaUE4 -ErrorAction SilentlyContinue | Stop-Process -Force
}
