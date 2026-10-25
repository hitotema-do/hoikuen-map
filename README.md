# 広島市 保育園空きマップ（試作）

広島市が毎月公開している「保育園等の空き状況」（区ごとのPDF）を、地図上で見られるようにする試作です。
空き人数を数字入りの色付きピンで表示し、年齢で切り替えられます。

市の公式サービスではありません。最新の状況は各区の福祉課で確認してください。

## フォルダ構成

| 場所 | 中身 |
|---|---|
| `data/pdf/YYYY-MM/` | 市の空き状況PDF（区ごと） |
| `data/facility_list/` | 市の「保育園・認定こども園等の一覧」PDF（住所・定員など） |
| `data/vacancy_YYYY-MM.csv` | 空き状況PDFから抽出した全施設の表 |
| `data/geocode_cache.json` | 住所→緯度経度の変換結果（国土地理院の住所検索） |
| `scripts/` | 抽出・変換のスクリプト |
| `web/` | 地図のページ（`index.html` と、生成される `data.js`） |

## 作り方

```
python scripts/extract_vacancy.py data/pdf/2026-10 data/vacancy_2026-10.csv
python scripts/build_map_data.py data/vacancy_2026-10.csv data/facility_list/ichiran_2026-04-01.pdf 中区 10 web/data.js
```

## 出典

- 広島市「保育園等の空き状況」「保育園・認定こども園等の一覧」
- 地図：国土地理院（淡色地図）
