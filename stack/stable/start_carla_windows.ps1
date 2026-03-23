param(
  [string]$RunDir,
  [string]$AssetRoot,
  [switch]$Execute
)

$carlaRoot = $env:CARLA_0915_ROOT
if (-not $carlaRoot) {
  $carlaRoot = "C:\CARLA_0.9.15"
}
$exe = Join-Path $carlaRoot "CarlaUE4.exe"
$command = "`"$exe`" -RenderOffScreen -carla-rpc-port=2000"

Write-Host "CARLA root: $carlaRoot"
Write-Host "RunDir: $RunDir"
Write-Host "AssetRoot: $AssetRoot"
Write-Host "Command: $command"

if ($Execute -and (Test-Path $exe)) {
  Start-Process -FilePath $exe -ArgumentList "-RenderOffScreen", "-carla-rpc-port=2000" | Out-Null
} elseif ($Execute) {
  throw "CARLA executable not found at $exe"
}
