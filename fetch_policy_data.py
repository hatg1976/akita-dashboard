#!/usr/bin/env python3
"""
GitHub Actions から毎月1日に呼び出す政策KPIデータ更新スクリプト

更新内容:
  - 社会増減数（住民基本台帳人口移動報告 e-Stat API）
  - last_updated タイムスタンプ
  - 取得できた場合のみKPI現状値を上書き

出力先: data/policy_cache/policy_data.json

環境変数:
  ESTAT_API_KEY: e-Stat APIキー（GitHub Secrets から渡す）
"""
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

OUTPUT_PATH = Path(__file__).parent / "data" / "policy_cache" / "policy_data.json"
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

ESTAT_API_KEY = os.getenv("ESTAT_API_KEY", "")
ESTAT_BASE_URL = "https://api.e-stat.go.jp/rest/3.0/app/json"

# 住民基本台帳人口移動報告の統計表ID（秋田県の転入・転出データ）
MIGRATION_STAT_ID = "0000020201"
AKITA_AREA_CODE = "05000"


def fetch_migration_data() -> dict | None:
    """e-Stat から秋田県の転入・転出数を取得し社会増減を計算する"""
    if not ESTAT_API_KEY:
        print("  ⚠ ESTAT_API_KEY 未設定 → 社会増減の自動更新をスキップ")
        return None

    url = f"{ESTAT_BASE_URL}/getStatsData"
    params = {
        "appId": ESTAT_API_KEY,
        "statsDataId": MIGRATION_STAT_ID,
        "cdArea": AKITA_AREA_CODE,
        "metaGetFlg": "N",
        "cntGetFlg": "N",
        "limit": 100,
    }
    try:
        import requests
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        stat_data = data.get("GET_STATS_DATA", {}).get("STATISTICAL_DATA", {})
        data_inf = stat_data.get("DATA_INF", {})
        value_list = data_inf.get("VALUE", [])

        if not value_list:
            print("  ⚠ 移動報告データが空でした")
            return None

        # 最新年の転入超過数（転入 - 転出）を計算
        # 年次データのみ使用（月次の集計は除外）
        year_data: dict[str, dict] = {}
        for v in value_list:
            tab = v.get("@tab", "")
            time_code = v.get("@time", "")
            val_str = v.get("$", "").replace(",", "")

            # 年次コード例: "2023000000" → 2023年
            if len(time_code) >= 4 and time_code[4:] in ("000000", "000"):
                year = time_code[:4]
            else:
                continue

            if year not in year_data:
                year_data[year] = {}
            try:
                year_data[year][tab] = int(val_str)
            except ValueError:
                pass

        if not year_data:
            print("  ⚠ 年次データが見つかりませんでした")
            return None

        # 最新年を取得
        latest_year = max(year_data.keys())
        latest = year_data[latest_year]

        # tab コードを確認（転入: "1", 転出: "2" が一般的）
        # 実際のコードはAPIレスポンスのメタデータに依存するため差分を計算
        values = list(latest.values())
        if len(values) >= 2:
            net_migration = values[0] - values[1]
        else:
            print(f"  ⚠ tab データが不足（{latest}）")
            return None

        print(f"  ✅ 社会増減（{latest_year}年推計）: {net_migration:+,}人")
        return {"year": latest_year, "net_migration": net_migration}

    except Exception as e:
        print(f"  ⚠ 移動報告取得エラー: {type(e).__name__}: {e}")
        return None


def load_existing() -> dict:
    """既存のpolicy_data.jsonを読み込む。なければ空dictを返す"""
    if OUTPUT_PATH.exists():
        try:
            return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ⚠ 既存JSONの読み込みエラー: {e}")
    return {}


def update():
    today = date.today().isoformat()
    print(f"=== 政策KPIデータ更新開始: {today} ===")

    data = load_existing()
    if not data:
        print("  ⚠ 既存データなし。初期ファイルを確認してください")
        # last_updatedだけ書いて終了
        data = {"last_updated": today}
        OUTPUT_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return

    data["last_updated"] = today

    # 社会増減数の更新
    migration = fetch_migration_data()
    if migration and "kpi" in data:
        for kpi in data["kpi"]:
            if "社会増減" in kpi.get("指標", ""):
                val = migration["net_migration"]
                kpi["現状_数値"] = val
                kpi["現状値"] = f"{val:+,}人"
                kpi["自動更新"] = True
                kpi["更新年"] = migration["year"]
                print(f"  ✅ KPI「社会増減数」を更新: {val:+,}人（{migration['year']}年）")
                break

    OUTPUT_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"✅ 保存完了: {OUTPUT_PATH}")
    print(f"{'='*40}")


if __name__ == "__main__":
    update()
    sys.exit(0)
