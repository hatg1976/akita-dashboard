"""
秋田県ダッシュボード データ自動更新スクリプト
毎月1日にリモートエージェントが実行する

使い方:
  python update_data.py

必要な環境変数:
  ESTAT_API_KEY: e-Stat APIキー（https://www.e-stat.go.jp/api/ で取得）

出力:
  data/akita_population.json
  data/akita_industry.json
  data/akita_economy.json
  data/last_updated.txt
"""

import os
import json
import requests
from datetime import datetime
from pathlib import Path

ESTAT_API_KEY = os.getenv("ESTAT_API_KEY", "")
BASE_URL = "https://api.e-stat.go.jp/rest/3.0/app/json"
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

AKITA_AREA = "05000"  # 秋田県コード


def estat_get(endpoint: str, params: dict) -> dict:
    params["appId"] = ESTAT_API_KEY
    params["lang"] = "J"
    r = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_population() -> list[dict]:
    """国勢調査 都道府県別人口（統計表ID: 0003410379）"""
    params = {
        "statsDataId": "0003410379",
        "cdArea": AKITA_AREA,
    }
    data = estat_get("getStatsData", params)
    values = data["GET_STATS_DATA"]["STATISTICAL_DATA"]["DATA_INF"]["VALUE"]
    if isinstance(values, dict):
        values = [values]
    return [{"value": v.get("$"), "time": v.get("@time"), "cat": v.get("@cat01")} for v in values]


def fetch_labor_market() -> list[dict]:
    """労働力調査 都道府県別（統計表ID: 0003031186）"""
    params = {
        "statsDataId": "0003031186",
        "cdArea": AKITA_AREA,
    }
    data = estat_get("getStatsData", params)
    values = data["GET_STATS_DATA"]["STATISTICAL_DATA"]["DATA_INF"]["VALUE"]
    if isinstance(values, dict):
        values = [values]
    return [{"value": v.get("$"), "time": v.get("@time"), "cat": v.get("@cat01")} for v in values]


def save_json(filename: str, data: dict) -> None:
    path = DATA_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"保存: {path}")


def main():
    if not ESTAT_API_KEY:
        print("エラー: ESTAT_API_KEY が設定されていません")
        print("https://www.e-stat.go.jp/api/ でAPIキーを取得してください")
        raise SystemExit(1)

    now = datetime.now().isoformat()
    print(f"データ更新開始: {now}")

    results = {}

    # 人口データ
    try:
        print("人口データを取得中...")
        results["population"] = fetch_population()
        print(f"  → {len(results['population'])} 件取得")
    except Exception as e:
        print(f"  → 人口データ取得失敗: {e}")
        results["population"] = []

    # 労働市場データ
    try:
        print("労働市場データを取得中...")
        results["labor"] = fetch_labor_market()
        print(f"  → {len(results['labor'])} 件取得")
    except Exception as e:
        print(f"  → 労働市場データ取得失敗: {e}")
        results["labor"] = []

    # 保存
    save_json("akita_stats.json", {
        "updated_at": now,
        "data": results,
    })

    # 更新日時を記録
    (DATA_DIR / "last_updated.txt").write_text(now, encoding="utf-8")

    print(f"更新完了: {now}")


if __name__ == "__main__":
    main()
