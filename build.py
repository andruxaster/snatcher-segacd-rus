#!/usr/bin/env python3
"""Russian translation of Snatcher (Sega CD, USA) - build.

    python build.py discs PATH            copy your redump BIN/CUE set into discs/
    python build.py extract               the data track's files -> work/files/
    python build.py build [--probe]       patched/Snatcher (USA).cue + tracks

`build` copies the data track, adds the Cyrillic font (tools/fontpatch.py)
and, with --probe, puts one Russian line in place of Mika's first one
(SP06) - the engine test from the start of the project. The other tracks
(audio) are linked, not copied.
"""
import argparse, hashlib, os, shutil, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "tools"))
DISCS = os.path.join(ROOT, "discs", "segacd_us")
WORK = os.path.join(ROOT, "work")
PATCHED = os.path.join(ROOT, "patched")
NAME = "Snatcher (USA)"
TRACK1 = f"{NAME} (Track 01).bin"
TRACK1_SHA1 = "1f4164205ed736a0d9a03eb7972868e9aa737d35"


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def cmd_discs(paths):
    os.makedirs(DISCS, exist_ok=True)
    n = 0
    for p in paths:
        files = [p] if os.path.isfile(p) else [os.path.join(d, f) for d, _, fs in os.walk(p) for f in fs]
        for f in files:
            b = os.path.basename(f)
            if b.startswith(NAME) and b.endswith((".bin", ".cue")):
                shutil.copyfile(f, os.path.join(DISCS, b))
                n += 1
    if not n:
        sys.exit("no 'Snatcher (USA)' tracks found (redump names expected)")
    t1 = os.path.join(DISCS, TRACK1)
    print(f"{n} files; track 1 {'ok' if sha1(t1) == TRACK1_SHA1 else 'WRONG DUMP (SHA1)'}")


def need_disc():
    t1 = os.path.join(DISCS, TRACK1)
    if not os.path.exists(t1):
        sys.exit(f"missing {os.path.relpath(t1, ROOT)} - see `build.py discs`")
    return t1


def cmd_extract():
    from cdimage import Mode1Image
    img = Mode1Image(need_disc())
    out = os.path.join(WORK, "files")
    os.makedirs(out, exist_ok=True)
    for name, v in sorted(img.files.items(), key=lambda x: x[1]["lba"]):
        if name.startswith("PCMLD"):
            continue                       # 84 MB of voice samples, not needed
        open(os.path.join(out, name), "wb").write(img.read_file(name))
    print(f"{len(img.files)} files -> {os.path.relpath(out, ROOT)}")


def cmd_build(a):
    import fontpatch
    from cdimage import Mode1Image
    need_disc()
    os.makedirs(PATCHED, exist_ok=True)
    for f in os.listdir(DISCS):
        dst = os.path.join(PATCHED, f)
        if os.path.lexists(dst):
            os.remove(dst)
        if f == TRACK1:
            print(f"copying {f}")
            shutil.copyfile(os.path.join(DISCS, f), dst)
        else:
            os.symlink(os.path.join(DISCS, f), dst)
    img = Mode1Image(os.path.join(PATCHED, TRACK1))
    import textpatch
    import names
    sub = fontpatch.patch_subcode(names.patch(img.read_file("SUBCODE.BIN")))
    img.write_file("SUBCODE.BIN", textpatch.patch_subcode(sub))
    print("SUBCODE.BIN: Cyrillic font, Russian nameplates, text remap")
    for n in range(39):
        name = f"SP{n:02d}.BIN"
        sp = img.read_file(name)
        import script
        new = script.load_ru(name[:4])
        if a.probe and name == "SP06.BIN":
            import probe_line
            new.update(probe_line.LINES)
        lead = b"\xff" * 4 if a.shift_test else b""
        img.write_file(name, textpatch.relayout(sp, new, lead))
    import overlays
    img.write_file("DATA_D1.BIN", overlays.patch_d1(img.read_file("DATA_D1.BIN")))
    img.write_file("DATA_D2.BIN", overlays.patch_d2(img.read_file("DATA_D2.BIN")))
    print("DATA_D1.BIN: disclaimer, dedication; DATA_D2.BIN: title menu, backup RAM screens")
    import acttitles
    for name in acttitles.TITLES:
        img.write_file(name, acttitles.patch(name, img.read_file(name)))
    print("act titles: " + ", ".join(acttitles.TITLES))
    import captions
    for name in captions.FILES:
        img.write_file(name, captions.patch(name, img.read_file(name)))
    print("city caption: " + ", ".join(captions.FILES))
    print("SP00-SP38: text relaid out" + (" (shift test)" if a.shift_test else ""))
    print(f"-> {os.path.relpath(os.path.join(PATCHED, NAME + '.cue'), ROOT)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("discs")
    p.add_argument("paths", nargs="+")
    sub.add_parser("extract")
    p = sub.add_parser("build")
    p.add_argument("--probe", action="store_true", help="Mika's first line in Russian")
    p.add_argument("--shift-test", action="store_true",
                   help="move every string by 4 bytes: the game must run unchanged")
    a = ap.parse_args()
    if a.cmd == "discs":
        cmd_discs(a.paths)
    elif a.cmd == "extract":
        cmd_extract()
    else:
        cmd_build(a)


if __name__ == "__main__":
    main()
