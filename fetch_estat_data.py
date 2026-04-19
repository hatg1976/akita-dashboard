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

    # APIキーの確認（値は表示しない）
    api_key = os.getenv("ESTAT_API_KEY", "")
    if api_key:
        print(f"✅ ESTAT_API_KEY: 設定済み（{len(api_key)}文字）")
    else:
        print("❌ ESTAT_API_KEY が設定されていません。GitHub Secrets を確認してください。")
        # APIキーがなければマニフェストだけ更新して正常終了
        manifest = {
            "last_updated": today,
            "fetched": [],
            "errors": ["APIキー未設定"],
        }
        (OUTPUT_DIR / "last_updated.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return

    for area_code, pref_name in TOHOKU_PREFS.items():
        print(f"\n--- {pref_name} ({area_code}) を取得中 ---")
        try:
            df, source = fetch_formatted_population_trend(area_code)
            if df.empty:
                print(f"  ⚠ データが空でした（スキップ）")
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
            print(f"  ✅ 保存完了: {out_path.name}（{len(df)}件）")
            print(f"     最新年: {int(df['年'].max())}年  総人口: {df.sort_values('年').iloc[-1]['総人口（万人）']}万人")
            fetched.append(pref_name)

        except Exception as e:
            print(f"  ❌ エラー: {type(e).__name__}: {e}")
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

    print(f"\n{'='*40}")
    print(f"完了: {today}")
    print(f"  成功: {fetched}")
    if errors:
        print(f"  失敗: {errors}")
    print(f"{'='*40}")


if __name__ == "__main__":
    fetch_all()
    # エラーがあっても exit(0) でワークフローを継続させる
    sys.exit(0)
