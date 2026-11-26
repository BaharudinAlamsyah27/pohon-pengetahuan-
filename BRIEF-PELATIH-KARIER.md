# AGENTS / MASTER BRIEF — PELATIH KARIER & KURIKULUM LINTAS PROFESI (TERHUBUNG KE POHON PENGETAHUAN)

Dokumen ini adalah panduan arsitektur, aturan kerja, dan rangkuman pengalaman teknis dari **Pohon Pengetahuan** (`c:\dev\pohon pengetahuan`) agar agen AI di workspace baru (`c:\dev\pelatih-karier`) dapat langsung membangun **Sistem Pelatih Karier, Bank Soal CAT & Kurikulum Universal** (CPNS/ASN, Programmer, Beasiswa, Imam/Dakwah, dll.) yang 100% gratis, terstruktur, dan terhubung *read-only* ke Otak Besar.

---

## 1. Visi & Arsitektur Hub-and-Spoke ("Terowongan Kurikulum Otomatis")

```
[ c:\dev\pohon pengetahuan ]  <─── baca read-only (.indeks.db / kartu/ / jurnal/ / .env) ───  [ c:\dev\pelatih-karier ]
  • Sumber PDF Bank Soal,                                                                        • Auto-Router ke Jalur Profesi & Sub-Bab
    Video YouTube, Tips X,                                                                       • Arena Tryout CAT (Timer + Passing Grade)
    Kartu Ilmu & Jurnal Nyata                                                                    • Mock Interview & Generator CV/Esai Nyata
                                                                                                 • Radar Kesiapan & Peta Penguasaan Materi
```

### Prinsip Utama: **Universal Lintas Profesi + Fokus Dekat CPNS**
Sistem **tidak terkunci** pada 1 profesi saja, melainkan modular dengan jalur profesi yang bisa ditambah kapan saja:
1. **`cpns-asn`** *(Prioritas Pertama — persiapan pendaftaran CPNS terdekat)*:
   - Sub-bab baku: `twk` (Nasionalisme, Integritas, Bela Negara, Pilar Negara, Bahasa), `tiu` (Verbal/Silogisme, Numerik/Deret, Figural), `tkp` (Pelayanan Publik, Jejaring Kerja, Sosial Budaya, TIK, Profesionalisme, Anti-Radikalisme), `skb` (Kompetensi Bidang TI/Umum), `strategi-pemberkasan`.
2. **`programmer-tech`**:
   - Sub-bab: `algoritma-struktur-data`, `web-fullstack`, `system-design`, `ai-engineering`, `live-coding-interview`.
3. **`beasiswa`**:
   - Sub-bab: `esai-kontribusi`, `wawancara-substansi`, `bahasa-ielts-toefl`, `riset-kampus-loa`.
4. **`imam-dan-dakwah`**:
   - Sub-bab: `tajwid-hafalan`, `fiqih-ibadah`, `retorika-khutbah`, `pembinaan-umat`.
5. **`umum-softskill`**:
   - Sub-bab: `cv-ats-portofolio`, `wawancara-hr`, `negosiasi-komunikasi`, `kepemimpinan`.

### Keputusan Hosting: **Local-First (`127.0.0.1:8790`)**
- 100% privat di laptop (karena membaca `persona.md` & `jurnal/` untuk menyusun CV/esai nyata serta menyimpan skor latihan pribadi).
- Dijalankan 1-klik lewat `tombol-cepat/1-Buka-Pelatih-Karier.bat`.

---

## 2. Kontrak "Terowongan" & Auto-Router Cerdas (Tidak Acak!)

Agen **DILARANG** mengubah file di dalam `c:\dev\pohon pengetahuan`. Hubungan bersifat **100% Read-Only**:
1. **Sumber Bahan Masuk:**
   - Membaca kartu aktif dari `c:\dev\pohon pengetahuan\data.json` / `.indeks.db` (kecualikan `kliping-hiburan` dan `status != 'aktif'`).
   - Membaca bukti pencapaian nyata dari `c:\dev\pohon pengetahuan\jurnal/` (khusus untuk Modul Esai/CV/Wawancara).
   - Membaca API key gratis dari `.env` lokal dengan fallback ke `c:\dev\pohon pengetahuan\.env`.
2. **Auto-Router Terstruktur (`sync_from_pohon()`):**
   - Setiap kartu/PDF/transkrip baru dari Pohon Pengetahuan yang relevan dengan karier/belajar otomatis dipetakan (1-call JSON AI + fallback kamus offline) ke **4 atribut baku** dan disimpan indeksnya di SQLite lokal `pelatih.db`:
     - **`jalur`**: `cpns-asn` | `programmer-tech` | `beasiswa` | `imam-dan-dakwah` | `umum-softskill` | *(custom)*
     - **`sub_bab`**: mis. `cpns-asn/tiu-silogisme`, `programmer-tech/system-design`, `imam-dan-dakwah/fiqih-ibadah`
     - **`tipe_aset`**:
       - `bank-soal` (soal pilihan ganda A–E + kunci jawaban + pembahasan langkah demi langkah)
       - `materi-inti` (konsep, rumus cepat, dalil/hafalan, kerangka berpikir)
       - `tips-rahasia` (trik cepat lulus, jebakan soal, strategi skor tinggi)
       - `skenario-wawancara` (pertanyaan wawancara + kerangka jawaban STAR)
     - **`tingkat`**: `dasar` | `menengah` | `lanjut`

---

## 3. Empat Modul Utama & Tahapan Pengerjaan

### Fase 1 — Fondasi, Auto-Router & Peta Kurikulum Sub-Bab
- Server lokal Python 3.13 (`127.0.0.1:8790`, 0 dependensi berat) + SQLite (`pelatih.db`).
- Tombol **🔄 Sinkronkan dari Pohon Pengetahuan** yang otomatis menyedot kartu baru (`kesuksesan`, `agama`, `ai/coding-dan-proyek`, `relasi`, `motivasi-dan-mindset`, dll.) dan menempatkannya rapi ke **Jalur $\rightarrow$ Sub-Bab $\rightarrow$ Tipe Aset** (bukan daftar acak!).
- Tampilan **Peta Kurikulum**: kartu progres per sub-bab, filter per profesi & tipe aset (`Materi`, `Tips Rahasia`, `Bank Soal`), plus form cepat input **Soal / PDF Tryout** langsung.

### Fase 2 — Arena Tryout CAT & Bank Soal Adaptif (SM-2)
- **Mode Latihan / Tryout CAT** (terutama CPNS: simulasi timer + skor TWK / TIU / TKP + indikator *Passing Grade*; juga mendukung kuis *Programmer* / *Fiqih* / *Umum*).
- AI dapat **mengubah kartu `materi-inti` dari Pohon Pengetahuan menjadi soal latihan baru** (1-call JSON) jika bank soal di suatu sub-bab masih sedikit.
- **Pelacak Kelemahan Otomatis (Spaced Repetition SM-2):** Soal yang salah dijawab otomatis masuk antrean ulang lebih cepat dan menandai sub-bab mana yang masih merah/lemah!

### Fase 3 — Simulator Wawancara (*Mock Interview*) & Generator Esai/CV Nyata
- **Mock Interview Interaktif:** Pilih jalur (`Wawancara CPNS/SKB`, `Tech Interview Programmer`, `Beasiswa LPDP`, `Tanya Jawab Keagamaan`) $\rightarrow$ AI berperan sebagai penguji tegas, memberi skor 1–10, dan memperbaiki jawaban dengan metode **STAR**.
- **Generator Esai & CV Anti-Halusinasi:** Menarik bukti proyek & pencapaian nyata dari `jurnal/` Pohon Pengetahuan + `persona.md` sehingga esai/CV 100% jujur berbasis pengalaman asli pengguna.

### Fase 4 — Radar Kesiapan & Target H-XX
- Penghitung mundur target (mis. `H-45 Pendaftaran CPNS`), grafik tren nilai Tryout per minggu, dan rekomendasi **30 menit belajar hari ini** (fokus pada sub-bab terlemah).

---

## 4. Pelajaran Teknis Wajib dari Pohon Pengetahuan
1. **Cascade 6 Penyedia AI Gratis (0 Biaya, Tanpa Kartu Kredit):**
   - Urutan: `GEMINI_API_KEY` (`gemini-3.5-flash-lite` $\rightarrow$ `gemini-2.5-flash`) $\rightarrow$ `GROQ_API_KEY` (`llama-3.3-70b-versatile`) $\rightarrow$ `OPENROUTER_API_KEY` (`openrouter/free`) $\rightarrow$ `MISTRAL_API_KEY` (skip jika HTTP 402) $\rightarrow$ `CEREBRAS_API_KEY` $\rightarrow$ `NVIDIA_API_KEY`.
   - **WAJIB:** Jangan pakai `gemini-2.5-flash-lite` (deprecated 404); **JANGAN** kirim `thinkingConfig` ke `gemini-3.5-flash-lite` (HTTP 400); selalu pakai `maxOutputTokens >= 2048`.
2. **Desain UI Seragam:** **Playful Neo-Brutalisme** (krem kertas `#faf6ed`, border hitam `2px`, shadow solid `3px 3px 0`, aksen kuning `#fbbf24`, tema Terang/Gelap), Bahasa Indonesia sederhana, tombol **`? Cara Pakai`** di setiap menu, dan folder **`tombol-cepat/`**.
3. **Privasi & Kualitas:** `persona.md` & `jurnal/` **tidak pernah** dipublikasikan; catat setiap aksi di `log.md`; buat skrip uji otomatis (`scripts/uji_kurikulum.py`) dan commit Git tiap fase.

---

### 💬 Prompt Siap Pakai untuk Memulai di Workspace Baru (`c:\dev\pelatih-karier`)
> *"Baca file `BRIEF-PELATIH-KARIER.md` seluruhnya. Kita akan membangun `pelatih-karier` di folder ini yang terhubung read-only ke `c:\dev\pohon pengetahuan`. Mulai dari **Fase 1 (Server lokal `127.0.0.1:8790`, Auto-Router cerdas yang memetakan kartu Pohon Pengetahuan ke Jalur Profesi -> Sub-Bab -> Tipe Aset [Bank Soal / Materi / Tips Rahasia], Peta Kurikulum dengan prioritas CPNS + dukungan lintas profesi Programmer/Beasiswa/Imam, UI Neo-Brutalisme, dan tombol `? Cara Pakai`)**."*
