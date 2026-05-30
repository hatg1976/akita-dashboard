#!/usr/bin/env python3
"""
GitHub Actions から毎月1日に呼び出す 労働市場データ更新スクリプト

【運用ルール】
  最低賃金は毎年10月に改定されます。改定後は MINIMUM_WAGE_DATA を
  直接編集して git push してください。
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


# ===========================================================
# ★ 最低賃金は毎年10月改定後にこのリストを更新してください ★
# 出典: 厚生労働省「地域別最低賃金額改定状況」
# 現在: 2025年度（秋田は令和8年3月31日発効、他県は令和7年10月頃発効）
# ===========================================================
MINIMUM_WAGE_DATA = [
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
MINIMUM_WAGE_YEAR = "2025年度"
MINIMUM_WAGE_NATIONAL_AVG = 1121  # 全国加重平均


def save_minimum_wage(today: str) -> bool:
    """最低賃金データをJSONに保存する"""
    print("\n--- 最低賃金データを保存中 ---")
    try:
        cache = {
            "fetched_at": today,
            "year": MINIMUM_WAGE_YEAR,
            "national_avg": MINIMUM_WAGE_NATIONAL_AVG,
            "source": "厚生労働省「地域別最低賃金額改定状況」・saichin.net集計",
            "note": "秋田県は令和8年3月31日発効。他県は令和7年10月頃発効。",
            "data": MINIMUM_WAGE_DATA,
        }
        out_path = OUTPUT_DIR / "minimum_wage.json"
        out_path.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        akita = next(d for d in MINIMUM_WAGE_DATA if d["都道府県"] == "秋田県")
        print(f"  ✅ 保存完了: {out_path.name}（{len(MINIMUM_WAGE_DATA)}都道府県）")
        print(f"     秋田県: {akita['最低賃金（円）']}円 / 全国加重平均: {MINIMUM_WAGE_NATIONAL_AVG}円")
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
