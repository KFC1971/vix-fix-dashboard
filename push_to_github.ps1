# Add Git to Path for this session
$GitPath = "C:\Program Files\Git\cmd"
if (Test-Path $GitPath) {
    $env:Path = "$env:Path;$GitPath"
    Write-Host "Added Git to PATH: $GitPath" -ForegroundColor Gray
}

# Define Repo URL
$RepoUrl = "https://github.com/KFC1971/vix-fix-dashboard.git"

Write-Host "Adding Remote Origin: $RepoUrl" -ForegroundColor Cyan
git remote add origin $RepoUrl

Write-Host "Renaming branch to main..." -ForegroundColor Cyan
git branch -M main

Write-Host "Pushing code to GitHub..." -ForegroundColor Cyan
try {
    git push -u origin main
    Write-Host "`nSUCCESS! Code pushed to GitHub." -ForegroundColor Green
    Write-Host "Now go to https://share.streamlit.io to deploy!" -ForegroundColor Yellow
}
catch {
    Write-Error "Push failed. You might need to authenticate."
}
