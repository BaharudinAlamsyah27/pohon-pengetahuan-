---
name: roadmap-persona
description: Menyusun roadmap atau kurikulum bertahap dari kartu-kartu Pohon Pengetahuan berdasarkan profil di persona.md, lengkap dengan fase, tindakan, dasar kartu, dan celah pengetahuan. Gunakan saat pengguna meminta rencana, jalur belajar, atau langkah berjenjang menuju sebuah tujuan.
---

# Roadmap Persona

## Gunakan skill ini bila
- Pengguna meminta rencana multi-tahap ("buatkan roadmap keuangan 12 bulan", "jalur belajar AI").

## Jangan gunakan bila
- Pengguna hanya minta 3-5 langkah berikutnya. Pakai mode SARAN (AGENTS.md Bagian 10).

## Prosedur
1. Baca `persona.md`. Bila umur, kondisi, tujuan, atau waktu per minggu belum ada, minta bagian itu dulu.
2. Tetapkan **titik awal, tujuan, dan horizon** (mis. 3/6/12 bulan atau per tahap hidup).
3. Kumpulkan bahan dengan jalur hemat (AGENTS.md Bagian 5): `indeks.md` → cabang tahap saat ini dan berikutnya → maksimal 10 kartu. Urutkan lewat relasi `prasyarat-untuk` dan `lanjutan-dari`: prasyarat selalu lebih dulu.
4. Susun **fase**. Tiap fase memuat tujuan, 2-4 tindakan konkret yang muat dalam kapasitas waktu/dana persona, kartu dasar, dan indikator selesai.
5. Periksa kendala persona (waktu, dana, kesehatan). Bila ada pertentangan relevan, jangan memilihkan: tandai sebagai "keputusan Anda" dan rujuk skill analisis-pertentangan.
6. Tandai **celah**: bagian tujuan yang belum punya kartu. Daftarkan topik yang perlu dicari. Isian dari agen berlabel `[inferensi AI]`.
7. Sertakan status penerapan tiap kartu dasar (Bagian 19) agar terlihat mana yang sudah dicoba.
8. Tawarkan menyimpan ke `roadmap/<tanggal>-<tujuan>.md`. Roadmap bersifat **pribadi** dan tidak pernah dipublikasikan.

## Format keluaran
```
## Roadmap: <tujuan> (<horizon>)
Titik awal: ... | Kapasitas: ... jam/minggu
### Fase 1: <nama> (<periode>)
Tujuan: ...
Tindakan: 1. ... 2. ...
Dasar: [[K-xxxx]] (kepercayaan, penerapan)
Selesai bila: ...
### Fase 2 ...
## Keputusan Anda (pertentangan)
## Celah pengetahuan
## Tinjau ulang: <tanggal, 4-8 minggu lagi>
```

## Aturan keras
- Setiap tindakan wajib punya kartu dasar; tanpa kartu → bagian `[inferensi AI]`.
- Tanpa janji hasil. Gunakan bahasa kemungkinan.
- Kesehatan/keuangan: pertimbangan saja; arahkan ke profesional untuk keputusan berisiko.
