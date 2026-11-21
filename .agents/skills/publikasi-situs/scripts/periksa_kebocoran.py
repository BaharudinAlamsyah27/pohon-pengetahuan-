#!/usr/bin/env python3
"""Pemeriksa kebocoran sebelum PUBLIKASI. Exit 1 bila ada GAGAL."""
import argparse, html, re, sys
from pathlib import Path

TEKS = {".html", ".json", ".js", ".css", ".md", ".txt", ".xml"}
TERLARANG = {"persona.md", "log.md", "agents.md"}
FIELD_PRIBADI = ("penerapan-catatan", "terakhir-ditinjau", "penerapan:")

def kata(t):
    return re.findall(r"\w+", html.unescape(re.sub(r"<[^>]+>", " ", t)).lower())

def shingles(w, n):
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}

def tubuh(t):
    if t.startswith("---"):
        p = t.split("---", 2)
        if len(p) == 3:
            return p[2]
    return t

def teks_asli(t):
    m = re.search(r"^## Teks Asli\s*$", t, re.M)
    return t[m.end():] if m else ""

def runs(w, sset, n):
    cocok = [" ".join(w[i:i + n]) in sset for i in range(len(w) - n + 1)]
    out, i = [], 0
    while i < len(cocok):
        if cocok[i]:
            j = i
            while j + 1 < len(cocok) and cocok[j + 1]:
                j += 1
            out.append((i, j - i + n))
            i = j + 1
        else:
            i += 1
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--situs", default="situs")
    ap.add_argument("--persona", default="persona.md")
    ap.add_argument("--sumber", default="sumber")
    a = ap.parse_args()
    situs = Path(a.situs)
    if not situs.is_dir():
        sys.exit(f"Folder situs tidak ada: {situs}")
    gagal, periksa = [], []
    berkas = [p for p in situs.rglob("*") if p.is_file()]
    for p in berkas:
        bagian = {x.lower() for x in p.relative_to(situs).parts}
        if p.name.lower() in TERLARANG or "sumber" in bagian or ".git" in bagian:
            gagal.append(f"Berkas terlarang di situs: {p}")
    isi = {p: p.read_text(encoding="utf-8", errors="ignore")
           for p in berkas if p.suffix.lower() in TEKS}
    for p, t in isi.items():
        for f in FIELD_PRIBADI:
            if f in t:
                gagal.append(f"Field pribadi '{f}' ada di {p}")
    kata_situs = {p: kata(t) for p, t in isi.items()}

    pp = Path(a.persona)
    if pp.is_file():
        baris = [l for l in tubuh(pp.read_text(encoding="utf-8")).splitlines()
                 if l.strip() and not l.lstrip().startswith(("#", "<"))]
        teks_p = "\n".join(baris)
        ps = shingles(kata(teks_p), 5)
        angka = set(re.findall(r"\d[\d.,]{3,}\d", teks_p))
        for p, w in kata_situs.items():
            hit = ps & shingles(w, 5)
            if hit:
                gagal.append(f"Frasa persona muncul di {p}: '{sorted(hit)[0]}'")
            for g in angka:
                if g in isi[p]:
                    periksa.append(f"Angka dari persona ('{g}') muncul di {p}")

    sd = Path(a.sumber)
    if sd.is_dir():
        for sp in sorted(sd.glob("S-*.md")):
            w_s = kata(teks_asli(sp.read_text(encoding="utf-8")))
            if len(w_s) < 12:
                continue
            sset = shingles(w_s, 12)
            for p, w in kata_situs.items():
                for mulai, panjang in runs(w, sset, 12):
                    cuplikan = " ".join(w[mulai:mulai + 12])
                    pesan = f"{panjang} kata identik dengan {sp.name} di {p}: '{cuplikan}...'"
                    (gagal if panjang >= 25 else periksa).append(pesan)

    for g in gagal:
        print("GAGAL  :", g)
    for q in periksa:
        print("PERIKSA:", q)
    if not gagal and not periksa:
        print("BERSIH : tidak ada temuan.")
    elif not gagal:
        print("Tidak ada GAGAL; tinjau temuan PERIKSA di atas.")
    sys.exit(1 if gagal else 0)

if __name__ == "__main__":
    main()
