# Panduan & Kamus Perintah — Pohon Pengetahuan

Catatan khusus agar Anda tidak lupa perintah harian, pertanyaan strategis untuk AI, dan perintah skrip lokal. File ini bersifat **pribadi (lokal saja)** dan tidak pernah masuk ke `situs/`.

---

## 1. Alur Cepat Harian (3 Langkah)

1. **Nyalakan server lokal** (sekali saat mulai kerja di laptop):
   ```powershell
   python scripts/server_lokal.py
   ```
   Lalu buka di browser: `http://127.0.0.1:8765/`
2. **Tangkap postingan dari sosmed (FB, IG, Threads, X, YouTube, Web):**
   - **Cara 1 (Bookmarklet 1-Klik):** blok teks postingan → klik bookmark **Tangkap ke Pohon** → klik **Simpan**.
   - **Cara 2 (Tempel Link):** buka tab **Tangkap** → tempel URL X / YouTube (transkrip) / artikel → klik **Tarik Isi Link** → **Simpan**.
   - **Cara 3 (Chat AI langsung):** tempel teks atau screenshot (bisa 5–15 postingan sekaligus).
3. **Matangkan & terjemahkan ke Bahasa Indonesia (di chat AI):**
   - Ketik: **`rapikan semua draf`** atau **`ekstrak S-0002 sampai S-0010`**
   - AI akan menerjemahkan ke Bahasa Indonesia, memecah jadi kartu presisi, mengisi `alat`/`tugas`/`tahap-kerja`, menggabungkan duplikat, menghubungkan relasi, dan membangun ulang pohon.

---

## 2. Daftar Perintah Chat ke Agen AI (Bahasa Alami)

| Tujuan | Contoh yang Bisa Anda Ketik di Chat |
|---|---|
| Memasukkan postingan/transkrip | *(langsung tempel teks/screenshot)* atau `"masukkan 5 postingan ini"` |
| Memproses sumber hasil Tangkap | `"ekstrak S-0002"` atau `"rapikan semua draf ke Bahasa Indonesia"` |
| Membuka kartu / sumber asli | `"buka K-0003"` / `"buka sumber S-0001"` |
| Mencari ilmu di catatan | `"cari tentang video ai"` / `"cari trik hook x"` |
| Merangkum satu cabang | `"ringkas cabang ai/video-dan-clipping"` / `"apa yang saya tahu tentang sosmed"` |
| **Membandingkan alat/metode AI** | `"bandingkan claude fable vs gemini vs kling untuk video ai"` |
| **Menyusun tahapan awal–akhir** | `"buatkan playbook lengkap dari awal sampai akhir untuk clipping"` |
| Menganalisis dua pendapat berlawanan | `"analisis pertentangan antara K-0001 dan K-0012"` |
| Meminta saran personal (`persona.md`) | `"saran untuk saya di bidang bisnis/sosmed sekarang"` |
| Menyusun roadmap bertahap | `"buatkan roadmap 6 bulan membangun pendapatan tambahan dari AI & sosmed"` |
| Ulasan mingguan (maks 5 kartu) | `"ulasan mingguan"` atau `"apa yang perlu saya coba minggu ini"` |
| Mencatat hasil praktik nyata | `"saya sudah coba K-0003 seminggu, hasilnya bagus/gagal karena ..."` |
| Cek kesehatan & rapikan pohon | `"status"` / `"rapikan"` |
| Menandai kartu untuk situs online | `"tandai publik K-0003"` lalu `"publikasikan"` |

---

## 3. Bank Pertanyaan Masa Depan (Siap Salin-Tempel)

### A. Untuk 4 Bab Dominan (AI, Bisnis, Sosmed, Digital Marketing)
- `"Dari seluruh catatanku tentang video AI, apa kesamaan triknya, apa perbedaan tiap alat, dan mana yang terbaik untuk modal nol?"`
- `"Buatkan SOP/playbook lengkap dari riset, skrip, produksi, edit, distribusi, sampai monetisasi untuk clipping/konten X berdasarkan catatanku."`
- `"Alat AI mana yang paling sering direkomendasikan di catatanku, dan tahap kerja mana yang masih punya celah pengetahuan?"`
- `"Bandingkan strategi pertumbuhan X vs YouTube vs TikTok yang ada di catatanku — mana yang paling realistis untuk waktu luangku?"`
- `"Gabungkan ilmu AI + Digital Marketing di catatanku untuk merancang 1 eksperimen produk/layanan kecil minggu ini."`

### B. Untuk Diri Sendiri, Karier & Anti-Overthinking (`persona.md`)
- `"Lihat persona.md dan catatan terbaruku: berikan 1 langkah kecil (≤15 menit) hari ini supaya saya tidak berhenti di rencana saja."`
- `"Di antara semua ide bisnis/AI yang sudah saya simpan, mana 1 yang paling cocok dieksekusi dengan kondisi gaji Rp2,3 jt dan waktu luang harian?"`
- `"Evaluasi cabang mana di pohonku yang sudut pandangnya masih tunggal (waspada gema) sehingga saya perlu cari sumber pembanding."`
- `"Dari penulis/akun yang sering saya simpan, siapa yang sarannya paling sering benar-benar berhasil saat saya terapkan?"`

### C. Untuk Menjaga Kualitas Big Data (Setiap 1–2 Bulan)
- `"Jalankan audit lengkap: ada cabang yang sudah >30 kartu dan perlu dipecah, atau kartu duplikat yang harus digabung?"`
- `"Kartu mana saja yang statusnya masih belum-diverifikasi dan paling penting dicek kebenarannya dulu?"`

---

## 4. Perintah Terminal Cepat (0 Token AI)

```powershell
# 1. Jalankan server web lokal (http://127.0.0.1:8765/)
python scripts/server_lokal.py

# 2. Bangun ulang tampilan offline + indeks pencarian FTS5
python scripts/bangun_pohon.py --mode lokal

# 3. Audit konsistensi & statistik pohon (STATUS)
python scripts/bangun_pohon.py --cek

# 4. Pencarian cepat FTS5 (BM25) & cek duplikat/tetangga
python scripts/bangun_pohon.py --cari "claude video ai"
python scripts/bangun_pohon.py --tetangga "tips membuat video ai konsisten"
python scripts/bangun_pohon.py --filter --tampilan belum-diverifikasi
python scripts/bangun_pohon.py --filter --tampilan pertentangan-terbuka
python scripts/bangun_pohon.py --filter --tampilan draf-otomatis

# 5. Mesin Cerdas: Bandingkan, Playbook 6 Tahap, Radar Big Data
python scripts/mesin_cerdas.py --bandingkan "video ai"
python scripts/mesin_cerdas.py --playbook "clipping"
python scripts/mesin_cerdas.py --tren
python scripts/mesin_cerdas.py --ringkas
python scripts/mesin_cerdas.py --ulasan
python scripts/mesin_cerdas.py --saran
python scripts/mesin_cerdas.py --roadmap ai
python scripts/mesin_cerdas.py --fondasi
python scripts/mesin_cerdas.py --gema
python scripts/mesin_cerdas.py --klaster ai

# 6. Pindah cabang massal (saat memecah cabang >30 kartu)
python scripts/bangun_pohon.py --pindah-cabang K-0010 K-0011 --ke ai/video-dan-clipping

# 7. Publikasi situs statis aman + cek kebocoran wajib
python scripts/bangun_pohon.py --mode publik
python .agents/skills/publikasi-situs/scripts/periksa_kebocoran.py --situs situs --persona persona.md --sumber sumber

# 8. Simpan cadangan ke Git (atau klik ganda backup.bat)
backup.bat
git add -A; git commit -m "catatan: update pohon"
```

---

## 5. Tutorial Penggunaan 9 Menu di Web (`http://127.0.0.1:8765/`)

1. **`Beranda` (Ruang Tamu):** Ringkasan jumlah kartu, sumber, dan pintu masuk cepat ke setiap topik.
2. **`+ Simpan Baru` (Tangkap):** Tempat memasukkan ilmu baru dengan 3 cara:
   - **Tempel Link:** masukkan link X, YouTube, atau artikel web → klik **Tarik Isi Link** (jika di dalam postingan X ada link artikel/GitHub/YouTube lain, isinya ikut ditarik otomatis).
   - **Baca Gambar / Screenshot:** klik **`📷 Baca Teks dari Gambar / Screenshot`** untuk mengekstrak teks dari gambar (via Tesseract lokal atau Gemini Vision gratis).
   - **Pilih Cara Memecah Kartu:**
     - `Simpan Jadi 1 Kartu Utuh Saja` (1 postingan = 1 kartu).
     - `Pecah Otomatis Jadi 1–3 Kartu Poin Inti` (postingan panjang otomatis diperas menjadi 1–3 kartu poin terpenting).
     - `Pecah Otomatis Jadi 1–5 Kartu` (khusus artikel/thread panjang).
   - Klik **`🔍 Cek Poin yang Akan Diambil`** bila ingin melihat pratinjau poinnya sebelum klik **Simpan**.
   - Buka **`Pengaturan Detail — Opsional`** bila ingin memilih topik manual atau mengetik nama topik baru (misal: `pengembangan-diri`).
3. **`Peta Pohon`:**
   - Klik **kotak topik kuning** di kiri (misal `AI` atau `Keuangan`) untuk membuka sub-topik dan daftar kartunya dalam 3 kolom rapi.
   - Klik **kartu di kolom kanan** untuk langsung memberi **Bintang (★ 1–5)**, menulis **Catatan Khusus**, mengubah status praktek, atau klik **Hapus / Arsip** jika ada kartu ganda.
4. **`Tanya AI`:**
   - Ajukan pertanyaan biasa tentang isi catatan Anda (misal: *"bagaimana aturan reupload OCR X?"*).
   - **Bedah Susunan Kata Viral:** tanyakan *"Apa rahasia konten AI viral berdasarkan susunan kata?"* untuk melihat pola kalimat pembuka (*hook*), rata-rata panjang kalimat, kata pemicu, dan 3 pola kalimat (*template*) dari koleksi Anda.
5. **`Cari Kartu`:**
   - Cari kata kunci (tekan tombol `/` dari mana saja) dan saring berdasarkan **Bintang (★)**, **Kepercayaan**, **Status Praktek**, **Usia**, atau **Nama Penulis**.
   - Klik sebuah kartu → klik **Edit Kartu** untuk mengubah judul ide, isi, atau memindahkannya ke cabang lain.
6. **`Jalur Usia` (Timeline):** Melihat kartu yang disusun berurutan menurut tahap usia (`sebelum-20`, `20-25`, `25-30`, dst.).
7. **`Sumber Asli` (Perpustakaan):** Membaca teks asli utuh (`S-XXXX`) dari setiap postingan yang pernah Anda simpan.
8. **`Praktek` (Ulasan):** Pilih **1 kartu** untuk menjadi **Fokus Eksperimen Minggu Ini**, tulis catatan hasil percobaan Anda, lalu tandai **Diterapkan** atau **Ditolak**.
9. **`Analisis`:** Memiliki 4 tombol utama:
   - **`1. Bandingkan Alat / Cara`**: membandingkan beberapa alat AI/strategi di satu topik.
   - **`2. Susun Langkah Kerja (6 Tahap)`**: mengurutkan kartu Anda dari tahap *Riset → Skrip → Produksi → Edit → Distribusi → Monetisasi*.
   - **`3. Ringkasan Tren Koleksi`**: melihat alat dan topik yang paling sering Anda kumpulkan.
   - **`4. Cek Kelengkapan & Kualitas`**: melihat tabel tahap kerja mana yang masih kosong (`0`), akun penulis paling bermanfaat, sumber paling subur (*Akar Terbaik*), dan kartu terkuat (*Daun Terbaik*).

---

## 6. Cara Pasang Bookmarklet 1-Klik (Pengingat Singkat)

1. Buka `http://127.0.0.1:8765/#tangkap` → klik **Salin kode Bookmarklet**.
2. Tekan `Ctrl + Shift + B` di Chrome/Edge → klik kanan bilah bookmark → **Add page…**.
3. Isi Nama: `Tangkap ke Pohon`, tempel kode di kolom URL → **Save**.
4. Saat baca postingan bagus di FB/IG/Threads/X/Web → blok teksnya → klik **Tangkap ke Pohon** → **Simpan**.

---

## 7. Cara Deploy Gratis ke Vercel / Cloudflare Pages (Untuk Portofolio)

- **Ruang Tamu (`Beranda`), `Pohon`, `Timeline`, `Pencarian`, dan `Perpustakaan`** berjalan 100% statis dan aman ditayangkan online untuk pengunjung portofolio.
- **Ruang Dapur Lokal (`Tangkap`, `Analisis`, `Ulasan`)** khusus berjalan saat `python scripts/server_lokal.py` menyala di laptop Anda — tidak muncul di versi online agar orang luar tidak bisa mengubah data pribadi Anda.
- **Foto Profil (Opsional):** letakkan foto Anda dengan nama `profil.jpg` ke dalam folder `situs/` sebelum push (bila belum ada, kartu profil otomatis menampilkan inisial `BA`).
- **Langkah tayang:**
  1. Tandai kartu pilihan Anda menjadi `publik: ya` (ketik di chat: *"tandai publik K-0003"*).
  2. Jalankan *"publikasikan"* (atau `python scripts/bangun_pohon.py --mode publik` lalu cek `periksa_kebocoran.py`).
  3. Push ke repo **Private** GitHub → sambungkan ke **Vercel** (sudah disiapkan [vercel.json](file:///c:/dev/pohon%20pengetahuan/vercel.json)) atau **Cloudflare Pages** (build command kosong, output directory `situs`).
  4. Tambahkan tautannya sebagai proyek unggulan di `portfolio-alam.vercel.app`.

---

## 8. Tab `Tanya` (Chat Q&A Berbasis Berkas)

- Berjalan **otomatis tanpa API key (0 biaya)** lewat Level 1 Sintesis Lokal — langsung menjawab pertanyaan dengan sitasi `[K-XXXX]`, baik offline (`file://`), lokal (`server_lokal.py`), maupun di Vercel.
- **Aktifkan Mode AI Gemini 2.5 Flash-Lite (RAG gratis):**
  - **Di laptop (lokal):** salin [.env.example](file:///c:/dev/pohon%20pengetahuan/.env.example) menjadi `.env`, isi `GEMINI_API_KEY` gratis dari Google AI Studio (`aistudio.google.com/apikey`), lalu restart `server_lokal.py`.
  - **Di Vercel (online):** tambahkan Environment Variable `GEMINI_API_KEY` (dan opsional `GEMINI_MODEL=gemini-2.5-flash-lite`) di pengaturan proyek Vercel — otomatis membaca hanya kartu `publik: ya` lewat [api/tanya.js](file:///c:/dev/pohon%20pengetahuan/api/tanya.js).
- **Di terminal (0 UI):** `python scripts/mesin_cerdas.py --tanya "pertanyaan Anda"`
