#!/usr/bin/env python3
"""
GitHub Actions から毎月1日に呼び出す 労働市場データ更新スクリプト

最低賃金は saichin.net（厚生労働省データ集計サイト）から自動取得します。
取得失敗時は MINIMUM_WAGE_FALLBACK（前回確認済み値）で保存します。
有効求人倍率は e-Stat API で毎月自動取得します（APIキー必要）。

出力先: data/labor_cache/minimum_wage.json
        data/labor_cache/job_ratio_pref.json
"""
import json
import os
import sys
from datetime import date
from pathlib import Path

# Windows環境でUTF-8出力を強制
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

OUTPUT_DIR = Path(__file__).parent / "data" / "labor_cache"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# 都道府県 → 地方の対応表
_REGION_MAP = {
    "北海道": "北海道",
    "青森県": "東北", "岩手県": "東北", "宮城県": "東北",
    "秋田県": "東北", "山形県": "東北", "福島県": "東北",
    "茨城県": "関東", "栃木県": "関東", "群馬県": "関東",
    "埼玉県": "関東", "千葉県": "関東", "東京都": "関東", "神奈川県": "関東",
    "新潟県": "中部", "富山県": "中部", "石川県": "中部", "福井県": "中部",
    "山梨県": "中部", "長野県": "中部", "岐阜県": "中部",
    "静岡県": "中部", "愛知県": "中部",
    "三重県": "近畿", "滋賀県": "近畿", "京都府": "近畿",
    "大阪府": "近畿", "兵庫県": "近畿", "奈良県": "近畿", "和歌山県": "近畿",
    "鳥取県": "中国", "島根県": "中国", "岡山県": "中国",
    "広島県": "中国", "山口県": "中国",
    "徳島県": "四国", "香川県": "四国", "愛媛県": "四国", "高知県": "四国",
    "福岡県": "九州", "佐賀県": "九州", "長崎県": "九州",
    "熊本県": "九州", "大分県": "九州", "宮崎県": "九州",
    "鹿児島県": "九州", "沖縄県": "九州",
}


def scrape_minimum_wage() -> tuple[list, str] | tuple[None, None]:
    """saichin.net から最低賃金データを自動取得する。
    出典: 厚生労働省「地域別最低賃金額改定状況」をsaichin.netが集計。
    Returns: (data_list, year_str) または (None, None)（取得失敗時）"""
    import requests
    from html.parser import HTMLParser

    class _TableParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.in_table = self.in_td = False
            self.current_row, self.all_rows = [], []
            self.current_cell = ""

        def handle_starttag(self, tag, attrs):
            if tag == "table": self.in_table = True
            if tag == "tr" and self.in_table: self.current_row = []
            if tag in ("td", "th") and self.in_table:
                self.in_td = True; self.current_cell = ""

        def handle_endtag(self, tag):
            if tag in ("td", "th") and self.in_td:
                self.current_row.append(self.current_cell.strip())
                self.in_td = False
            if tag == "tr" and self.current_row:
                self.all_rows.append(self.current_row); self.current_row = []
            if tag == "table": self.in_table = False

        def handle_data(self, data):
            if self.in_td: self.current_cell += data

    try:
        resp = requests.get(
            "https://saichin.net/",
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.encoding = "utf-8"
        parser = _TableParser()
        parser.feed(resp.text)
        rows = parser.all_rows

        # ヘッダー行を除く（列: No., 都道府県, 最低賃金, 前年比, 引き上げ率, 発効日, 区分）
        # 都道府県行のみ抽出（No.が数字、都道府県名が「県/都/道/府」で終わる）
        data_rows = [
            r for r in rows
            if len(r) >= 3 and r[0].isdigit()
            and any(r[1].endswith(s) for s in ["県", "都", "道", "府"])
        ]
        if len(data_rows) < 47:
            print(f"  ⚠ 取得行数が少ない（{len(data_rows)}行）。構造が変わった可能性あり。")
            return None, None

        result = []
        # 発効日から年度を推定（最も多い発効年度）
        years = []
        for row in data_rows:
            pref = row[1]
            wage_str = row[2].replace(",", "").replace("円", "").strip()
            eff_date = row[5] if len(row) > 5 else ""
            try:
                wage = int(wage_str)
                result.append({
                    "都道府県": pref,
                    "最低賃金（円）": wage,
                    "発効日": eff_date,
                    "地方": _REGION_MAP.get(pref, "その他"),
                })
                if eff_date:
                    years.append(eff_date[:4])
            except ValueError:
                continue

        # 年度文字列（例: 2025年度）
        dominant_year = max(set(years), key=years.count) if years else "不明"
        year_str = f"{dominant_year}年度"

        print(f"  saichin.net から {len(result)}都道府県 取得完了（{year_str}）")
        return result, year_str

    except Exception as e:
        print(f"  ⚠ saichin.net 取得エラー: {type(e).__name__}: {e}")
        return None, None


# ===========================================================
# フォールバック用ハードコードデータ（saichin.net 取得失敗時に使用）
# 出典: 厚生労働省「地域別最低賃金額改定状況」2025年度
# ===========================================================
MINIMUM_WAGE_FALLBACK = [
    {"都道府県": "北海道", "最低賃金（円）": 1075, "地方": "北海道"},
    {"都道府県": "青森県", "最低賃金（円）": 1029, "地方": "東北"},
    {"都道府県": "岩手県", "最低賃金（円）": 1031, "地方": "東北"},
    {"都道府県": "宮城県", "最低賃金（円）": 1038, "地方": "東北"},
    {"都道府県": "秋田県", "最低賃金（円）": 1031, "地方": "東北"},
    {"都道府県": "山形県", "最低賃金（円）": 1032, "地方": "東北"},
    {"都道府県": "福島県", "最低賃金（円）": 1033, "地方": "東北"},
    {"都道府県": "茨城県", "最低賃金（円）": 1074, "地方": "関東"},
    {"都道府県": "栃木県", "最低賃金（円）": 1068, "地方": "関東"},
    {"都道府県": "群馬県", "最低賃金（円）": 1063, "地方": "関東"},
    {"都道府県": "埼玉県", "最低賃金（円）": 1141, "地方": "関東"},
    {"都道府県": "千葉県", "最低賃金（円）": 1140, "地方": "関東"},
    {"都道府県": "東京都", "最低賃金（円）": 1226, "地方": "関東"},
    {"都道府県": "神奈川県", "最低賃金（円）": 1225, "地方": "関東"},
    {"都道府県": "新潟県", "最低賃金（円）": 1050, "地方": "中部"},
    {"都道府県": "富山県", "最低賃金（円）": 1062, "地方": "中部"},
    {"都道府県": "石川県", "最低賃金（円）": 1054, "地方": "中部"},
    {"都道府県": "福井県", "最低賃金（円）": 1053, "地方": "中部"},
    {"都道府県": "山梨県", "最低賃金（円）": 1052, "地方": "中部"},
    {"都道府県": "長野県", "最低賃金（円）": 1061, "地方": "中部"},
    {"都道府県": "岐阜県", "最低賃金（円）": 1065, "地方": "中部"},
    {"都道府県": "静岡県", "最低賃金（円）": 1097, "地方": "中部"},
    {"都道府県": "愛知県", "最低賃金（円）": 1140, "地方": "中部"},
    {"都道府県": "三重県", "最低賃金（円）": 1087, "地方": "近畿"},
    {"都道府県": "滋賀県", "最低賃金（円）": 1080, "地方": "近畿"},
    {"都道府県": "京都府", "最低賃金（円）": 1122, "地方": "近畿"},
    {"都道府県": "大阪府", "最低賃金（円）": 1177, "地方": "近畿"},
    {"都道府県": "兵庫県", "最低賃金（円）": 1116, "地方": "近畿"},
    {"都道府県": "奈良県", "最低賃金（円）": 1051, "地方": "近畿"},
    {"都道府県": "和歌山県", "最低賃金（円）": 1045, "地方": "近畿"},
    {"都道府県": "鳥取県", "最低賃金（円）": 1030, "地方": "中国"},
    {"都道府県": "島根県", "最低賃金（円）": 1033, "地方": "中国"},
    {"都道府県": "岡山県", "最低賃金（円）": 1047, "地方": "中国"},
    {"都道府県": "広島県", "最低賃金（円）": 1085, "地方": "中国"},
    {"都道府県": "山口県", "最低賃金（円）": 1043, "地方": "中国"},
    {"都道府県": "徳島県", "最低賃金（円）": 1046, "地方": "四国"},
    {"都道府県": "香川県", "最低賃金（円）": 1036, "地方": "四国"},
    {"都道府県": "愛媛県", "最低賃金（円）": 1033, "地方": "四国"},
    {"都道府県": "高知県", "最低賃金（円）": 1023, "地方": "四国"},
    {"都道府県": "福岡県", "最低賃金（円）": 1057, "地方": "九州"},
    {"都道府県": "佐賀県", "最低賃金（円）": 1030, "地方": "九州"},
    {"都道府県": "長崎県", "最低賃金（円）": 1031, "地方": "九州"},
    {"都道府県": "熊本県", "最低賃金（円）": 1034, "地方": "九州"},
    {"都道府県": "大分県", "最低賃金（円）": 1035, "地方": "九州"},
    {"都道府県": "宮崎県", "最低賃金（円）": 1023, "地方": "九州"},
    {"都道府県": "鹿児島県", "最低賃金（円）": 1026, "地方": "九州"},
    {"都道府県": "沖縄県", "最低賃金（円）": 1023, "地方": "九州"},
]
MINIMUM_WAGE_FALLBACK_YEAR = "2025年度"
MINIMUM_WAGE_NATIONAL_AVG = 1121  # 全国加重平均（2025年度）


def save_minimum_wage(today: str) -> bool:
    """最低賃金データを取得してJSONに保存する。
    saichin.net から自動取得し、失敗時はフォールバック値を使用。"""
    print("\n--- 最低賃金データを取得中 ---")
    try:
        # 1. saichin.net から自動取得を試みる
        scraped_data, scraped_year = scrape_minimum_wage()

        if scraped_data:
            wage_data = scraped_data
            wage_year = scraped_year
            source = "saichin.net 自動取得（出典: 厚生労働省「地域別最低賃金額改定状況」）"
            # 全国加重平均は公式値を使用（単純平均≠加重平均）
            avg = MINIMUM_WAGE_NATIONAL_AVG
        else:
            # 2. フォールバック: ハードコードデータを使用
            print("  ⚠ 自動取得失敗。フォールバックデータを使用します。")
            wage_data = MINIMUM_WAGE_FALLBACK
            wage_year = MINIMUM_WAGE_FALLBACK_YEAR
            source = "フォールバック（厚生労働省「地域別最低賃金額改定状況」2025年度）"
            avg = MINIMUM_WAGE_NATIONAL_AVG

        cache = {
            "fetched_at": today,
            "year": wage_year,
            "national_avg": avg,
            "source": source,
            "data": wage_data,
        }
        out_path = OUTPUT_DIR / "minimum_wage.json"
        out_path.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        akita = next((d for d in wage_data if d["都道府県"] == "秋田県"), {})
        print(f"  ✅ 保存完了: {out_path.name}（{len(wage_data)}都道府県、{wage_year}）")
        print(f"     秋田県: {akita.get('最低賃金（円）', '?')}円 / 全国平均: {avg}円")
        return True
    except Exception as e:
        print(f"  ❌ エラー: {type(e).__name__}: {e}")
        return False


def fetch_job_ratio_pref(today: str) -> bool:
    """e-Stat から都道府県別有効求人倍率（最新月）を取得して保存する"""
    api_key = os.getenv("ESTAT_API_KEY", "")
    if not api_key:
        print("\n--- 有効求人倍率（都道府県別）: APIキー未設定のためスキップ ---")
        return False

    print("\n--- 有効求人倍率（都道府県別）を e-Stat から取得中 ---")
    import requests

    base_url = "https://api.e-stat.go.jp/rest/3.0/app/json"

    # 1. 一般職業紹介状況から都道府県別有効求人倍率のテーブルを検索
    try:
        resp = requests.get(
            f"{base_url}/getStatsList",
            params={
                "appId": api_key,
                "lang": "J",
                "statsCode": "00450222",  # 職業安定業務統計
                "searchWord": "都道府県 有効求人倍率",
                "limit": 20,
            },
            timeout=30,
        )
        resp.raise_for_status()
        tables = (resp.json()
                  .get("GET_STATS_LIST", {})
                  .get("DATALIST_INF", {})
                  .get("TABLE_INF", []))
        if isinstance(tables, dict):
            tables = [tables]
    except Exception as e:
        print(f"  ❌ テーブル検索エラー: {e}")
        return False

    # 最新のテーブルを選択（SURVEY_DATE が最大のもの）
    candidates = []
    for t in tables:
        title = (t.get("TITLE") or {}).get("$", "")
        survey = str(t.get("SURVEY_DATE", ""))
        tid = t.get("@id", "")
        if "有効求人倍率" in title and "都道府県" in title and tid:
            candidates.append({"id": tid, "title": title, "survey": survey})

    if not candidates:
        print("  ⚠ 対象テーブルが見つかりませんでした")
        return False

    candidates.sort(key=lambda x: x["survey"], reverse=True)
    latest = candidates[0]
    print(f"  最新テーブル: {latest['title'][:60]}（調査: {latest['survey']}）")

    # 2. データ取得
    try:
        resp2 = requests.get(
            f"{base_url}/getStatsData",
            params={
                "appId": api_key,
                "lang": "J",
                "statsDataId": latest["id"],
                "metaGetFlg": "Y",
                "cntGetFlg": "N",
            },
            timeout=30,
        )
        resp2.raise_for_status()
        stat_data = resp2.json().get("GET_STATS_DATA", {}).get("STATISTICAL_DATA", {})
        values = stat_data.get("DATA_INF", {}).get("VALUE", [])
        if isinstance(values, dict):
            values = [values]
    except Exception as e:
        print(f"  ❌ データ取得エラー: {e}")
        return False

    if not values:
        print("  ⚠ データが空でした")
        return False

    import pandas as pd
    df = pd.DataFrame(values)
    df.columns = [c.lstrip("@") for c in df.columns]

    cache = {
        "fetched_at": today,
        "table_id": latest["id"],
        "survey": latest["survey"],
        "source": "厚生労働省「一般職業紹介状況（職業安定業務統計）」/ e-Stat",
        "data": df.to_dict(orient="records"),
    }
    out_path = OUTPUT_DIR / "job_ratio_pref.json"
    out_path.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  ✅ 保存完了: {out_path.name}（{len(df)}件）")
    return True


def main():
    today = date.today().isoformat()
    fetched, errors = [], []

    if save_minimum_wage(today):
        fetched.append("最低賃金（全47都道府県）")
    else:
        errors.append("最低賃金")

    if fetch_job_ratio_pref(today):
        fetched.append("有効求人倍率（都道府県別）")
    else:
        errors.append("有効求人倍率（APIキー未設定またはエラー）")

    manifest = {
        "last_updated": today,
        "fetched": fetched,
        "errors": errors,
    }
    (OUTPUT_DIR / "last_updated.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n完了: {today}  成功={fetched}  エラー={errors}")


if __name__ == "__main__":
    main()
    sys.exit(0)
