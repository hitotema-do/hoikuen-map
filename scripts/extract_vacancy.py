"""広島市「保育園等の空き状況」PDF（区ごと）から表を抽出して1つのCSVにまとめる。

使い方:
    python scripts/extract_vacancy.py <PDFのあるフォルダ> <出力CSV>

PDFのファイル名は 01naka081001.pdf のように「区番号+区名」で始まる想定。
"""
import csv
import re
import sys
import unicodedata
from pathlib import Path

import fitz  # PyMuPDF

WARDS = {
    "01": "中区", "02": "東区", "03": "南区", "04": "西区",
    "05": "安佐南区", "06": "安佐北区", "07": "安芸区", "08": "佐伯区",
}
AGES = range(6)

# 施設区分の表記ゆれ → 種別
CATEGORY_CODES = {
    "公": "保育園", "公※": "保育園", "私": "保育園",
    "認保": "認定こども園", "認幼": "認定こども園",
    "小規": "小規模保育", "事": "事業所内保育",
}
# 表見出しに書かれた種別（佐伯区など）
CATEGORY_HEADERS = [
    ("事業所内", "事業所内保育"),
    ("小規模", "小規模保育"),
    ("認定こども園", "認定こども園"),
]
# 施設名に付いた印 → 種別。マッチした部分は施設名から取り除く
NAME_TAGS = [
    (r"[（(]\s*小規模保育\s*[）)]", "小規模保育"),
    (r"[（(]\s*事業所内保育施設\s*[）)]", "事業所内保育"),
    (r"^[（(]認[）)]", "認定こども園"),
    (r"^[（(]小[）)]", "小規模保育"),
    (r"[（(]事[）)]", "事業所内保育"),
    (r"^◎", "認定こども園"),
]

# 区ごとの※印の意味（各PDFの欄外注記より）。(種別 or None, 備考に書く説明)
FOOTNOTES = {
    ("南区", "※1"): (None, "延長保育は1歳3か月から"),
    ("南区", "※2"): (None, "延長保育は1歳児クラスから"),
    ("安佐北区", "※1"): (None, "0〜2歳と3〜5歳で保育場所が別住所"),
    ("安佐北区", "※2"): (None, "満1歳以上から受入れ"),
    ("安芸区", "※1"): (None, "満1歳以上から受入れ（()内は満1歳の0歳児の人数）"),
    ("安芸区", "※2"): ("小規模保育", ""),
    ("安芸区", "※3"): ("事業所内保育", ""),
}

# 「1〜2歳児入園可能人数」「3〜5歳の待機者数 0」のように複数年齢をまとめた結合セル
MERGED_CELL = re.compile(r"(\d)[~～](\d)歳.*?(入園可能人数|待機者数)\s*(\d+)?$")


def norm(text):
    if text is None:
        return ""
    text = unicodedata.normalize("NFKC", text).replace("\n", "")
    # 安佐北区は「白 木 い づ み」のように1文字ずつ空白が入っている
    stripped = text.strip()
    if stripped and stripped.count(" ") > len(stripped) * 0.3:
        return re.sub(r"\s+", "", stripped)
    return re.sub(r"\s+", " ", stripped)


def parse_value(raw):
    """セル文字列 → (数値 or None, 備考)。None は対象年齢外（空欄・━）。"""
    t = norm(raw)
    if t in ("", "━", "-", "―"):
        return None, ""
    if re.fullmatch(r"\d+", t):
        return int(t), ""
    m = re.fullmatch(r"(\d+)以上", t)
    if m:
        return int(m.group(1)), t
    m = re.fullmatch(r"(\d+)\((\d+)\)", t)
    if m:
        return int(m.group(1)), t
    return None, t


def locate_columns(header):
    """見出し行から 年齢列・所在地列・施設区分列・施設名候補列 を特定する。"""
    cells = [norm(c) for c in header]
    age_cols = {}
    for i, c in enumerate(cells):
        m = re.fullmatch(r"(\d)歳", c)
        if m:
            age_cols[int(m.group(1))] = i
    first_age = min(age_cols.values())
    addr_col = next((i for i, c in enumerate(cells) if c == "所在地"), None)
    cat_col = next((i for i, c in enumerate(cells) if c == "施設区分"), None)
    name_cols = [i for i in range(first_age) if i not in (addr_col, cat_col)]
    return age_cols, addr_col, cat_col, name_cols, cells


def pick_name(row, name_cols):
    """施設名候補列のうち文字数が最も多い列を施設名とし、その右にある印（（私）など）を連結する。"""
    texts = [(i, norm(row[i])) for i in name_cols if norm(row[i])]
    if not texts:
        return ""
    main = max(texts, key=lambda x: len(x[1]))
    return "".join(t for i, t in texts if i >= main[0])


def classify(name, cat_code, table_title, ward):
    category = None
    for pattern, cat in NAME_TAGS:
        if re.search(pattern, name):
            category = category or cat
            name = re.sub(pattern, "", name)
    public = None
    m = re.search(r"[（(]私[）)]", name)
    if m:
        public = "私立"
        name = name.replace(m.group(0), "")
    notes = []
    for raw_mark in re.findall(r"[（(]?\s*※\s*\d\s*[）)]?", name):
        name = name.replace(raw_mark, "")
        mark = "※" + re.search(r"\d", raw_mark).group(0)
        cat, text = FOOTNOTES.get((ward, mark), (None, mark))
        category = category or cat
        if text:
            notes.append(text)
    name = name.strip()
    if cat_code:
        category = category or CATEGORY_CODES.get(cat_code)
        public = "公立" if cat_code.startswith("公") else "私立"
    if not category:
        # 佐伯区は表ごとに見出し（「認定こども園」「小規模保育事業所」…）で種別が分かれている
        for key, cat in CATEGORY_HEADERS:
            if table_title.startswith(key):
                category = cat
                break
    if not category:
        category = "認定こども園" if "こども園" in name else "保育園"
    return name, category, public, notes


def find_merged(raw, age_cols):
    """結合セルを探して [(開始年齢, 終了年齢, "空き"/"待機", 人数)] を返す。"""
    found = []
    for i, cell in enumerate(raw):
        m = MERGED_CELL.search(norm(cell))
        if not m:
            continue
        lo, hi = int(m.group(1)), int(m.group(2))
        kind = "空き" if m.group(3) == "入園可能人数" else "待機"
        if m.group(4) is not None:
            value = int(m.group(4))
        else:
            # 人数が別セル（結合範囲の右端の列）にある場合
            value, _ = parse_value(raw[age_cols[hi] + 1])
        found.append((lo, hi, kind, value))
    return found


def apply_merged(row, merged):
    for lo, hi, kind, value in merged:
        for age in range(lo, hi + 1):
            row[f"{age}歳{kind}"] = value
        note = f"{lo}〜{hi}歳は合算で{kind}{value}人"
        if note not in row["備考"]:
            row["備考"] = " ".join(filter(None, [row["備考"], note]))


def extract_pdf(path):
    ward = WARDS[path.name[:2]]
    rows = []
    for page in fitz.open(path):
        for table in page.find_tables().tables:
            data = table.extract()
            if not data or not any("歳" in norm(c) for c in data[0]):
                continue
            age_cols, addr_col, cat_col, name_cols, header = locate_columns(data[0])
            title = "".join(header[i] for i in name_cols)
            for raw in data[2:]:
                name = pick_name(raw, name_cols)
                merged = find_merged(raw, age_cols)
                values = {}
                remarks = []
                for age, col in age_cols.items():
                    for kind, offset in (("空き", 0), ("待機", 1)):
                        cell = raw[col + offset] if col + offset < len(raw) else None
                        if MERGED_CELL.search(norm(cell)):
                            cell = None
                        v, note = parse_value(cell)
                        values[f"{age}歳{kind}"] = v
                        if note:
                            remarks.append(f"{age}歳{kind}「{note}」")
                if not name:
                    # 名前のない行は直前の施設の続き（分園の3〜5歳など）として空欄を埋める
                    if rows and any(v is not None for v in values.values()):
                        prev = rows[-1]
                        for k, v in values.items():
                            if prev[k] is None:
                                prev[k] = v
                        if remarks:
                            prev["備考"] = " ".join(filter(None, [prev["備考"], *remarks]))
                        apply_merged(prev, merged)
                    continue
                if "ご注意" in name:
                    continue
                cat_code = norm(raw[cat_col]) if cat_col is not None else ""
                name, category, public, notes = classify(name, cat_code, title, ward)
                rows.append({
                    "区": ward,
                    "施設名": name,
                    "種別": category,
                    "公立私立": public or "",
                    "所在地": norm(raw[addr_col]) if addr_col is not None else "",
                    **values,
                    "備考": " ".join(filter(None, [*notes, *remarks])),
                })
                apply_merged(rows[-1], merged)
    return rows


def extract_folder(src):
    """フォルダ内の区ごとのPDF（01〜08で始まる名前）をすべて抽出して、全施設の行を返す。"""
    rows = []
    for pdf in sorted(Path(src).glob("0*.pdf")):
        got = extract_pdf(pdf)
        print(f"{pdf.name}: {len(got)}施設")
        rows.extend(got)
    return rows


def write_csv(rows, out):
    out = Path(out)
    fields = ["区", "施設名", "種別", "公立私立", "所在地"]
    fields += [f"{a}歳{k}" for a in AGES for k in ("空き", "待機")] + ["備考"]
    out.parent.mkdir(parents=True, exist_ok=True)
    # Excelで文字化けしないようBOM付きUTF-8
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"合計 {len(rows)}施設 → {out}")


def main():
    write_csv(extract_folder(sys.argv[1]), sys.argv[2])


if __name__ == "__main__":
    main()
