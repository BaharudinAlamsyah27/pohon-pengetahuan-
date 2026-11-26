#!/usr/bin/env python3
"""
Penarik isi link lokal untuk Pohon Pengetahuan (zero external dependencies).
Hanya dijalankan atas permintaan eksplisit pengguna (AGENTS.md Bagian 14 & 21).

Mendukung:
  - X / Twitter publik (via endpoint oEmbed resmi publish.twitter.com)
  - YouTube (judul, kanal, + transkrip/subtitle bila tersedia publik)
  - Artikel web / blog / berita (ekstraksi teks bersih dari HTML)
  - Facebook / Instagram / Threads: mengarahkan ke Bookmarklet 1-Klik agar tidak kena blokir login.
"""

from __future__ import annotations

import argparse
import base64
import html as html_lib
import ipaddress
import json
import math
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PohonPengetahuan/1.0"
MAX_BYTES = 2 * 1024 * 1024  # 2 MB
TIMEOUT = 10


def detect_platform(url: str) -> str:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if any(d in host for d in ("x.com", "twitter.com")):
        return "X"
    if any(d in host for d in ("youtube.com", "youtu.be")):
        return "YouTube"
    if any(d in host for d in ("facebook.com", "fb.com", "fb.watch", "m.facebook.com")):
        return "Facebook"
    if "instagram.com" in host:
        return "Instagram"
    if "threads.net" in host or "threads.com" in host:
        return "Threads"
    if "tiktok.com" in host:
        return "TikTok"
    if "linkedin.com" in host:
        return "LinkedIn"
    return "web"


def validate_public_url(url: str) -> tuple[bool, str]:
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        return False, "URL harus diawali http:// atau https://"
    host = parsed.hostname
    if not host:
        return False, "Host URL tidak valid"
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(host))
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False, "Akses ke alamat jaringan lokal/privat diblokir demi keamanan"
    except Exception:
        pass
    return True, ""


def http_get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "id,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read(MAX_BYTES)
        charset = resp.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def strip_html_tags(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</p\s*>", "\n\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html_lib.unescape(s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _load_local_gemini_key() -> tuple[str, str]:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_MODEL", "").strip()
    env_fp = Path(__file__).resolve().parent.parent / ".env"
    if env_fp.exists():
        for line in env_fp.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k == "GEMINI_API_KEY" and not api_key:
                api_key = v
            elif k == "GEMINI_MODEL" and not model:
                model = v
    return api_key, (model or "gemini-2.5-flash")


def _fetch_fxtwitter_raw(user: str, status_id: str) -> dict | None:
    api_url = f"https://api.fxtwitter.com/{user}/status/{status_id}"
    data = json.loads(http_get_text(api_url))
    tw = data.get("tweet")
    return tw if isinstance(tw, dict) else None


def fetch_x_fxtwitter(url: str) -> dict | None:
    """
    Ambil teks penuh postingan X (termasuk long-form >280 karakter) via API publik FxTwitter.
    Fitur tambahan:
      1. Otomatis melacak thread berantai ke atas (self-reply) hingga 15 tweet jika ditempel link tweet akhir.
      2. Otomatis membaca teks/infografis dari foto lampiran tweet (via altText / Tesseract / Gemini Vision Gratis).
    """
    m = re.search(r"(?:x\.com|twitter\.com)/([^/]+)/status/(\d+)", url)
    if not m:
        return None
    user, status_id = m.group(1), m.group(2)
    tw = _fetch_fxtwitter_raw(user, status_id)
    if not tw:
        return None

    author = tw.get("author") or {}
    name = author.get("name") or user
    screen = (author.get("screen_name") or user).lower()
    penulis = f"{name} (@{author.get('screen_name') or user})"

    # 1. Telusuri thread berantai ke atas jika penulis membalas tweetnya sendiri (maks 15 tweet)
    chain = [tw]
    visited = {str(tw.get("id") or status_id)}
    curr = tw
    for _ in range(14):
        parent_id = str(curr.get("replying_to_status") or "").strip()
        parent_user = str(curr.get("replying_to") or "").strip().lower()
        if not parent_id or parent_id in visited or (parent_user and parent_user != screen):
            break
        try:
            ptw = _fetch_fxtwitter_raw(parent_user or screen, parent_id)
        except Exception:
            break
        if not ptw:
            break
        p_screen = str((ptw.get("author") or {}).get("screen_name") or "").lower()
        if p_screen and p_screen != screen:
            break
        visited.add(parent_id)
        chain.append(ptw)
        curr = ptw

    chain.reverse()  # Urutkan dari tweet pertama (1/N) ke terakhir

    text_blocks: list[str] = []
    photo_items: list[tuple[str, str]] = []  # (url, altText)
    for idx, item in enumerate(chain, 1):
        t = (item.get("text") or "").strip()
        if t:
            prefix = f"[{idx}/{len(chain)}] " if len(chain) > 1 else ""
            text_blocks.append(f"{prefix}{t}")
        photos = ((item.get("media") or {}).get("photos") or [])
        for ph in photos:
            if isinstance(ph, dict) and ph.get("url") and len(photo_items) < 4:
                photo_items.append((ph["url"], (ph.get("altText") or "").strip()))

    teks = "\n\n".join(text_blocks).strip()
    if not teks and not photo_items:
        return None

    # 2. Ekstrak teks dari foto lampiran (maks 4 foto) memakai altText atau Gemini Vision / Tesseract
    ocr_blocks: list[str] = []
    api_key, _ = _load_local_gemini_key()
    for p_idx, (p_url, alt_txt) in enumerate(photo_items, 1):
        extracted = ""
        if alt_txt and len(alt_txt) >= 15:
            extracted = alt_txt
        else:
            try:
                req = urllib.request.Request(p_url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    raw_img = resp.read(MAX_BYTES)
                    ctype = (resp.headers.get("Content-Type") or "image/jpeg").split(";")[0].strip()
                ocr_res = extract_text_from_image(raw_img, ctype, api_key=api_key)
                if ocr_res.get("ok") and ocr_res.get("teks_asli"):
                    extracted = ocr_res["teks_asli"].strip()
            except Exception:
                pass
        if extracted:
            ocr_blocks.append(f"--- Isi Teks dari Foto ({p_idx}/{len(photo_items)}) ---\n{extracted}")
        else:
            ocr_blocks.append(f"--- Lampiran Foto ({p_idx}/{len(photo_items)}) ---\n{p_url}")

    if ocr_blocks:
        teks = (teks + "\n\n" + "\n\n".join(ocr_blocks)).strip()

    first_line = (teks.splitlines()[0] if teks else f"Postingan {penulis}")[:90]
    notes = ["Teks penuh berhasil ditarik."]
    if len(chain) > 1:
        notes.append(f"Thread utuh {len(chain)} tweet berhasil digabung otomatis.")
    if photo_items:
        notes.append(f"{len(photo_items)} foto lampiran ikut diproses.")
    return {
        "ok": True,
        "platform": "X",
        "jenis": "postingan",
        "judul": first_line,
        "penulis": penulis,
        "url": url,
        "teks_asli": teks,
        "peringatan": " ".join(notes),
    }


def fetch_x_oembed(url: str) -> dict:
    try:
        full = fetch_x_fxtwitter(url)
        if full:
            return full
    except Exception:
        pass
    oembed_url = "https://publish.twitter.com/oembed?omit_script=true&url=" + urllib.parse.quote(url, safe="")
    data = json.loads(http_get_text(oembed_url))
    author = data.get("author_name") or "tidak diketahui"
    author_url = data.get("author_url") or ""
    handle = author_url.rstrip("/").split("/")[-1] if author_url else ""
    penulis = f"{author} (@{handle})" if handle else author
    raw_html = data.get("html") or ""
    teks = strip_html_tags(raw_html)
    first_line = teks.splitlines()[0][:72] if teks else f"Postingan {penulis}"
    return {
        "ok": True,
        "platform": "X",
        "jenis": "postingan",
        "judul": first_line,
        "penulis": penulis,
        "url": url,
        "teks_asli": teks,
        "peringatan": "Diambil via oEmbed X (postingan >280 karakter terpotong). Gunakan Bookmarklet 1-Klik di halaman X untuk teks penuh.",
    }


def fetch_youtube(url: str) -> dict:
    page = http_get_text(url)
    title_m = re.search(r"<title>(.*?)</title>", page, re.S | re.I)
    judul = html_lib.unescape(title_m.group(1)).replace(" - YouTube", "").strip() if title_m else "Video YouTube"
    author_m = re.search(r'"author":"([^"]+)"', page)
    penulis = author_m.group(1) if author_m else "tidak diketahui"

    # Cari captionTracks publik untuk transkrip (prioritas id lalu en)
    transcript = ""
    note = ""
    tracks_m = re.search(r'"captionTracks":(\[.*?\])', page)
    if tracks_m:
        try:
            tracks = json.loads(tracks_m.group(1))
            chosen = None
            for lang in ("id", "en"):
                chosen = next((t for t in tracks if str(t.get("languageCode", "")).startswith(lang)), None)
                if chosen:
                    break
            if not chosen and tracks:
                chosen = tracks[0]
            if chosen and chosen.get("baseUrl"):
                xml_txt = http_get_text(chosen["baseUrl"])
                root = ET.fromstring(xml_txt)
                lines = []
                for elem in root.findall(".//text"):
                    start = float(elem.attrib.get("start", "0"))
                    mm, ss = divmod(int(start), 60)
                    txt = html_lib.unescape("".join(elem.itertext())).replace("\n", " ").strip()
                    if txt:
                        lines.append(f"[{mm:02d}:{ss:02d}] {txt}")
                transcript = "\n".join(lines)
                note = f"Transkrip berhasil ditarik (bahasa: {chosen.get('languageCode', '?')})."
        except Exception as exc:
            note = f"Subtitle terdeteksi tetapi gagal diurai ({exc}). Tempel transkrip manual."
    else:
        note = "Subtitle/transkrip publik tidak tersedia pada video ini. Silakan salin transkrip dari YouTube lalu tempel."

    return {
        "ok": True,
        "platform": "YouTube",
        "jenis": "transkrip-video",
        "judul": judul,
        "penulis": penulis,
        "url": url,
        "teks_asli": transcript,
        "peringatan": note,
    }


def extract_dense_article_text(page: str) -> str:
    """
    Algoritma Text-to-Tag Density & Link-Density Boilerplate Removal (Kohlschütter et al.).
    Menilai setiap blok DOM dari kepadatan kata vs tag HTML dan rasio kata di dalam <a href>:
      Density(B) = (Words / max(1, Tags)) * (1 - LinkWords / max(1, Words))
    Blok menu, navigasi, footer, dan iklan otomatis terbuang tanpa API berbayar.
    """
    cleaned = re.sub(
        r"<(script|style|noscript|nav|footer|header|aside|form|svg|button|iframe)\b[^>]*>.*?</\1>",
        " ",
        page,
        flags=re.S | re.I,
    )
    art_m = re.search(r"<(article|main)\b[^>]*>(.*?)</\1>", cleaned, flags=re.S | re.I)
    scope = art_m.group(2) if art_m else cleaned

    raw_blocks = re.findall(r"<(p|li|blockquote|h[1-4]|pre)\b[^>]*>(.*?)</\1>", scope, flags=re.S | re.I)
    kept_blocks: list[str] = []
    seen_norm: set[str] = set()

    for tag_name, inner in raw_blocks:
        tag_count = len(re.findall(r"<[^>]+>", inner)) + 1
        link_texts = " ".join(strip_html_tags(a) for a in re.findall(r"<a\b[^>]*>(.*?)</a>", inner, flags=re.S | re.I))
        plain = re.sub(r"\s+", " ", strip_html_tags(inner)).strip()
        words = plain.split()
        w_cnt = len(words)
        if w_cnt < 5 and not tag_name.lower().startswith("h"):
            continue
        link_w_cnt = len(link_texts.split())
        link_ratio = link_w_cnt / max(1, w_cnt)
        density = (w_cnt / max(1, tag_count)) * (1.0 - link_ratio)
        # Filter boilerplate: link density tinggi (>0.55) atau densitas teks terlalu rendah
        if link_ratio > 0.55 or (density < 1.2 and not tag_name.lower().startswith("h")):
            continue
        norm_key = plain.lower()[:120]
        if norm_key in seen_norm:
            continue
        seen_norm.add(norm_key)
        kept_blocks.append(plain)

    if not kept_blocks:
        # Fallback jika halaman memakai <div> tanpa <p>
        paras = [strip_html_tags(p) for p in re.findall(r"<div\b[^>]*>([^<]{40,})</div>", scope, flags=re.S | re.I)]
        kept_blocks = [re.sub(r"\s+", " ", p).strip() for p in paras if len(p.split()) >= 7]

    return "\n\n".join(kept_blocks[:140])


def chase_embedded_links(teks: str, origin_url: str = "", max_chase: int = 2) -> tuple[str, list[str]]:
    """
    Recursive Link Chasing (1-hop): jika postingan sosmed menyuruh membuka link artikel/video
    eksternal di dalam teksnya, tarik otomatis isi artikel/transkrip tersebut.
    """
    urls = re.findall(r"https?://[^\s)\]>\"']+", teks or "")
    chased_sections: list[str] = []
    chased_urls: list[str] = []
    skip_ext = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".mp4", ".pdf")

    for u in urls:
        u_clean = u.rstrip(".,;:!?")
        if u_clean == origin_url or u_clean in chased_urls:
            continue
        low_u = u_clean.lower()
        if any(low_u.endswith(ext) for ext in skip_ext):
            continue
        host = (urllib.parse.urlparse(u_clean).hostname or "").lower()
        # Lewati self-link status X atau gambar pic.twitter
        if any(h in host for h in ("pic.twitter.com", "pbs.twimg.com", "x.com", "twitter.com")):
            continue
        valid, _ = validate_public_url(u_clean)
        if not valid:
            continue
        try:
            plat = detect_platform(u_clean)
            if plat == "YouTube":
                sub_res = fetch_youtube(u_clean)
            elif plat == "web":
                sub_res = fetch_web_article(u_clean, chase=False)
            else:
                continue
            sub_txt = (sub_res.get("teks_asli") or "").strip()
            if sub_res.get("ok") and len(sub_txt) >= 60:
                chased_urls.append(u_clean)
                chased_sections.append(
                    f"--- Ekstraksi Otomatis Tautan Terlampir: {sub_res.get('judul', u_clean)} ({u_clean}) ---\n{sub_txt[:2500]}"
                )
        except Exception:
            continue
        if len(chased_urls) >= max_chase:
            break

    return ("\n\n".join(chased_sections), chased_urls)


def extract_image_text(image_b64: str, mime_type: str = "image/png", api_key: str = "") -> dict:
    """
    Ekstraksi teks & poin dari gambar/infografis/screenshot (100% gratis):
      1. Lapis 1 (Offline 0 Biaya): Tesseract OCR lokal bila terpasang di sistem.
      2. Lapis 2 (Online Free Tier): Gemini 2.5 Flash-Lite Multimodal bila GEMINI_API_KEY tersedia.
    """
    try:
        raw_bytes = base64.b64decode(re.sub(r"^data:[^;]+;base64,", "", image_b64.strip()))
    except Exception:
        return {"ok": False, "error": "Data base64 gambar tidak valid."}

    if len(raw_bytes) > 5 * 1024 * 1024:
        return {"ok": False, "error": "Ukuran gambar maksimal 5 MB."}

    # Lapis 1: Tesseract OCR lokal (0 kuota, 100% offline)
    tess_bin = shutil.which("tesseract")
    if tess_bin:
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                tf.write(raw_bytes)
                tmp_path = tf.name
            try:
                proc = subprocess.run(
                    [tess_bin, tmp_path, "stdout"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                ocr_txt = (proc.stdout or "").strip()
                if len(ocr_txt) >= 15:
                    return {"ok": True, "mode": "tesseract-lokal", "teks_asli": ocr_txt}
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass

    # Lapis 2: Gemini Vision Multimodal (Free Tier)
    if api_key:
        clean_b64 = base64.b64encode(raw_bytes).decode("ascii")
        last_exc = None
        for mdl in ("gemini-2.5-flash-lite", "gemini-2.5-flash"):
            try:
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent?key={api_key}"
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": "Ekstrak seluruh teks penting, angka, dan poin utama dari gambar/infografis ini secara akurat dalam bahasa aslinya (atau Bahasa Indonesia bila berupa diagram). Jangan mengarang."},
                            {"inline_data": {"mime_type": mime_type or "image/png", "data": clean_b64}},
                        ]
                    }],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048},
                }
                req = urllib.request.Request(
                    endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=25) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                cands = data.get("candidates") or []
                if cands:
                    parts = ((cands[0].get("content") or {}).get("parts")) or []
                    out_txt = "\n".join(p.get("text", "") for p in parts if p.get("text")).strip()
                    if out_txt:
                        return {"ok": True, "mode": f"gemini-vision ({mdl})", "teks_asli": out_txt}
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code == 404:
                    continue
                break
            except Exception as exc:
                last_exc = exc
                break
        if last_exc:
            return {"ok": False, "error": f"Gagal membaca gambar via Gemini Vision: {last_exc}"}

    return {
        "ok": False,
        "error": "Untuk membaca gambar gratis: pasang Tesseract OCR lokal (offline) atau isi GEMINI_API_KEY gratis di .env.",
    }


def fetch_web_article(url: str, chase: bool = True) -> dict:
    page = http_get_text(url)
    title_m = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
    judul = html_lib.unescape(re.sub(r"\s+", " ", title_m.group(1))).strip() if title_m else url
    author_m = re.search(r'<meta[^>]+name=["\']author["\'][^>]+content=["\']([^"\']+)["\']', page, re.I)
    penulis = html_lib.unescape(author_m.group(1)).strip() if author_m else (urllib.parse.urlparse(url).hostname or "tidak diketahui")

    teks = extract_dense_article_text(page)

    return {
        "ok": True,
        "platform": "web",
        "jenis": "artikel",
        "judul": judul[:120],
        "penulis": penulis,
        "url": url,
        "teks_asli": teks,
        "peringatan": "Diekstrak dengan Text-to-Tag Density (bebas iklan/menu)." if teks else "Teks utama tidak terdeteksi (kemungkinan halaman butuh JavaScript). Gunakan Bookmarklet 1-Klik di browser.",
    }


def fetch_url(url: str) -> dict:
    url = url.strip()
    valid, err = validate_public_url(url)
    if not valid:
        return {"ok": False, "error": err}

    platform = detect_platform(url)
    if platform in ("Facebook", "Instagram", "Threads", "TikTok", "LinkedIn"):
        return {
            "ok": False,
            "platform": platform,
            "url": url,
            "error": (
                f"{platform} memblokir penarikan link langsung tanpa login. "
                f"Buka postingan di browser Anda, lalu klik Bookmarklet 'Tangkap ke Pohon' (1 klik, tanpa copy-paste)."
            ),
        }

    try:
        if platform == "X":
            res = fetch_x_oembed(url)
        elif platform == "YouTube":
            res = fetch_youtube(url)
        else:
            res = fetch_web_article(url)
        # Recursive Link Chasing: jika postingan sosmed memuat link artikel/video eksternal, tarik isinya
        if res.get("ok") and platform == "X" and res.get("teks_asli"):
            chased_txt, chased_urls = chase_embedded_links(res["teks_asli"], origin_url=url)
            if chased_txt:
                res["teks_asli"] = res["teks_asli"].rstrip() + "\n\n" + chased_txt
                res["peringatan"] = (res.get("peringatan") or "") + f" (+{len(chased_urls)} tautan artikel/video di dalam postingan berhasil diekstrak otomatis)."
        return res
    except Exception as exc:
        return {
            "ok": False,
            "platform": platform,
            "url": url,
            "error": f"Gagal menarik konten ({exc}). Gunakan Bookmarklet 1-Klik di browser atau tempel teks manual.",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Tarik preview teks/transkrip dari URL publik.")
    parser.add_argument("url", help="URL postingan X, YouTube, atau artikel web")
    args = parser.parse_args()
    res = fetch_url(args.url)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
