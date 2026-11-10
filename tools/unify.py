"""Make the parallel translators' work/out consistent (in place).

    python tools/unify.py            report
    python tools/unify.py --write

1. Menu items: one Russian label per English one (MENU). An item now in
   Latin is left alone: those are typed-search names (Jordan's ID file) or
   letter puzzles (Queen/Oleen).
2. Terms spelled differently by different translators (TERMS).
3. Words mixing Cyrillic and Latin look-alike letters (a typo the validator
   cannot see: both are valid glyphs) are fixed to Cyrillic.
"""
import glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "work", "out")
TASKS = os.path.join(ROOT, "work", "tasks")

MENU = {
    "LOOK": "ОСМОТРЕТЬ", "USE METAL GEAR": "МЕТАЛ ГИР", "AREA": "ОКРЕСТНОСТИ",
    "CASH": "ДЕНЬГИ", "JUNKER I.D.": "УДОСТОВЕРЕНИЕ", "CHESS PIECE": "ШАХМ. ФИГУРА",
    "ENTER TURBOCYCLE": "В ТУРБОЦИКЛ", "EXIT TURBOCYCLE": "ВЫЙТИ", "LITTLE JOHN": "ЛИТЛ ДЖОН",
    "MONTAGE PHOTO": "ФОТОРОБОТ", "SUNSCREEN": "КРЕМ ОТ ЗАГАРА", "VIDEO MEMORY": "ВИДЕОПАМЯТЬ",
    "PATIENT RECORD": "МЕДКАРТА", "RED SQUARE": "КРАСНАЯ ПЛОЩАДЬ", "SMELL": "ПОНЮХАТЬ",
    "CONTINUE INVESTIGATE": "ИСКАТЬ ДАЛЬШЕ", "QUIT INVESTIGATE": "ЗАКОНЧИТЬ ПОИСК",
    "DETECTIVE'S ROOM": "ОПЕРОТДЕЛ", "ENGINEERING ROOM": "ТЕХОТДЕЛ", "ALTON PLAZA": "АЛТОН-ПЛАЗА",
    "QUEENS HOSPITAL": 'БОЛЬНИЦА "КУИН"', "FRONT POD": "КАПСУЛА", "SNOW 9": "СНОУ-9",
    "POSTER": "ПЛАКАТ", "ALICE": "ЭЛИС", "ABOUT ALICE": "ОБ ЭЛИС", "OPERATING TABLE": "ОПЕР. СТОЛ",
    "AROUND ROOM": "КОМНАТА", "LIQUID SKY": "ЖИДКОЕ НЕБО", "TEMPLE": "ХРАМ",
    "GILLIAN'S APARTMENT": "КВАРТИРА ГИЛЛИАНА", "HOW TO USE": "КАК ПОЛЬЗОВАТЬСЯ",
    "HOW TO PRACTICE": "О ТРЕНИРОВКЕ", "PRACTICE BOOTH": "КАБИНКА ТИРА",
    "SWITCH 1": "ВЫКЛЮЧАТЕЛЬ 1", "SWITCH 2": "ВЫКЛЮЧАТЕЛЬ 2", "SWITCHES": "ВЫКЛЮЧАТЕЛИ",
    "USE SWITCHES": "ПЕРЕКЛЮЧИТЬ", "QUIT INVESTIGATION": "ЗАКОНЧИТЬ ДЕЛО",
    "ASK OUT ON DATE": "НА СВИДАНИЕ", "DESK TOP": "СТОЛ", "NEARBY PEOPLE": "ПРОХОЖИЕ",
    "DO SOMETHING": "ДЕЙСТВОВАТЬ", "INSIDE BOOTH": "В КАБИНКЕ", "BOOTH'S SHADOWS": "ТЕНЬ КАБИНОК",
    "LITTLE MEMORY": "ПАМЯТЬ ДЖОНА", "FACIAL SHAPE": "ФОРМА ЛИЦА", "GET FORTUNE TOLD": "ПОГАДАТЬ",
    **{f"SAVE {n}": f"ЗАПИСЬ {n}" for n in range(1, 5)},
    **{f"OVERWRITE SAVE {n}": f"ПОВЕРХ ЗАПИСИ {n}" for n in range(1, 5)},
}

TERMS = [
    (r"Альфа-(Один|Одного|Одном|Одному|Одним)\b", "Альфа-1"),
    (r"(?:Олтон|Алтон)[- ][Пп]лаз", "Алтон-Плаз"),
    (r"Тин Сё О\b|Чин Шу О\b", "Чин Шу Хо"),
    (r"Малыш\w* (Джон\w*)", r"Литл \1"),
    (r"Сноу 9", "Сноу-9"), (r"СНОУ 9", "СНОУ-9"),
    (r"[Лл]иквид [Сс]кай", "жидкое небо"),
]

LOOKALIKE = str.maketrans("aceopxyABCEHKMOPTX", "асеорхуАВСЕНКМОРТХ")


def fix_mixed(t):
    def one(m):
        w = m.group(0)
        if re.search("[а-яёА-ЯЁ]", w) and re.search("[A-Za-z]", w):
            return w.translate(LOOKALIKE)
        return w
    return re.sub(r"[A-Za-zА-Яа-яЁё]+", one, t)


def main():
    write = "--write" in sys.argv
    menu_en = {}
    for tp in glob.glob(os.path.join(TASKS, "*.json")):
        name = os.path.basename(tp)[:-5]
        for it in json.load(open(tp, encoding="utf-8"))["items"]:
            if it.get("menu"):
                menu_en[(name, it["id"])] = it["en"]
    changes = 0
    for p in sorted(glob.glob(os.path.join(OUT, "*", "*.json"))):
        name = os.path.basename(os.path.dirname(p))
        d = json.load(open(p, encoding="utf-8"))
        for k, v in list(d.items()):
            n = v
            en = menu_en.get((name, k))
            if en in MENU and re.search("[А-Яа-яЁё]", v):
                n = MENU[en]
            for pat, rep in TERMS:
                n = re.sub(pat, rep, n)
            n = fix_mixed(n)
            if n != v:
                print(f"{name} {k}: {v[:60]!r} -> {n[:60]!r}")
                d[k] = n
                changes += 1
        if write:
            json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(changes, "changes")


if __name__ == "__main__":
    main()
