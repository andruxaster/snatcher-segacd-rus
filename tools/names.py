"""Speaker nameplates (SUBCODE.BIN).

The names sit at file offset 0x5F9E-0x6150: entry 0 is an empty string,
then 47 records `<attr> <name> 0xFF` (attr 0x32: colour 2, yellow). A table
of 48 signed word offsets from its own start follows at 0x6152 ($13552);
the dialogue code ($136B2) picks a name by speaker number through it. The
Russian names are written into the same 435 bytes and the table is
rewritten; the names follow the US script (Jordan for Gaudi, Katrina,
Random).
"""
import struct
import cyrfont

REGION, TABLE = 0x5F9E, 0x6152

# US English -> Russian, in table order (entries 1..47)
NAMES = [
    ("Metal Gear", "Метал Гир"), ("Gillian", "Гиллиан"), ("Mika", "Мика"),
    ("Togo", "Того"), ("Driver", "Водитель"), ("Chief", "Шеф"), ("Harry", "Гарри"),
    ("Napoleon", "Наполеон"), ("Jamie", "Джейми"), ("Employee", "Служащий"),
    ("Man", "Мужчина"), ("Stella", "Стелла"), ("Christy", "Кристи"),
    ("Woman", "Женщина"), ("Fukui II", "Фукуи II"), ("Miss Hayasaka", "Хаясака"),
    ("Mr. Togo", "Г-н Того"), ("Mr. Nakamura", "Г-н Накамура"), ("Nakamura", "Накамура"),
    ("Mr. Sasaki", "Г-н Сасаки"), ("Jeremy", "Джереми"), ("Chie", "Тиэ"), ("Kiwi", "Киви"),
    ("Mr. Kushibuchi", "Г-н Кусибути"), ("Mr. Inamura", "Г-н Инамура"),
    ("Jordan", "Джордан"), ("Konami", "Konami"), ("Vangie", "Ванджи"),
    ("Katrina", "Катрина"), ("Passerby", "Прохожий"), ("P.A.", "Диктор"),
    ("Doorman", "Швейцар"), ("Manager", "Менеджер"), ("Isabella", "Изабелла"),
    ("Sparkster", "Спаркстер"), ("Goemon", "Гоэмон"), ("Mr. Ueda", "Г-н Уэда"),
    ("Contra", "Contra"), ("Castlevania pair", "Castlevania"),
    ("Customer", "Клиент"), ("Dracula", "Дракула"), ("Simon Belmont", "Саймон Бельмонт"),
    ("Freeman", "Фримен"), ("Ivan", "Иван"), ("Lisa", "Лиза"), ("Parrot", "Попугай"),
    ("Random", "Рэндам"),
]


def read(sub):
    """[(attr, name bytes)] for entries 1..47, checking the layout."""
    out = []
    for i in range(1, 48):
        o = TABLE + struct.unpack(">h", sub[TABLE + 2 * i:TABLE + 2 * i + 2])[0]
        j = sub.index(b"\xff", o)
        out.append((sub[o], sub[o + 1:j]))
    return out


def patch(sub):
    sub = bytearray(sub)
    old = read(sub)
    assert [n.decode() for _, n in old] == [e for e, _ in NAMES], "unexpected name table"
    blob, offs = bytearray(b"\xff"), [REGION - TABLE]
    for (attr, _), (_, ru) in zip(old, NAMES):
        offs.append(REGION + len(blob) - TABLE)
        blob += bytes([attr]) + cyrfont.encode(ru) + b"\xff"
    room = TABLE - REGION
    if len(blob) > room:
        raise SystemExit(f"names: {len(blob)} bytes > {room}")
    sub[REGION:TABLE] = blob + b"\x00" * (room - len(blob))
    for i, o in enumerate(offs):
        sub[TABLE + 2 * i:TABLE + 2 * i + 2] = struct.pack(">h", o)
    return bytes(sub)
