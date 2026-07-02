# Bootstrap script for coin-analyzer development environment
# Run this script after cloning the repository to set up the development environment

Write-Host "Setting up coin-analyzer development environment..." -ForegroundColor Cyan

# Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Yellow
py -m pip install --upgrade pip

# Install core dependencies
Write-Host "Installing core dependencies..." -ForegroundColor Yellow
py -m pip install -r requirements.txt

# Optional: Install OCR dependencies
$installOCR = Read-Host "Install OCR dependencies (pytesseract)? (y/n)"
if ($installOCR -eq 'y' -or $installOCR -eq 'Y') {
    Write-Host "Installing OCR dependencies..." -ForegroundColor Yellow
    py -m pip install -r requirements-ocr.txt
    Write-Host "Note: You must also install Tesseract OCR separately from https://github.com/UB-Mannheim/tesseract/wiki" -ForegroundColor Yellow
}

# Run tests
Write-Host "Running tests to verify installation..." -ForegroundColor Yellow
py -m unittest discover

Write-Host "Setup complete!" -ForegroundColor Green
