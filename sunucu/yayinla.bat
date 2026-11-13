@echo off
chcp 65001 >nul
rem Oğul Tarım sunucusunu Cloudflare'e kurar. Çift tıklayın.
cd /d "%~dp0"
if exist "%USERPROFILE%\tools\node-v22.11.0-win-x64\node.exe" set "PATH=%USERPROFILE%\tools\node-v22.11.0-win-x64;%PATH%"
where node >nul 2>nul || (echo Node.js bulunamadi. https://nodejs.org adresinden LTS surumunu kurun. & pause & exit /b 1)
if not exist node_modules call npm install --no-fund --no-audit
node yayinla.mjs
pause
