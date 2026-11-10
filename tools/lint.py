"""Check text/ru: line widths and lines per dialogue page.

    python tools/lint.py
"""
import glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import script
from collections import Counter

ROOT = script.ROOT


def pages(t):
    return re.split(r"[▼◆]", t)


def main():
    bad = 0
    maxlines = Counter()
    for p in sorted(glob.glob(os.path.join(script.TASKS, "*.json"))):
        for it in json.load(open(p, encoding="utf-8"))["items"]:
            if not it["en"].startswith("<fe>") and not it.get("menu"):
                for pg in pages(it["en"]):
                    maxlines[pg.count("\n") + 1] += 1
    print("English dialogue pages by line count:", sorted(maxlines.items()))
    limit_lines = max(k for k, v in maxlines.items())
    for p in sorted(glob.glob(os.path.join(ROOT, "text", "ru", "*.json"))):
        name = os.path.basename(p)[:-5]
        en = {it["id"]: it for it in json.load(open(os.path.join(script.TASKS, name + ".json"), encoding="utf-8"))["items"]}
        for k, v in json.load(open(p, encoding="utf-8")).items():
            it = en[k]
            if it.get("menu"):
                continue
            db = v.startswith("<fe>")
            lim = script.DB_PX if db else script.LINE_PX
            for line in re.split(r"[\n▼◆]", v):
                if script.px(line.replace("<fe>", "")) > lim + 2:
                    print(f"{name} {k}: {script.px(line)} px > {lim}: {line!r}")
                    bad += 1
            if not db:
                enmax = max(pg.count("\n") + 1 for pg in pages(it["en"]))
                for pg in pages(v):
                    n = pg.count("\n") + 1
                    if n > max(enmax, 3):
                        print(f"{name} {k}: page of {n} lines (English {enmax}): {pg[:60]!r}")
                        bad += 1
    print(bad, "problems")


if __name__ == "__main__":
    main()
