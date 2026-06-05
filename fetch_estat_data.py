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
from estat_api import fetch_sales_municipal_matrix
from estat_api import fetch_openclose_stats, OPENCLOSE_CENSUS_IDS, _fetch_estat

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


def fetch_sales_matrix(today: str) -> bool:
    """産業×市町村 売上（収入）金額マトリックスを取得して JSON に保存する（単位: 百万円）"""
    print("\n--- 産業×市町村 売上（収入）金額マトリックスを取得中 ---")
    try:
        df_pivot, source_note = fetch_sales_municipal_matrix()
        if df_pivot.empty:
            print("  ⚠ 売上マトリックスデータが空でした（スキップ）")
            return False

        # 値は int（百万円）、"-"（秘匿処理）、None（データなし）のいずれか
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
            "unit": "百万円",
            "columns": [str(c) for c in df_pivot.columns],
            "index": [str(i) for i in df_pivot.index],
            "data": records,
        }
        out_path = OUTPUT_DIR / "sales_matrix.json"
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


def discover_new_census_ids() -> dict:
    """
    e-Stat を検索して、OPENCLOSE_CENSUS_IDS に未登録の経済センサス 開廃業IDを探す

    Returns:
        {year_label: {"stats_id": "...", "duration_years": N}} の辞書
        新規IDがない場合は空辞書
    """
    IDS_CACHE = OUTPUT_DIR / "openclose_census_ids.json"

    # 既知の調査年（ハードコード + 過去の発見済み）
    known_years = {int(y.replace("年", "")) for y in OPENCLOSE_CENSUS_IDS}
    if IDS_CACHE.exists():
        try:
            existing = json.loads(IDS_CACHE.read_text(encoding="utf-8"))
            for y in existing.get("ids", {}):
                known_years.add(int(y.replace("年", "")))
        except Exception:
            pass

    print("\n--- 経済センサス 新規IDを e-Stat で検索中 ---")
    print(f"  既知の調査年: {sorted(known_years)}")

    try:
        data = _fetch_estat("getStatsList", {
            "searchWord": "経済センサス 存続 廃業 大分類",
            "limit": 40,
        })
        tables = (data.get("GET_STATS_LIST", {})
                      .get("DATALIST_INF", {})
                      .get("TABLE_INF", []))
        if isinstance(tables, dict):
            tables = [tables]
    except Exception as e:
        print(f"  ⚠ 検索エラー: {e}")
        return {}

    def _s(v):
        if isinstance(v, dict): return v.get("$", "")
        return str(v) if v else ""

    new_ids: dict = {}
    for t in tables:
        title = _s(t.get("TITLE", ""))
        survey_date = str(t.get("SURVEY_DATE", ""))
        stats_id = t.get("@id", "")

        # 対象テーブルの絞り込み: 産業大分類×都道府県×市区町村×存続・廃業
        if not all(kw in title for kw in ["大分類", "廃業"]):
            continue
        if not any(kw in title for kw in ["都道府県", "市区町村"]):
            continue

        # 調査年を SURVEY_DATE（YYYYMM 形式）から抽出
        try:
            survey_year = int(survey_date[:4])
        except (ValueError, IndexError):
            continue

        if survey_year in known_years:
            continue  # 既知の年はスキップ

        year_label = f"{survey_year}年"
        # 比較期間 = 新調査年 - 直前の既知調査年
        prev = sorted(y for y in known_years if y < survey_year)
        duration = survey_year - prev[-1] if prev else 5

        if year_label not in new_ids:
            new_ids[year_label] = {"stats_id": stats_id, "duration_years": duration}
            print(f"  🆕 新ID発見: {year_label}  stats_id={stats_id}  期間={duration}年")
            print(f"     表題: {title[:70]}")

    if not new_ids:
        print(f"  新規IDなし（次回の経済センサスは{max(known_years)+5}年頃の予定）")

    return new_ids


def save_discovered_ids(new_ids: dict, today: str) -> None:
    """発見した新規IDを openclose_census_ids.json にマージ保存する"""
    IDS_CACHE = OUTPUT_DIR / "openclose_census_ids.json"

    existing: dict = {}
    if IDS_CACHE.exists():
        try:
            existing = json.loads(IDS_CACHE.read_text(encoding="utf-8")).get("ids", {})
        except Exception:
            pass

    merged = {**existing, **new_ids}
    if merged:
        IDS_CACHE.write_text(
            json.dumps({"updated_at": today, "ids": merged}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  ✅ IDキャッシュ更新: {list(merged.keys())} → {IDS_CACHE.name}")


def fetch_openclose(today: str) -> list[str]:
    """
    経済センサス 開廃業データを取得して JSON に保存する
    OPENCLOSE_CENSUS_IDS（ハードコード）＋ openclose_census_ids.json（自動発見）を統合して処理する

    Returns:
        成功した調査年ラベルのリスト
    """
    # 既知の比較期間（年数）— ハードコード分のデフォルト
    DURATION: dict[str, int] = {"2012年": 3, "2016年": 4, "2021年": 5}

    # ハードコードIDと自動発見IDをマージ
    all_ids: dict[str, str] = dict(OPENCLOSE_CENSUS_IDS)
    ids_cache = OUTPUT_DIR / "openclose_census_ids.json"
    if ids_cache.exists():
        try:
            cached_data = json.loads(ids_cache.read_text(encoding="utf-8"))
            for year_label, info in cached_data.get("ids", {}).items():
                all_ids[year_label] = info["stats_id"]
                if "duration_years" in info:
                    DURATION[year_label] = int(info["duration_years"])
        except Exception as e:
            print(f"  ⚠ IDキャッシュ読み込みエラー: {e}")

    succeeded = []

    for year_label, stats_id in all_ids.items():
        print(f"\n--- 開廃業データ {year_label}（ID: {stats_id}）を取得中 ---")
        # ファイル名: openclose_2021.json など
        year_short = year_label.replace("年", "")
        out_path = OUTPUT_DIR / f"openclose_{year_short}.json"

        try:
            df, source = fetch_openclose_stats(stats_id=stats_id)
            if df.empty:
                print(f"  ⚠ データが空でした（スキップ）")
                continue

            cache = {
                "fetched_at": today,
                "survey_year": year_label,
                "stats_id": stats_id,
                "duration_years": DURATION.get(year_label, 5),
                "source": source,
                "data": df.to_dict(orient="records"),
            }
            out_path.write_text(
                json.dumps(cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            new_cnt = int(df[df["区分"] == "新設事業所"]["事業所数"].sum())
            clo_cnt = int(df[df["区分"] == "廃業事業所"]["事業所数"].sum())
            print(f"  ✅ 保存完了: {out_path.name}"
                  f"（新設 {new_cnt:,}件 / 廃業 {clo_cnt:,}件）")
            succeeded.append(year_label)

        except Exception as e:
            print(f"  ❌ エラー: {type(e).__name__}: {e}")

    return succeeded


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

    # 産業×市町村 売上（収入）金額マトリックスを取得
    if fetch_sales_matrix(today):
        fetched.append("産業×市町村 売上金額マトリックス")
    else:
        errors.append("産業×市町村 売上金額マトリックス")

    # 新規経済センサスIDを e-Stat で自動検索（次回調査年 = 2026年頃の予定）
    # 新IDが見つかった場合は openclose_census_ids.json に保存し次回 fetch_openclose で取得される
    new_ids = discover_new_census_ids()
    if new_ids:
        save_discovered_ids(new_ids, today)

    # 開廃業データ（ハードコードID＋自動発見ID）を取得・保存
    # ※ 経済センサスは5年ごとのため毎月同じデータが上書きされる（初回キャッシュ生成に必要）
    oc_succeeded = fetch_openclose(today)
    if oc_succeeded:
        fetched.extend([f"開廃業_{y}" for y in oc_succeeded])
    else:
        errors.append("開廃業データ")

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
