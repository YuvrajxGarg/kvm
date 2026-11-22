@echo off
REM Builds dist\Kvm\Kvm.exe. Run on Windows with Python 3.9+ installed.
cd /d "%~dp0"
py -3 -m venv .venv-build || python -m venv .venv-build
call .venv-build\Scripts\activate.bat
python -m pip install --upgrade pip
pip install pyinstaller certifi -r requirements.txt
pyinstaller --noconfirm --log-level WARN Kvm.spec
echo.
echo Done: dist\Kvm\Kvm.exe
pause
