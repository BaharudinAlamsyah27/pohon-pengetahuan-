@echo off
echo === 1. Audit & Rebuild Lokal ===
python scripts/bangun_pohon.py --cek
python scripts/bangun_pohon.py --mode lokal
echo.
echo === 2. Simpan ke Git ===
git add -A
git commit -m "backup: %date% %time%"
git status --short
echo.
echo Selesai. Jika sudah terhubung ke GitHub privat, jalankan: git push
pause
