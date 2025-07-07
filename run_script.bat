@echo off
echo Starting Python script at %time% on %date%
start /B python main.py --mode auto

:: Wait for 10 hours (in seconds: 10 hours * 60 minutes * 60 seconds)
timeout /t 36000 /nobreak

:: Kill the Python process after 10 hours
taskkill /F /IM python.exe /T
echo Script terminated at %time% on %date%