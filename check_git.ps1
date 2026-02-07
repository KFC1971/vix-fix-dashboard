$GitPath = "C:\Program Files\Git\cmd"
if (Test-Path $GitPath) {
    $env:Path = "$env:Path;$GitPath"
}
Write-Host "Checking tracked files in .streamlit..."
git ls-files .streamlit/

Write-Host "Checking .gitignore status for secrets.toml..."
git check-ignore -v .streamlit/secrets.toml
