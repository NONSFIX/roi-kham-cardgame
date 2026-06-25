@echo off
cd /d "C:\Users\ASUS\Documents\Vault\Claude Vault\roi-kham-cardgame"

echo ========================================
echo  Roi-Kham Update Pipeline
echo ========================================
echo  Requires Ollama running with the model (default qwen3.5:2b).
echo  The web scraper (scrape_categories.py) is optional/legacy and
echo  is NOT part of this pipeline -- the local LLM supersedes it.

echo.
echo [1/3] Local-LLM categorizer (5000 words)...
python scraper/categorize_llm.py --limit 5000 --no-export
if errorlevel 1 (
    echo ERROR: Categorizer failed. Check scraper/logs/ for details.
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
