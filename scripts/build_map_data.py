"""空き状況CSVと市の施設一覧PDFを突き合わせ、緯度経度を付けて地図用データ(web/data.js)を作る。

使い方:
    python scripts/build_map_data.py <空き状況CSV> <施設一覧PDF> <区> <件数> <出力JS>

<区> に「全区」、<件数> に「全件」を指定すると全区・全施設を処理する（区ごとの件数上限）。
緯度経度は国土地理院の住所検索APIで取得し、data/geocode_cache.json に保存して再利用する。
"""
import csv
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

import fitz  # PyMuPDF

from extract_vacancy import WARDS

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "geocode_cache.json"
GSI_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch?q="


def key(name):
    """施設名の表記ゆれ（全角半角・空白・ハイフン類・(注7)など）を吸収した照合用キー。"""
    s = unicodedata.normalize("NFKC", name or "").replace("\n", "")
    s = re.sub(r"^○", "", s)
    s = re.sub(r"[(（]注\d*[)）]", "", s)
    return re.sub(r"[\s・\-－ｰ―‐ー]", "", s)


# 空き状況PDFと一覧PDFで付け方が違う語。完全一致しなかった施設だけ、これを除いて照合し直す
LOOSE_WORDS = ["京進のほいくえん", "事業所内保育施設", "認定こども園", "認定こども", "(分園)", "分園"]


# 語の除去では合わせられない施設の対応表（空き状況PDFでの名称 → 一覧PDFでの名称）
ALIASES = {
    "おうち保育すまいる": "おうち保育すまいる第一園舎",
    "おうち保育すまいる第2園舎": "おうち保育すまいる第二園舎",
}


def loose_key(name):
    s = unicodedata.normalize("NFKC", key(name))
    for w in LOOSE_WORDS:
        s = s.replace(unicodedata.normalize("NFKC", w), "")
    return s


def match_facilities(vacancy_rows, facility_list):
    """空き状況の各行に対応する一覧の施設を探し、{行の番号: 情報} と 見つからなかった行 を返す。

    1) 表記ゆれを吸収した完全一致  2) 残った施設どうしを、LOOSE_WORDS を除いて照合（一意に決まるものだけ）
    """
    matched, rest = {}, []
    used = set()
    for i, v in enumerate(vacancy_rows):
        k = key(ALIASES.get(v["施設名"], v["施設名"]))
        if k in facility_list and k not in used:
            matched[i] = facility_list[k]
            used.add(k)
        else:
            rest.append(i)
    loose = {}
    for k, info in facility_list.items():
        if k not in used:
            loose.setdefault(loose_key(info["一覧名称"]), []).append(info)
    missing = []
    for i in rest:
        cands = loose.get(loose_key(vacancy_rows[i]["施設名"]), [])
        if len(cands) == 1:
            matched[i] = cands[0]
            print(f"  表記ゆれで照合: {vacancy_rows[i]['施設名']} → {cands[0]['一覧名称']}")
        else:
            missing.append(i)
    return matched, missing


def cell(s):
    return unicodedata.normalize("NFKC", s or "").replace("\n", "").strip()


def load_facility_list(pdf_path, ward):
    """一覧PDFから指定区のページの施設行を {照合キー: 情報} で返す。"""
    facilities = {}
    heading = re.compile("(" + "|".join(WARDS.values()) + ")[①②③]?")
    for page in fitz.open(pdf_path):
        # 1ページに複数の区の表が載ることがある（西区②のページに安芸区など）ので、
        # 表ごとに「その表より上にある、いちばん近い区の見出し」を持ち主とみなす
        heads = sorted(
            (b[1], heading.fullmatch(b[4].strip()).group(1))
            for b in page.get_text("blocks")
            if heading.fullmatch(b[4].strip())
        )
        for table in page.find_tables().tables:
            owners = [w for y, w in heads if y <= table.bbox[1] + 5]
            if not owners or owners[-1] != ward:
                continue
            rows = table.extract()
            if len(rows) < 3 or not any("施設名" in re.sub(r"\s", "", cell(c)) for c in rows[0]):
                continue  # 注記の表など
            # 見出しは2段（「利用定員」の下に「3歳未満/3歳以上/合計」）なので両方から列を引く
            col = {}
            for header in rows[:2]:
                for i, c in enumerate(header):
                    h = re.sub(r"\s", "", cell(c))
                    if h:
                        col.setdefault(h, i)
            for r in rows[2:]:
                name = re.sub(r"^○", "", cell(r[col["施設名"]]))
                if not name:
                    continue
                facilities[key(name)] = {
                    "一覧名称": name,
                    "住所": f"広島市{ward}{cell(r[col['所在地']])}",
                    "電話": "082-" + cell(r[col["Tel"]]) if cell(r[col["Tel"]]) else "",
                    "定員": cell(r[col["合計"]]),
                    "開所時間": cell(r[col["標準時間"]]),
                    "延長保育": cell(r[col["延長保育時間"]]),
                    "一時預かり": cell(r[0]) == "○",
                }
    return facilities


def geocode(address, cache):
    if address in cache:
        return cache[address]
    with urllib.request.urlopen(GSI_URL + urllib.parse.quote(address), timeout=20) as res:
        hits = json.load(res)
    time.sleep(1)  # 公共APIなので間隔をあける
    if not hits:
        cache[address] = None
        return None
    lng, lat = hits[0]["geometry"]["coordinates"]
    cache[address] = {"lat": lat, "lng": lng, "検索結果": hits[0]["properties"]["title"]}
    return cache[address]


def main():
    vacancy_csv, list_pdf, ward_arg, limit_arg, out_js = sys.argv[1:6]
    wards = list(WARDS.values()) if ward_arg == "全区" else [ward_arg]
    limit = None if limit_arg == "全件" else int(limit_arg)
    all_rows = list(csv.DictReader(open(vacancy_csv, encoding="utf-8-sig")))
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}

    out, problems = [], []
    for ward in wards:
        facility_list = load_facility_list(list_pdf, ward)
        vacancy = [r for r in all_rows if r["区"] == ward][:limit]
        if not facility_list:
            print(f"{ward}: 施設一覧PDFにこの区のページがないため、{len(vacancy)}施設を飛ばす")
            problems += [(ward, v["施設名"], "一覧PDFに区のページなし") for v in vacancy]
            continue
        matched, missing = match_facilities(vacancy, facility_list)
        for i in missing:
            print(f"一覧に見つからない: {ward} {vacancy[i]['施設名']}")
            problems.append((ward, vacancy[i]["施設名"], "一覧に見つからない"))
        for i, v in enumerate(vacancy):
            info = matched.get(i)
            if not info:
                continue
            try:
                geo = geocode(info["住所"], cache)
            except OSError as e:  # 通信失敗はキャッシュに残さず、あとで再実行できるようにする
                print(f"通信に失敗: {v['施設名']} {info['住所']} ({e})")
                problems.append((ward, v["施設名"], "通信失敗"))
                continue
            if not geo:
                print(f"緯度経度が取れない: {v['施設名']} {info['住所']}")
                problems.append((ward, v["施設名"], "緯度経度が取れない"))
                continue
            print(f"{v['施設名']}\t{info['住所']}\t{geo['lat']:.5f},{geo['lng']:.5f}\t({geo['検索結果']})")
            out.append({
                "name": v["施設名"],
                "ward": ward,
                "type": v["種別"],
                "address": info["住所"],
                "tel": info["電話"],
                "capacity": info["定員"],
                "hours": info["開所時間"],
                "extended": info["延長保育"],
                "lat": geo["lat"],
                "lng": geo["lng"],
                "vacancy": [None if v[f"{a}歳空き"] == "" else int(v[f"{a}歳空き"]) for a in range(6)],
                "waiting": [None if v[f"{a}歳待機"] == "" else int(v[f"{a}歳待機"]) for a in range(6)],
                "note": v["備考"],
            })

    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    Path(out_js).parent.mkdir(parents=True, exist_ok=True)
    Path(out_js).write_text(
        "// scripts/build_map_data.py で生成。手で編集しない\n"
        f"window.FACILITIES = {json.dumps(out, ensure_ascii=False, indent=1)};\n",
        encoding="utf-8",
    )
    print(f"{len(out)}施設 → {out_js}")
    if problems:
        print(f"地図に載せられなかった施設: {len(problems)}件")
        for ward, name, reason in problems:
            print(f"  {ward} {name}: {reason}")


if __name__ == "__main__":
    main()
