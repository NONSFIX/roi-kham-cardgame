@echo off
cd /d "C:\Users\ASUS\Documents\Vault\Claude Vault\roi-kham-cardgame"

echo ========================================
echo  Roi-Kham Category Scraper
echo ========================================

echo.
echo [1/2] Running scraper (1000 words)...
python scraper/scrape_categories.py --limit 1000
if errorlevel 1 (
    echo ERROR: Scraper failed. Check scraper/logs/ for details.
    pause
    exit /b 1
)

echo.
echo [2/2] Re-exporting words.js...
node export_words.js
if errorlevel 1 (
    echo ERROR: Export failed.
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Done! Open prototype/index.html to test
echo ========================================
pause
