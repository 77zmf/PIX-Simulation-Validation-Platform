param(
  [ValidateSet("bootstrap", "run", "stop", "replay")]
  [string]$Mode,
  [string]$RepoRoot,
  [string]$ScenarioPath,
  [string]$RunDir,
  [string]$AssetBundle,
  [switch]$Execute
)

$remoteHost = if ($env:SIMCTL_UE5_REMOTE) { $env:SIMCTL_UE5_REMOTE } else { "ue5-gpu" }
$command = switch ($Mode) {
  "bootstrap" { "ansible-playbook -i infra/ansible/inventory.example.ini infra/ansible/ue5_remote_bootstrap.yml" }
  "run" { "ssh $remoteHost `"cd /srv/simctl && ./run_ue5_job.sh '$ScenarioPath' '$RunDir' '$AssetBundle'`"" }
  "stop" { "ssh $remoteHost `"pkill -f CarlaUnreal || true`"" }
  "replay" { "ssh $remoteHost `"ls -lah '$RunDir'`"" }
}

Write-Host "Mode: $Mode"
Write-Host "Remote host: $remoteHost"
Write-Host "Command: $command"

if ($Execute) {
  Invoke-Expression $command
}
