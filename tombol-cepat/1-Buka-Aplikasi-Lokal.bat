@echo off
chcp 65001 >nul
cd /d "%~dp0.."

echo ==================================================
echo   POHON PENGETAHUAN - BUKA APLIKASI LOKAL
echo ==================================================
echo.
echo [1/2] Menyalakan server lokal di http://127.0.0.1:8765 ...
echo [2/2] Membuka browser otomatis ke halaman Simpan Baru...
echo.
echo * Biarkan jendela ini tetap terbuka selama Anda bekerja.
echo * Tekan Ctrl + C atau tutup jendela ini jika sudah selesai.
echo.

start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8765/#tangkap"
python scripts/server_lokal.py
pause
