# AGENTS / MASTER BRIEF — STUDIO KONTEN TERPADU (TERHUBUNG KE POHON PENGETAHUAN)

Dokumen ini adalah panduan arsitektur, aturan kerja, dan rangkuman pengalaman nyata dari pengembangan **Pohon Pengetahuan** (`c:\dev\pohon pengetahuan`) agar agen AI di workspace baru (`c:\dev\studio-konten`) dapat langsung membangun **Studio Konten Viral Mandiri** dengan benar, cepat, gratis, dan bebas kesalahan berulang.

---

## 1. Visi & Arsitektur Hub-and-Spoke ("Terowongan ke Otak Besar")

```
[ c:\dev\pohon pengetahuan ]  <─── baca read-only (.indeks.db / kartu/ / .env) ───  [ c:\dev\studio-konten ]
  • Otak Besar (Ilmu Sosmed,                                                          • Modul 1: Berita/Link -> Gambar PNG + Caption Viral
    Komunikasi, Video AI, Tone,                                                       • Modul 2: YouTube -> Momen Viral + Potong 9:16 (ffmpeg)
    Bisnis, Kesehatan, dll.)                                                          • Output MP4/PNG (terisolasi, tidak mengotori repo Otak)
```

### Keputusan Hosting Terbaik: **Local-First (`127.0.0.1:8788`)**
- **Mengapa Localhost (bukan full Vercel)?** Pemotongan video (`yt-dlp` + `ffmpeg`) membutuhkan biner lokal, penyimpanan MP4 ratusan MB, dan waktu render >10 detik (Vercel Serverless memiliki batas timeout & filesystem *read-only*).
- **Akses dari HP / Online Opsional:** Untuk modul ringan (Generator Berita $\rightarrow$ Caption & Gambar Canvas), arsitekturnya tetap memakai **HTML/CSS/JS murni + Serverless API** sehingga *mudah* di-deploy ke Vercel jika suatu saat dibutuhkan, sementara dapur video berjalan mulus di laptop via 1-klik `tombol-cepat/1-Buka-Studio-Konten.bat`.

---

## 2. Kontrak "Terowongan" ke Otak Besar (`c:\dev\pohon pengetahuan`)

Agen **DILARANG** mengubah atau menulis langsung ke folder `c:\dev\pohon pengetahuan`. Hubungan bersifat **100% Read-Only**:
1. **Membaca Kartu Ilmu:**
   - Baca langsung dari `c:\dev\pohon pengetahuan\data.json` atau query SQLite FTS5 + Trigram di `c:\dev\pohon pengetahuan\.indeks.db` (tabel `kartu_meta`, `kartu_fts`, `kartu_trigram`).
   - **WAJIB kecualikan** kartu dengan `status != 'aktif'` dan cabang `kliping-hiburan`.
   - **Prioritas Cabang Otak untuk Studio Konten:**
     - `sosmed` (algoritma X/TikTok/YT, *mutual reply*, *copy-link share*, hook)
     - `ai/video-dan-clipping` (editing, voiceover, anti-flag AI, CapCut)
     - `ai/tulisan-dan-artikel` (*tone-of-voice*, anti-AI-slop)
     - `digital-marketing` (copywriting, CTR, persuasi)
     - `relasi` & `motivasi-dan-mindset` (psikologi audiens & strategi komunikasi)
2. **Berbagi API Key Gratis (Tanpa Duplikasi Rahasia):**
   - Boleh membaca `.env` lokal sendiri, dengan fallback otomatis membaca `c:\dev\pohon pengetahuan\.env` (JANGAN pernah commit `.env` ke Git!).

---

## 3. Pelajaran Penting dari Pengalaman Sebelumnya (WAJIB DIPATUHI)

Pelajaran keras yang sudah teruji di lapangan agar agen baru tidak membuang waktu mengulang bug yang sama:
1. **Model AI Gratis & Cascade 6 Penyedia (0 Biaya, Tanpa Kartu Kredit):**
   - Gunakan urutan cascade otomatis:
     1. **Google Gemini:** `gemini-3.5-flash-lite` (fallback `gemini-2.5-flash`). **PENTING:** `gemini-2.5-flash-lite` sudah *deprecated* (HTTP 404). **JANGAN** mengirim `thinkingConfig` ke `gemini-3.5-flash-lite` (akan memicu HTTP 400 `INVALID_ARGUMENT`). Selalu set `maxOutputTokens >= 2048` agar output model *thinking* tidak terpotong di tengah kalimat.
     2. **Groq:** `https://api.groq.com/openai/v1/chat/completions` (`llama-3.3-70b-versatile` $\rightarrow$ `llama-3.1-8b-instant`).
     3. **OpenRouter:** `https://openrouter.ai/api/v1/chat/completions` (`openrouter/free` + header `HTTP-Referer` & `X-Title`).
     4. **Mistral:** `mistral-small-latest` (hati-hati: butuh aktivasi Experiment Plan gratis, jika HTTP 402 langsung skip).
     5. **Cerebras:** `llama-3.3-70b`.
     6. **NVIDIA NIM:** `meta/llama-3.3-70b-instruct`.
2. **Satu Panggilan JSON Terstruktur:** Jangan memanggil AI berkali-kali per item. Gabungkan analisis + penulisan skrip + hook + caption + teks slide dalam **1x panggilan JSON** (`responseMimeType: "application/json"`).
3. **Anti-Halusinasi & Jejak Ilmu:** Setiap strategi/hook yang dihasilkan AI wajib mencantumkan sitasi kartu ilmu dari Pohon Pengetahuan (mis. `[K-0011]`, `[K-0022]`) agar pengguna tahu alasan rasional di balik desain kontennya.
4. **Penarikan Sumber Tangguh (0 Biaya):**
   - YouTube: HTML `captionTracks` + fallback **YouTube Innertube Player API (`ANDROID` client)** untuk transkrip bertimestamp `[mm:ss]`.
   - Artikel Web: *Text-to-Tag Density* boilerplate removal.
   - X / X Articles: FxTwitter API (`tweet.text`, `tweet.article.content.blocks`, `tweet.quote`).
5. **Desain UI & Kemudahan Pengguna:**
   - Gaya seragam: **Playful Neo-Brutalisme** (latar kertas hangat `#faf6ed`, border hitam pekat `2px`, bayangan solid `3px 3px 0`, aksen kuning `#fbbf24`, tema Terang/Gelap).
   - Bahasa Indonesia sederhana, anti-jargon, dan **setiap fitur wajib punya tombol bantuan `? Cara Pakai`** (laci tutorial ringkas).
   - Sediakan folder **`tombol-cepat/`** berisi `.bat` 1-klik untuk membuka aplikasi di browser tanpa mengetik perintah terminal.

---

## 4. Dua Modul Utama & Tahapan Pengerjaan

### Modul A — Berita / Link $\rightarrow$ Gambar Carousel & Caption Viral (Fase 1 · Paling Cepat & Ringan)
- **Input:** 1 URL berita / artikel / teks mentah + pilih platform target (`X Thread`, `Instagram Carousel`, `Threads`, `LinkedIn`, `TikTok Script`).
- **Proses Otak:** Ambil Top-6 kartu strategi komunikasi/viral/tone-of-voice dari `pohon pengetahuan` $\rightarrow$ 1-call AI JSON menghasilkan:
  1. **3 Variasi Hook** (dengan skor & alasan berbasis kartu `[K-XXXX]`).
  2. **Caption / Thread Utuh** siap salin (dengan CTA pemicu *mutual reply* & *share*).
  3. **Konten Visual 1–5 Slide** (judul besar, poin inti, kutipan, sumber berita, watermark akun).
- **Render Gambar 100% Gratis:** Render langsung di browser menggunakan **HTML5 Canvas / SVG-to-PNG** (`1080×1350` portrait IG/Threads atau `1200×675` X) dengan 3 preset gaya (*Editorial News*, *Neo-Brutalist Card*, *Minimalist Dark*) + tombol **Unduh PNG** instan!

### Modul B — YouTube $\rightarrow$ Pencari Momen Viral & Pemotong Video 9:16 (Fase 2)
- **Input:** URL YouTube (atau file MP4 lokal).
- **Tahap 1 (Otak — 0 Biaya):** Tarik transkrip bertimestamp `[mm:ss]` $\rightarrow$ AI + kartu `sosmed` & `ai/video-dan-clipping` memilih **Top-3 segmen 30–60 detik** paling potensial viral, lengkap dengan:
  - `mulai` (`mm:ss`), `selesai` (`mm:ss`), skor potensi viral, alasan.
  - **Teks Hook Overlay** 3 detik pertama, **narasi tambahan / komentar reaksi**, dan **caption posting**.
- **Tahap 2 (Render Lokal — 0 Biaya):** Jika `yt-dlp` & `ffmpeg` tersedia di laptop, tombol **1-Klik Potong & Render 9:16** otomatis memotong persis di timestamp, crop vertikal `9:16` (1080×1920), membakar subtitle `.srt` yang rapi, dan menyimpan MP4 ke folder `output-video/` (diabaikan `.gitignore`).

---

## 5. Aturan Kualitas, Privasi & Disiplin
- **Privasi:** `persona.md` dan folder `jurnal/` milik Pohon Pengetahuan **tidak pernah** dikirim keluar ke internet atau dipakai untuk konten publik.
- **Zero Dependency Berat di Core:** Backend utama pakai Python 3.13 standard library (`http.server`, `sqlite3`, `urllib.request`, `subprocess`); `yt-dlp` & `ffmpeg` dipanggil opsional lewat `subprocess` dengan pengecekan otomatis (*graceful fallback* ke mode skrip + timestamp bila belum terpasang).
- **Log & Uji:** Catat setiap perubahan di `log.md`, siapkan skrip uji otomatis, dan buat 1 commit Git per fase.

---

### 💬 Prompt Siap Pakai untuk Memulai di Workspace Baru (`c:\dev\studio-konten`)
> *"Baca file `BRIEF-STUDIO-KONTEN.md` seluruhnya. Kita akan membangun `studio-konten` di folder ini yang terhubung read-only ke Otak Besar di `c:\dev\pohon pengetahuan`. Mulai dari **Fase 1 (Fondasi server lokal `127.0.0.1:8788`, jembatan read-only ke `.indeks.db` Pohon Pengetahuan, dan Modul A: Berita/Link $\rightarrow$ Gambar PNG Canvas + Caption Viral)** dengan gaya Neo-Brutalisme dan tombol `? Cara Pakai`."*
