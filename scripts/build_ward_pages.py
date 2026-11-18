"""区ごとのページ（検索の入口）を、web/data.js から作る。

web/ku/<区>.html を8枚、web/ku/index.html を1枚作り、web/sitemap.xml にも足す。
数字は地図と同じデータだけを使う。待機児童の人数は載せない（合計値を出さない決まりのため）。
update_monthly.py が data.js を作ったあとに呼ぶ。手で動かすときは：

    python scripts/build_ward_pages.py
"""
import html
import json
import re
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
OUT = WEB / "ku"
BASE = "https://hitotema-do.github.io/hoikuen-map/"
OFFICIAL = "https://www.city.hiroshima.lg.jp/living/kosodate/1021251/1025847/1023646.html"
WARDS = [("中区", "naka"), ("東区", "higashi"), ("南区", "minami"), ("西区", "nishi"),
         ("安佐南区", "asaminami"), ("安佐北区", "asakita"), ("安芸区", "aki"), ("佐伯区", "saeki")]
TYPES = ["保育園", "認定こども園", "小規模保育", "事業所内保育"]
e = html.escape


def load():
    s = (WEB / "data.js").read_text(encoding="utf-8")
    info = json.loads(re.search(r"window\.DATA_INFO = (\{.*?\});", s).group(1))
    fac = json.loads(re.search(r"window\.FACILITIES = (\[.*\]);", s, re.S).group(1))
    return info, fac


def cell(v):
    if v is None:
        return '<td class="na">−</td>'
    return f'<td class="{"ok" if v > 0 else "zero"}">{v}</td>'

# ひとてま堂の数え係（案内ページ用）：このページを、この端末で1日1回だけ「+1」する。
# 送るのはアプリ名・ページ名・来たサイトの名前だけ（名前や端末を見分ける番号は送らない）。
# 作者の端末（アプリ側で「数えない」にしたもの）は数えない
COUNTER = r"""<script>
(function () {
  try {
    if (localStorage.getItem("hitotema.count.off")) return;
    var APP = "hoikuen", KEY = "hitotema.page." + APP;
    var page = decodeURIComponent(location.pathname.split("/").pop().replace(/\.html$/, "")) || "index";
    var day = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
    var s = JSON.parse(localStorage.getItem(KEY) || "null");
    if (!s || s.d !== day) s = { d: day, p: [] };
    if (s.p.indexOf(page) >= 0) return;
    s.p.push(page);
    localStorage.setItem(KEY, JSON.stringify(s));
    var ref = ""; try { ref = new URL(document.referrer).hostname; if (ref === location.hostname) ref = "self"; } catch (e) {}
    navigator.sendBeacon("https://hitotema-count.hitotema-do.workers.dev/page",
      new Blob([JSON.stringify({ a: APP, p: page, r: ref })], { type: "text/plain" }));
  } catch (e) {}
})();
</script>"""

def page(title, desc, url, body):
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:locale" content="ja_JP">
<meta property="og:site_name" content="広島市 保育園空きマップ">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{BASE}og.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="../icon.svg" type="image/svg+xml">
<link rel="stylesheet" href="../pages.css">
<style>
.crumb {{ font-size: 13px; color: var(--sub); }}
.crumb a {{ color: var(--sub); }}
.asof {{ background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 12px 16px; margin: 0 0 16px; }}
.sum {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 0 0 16px; }}
.sum div {{ background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 8px; text-align: center; font-size: 13px; color: var(--sub); }}
.sum b {{ display: block; font-size: 22px; color: var(--ink); }}
.small {{ font-size: 13px; color: var(--sub); }}
.tbl {{ overflow-x: auto; }}
.tbl table {{ font-size: 14px; min-width: 520px; }}
.tbl th, .tbl td {{ padding: 8px 4px; }}
.tbl th {{ width: auto; font-size: 12px; color: var(--sub); }}
.tbl td.ok, .tbl td.zero, .tbl td.na {{ text-align: center; width: 2.6em; }}
.tbl td.ok {{ font-weight: 700; color: var(--accent); }}
.tbl td.zero, .tbl td.na {{ color: var(--sub); }}
.tbl .t {{ display: block; font-size: 12px; color: var(--sub); }}
.links {{ display: flex; flex-wrap: wrap; gap: 6px 14px; list-style: none; padding: 0; }}
</style>
{COUNTER}
</head>
<body>
<div class="wrap">
{body}
  <div class="foot">
    <nav aria-label="運営情報">
      <a href="../about.html">このアプリについて</a>
      <a href="../privacy.html">プライバシーポリシー</a>
      <a href="../contact.html">お問い合わせ</a>
      <a href="../hitotema.html">ひとてま堂について</a>
    </nav>
    <p>広島市が毎月公開している<a href="{OFFICIAL}" rel="noopener">保育園等の空き状況</a>をもとに、ひとてま堂が作っています。広島市の公式サービスではありません。空きがあっても入園できるとは限りません。最新の状況は各区の福祉課で確かめてください。</p>
  </div>
</div>
</body>
</html>
"""


def main():
    info, fac = load()
    when = f"{info['asOf']}時点・{info['entry']}入所分"
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.html"):
        old.unlink()
    others = lambda me: '  <ul class="links">' + "".join(
        f'<li><a href="{slug}.html">{w}</a></li>' for w, slug in WARDS if w != me) + "</ul>"

    for ward, slug in WARDS:
        fs = [f for f in fac if f["ward"] == ward]
        fs.sort(key=lambda f: (TYPES.index(f["type"]) if f["type"] in TYPES else 9, f["name"]))
        n_open = [sum(1 for f in fs if (f["vacancy"][a] or 0) > 0) for a in range(6)]
        any_open = sum(1 for f in fs if any((v or 0) > 0 for v in f["vacancy"]))
        url = f"{BASE}ku/{slug}.html"
        title = f"{ward}の保育園 空き状況（{info['entry']}入所分）｜広島市 保育園空きマップ"
        desc = (f"広島市{ward}の保育園・認定こども園など{len(fs)}施設の空き状況（{when}）。"
                f"0歳の空きがある施設は{n_open[0]}、1歳は{n_open[1]}、2歳は{n_open[2]}。年齢ごとの空き人数を一覧と地図で見られます（非公式・毎月更新）。")
        rows = "".join(
            f'<tr><td>{e(f["name"])}<span class="t">{e(f["type"])}'
            + (f'・{e(f["note"])}' if f.get("note") else "") + "</span></td>"
            + "".join(cell(v) for v in f["vacancy"]) + "</tr>" for f in fs)
        body = f"""  <p class="crumb"><a href="../">保育園空きマップ</a> ＞ <a href="./">区から探す</a></p>
  <h1>広島市{ward}の保育園・こども園の空き状況</h1>
  <p class="asof"><strong>{e(when)}</strong><br>広島市が毎月公開している資料から。次の更新は来月の初めです。</p>
  <div class="sum">
    <div>0歳の空き<b>{n_open[0]}</b>施設</div>
    <div>1歳の空き<b>{n_open[1]}</b>施設</div>
    <div>2歳の空き<b>{n_open[2]}</b>施設</div>
  </div>
  <p>{ward}には、地図に載せている施設が{len(fs)}あります。そのうち、どこかの年齢に空きがある施設は{any_open}です。</p>
  <p><a class="btn" href="../?from=ku&amp;ward={quote(ward)}">{ward}の空きを地図で見る</a></p>
  <p class="small">地図では、年齢を選ぶと空き人数が数字入りのピンで出ます。無料・登録不要です。</p>
  <h2>施設ごとの空き人数（{e(info['entry'])}入所分）</h2>
  <p class="small">数字は空き人数。「−」はその年齢を受け入れていない施設です。表は横に動かせます。</p>
  <div class="tbl"><table>
    <thead><tr><th>施設名</th><th>0歳</th><th>1歳</th><th>2歳</th><th>3歳</th><th>4歳</th><th>5歳</th></tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
  <h2>ほかの区</h2>
{others(ward)}"""
        (OUT / f"{slug}.html").write_text(page(title, desc, url, body), encoding="utf-8")

    # 一覧
    lines = []
    for ward, slug in WARDS:
        fs = [f for f in fac if f["ward"] == ward]
        n0 = sum(1 for f in fs if (f["vacancy"][0] or 0) > 0)
        n1 = sum(1 for f in fs if (f["vacancy"][1] or 0) > 0)
        lines.append(f'<tr><td><a href="{slug}.html">{ward}</a></td><td>{len(fs)}</td><td>{n0}</td><td>{n1}</td></tr>')
    body = f"""  <p class="crumb"><a href="../">保育園空きマップ</a> ＞ 区から探す</p>
  <h1>広島市の保育園 空き状況（区ごと）</h1>
  <p class="asof"><strong>{e(when)}</strong><br>広島市が毎月公開している資料から。</p>
  <div class="tbl"><table style="min-width:0">
    <thead><tr><th>区</th><th>施設</th><th>0歳の空きあり</th><th>1歳の空きあり</th></tr></thead>
    <tbody>{''.join(lines)}</tbody>
  </table></div>
  <p class="small">数字は施設の数です。区の名前を押すと、施設ごとの空き人数が分かります。</p>
  <p><a class="btn" href="../?from=kulist">地図で見る</a></p>"""
    (OUT / "index.html").write_text(page(
        f"広島市の保育園 空き状況（区ごと・{info['entry']}入所分）｜広島市 保育園空きマップ",
        f"広島市の全8区の保育園・認定こども園などの空き状況（{when}）を、区ごとにまとめました。年齢ごとの空き人数が分かります（非公式・毎月更新）。",
        f"{BASE}ku/", body), encoding="utf-8")

    sm = WEB / "sitemap.xml"
    keep = [u for u in re.findall(r"<loc>(.*?)</loc>", sm.read_text(encoding="utf-8")) if "/ku/" not in u]
    urls = keep + [f"{BASE}ku/"] + [f"{BASE}ku/{slug}.html" for _, slug in WARDS]
    sm.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                  + "".join(f"  <url>\n    <loc>{u}</loc>\n  </url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    print(f"区のページ {len(WARDS)} 枚と一覧を作りました（{when}）")


if __name__ == "__main__":
    main()
