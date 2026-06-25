@echo off
cd /d "C:\Users\ASUS\Documents\Vault\Claude Vault\roi-kham-cardgame"

echo ========================================
echo  Roi-Kham Update Pipeline
echo ========================================

echo.
echo [1/3] Web scraper -- querying Thai dictionaries (1000 words)...
python scraper/scrape_categories.py --limit 1000 --no-export
if errorlevel 1 (
    echo ERROR: Scraper failed. Check scraper/logs/ for details.
    pause
    exit /b 1
)

echo.
echo [2/3] Compound decomposer -- inferring categories from sub-words (5000 words)...
python scraper/decompose_words.py --limit 5000 --no-export
if errorlevel 1 (
    echo ERROR: Decomposer failed. Check scraper/logs/ for details.
    pause
    exit /b 1
)

echo.
echo [3/3] Re-exporting words.js...
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
