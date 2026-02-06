# Add Git to Path for this session
$GitPath = "C:\Program Files\Git\cmd"
if (Test-Path $GitPath) {
    $env:Path = "$env:Path;$GitPath"
    Write-Host "Added Git to PATH: $GitPath" -ForegroundColor Gray
}

Write-Host "Committing changes..." -ForegroundColor Cyan
git add .
try {
    git commit -m "Fix plot error for NoneType values"
}
catch {
    Write-Warning "Nothing to commit?"
}

Write-Host "Force Pushing to GitHub..." -ForegroundColor Yellow
git push -f origin main
