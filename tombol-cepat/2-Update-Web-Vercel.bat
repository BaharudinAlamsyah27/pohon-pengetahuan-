@echo off
chcp 65001 >nul
cd /d "%~dp0.."

echo ==================================================
echo   POHON PENGETAHUAN - UPDATE WEB VERCEL (1-KLIK)
echo ==================================================
echo.

echo [1/4] Membangun ulang indeks lokal & situs publik...
python scripts/bangun_pohon.py --mode lokal
if errorlevel 1 goto :gagal
python scripts/bangun_pohon.py --mode publik
if errorlevel 1 goto :gagal

echo.
echo [2/4] Memeriksa keamanan & kebocoran data pribadi...
python .agents/skills/publikasi-situs/scripts/periksa_kebocoran.py --situs situs --persona persona.md --sumber sumber
if errorlevel 1 goto :bocor

echo.
echo [3/4] Menyimpan perubahan ke Git...
set /p PESAN="Tulis catatan singkat update (atau langsung tekan Enter): "
if "%PESAN%"=="" set PESAN=update catatan pohon pengetahuan
git add -A
git commit -m "%PESAN%"

echo.
echo [4/4] Mengirim ke GitHub (Vercel otomatis update dalam ~30 detik)...
git push
if errorlevel 1 goto :gagal

echo.
echo ==================================================
echo   SELESAI! Website Vercel sedang diperbarui.
echo   Buka: https://pohon-pengetahuan.vercel.app/
echo ==================================================
pause
exit /b 0

:bocor
echo.
echo [DIBATALKAN] Ditemukan potensi kebocoran data pribadi! Upload dihentikan demi keamanan.
pause
exit /b 1

:gagal
echo.
echo [GAGAL] Terjadi kendala saat proses update. Cek pesan di atas.
pause
exit /b 1
