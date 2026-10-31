"""毎月の更新を1回で行う。

    python scripts/update_monthly.py           新しい月のPDFが出ていれば更新する
    python scripts/update_monthly.py --force   同じ月でも作り直す（PDFは取り直さない）

1. 市の「保育園等の空き状況」ページから、何月1日現在のリストかと8区のPDFの場所を読む
2. data/pdf/YYYY-MM/ にPDFを保存（すでにあれば取り直さない）
3. 抽出して data/vacancy_YYYY-MM.csv を作る
4. 前の月と比べて、おかしな点がないか確認する
5. 地図用データ web/data.js を作る

確認で気になる点があれば「要確認」を表示して終了コード2で終わる（ファイルは作るので中身を見て判断する）。
将来 GitHub Actions で自動化するときは、終了コードが0のときだけ反映する。
"""
import argparse
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from build_map_data import build
from extract_vacancy import WARDS, extract_folder, write_csv

ROOT = Path(__file__).resolve().parent.parent
PAGE_URL = "https://www.city.hiroshima.lg.jp/living/kosodate/1021251/1025847/1023646.html"

# 前の月から区の施設数がこれ以上増減したら、表の読み取りがずれていないか確認する
WARD_CHANGE_LIMIT = 3

HEADERS = {"User-Agent": "hoikuen-map-update (+https://hitotema-do.github.io/hoikuen-map/)"}


def read_page():
    """市のページから (いつ時点の年月, 見出し用の情報, {区番号: PDFのURL}) を読む。"""
    with urllib.request.urlopen(urllib.request.Request(PAGE_URL, headers=HEADERS), timeout=30) as res:
        html = res.read().decode("utf-8", errors="replace")
    # 「10</strong><strong>月1日現在…」のように文の途中にタグが入るので、タグを除いてから探す
    text = re.sub(r"<[^>]+>", "", html)
    m = re.search(r"(\d{1,2})月1日現在の令和(\d+)年(\d{1,2})月入所", text)
    if not m:
        raise SystemExit("市のページで「〇月1日現在の令和〇年〇月入所」が見つからない。ページの作りが変わった可能性がある")
    as_of_month, reiwa, entry_month = int(m[1]), int(m[2]), int(m[3])
    entry_year = 2018 + reiwa
    as_of_year = entry_year - 1 if as_of_month > entry_month else entry_year  # 12月1日現在の1月入所分
    links = {}
    for href in re.findall(r'href="([^"]+\.pdf)"', html):
        name = href.rsplit("/", 1)[-1]
        if name[:2] in WARDS and name[:2] not in links:
            links[name[:2]] = urllib.parse.urljoin(PAGE_URL, href)
    info = {"asOf": f"{as_of_month}月1日", "entry": f"{entry_month}月"}
    return f"{as_of_year}-{as_of_month:02d}", info, links


def download(links, folder):
    folder.mkdir(parents=True, exist_ok=True)
    for code, url in sorted(links.items()):
        path = folder / url.rsplit("/", 1)[-1]
        if list(folder.glob(f"{code}*.pdf")):
            continue  # この区のPDFは取得済み（ファイル名が違っても取り直さない）
        print(f"ダウンロード: {path.name}")
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as res:
            data = res.read()
        if not data.startswith(b"%PDF"):
            raise SystemExit(f"{url} がPDFではない")
        path.write_bytes(data)


def counts_by_ward(rows):
    c = {w: 0 for w in WARDS.values()}
    for r in rows:
        c[r["区"]] += 1
    return c


def open_count(rows, age):
    return sum(1 for r in rows if str(r[f"{age}歳空き"]).isdigit() and int(r[f"{age}歳空き"]) > 0)


def check(rows, prev_rows, problems):
    """前の月と比べて気になる点を返す。"""
    warnings = []
    now = counts_by_ward(rows)
    for ward, n in now.items():
        if n == 0:
            warnings.append(f"{ward}の施設が0件（PDFが読めていない可能性）")
    if prev_rows:
        before = counts_by_ward(prev_rows)
        for ward in now:
            if abs(now[ward] - before[ward]) >= WARD_CHANGE_LIMIT:
                warnings.append(f"{ward}の施設数が {before[ward]} → {now[ward]} と大きく変わった（表の読み取りのずれがないか確認）")
    for ward, name, reason in problems:
        warnings.append(f"地図に載せられない施設：{ward} {name}（{reason}）")
    # 抽出で数として読めなかったセル（備考に「」付きで残る）。既知の書き方は除く
    for r in rows:
        for raw in re.findall(r"「([^」]*)」", r["備考"]):
            if not re.fullmatch(r"\d+以上|\d+\(\d+\)", raw):
                warnings.append(f"読み取れない値：{r['区']} {r['施設名']}「{raw}」")
    return warnings


def latest_previous_csv(month):
    olds = sorted(p for p in (ROOT / "data").glob("vacancy_*.csv") if p.stem < f"vacancy_{month}")
    return olds[-1] if olds else None


def read_csv(path):
    import csv
    return list(csv.DictReader(open(path, encoding="utf-8-sig")))


def main():
    parser = argparse.ArgumentParser(description="保育園空きマップの月次更新")
    parser.add_argument("--force", action="store_true", help="同じ月でも作り直す")
    args = parser.parse_args()

    month, info, links = read_page()
    print(f"市のページ：{info['asOf']}現在・{info['entry']}入所分（{len(links)}区のPDF）")
    if len(links) != len(WARDS):
        raise SystemExit(f"区のPDFが {len(links)} 個しか見つからない（8個のはず）。ページの作りが変わった可能性がある")

    folder = ROOT / "data" / "pdf" / month
    vacancy_csv = ROOT / "data" / f"vacancy_{month}.csv"
    if vacancy_csv.exists() and not args.force:
        print(f"{month} の分はすでに作成済み。新しい月のPDFはまだ出ていない（作り直すときは --force）")
        return 0

    download(links, folder)
    for code in WARDS:
        n = len(list(folder.glob(f"{code}*.pdf")))
        if n != 1:
            raise SystemExit(f"{folder} に {WARDS[code]} のPDFが {n} 個ある（1個のはず）。余分なファイルを消してからやり直す")
    rows = extract_folder(folder)
    write_csv(rows, vacancy_csv)
    rows = read_csv(vacancy_csv)  # 数値・空欄の扱いをCSVと同じにそろえる

    list_pdf = sorted((ROOT / "data" / "facility_list").glob("ichiran_*.pdf"))[-1]
    print(f"施設一覧：{list_pdf.name}")
    out, problems = build(vacancy_csv, list_pdf, list(WARDS.values()), None, ROOT / "web" / "data.js", info)

    prev_csv = latest_previous_csv(month)
    prev_rows = read_csv(prev_csv) if prev_csv else []
    warnings = check(rows, prev_rows, problems)

    print("\n===== まとめ =====")
    print(f"{info['asOf']}現在・{info['entry']}入所分")
    if prev_rows:
        print(f"比べた月：{prev_csv.stem.replace('vacancy_', '')}")
        print(f"施設数：{len(prev_rows)} → {len(rows)}（地図に載せた施設 {len(out)}）")
        before_names = {(r['区'], r['施設名']) for r in prev_rows}
        now_names = {(r['区'], r['施設名']) for r in rows}
        for w, n in sorted(now_names - before_names):
            print(f"  新しく載った施設：{w} {n}")
        for w, n in sorted(before_names - now_names):
            print(f"  載らなくなった施設：{w} {n}")
        for age in (0, 1, 2):
            print(f"{age}歳の空きがある施設：{open_count(prev_rows, age)} → {open_count(rows, age)}")
    else:
        print(f"施設数：{len(rows)}（地図に載せた施設 {len(out)}）")
    if warnings:
        print(f"\n要確認（{len(warnings)}件）")
        for w in warnings:
            print(f"  - {w}")
        return 2
    print("\n確認で気になる点はなし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
