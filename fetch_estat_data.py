#!/usr/bin/env python3
"""
GitHub Actions から毎月1日に呼び出す e-Stat データ取得スクリプト

取得データ:
  - 東北4県（青森・岩手・秋田・山形）の人口推計（年次）
  - 各県のデータを data/estat_cache/ に JSON で保存する

環境変数:
  ESTAT_API_KEY: e-Stat APIキー（GitHub Secrets から渡す）
"""
import json
import os
import sys
from datetime import date
from pathlib import Path

# プロジェクトルートを sys.path に追加
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from estat_api import fetch_formatted_population_trend, TOHOKU_PREFS

OUTPUT_DIR = Path(__file__).parent / "data" / "estat_cache"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_all():
    today = date.today().isoformat()
    fetched = []
    errors = []

    for area_code, pref_name in TOHOKU_PREFS.items():
        print(f"取得中: {pref_name} ({area_code}) ...", end=" ", flush=True)
        try:
            df, source = fetch_formatted_population_trend(area_code)
            if df.empty:
                print("データなし（スキップ）")
                errors.append(pref_name)
                continue

            cache = {
                "fetched_at": today,
                "area_code": area_code,
                "pref_name": pref_name,
                "source": source,
                "data": df.to_dict(orient="records"),
            }
            out_path = OUTPUT_DIR / f"population_{area_code}.json"
            out_path.write_text(
                json.dumps(cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"OK ({len(df)}件) -> {out_path.name}")
            fetched.append(pref_name)

        except Exception as e:
            print(f"エラー: {e}")
            errors.append(pref_name)

    # マニフェスト（最終更新日・成否サマリー）
    manifest = {
        "last_updated": today,
        "fetched": fetched,
        "errors": errors,
    }
    manifest_path = OUTPUT_DIR / "last_updated.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nマニフェスト更新: {manifest_path}")

    if errors:
        print(f"警告: {errors} の取得に失敗しました")
    print(f"完了: {fetched} のデータを更新しました（{today}）")

    return len(errors) == 0


if __name__ == "__main__":
    success = fetch_all()
    sys.exit(0 if success else 1)
