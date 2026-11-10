"""Script text of the Sega CD Snatcher: export, reference match, validate, encode.

    python tools/script.py export [--ps1 ../snatcher-translated-rus]
        work/tasks/SPxx.json - every string with its English and, where one
        is close, the PS1 line and its Russian translation as a reference
    python tools/script.py validate [SPxx ...]
        check translations in work/out/SPxx/*.json (tokens, encodable, fit)

Readable form of the engine bytes (export and translations use it):
    \\n   0xF2 line break (recomputed by `wrap`: translators may omit them)
    ▼    0xF6 new page          ◆  0xF4
    {    0xFB start highlight   }  0xF9 end highlight
    <xx> any other code byte 0xEC-0xFE kept as is
"""
import argparse, glob, json, math, os, re, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import cyrfont, textpatch

WORK = os.path.join(ROOT, "work")
FILES = os.path.join(WORK, "files")
TASKS = os.path.join(WORK, "tasks")
OUT = os.path.join(WORK, "out")
LINE_PX = 200                 # dialogue box: the English runs to ~206 px
DB_PX = 158                   # Jordan's database pages (text after <fe>): ~161 px
MENU_PX = 160

SIMPLE = {0xF2: "\n", 0xF6: "▼", 0xF4: "◆", 0xFB: "{", 0xF9: "}"}
BACK = {v: k for k, v in SIMPLE.items()}


def decode(b):
    out = []
    for c in b:
        if c in SIMPLE:
            out.append(SIMPLE[c])
        elif c >= 0xEC or c < 0x20:
            out.append(f"<{c:02x}>")
        else:
            out.append(chr(c))
    return "".join(out)


def encode(t):
    out, i = bytearray(), 0
    while i < len(t):
        m = re.match(r"<([0-9a-f]{2})>", t[i:])
        if m:
            out.append(int(m.group(1), 16))
            i += 4
            continue
        ch = t[i]
        if ch in BACK:
            out.append(BACK[ch])
        else:
            out += cyrfont.encode(ch)
        i += 1
    return bytes(out)


def tokens(t):
    return re.findall(r"<[0-9a-f]{2}>|[▼◆{}]", t)


# --- pixel width and wrapping ---------------------------------------------------

_W = None


def widths():
    global _W
    if _W is None:
        sub = open(os.path.join(FILES, "SUBCODE.BIN"), "rb").read()
        font = sub[0x777C:0x777C + 102 * 8]
        w = sub[0x7AAC:0x7AAC + 102]
        _, cw = cyrfont.build(font, w)
        _W = {chr(i + 0x20): w[i] for i in range(0x60)}
        for ch, code in cyrfont.CODES.items():
            _W[ch] = cw[code - cyrfont.FIRST]
    return _W


def px(s):
    w = widths()
    s = re.sub(r"<(ec|ee|f0)>", "\x7f", s)
    s = re.sub(r"<[0-9a-f]{2}>|[{}]", "", s)
    return sum(w.get(ch, 9) for ch in s)


def wrap(t, limit=LINE_PX):
    """Re-break each page of `t` at `limit` pixels on spaces."""
    pages = re.split(r"([▼◆])", t)
    out = []
    for part in pages:
        if part in ("▼", "◆"):
            out.append(part)
            continue
        lines = []
        for para in part.split("\n"):
            body = para.lstrip(" ")
            indent = para[:len(para) - len(body)]      # a field value's indent stays
            cur = indent
            for w in body.split(" "):
                cand = w if not cur.strip() else cur + " " + w
                if not cur.strip():
                    cand = cur + w
                if cur and px(cand) > limit:
                    lines.append(cur)
                    cur = w
                else:
                    cur = cand
            lines.append(cur)
        out.append("\n".join(lines))
    return "".join(out)


# --- export ---------------------------------------------------------------------

def is_menu(t):
    return bool(t) and t == t.upper() and "\n" not in t and len(t) <= 20 and re.search("[A-Z]", t)


def ps1_lines(ps1):
    """[(english, russian)] from the PS1 translation (script strings and subtitles)."""
    out = []
    for f in glob.glob(os.path.join(ps1, "ps1", "translation", "ISZ_*.json")):
        for s in json.load(open(f, encoding="utf-8"))["strings"]:
            if s.get("ru"):
                en = s.get("long_src") or s.get("en_src") or ""
                ru = s.get("long") or s.get("en") or ""
                out.append((en, ru))
    for f in glob.glob(os.path.join(ps1, "ps1", "translation", "subs_*.json")):
        for c in json.load(open(f, encoding="utf-8"))["cues"]:
            if c.get("en_src"):
                out.append((c["en_src"], c["en"]))
    clean = lambda t: re.sub(r"＠.|￥", " ", t)
    return [(re.sub(r"\s+", " ", clean(e)).strip(), re.sub(r"\s+", " ", clean(r)).strip())
            for e, r in out if e and r]


WORD = re.compile(r"[a-z']+")


class Matcher:
    def __init__(self, pairs):
        self.pairs = pairs
        self.docs = [Counter(WORD.findall(e.lower())) for e, _ in pairs]
        df = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {w: math.log(n / (1 + c)) + 1 for w, c in df.items()}
        self.index = defaultdict(list)
        for i, d in enumerate(self.docs):
            for w in d:
                self.index[w].append(i)
        self.norm = [math.sqrt(sum((v * self.idf[w]) ** 2 for w, v in d.items())) or 1 for d in self.docs]

    def best(self, text):
        q = Counter(WORD.findall(text.lower()))
        if not q:
            return None, 0.0
        qn = math.sqrt(sum((v * self.idf.get(w, 1)) ** 2 for w, v in q.items())) or 1
        score = defaultdict(float)
        for w, v in q.items():
            if w not in self.idf or len(self.index[w]) > 2000:
                continue
            for i in self.index[w]:
                score[i] += v * self.docs[i][w] * self.idf[w] ** 2
        if not score:
            return None, 0.0
        i = max(score, key=lambda k: score[k] / self.norm[k])
        return i, score[i] / self.norm[i] / qn


def cmd_export(a):
    m = Matcher(ps1_lines(a.ps1))
    os.makedirs(TASKS, exist_ok=True)
    tot = good = 0
    for f in sorted(glob.glob(os.path.join(FILES, "SP*.BIN"))):
        name = os.path.basename(f)[:4]
        items, seen = [], {}
        for off, s in textpatch.strings(open(f, "rb").read()):
            if not s or s == b"\xff":
                continue
            en = decode(s)
            if not re.search("[A-Za-z]", en):
                continue
            it = {"id": f"{off:04x}", "en": en}
            if is_menu(en):
                it["menu"] = True
            flat = re.sub(r"\s+", " ", re.sub(r"<..>|[▼◆{}\n]", " ", en)).strip()
            if flat in seen:
                it["same_as"] = seen[flat]
            else:
                seen[flat] = it["id"]
                i, sc = m.best(flat) if not it.get("menu") and len(flat) > 12 else (None, 0)
                ratio = len(m.pairs[i][0]) / max(len(flat), 1) if i is not None else 0
                if i is not None and sc >= 0.5 and 0.5 <= ratio <= 2.0:
                    it["ps1_en"], it["ps1_ru"] = m.pairs[i]
                    it["match"] = round(sc, 2)
                    good += 1
            items.append(it)
            tot += 1
        json.dump({"file": name, "items": items}, open(os.path.join(TASKS, name + ".json"), "w",
                  encoding="utf-8"), ensure_ascii=False, indent=1)
        print(name, len(items))
    print(f"{tot} strings, {good} with a PS1 reference")


# --- translations ---------------------------------------------------------------

def collect(name):
    out = {}
    for p in sorted(glob.glob(os.path.join(OUT, name, "*.json"))):
        out.update(json.load(open(p, encoding="utf-8")))
    return out


NORMALIZE = {"«": '"', "»": '"', "“": '"', "”": '"', "„": '"', "‘": "'", "’": "'",
             "—": "-", "–": "-", "…": "...", " ": " "}


def normalize(t):
    for k, v in NORMALIZE.items():
        t = t.replace(k, v)
    return t


def check(it, ru):
    err = []
    if tokens(ru) != tokens(it["en"]):
        err.append(f"коды {tokens(it['en'])} -> {tokens(ru)}")
    try:
        encode(ru)
    except ValueError as e:
        err.append(str(e))
        return err
    if it.get("menu"):
        if px(ru) > MENU_PX:
            err.append(f"пункт меню шире {MENU_PX} px ({px(ru)})")
    return err


def translated(name):
    """{offset: Russian (normalized, wrapped)} for one file, `same_as` resolved."""
    t = json.load(open(os.path.join(TASKS, name + ".json"), encoding="utf-8"))
    got = {k: normalize(v) for k, v in collect(name).items()}
    out = {}
    for it in t["items"]:
        ru = got.get(it["id"]) or got.get(it.get("same_as", ""))
        if ru is None:
            continue
        out[int(it["id"], 16)] = ru if it.get("menu") else wrap(ru, DB_PX if ru.startswith("<fe>") else LINE_PX)
    return out


def cmd_validate(a):
    names = a.files or [os.path.basename(p)[:-5] for p in sorted(glob.glob(os.path.join(TASKS, "*.json")))]
    bad = 0
    for name in names:
        t = json.load(open(os.path.join(TASKS, name + ".json"), encoding="utf-8"))
        got = {k: normalize(v) for k, v in collect(name).items()}
        need = [it for it in t["items"] if "same_as" not in it]
        miss = [it["id"] for it in need if it["id"] not in got]
        ne = 0
        for it in need:
            if it["id"] in got:
                for e in check(it, got[it["id"]]):
                    print(f"{name} {it['id']}: ERROR {e}")
                    ne += 1
        ids = {it["id"] for it in t["items"]}
        extra = [k for k in got if k not in ids]
        size = None
        if not miss and not ne:
            sp = open(os.path.join(FILES, name + ".BIN"), "rb").read()
            new = {o: encode(r) for o, r in translated(name).items()}
            try:
                size = len(textpatch.relayout(sp, new))
            except SystemExit as e:
                print(f"{name}: ERROR {e}")
                ne += 1
        print(f"== {name}: {len(need) - len(miss)}/{len(need)} translated, {len(miss)} missing, "
              f"{ne} errors" + (f", unknown ids {extra[:5]}" if extra else "")
              + (f", file {size}/{textpatch.SP_MAX}" if size else ""))
        if a.missing and miss:
            print("   missing:", " ".join(miss[:30]))
        bad += ne + len(extra)
    sys.exit(1 if bad else 0)


RU = os.path.join(ROOT, "text", "ru")


def cmd_collect(a):
    """work/out -> text/ru/SPxx.json: {offset hex: Russian, wrapped} (what build.py uses)."""
    os.makedirs(RU, exist_ok=True)
    for p in sorted(glob.glob(os.path.join(TASKS, "*.json"))):
        name = os.path.basename(p)[:-5]
        tr = translated(name)
        if not tr:
            continue
        json.dump({f"{k:04x}": v for k, v in sorted(tr.items())},
                  open(os.path.join(RU, name + ".json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(name, len(tr))


def load_ru(name):
    """{offset: game bytes} from text/ru/SPxx.json, or {}."""
    p = os.path.join(RU, name + ".json")
    if not os.path.exists(p):
        return {}
    return {int(k, 16): encode(v) for k, v in json.load(open(p, encoding="utf-8")).items()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    e = sp.add_parser("export")
    e.add_argument("--ps1", default=os.path.join(ROOT, "..", "snatcher-translated-rus"))
    v = sp.add_parser("validate")
    v.add_argument("files", nargs="*")
    v.add_argument("--missing", action="store_true")
    sp.add_parser("collect")
    a = ap.parse_args()
    {"export": cmd_export, "validate": cmd_validate, "collect": cmd_collect}[a.cmd](a)
