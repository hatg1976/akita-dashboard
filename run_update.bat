@echo off
chcp 65001 > nul
cd /d "%~dp0"

REM APIキーはリポジトリ管理外の .env から読み込む(直書き禁止)
for /f "usebackq tokens=1,2 delims==" %%a in (".env") do (
    if "%%a"=="ESTAT_API_KEY" set ESTAT_API_KEY=%%b
)

echo [%date% %time%] データ更新開始 >> logs\update_log.txt

git pull origin main >> logs\update_log.txt 2>&1

python update_data.py >> logs\update_log.txt 2>&1

git config user.email "bot@akita-dashboard"
git config user.name "Akita Dashboard Bot"
git add data\
git diff --cached --quiet || (
    for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set YDATE=%%c年%%a月%%b日
    git commit -m "データ自動更新: %YDATE%" >> logs\update_log.txt 2>&1
    git push origin main >> logs\update_log.txt 2>&1
)

echo [%date% %time%] 更新完了 >> logs\update_log.txt
