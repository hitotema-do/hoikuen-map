"""空き状況CSVと市の施設一覧PDFを突き合わせ、緯度経度を付けて地図用データ(web/data.js)を作る。

使い方:
    python scripts/build_map_data.py <空き状況CSV> <施設一覧PDF> <区> <件数> <出力JS>

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

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "geocode_cache.json"
GSI_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch?q="


def key(name):
    """施設名の表記ゆれ（全角半角・空白・ハイフン類・(注7)など）を吸収した照合用キー。"""
    s = unicodedata.normalize("NFKC", name or "").replace("\n", "")
    s = re.sub(r"^○", "", s)
    s = re.sub(r"[(（]注\d+[)）]", "", s)
    return re.sub(r"[\s・\-－ｰ―‐ー]", "", s)


def cell(s):
    return unicodedata.normalize("NFKC", s or "").replace("\n", "").strip()


def load_facility_list(pdf_path, ward):
    """一覧PDFから指定区のページの施設行を {照合キー: 情報} で返す。"""
    facilities = {}
    for page in fitz.open(pdf_path):
        if not page.get_text().strip().startswith(ward):
            continue
        for table in page.find_tables().tables:
            rows = table.extract()
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
    vacancy_csv, list_pdf, ward, limit, out_js = sys.argv[1:6]
    facility_list = load_facility_list(list_pdf, ward)
    vacancy = [r for r in csv.DictReader(open(vacancy_csv, encoding="utf-8-sig")) if r["区"] == ward]
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}

    out = []
    for v in vacancy[: int(limit)]:
        info = facility_list.get(key(v["施設名"]))
        if not info:
            print(f"一覧に見つからない: {v['施設名']}")
            continue
        geo = geocode(info["住所"], cache)
        if not geo:
            print(f"緯度経度が取れない: {v['施設名']} {info['住所']}")
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


if __name__ == "__main__":
    main()
