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

import pandas as pd
from estat_api import fetch_formatted_population_trend, fetch_stats_data, TOHOKU_PREFS
from estat_api import fetch_industry_municipal_matrix

OUTPUT_DIR = Path(__file__).parent / "data" / "estat_cache"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_matrix(today: str) -> bool:
    """産業×市町村マトリックスデータを取得して JSON に保存する"""
    print("\n--- 産業×市町村マトリックスを取得中 ---")
    try:
        df_pivot, source_note = fetch_industry_municipal_matrix()
        if df_pivot.empty:
            print("  ⚠ マトリックスデータが空でした（スキップ）")
            return False

        # DataFrame を JSON シリアライズ可能な形式に変換
        # 値は int（事業所数）、"-"（秘匿処理）、None（データなし）のいずれか
        records: dict = {}
        for industry in df_pivot.index:
            records[str(industry)] = {}
            for city in df_pivot.columns:
                val = df_pivot.loc[industry, city]
                if isinstance(val, str):
                    records[str(industry)][str(city)] = val   # "-"
                elif pd.isna(val):
                    records[str(industry)][str(city)] = None
                else:
                    records[str(industry)][str(city)] = int(val)

        cache = {
            "fetched_at": today,
            "source": source_note,
            "columns": [str(c) for c in df_pivot.columns],
            "index": [str(i) for i in df_pivot.index],
            "data": records,
        }
        out_path = OUTPUT_DIR / "industry_matrix.json"
        out_path.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  ✅ 保存完了: {out_path.name}"
              f"（{len(df_pivot)}産業 × {len(df_pivot.columns)}市区町村）")
        return True
    except Exception as e:
        print(f"  ❌ エラー: {type(e).__name__}: {e}")
        return False


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

    # 最初の1県でデバッグ用の時間メタを確認
    first_area = list(TOHOKU_PREFS.keys())[0]
    try:
        _df_debug, _meta_debug = fetch_stats_data("0003448237", area_code=first_area, limit=5)
        time_meta = _meta_debug.get("time", {})
        if time_meta:
            print(f"\n[DEBUG] 時間コード → ラベル（最初の5件）:")
            for k, v in list(time_meta.items())[:5]:
                print(f"  {k!r} → {v!r}")
        else:
            print(f"\n[DEBUG] time メタなし。利用可能なメタキー: {list(_meta_debug.keys())}")
    except Exception as e:
        print(f"[DEBUG] メタ確認エラー: {e}")

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

    # 産業×市町村マトリックスを取得
    if fetch_matrix(today):
        fetched.append("産業×市町村マトリックス")
    else:
        errors.append("産業×市町村マトリックス")

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
