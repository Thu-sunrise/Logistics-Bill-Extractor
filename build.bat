@echo off
echo ==============================================
echo   TIEN TRINH DONG GOI APP LOGISTICS (PYINSTALLER)
echo ==============================================

echo [1] Cai dat PyInstaller neu chua co...
pip install pyinstaller

echo [2] Dang bien dich thanh 1 file .exe duy nhat...
echo.
pyinstaller --noconfirm --onefile --windowed --name "Tool_Boc_Tach_ONE_Bill" "app.py"

echo.
echo ==============================================
echo HOAN THANH! File .exe nam trong thu muc 'dist'
echo ==============================================
pause
