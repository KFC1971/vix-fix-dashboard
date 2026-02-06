# Add Git to Path for this session
$GitPath = "C:\Program Files\Git\cmd"
if (Test-Path $GitPath) {
    $env:Path = "$env:Path;$GitPath"
    Write-Host "Added Git to PATH: $GitPath" -ForegroundColor Gray
}

# Check for Git again
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "Git command still not found. Please re-install Git."
    exit 1
}

Write-Host "Initialize Git Repository..." -ForegroundColor Cyan
git init

Write-Host "Adding files..." -ForegroundColor Cyan
git add .

Write-Host "Committing files..." -ForegroundColor Cyan
git commit -m "Initial commit of Vix Fix Dashboard"

Write-Host "`nSUCCESS! Repository Ready." -ForegroundColor Green
Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host "1. Go to GitHub.com and create a new repository."
Write-Host "2. Copy the 'git remote add origin...' command."
Write-Host "3. Paste and run it here."
Write-Host "4. Run: git push -u origin master"
