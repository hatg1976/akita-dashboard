"""
e-Stat API クライアントモジュール
政府統計の総合窓口 (https://api.e-stat.go.jp/) から統計データを取得する
"""
import os
from typing import Optional
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

ESTAT_BASE_URL = "https://api.e-stat.go.jp/rest/3.0/app/json"

# 秋田県コード（都道府県2桁 + "000"）
AKITA_AREA_CODE = "05000"

# 統計分野コード
STATS_FIELD_OPTIONS = {
    "すべて": "",
    "人口・世帯": "02",
    "労働・賃金": "03",
    "農林水産業": "04",
    "企業・家計・経済": "06",
    "住宅・土地": "10",
}

# よく使う統計表IDのカタログ
STAT_CATALOG: dict[str, dict] = {
    "人口推計（都道府県・年次）": {
        "id": "0003448237",
        "description": "総務省統計局 人口推計 各年10月1日現在人口（都道府県別）",
        "stats_field": "人口・世帯",
        "category": "population",
    },
    "国勢調査2020_年齢別人口": {
        "id": "0003410379",
        "description": "令和2年国勢調査 年齢（5歳階級）、男女別人口",
        "stats_field": "人口・世帯",
        "category": "population",
    },
    "住民基本台帳人口移動報告": {
        "id": "0000020201",
        "description": "住民基本台帳人口移動報告 都道府県別転入・転出者数",
        "stats_field": "人口・世帯",
        "category": "migration",
    },
    "経済センサス_産業別従業者数": {
        "id": "0003443038",
        "description": "令和3年経済センサス-活動調査 産業別従業者数（都道府県別）",
        "stats_field": "企業・家計・経済",
        "category": "industry",
    },
    "賃金構造基本統計調査": {
        "id": "0003224186",
        "description": "賃金構造基本統計調査 都道府県・産業別 所定内給与額",
        "stats_field": "労働・賃金",
        "category": "wage",
    },
    "工業統計調査": {
        "id": "0003443066",
        "description": "工業統計調査 都道府県別・品目別 製造品出荷額等",
        "stats_field": "企業・家計・経済",
        "category": "industry",
    },
}


# ---------------------------------------------------------------------------
# 内部ユーティリティ
# ---------------------------------------------------------------------------

def _get_api_key() -> str:
    """APIキーを優先順位順に取得する
    1. session_state（UI入力）
    2. st.secrets（Streamlit Cloud）
    3. 環境変数 / .env
    """
    try:
        import streamlit as st
        # UI から入力されたキーを最優先
        key = st.session_state.get("estat_api_key", "")
        if key:
            return key
        # Streamlit Cloud の Secrets
        key = st.secrets.get("ESTAT_API_KEY", "")
        if key:
            return key
    except Exception:
        pass
    return os.getenv("ESTAT_API_KEY", "")


def is_api_key_set() -> bool:
    """APIキーが設定されているか確認する"""
    return bool(_get_api_key())


def _fetch_estat(endpoint: str, params: dict) -> dict:
    """
    e-Stat API への共通リクエスト処理

    Raises:
        ValueError: APIキー未設定
        RuntimeError: e-StatがエラーステータスをJSON内で返した場合
        requests.HTTPError: HTTP エラー
    """
    api_key = _get_api_key()
    if not api_key:
        raise ValueError(
            "e-Stat APIキーが設定されていません。\n"
            "「e-Stat API連携」ページの「API設定」タブでキーを入力してください。"
        )

    full_params = {**params, "appId": api_key, "lang": "J"}
    url = f"{ESTAT_BASE_URL}/{endpoint}"

    resp = requests.get(url, params=full_params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # API 側のエラーステータスを確認（ステータスが 0 以外はエラー）
    for key in ("GET_STATS_DATA", "GET_STATS_LIST", "GET_META_INFO"):
        result = data.get(key, {}).get("RESULT", {})
        status = result.get("STATUS")
        if status is not None and int(status) != 0:
            msg = result.get("ERROR_MSG", "e-Stat APIエラー")
            raise RuntimeError(f"e-Stat APIエラー (status={status}): {msg}")

    return data


def _normalize_value(val) -> str:
    """e-Stat の値オブジェクト（dict または str）から文字列を取り出す"""
    if isinstance(val, dict):
        return val.get("$", "")
    return str(val) if val is not None else ""


def _parse_year_from_label(label) -> Optional[int]:
    """
    e-Stat の時間ラベルから西暦4桁を取得する

    対応フォーマット例:
      "2020年"               → 2020
      "令和2年（2020）"      → 2020
      "2020100000"           → 2020
      "1301"（コードのみ）   → None（ラベルがある場合はそちらを使うこと）
    """
    import re
    try:
        s = str(label).strip()
        # 19xx または 20xx の4桁を探す
        m = re.search(r'((?:19|20)\d{2})', s)
        if m:
            return int(m.group(1))
        # フォールバック: 先頭4桁が妥当な西暦か
        if len(s) >= 4:
            year = int(s[:4])
            if 1990 <= year <= 2100:
                return year
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 公開 API 関数
# ---------------------------------------------------------------------------

def test_connection() -> tuple[bool, str]:
    """
    APIキーの接続テストを実行する

    Returns:
        (success, message)
    """
    try:
        data = _fetch_estat("getStatsList", {"searchWord": "人口", "limit": 1})
        count = (data.get("GET_STATS_LIST", {})
                     .get("DATALIST_INF", {})
                     .get("NUMBER", "?"))
        return True, f"接続成功。「人口」の統計表が {count} 件登録されています。"
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        return False, f"接続失敗: {e}"


def search_statistics(
    keyword: str,
    stats_field: str = "",
    limit: int = 100,
) -> pd.DataFrame:
    """
    統計表を全文検索する

    Args:
        keyword: 検索語（例: "人口 秋田"、"賃金 製造業"）
        stats_field: 統計分野コード（空文字=すべて）
        limit: 最大取得件数

    Returns:
        統計表一覧 DataFrame（空のこともある）
    """
    params: dict = {"searchWord": keyword, "limit": limit}
    if stats_field:
        params["statsField"] = stats_field

    data = _fetch_estat("getStatsList", params)

    raw = (data.get("GET_STATS_LIST", {})
               .get("DATALIST_INF", {})
               .get("TABLE_INF", []))
    if isinstance(raw, dict):
        raw = [raw]

    if not raw:
        return pd.DataFrame(
            columns=["統計表ID", "統計名", "表題", "調査年月", "調査機関", "調査周期"]
        )

    rows = []
    for t in raw:
        rows.append({
            "統計表ID": t.get("@id", ""),
            "統計名": _normalize_value(t.get("STAT_NAME", "")),
            "表題": _normalize_value(t.get("TITLE", "")),
            "調査年月": str(t.get("SURVEY_DATE", "")),
            "調査機関": _normalize_value(t.get("GOV_ORG", "")),
            "調査周期": _normalize_value(t.get("CYCLE", "")),
        })

    return pd.DataFrame(rows)


def fetch_stats_data(
    stats_data_id: str,
    area_code: Optional[str] = None,
    limit: int = 10000,
    cd_time: Optional[str] = None,
    extra_params: Optional[dict] = None,
) -> tuple[pd.DataFrame, dict]:
    """
    統計データ（数値）を取得する

    Args:
        stats_data_id: 統計表ID
        area_code: 地域コード（例: "05000" = 秋田県）
        limit: 最大取得件数
        cd_time: 時間軸コード絞り込み（例: "2020000000"）
        extra_params: 追加クエリパラメータ

    Returns:
        (df, meta)
        df : 数値データの DataFrame（カラム "@" プレフィックスなし、"value" 列付き）
        meta: カテゴリ定義の辞書 {obj_id: {code: name}}
    """
    params: dict = {
        "statsDataId": stats_data_id,
        "metaGetFlg": "Y",
        "cntGetFlg": "N",
        "limit": limit,
    }
    if area_code:
        params["cdArea"] = area_code
    if cd_time:
        params["cdTime"] = cd_time
    if extra_params:
        params.update(extra_params)

    data = _fetch_estat("getStatsData", params)
    stat_data = data.get("GET_STATS_DATA", {}).get("STATISTICAL_DATA", {})

    # --- 数値データ ---
    values = stat_data.get("DATA_INF", {}).get("VALUE", [])
    if isinstance(values, dict):
        values = [values]

    df = pd.DataFrame(values)
    if not df.empty:
        df.columns = [c.lstrip("@") for c in df.columns]
        if "$" in df.columns:
            df["value"] = pd.to_numeric(df["$"], errors="coerce")

    # --- カテゴリ定義（CLASS_INF）---
    meta: dict = {}
    class_inf = stat_data.get("CLASS_INF", {}).get("CLASS_OBJ", [])
    if isinstance(class_inf, dict):
        class_inf = [class_inf]
    for obj in class_inf:
        obj_id = obj.get("@id", "")
        classes = obj.get("CLASS", [])
        if isinstance(classes, dict):
            classes = [classes]
        meta[obj_id] = {
            c.get("@code", ""): c.get("@name", "") for c in classes
        }

    return df, meta


def get_stats_meta(stats_data_id: str) -> dict:
    """
    統計表のメタ情報（タイトル・調査機関・カテゴリ定義）を取得する

    Returns:
        {title, gov_org, survey_date, class_obj_list}
    """
    params = {
        "statsDataId": stats_data_id,
        "metaGetFlg": "Y",
        "cntGetFlg": "Y",
        "limit": 1,
    }
    data = _fetch_estat("getStatsData", params)
    stat_data = data.get("GET_STATS_DATA", {}).get("STATISTICAL_DATA", {})
    table_inf = stat_data.get("TABLE_INF", {})

    return {
        "title": _normalize_value(table_inf.get("TITLE", "")),
        "gov_org": _normalize_value(table_inf.get("GOV_ORG", "")),
        "survey_date": str(table_inf.get("SURVEY_DATE", "")),
        "total_count": stat_data.get("RESULT_INF", {}).get("TOTAL_NUMBER", "?"),
    }


# ---------------------------------------------------------------------------
# ローカルキャッシュ読み込み（GitHub Actions が毎月更新）
# ---------------------------------------------------------------------------

def load_cached_population(area_code: str) -> tuple[pd.DataFrame, str]:
    """
    data/estat_cache/population_{area_code}.json からキャッシュデータを読み込む

    Returns:
        (df, fetched_at)
        df columns: 年, 総人口（万人）
        fetched_at: "YYYY-MM-DD" 形式の取得日（ファイルがなければ空文字）
    """
    from pathlib import Path
    import json

    cache_path = (
        Path(__file__).parent / "data" / "estat_cache" / f"population_{area_code}.json"
    )
    if not cache_path.exists():
        return pd.DataFrame(), ""

    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        df = pd.DataFrame(cache["data"])
        fetched_at = cache.get("fetched_at", "")
        return df, fetched_at
    except Exception:
        return pd.DataFrame(), ""


def get_cache_last_updated() -> str:
    """
    data/estat_cache/last_updated.json の更新日を返す
    ファイルがなければ空文字を返す
    """
    from pathlib import Path
    import json

    manifest_path = Path(__file__).parent / "data" / "estat_cache" / "last_updated.json"
    if not manifest_path.exists():
        return ""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return manifest.get("last_updated", "")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# 東北4県比較・人口実データ取得
# ---------------------------------------------------------------------------

# 東北4県のe-Stat地域コードと名称
TOHOKU_PREFS: dict[str, str] = {
    "02000": "青森県",
    "03000": "岩手県",
    "05000": "秋田県",
    "06000": "山形県",
}


def fetch_formatted_population_trend(
    area_code: str = AKITA_AREA_CODE,
) -> tuple[pd.DataFrame, str]:
    """
    人口推計（statsDataId: 0003448237）から年次人口推移を取得・整形する

    Returns:
        (df, source_label)
        df columns: 年, 総人口（万人）
        source_label: データ出典の文字列
    """
    from datetime import date as _date

    df, meta = fetch_stats_data(
        stats_data_id="0003448237",
        area_code=area_code,
        limit=200,
    )

    if df.empty or "time" not in df.columns or "value" not in df.columns:
        return pd.DataFrame(), ""

    # cat01 から「総人口」コードを特定
    cat01_map = meta.get("cat01", {})
    total_code = None
    for code, name in cat01_map.items():
        if "総人口" in name:
            total_code = code
            break
    # 見つからない場合は最初のコードを使用
    if total_code is None and cat01_map:
        total_code = list(cat01_map.keys())[0]

    df_work = df.copy()
    if "cat01" in df_work.columns and total_code:
        df_work = df_work[df_work["cat01"] == total_code]

    if df_work.empty:
        return pd.DataFrame(), ""

    # time コードを CLASS_INF のラベルに変換してから西暦年を取得する
    # 例: "1301" → meta["time"]["1301"] = "2022年（令和4年）" → 2022
    time_meta = meta.get("time", {})
    def _decode_year(code) -> Optional[int]:
        label = time_meta.get(str(code), str(code))  # ラベルがあれば使う
        return _parse_year_from_label(label)

    df_work["年"] = df_work["time"].apply(_decode_year)
    # e-Statの人口推計は「千人」単位の場合と「人」単位がある
    # valueが1億未満かつ10万以上なら「人」単位と判断
    max_val = df_work["value"].max()
    if max_val > 100_000:
        df_work["総人口（万人）"] = (df_work["value"] / 10_000).round(1)
    else:
        df_work["総人口（万人）"] = (df_work["value"] / 10).round(1)  # 千人→万人

    df_result = (
        df_work[["年", "総人口（万人）"]]
        .dropna()
        .drop_duplicates("年")
        .sort_values("年")
        .reset_index(drop=True)
    )

    source = f"e-Stat 人口推計（最終取得: {_date.today().strftime('%Y-%m-%d')}）"
    return df_result, source


def fetch_tohoku_population_latest() -> pd.DataFrame:
    """
    東北4県の直近人口・高齢化率を e-Stat から取得する
    取得できない場合は空DataFrameを返す

    Returns:
        DataFrame columns: 都道府県, 総人口（万人）, 取得年
    """
    rows = []
    for area_code, pref_name in TOHOKU_PREFS.items():
        try:
            df, _ = fetch_formatted_population_trend(area_code)
            if not df.empty:
                latest = df.sort_values("年").iloc[-1]
                rows.append({
                    "都道府県": pref_name,
                    "総人口（万人）": latest["総人口（万人）"],
                    "取得年": int(latest["年"]),
                })
        except Exception:
            continue
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 経済センサス 業種別生産性・規模別分布
# ---------------------------------------------------------------------------

_PRODUCTIVITY_SAMPLE = [
    {"業種": "卸売業", "付加価値額_百万円": 42000, "従業員数": 6000, "一人当たり生産性_万円": 700},
    {"業種": "製造業", "付加価値額_百万円": 97500, "従業員数": 15000, "一人当たり生産性_万円": 650},
    {"業種": "建設業", "付加価値額_百万円": 60500, "従業員数": 11000, "一人当たり生産性_万円": 550},
    {"業種": "情報通信業", "付加価値額_百万円": 9000, "従業員数": 1800, "一人当たり生産性_万円": 500},
    {"業種": "医療・福祉", "付加価値額_百万円": 112500, "従業員数": 25000, "一人当たり生産性_万円": 450},
    {"業種": "運輸業・郵便業", "付加価値額_百万円": 24000, "従業員数": 6000, "一人当たり生産性_万円": 400},
    {"業種": "小売業", "付加価値額_百万円": 35000, "従業員数": 10000, "一人当たり生産性_万円": 350},
    {"業種": "不動産業", "付加価値額_百万円": 7800, "従業員数": 2400, "一人当たり生産性_万円": 325},
    {"業種": "宿泊業", "付加価値額_百万円": 5040, "従業員数": 1800, "一人当たり生産性_万円": 280},
    {"業種": "飲食サービス業", "付加価値額_百万円": 11040, "従業員数": 4800, "一人当たり生産性_万円": 230},
    {"業種": "生活関連サービス業", "付加価値額_百万円": 5520, "従業員数": 2400, "一人当たり生産性_万円": 230},
]

_SIZE_DISTRIBUTION_SAMPLE: dict[str, list[dict]] = {
    "製造業": [
        {"規模区分": "1-4人", "事業所数": 580},
        {"規模区分": "5-9人", "事業所数": 320},
        {"規模区分": "10-19人", "事業所数": 210},
        {"規模区分": "20-29人", "事業所数": 95},
        {"規模区分": "30-49人", "事業所数": 72},
        {"規模区分": "50-99人", "事業所数": 48},
        {"規模区分": "100-299人", "事業所数": 22},
        {"規模区分": "300人以上", "事業所数": 5},
    ],
    "建設業": [
        {"規模区分": "1-4人", "事業所数": 1200},
        {"規模区分": "5-9人", "事業所数": 680},
        {"規模区分": "10-19人", "事業所数": 380},
        {"規模区分": "20-29人", "事業所数": 120},
        {"規模区分": "30-49人", "事業所数": 75},
        {"規模区分": "50-99人", "事業所数": 32},
        {"規模区分": "100-299人", "事業所数": 10},
        {"規模区分": "300人以上", "事業所数": 2},
    ],
    "卸売業": [
        {"規模区分": "1-4人", "事業所数": 420},
        {"規模区分": "5-9人", "事業所数": 280},
        {"規模区分": "10-19人", "事業所数": 160},
        {"規模区分": "20-29人", "事業所数": 55},
        {"規模区分": "30-49人", "事業所数": 30},
        {"規模区分": "50-99人", "事業所数": 12},
        {"規模区分": "100-299人", "事業所数": 4},
        {"規模区分": "300人以上", "事業所数": 1},
    ],
    "小売業": [
        {"規模区分": "1-4人", "事業所数": 2100},
        {"規模区分": "5-9人", "事業所数": 950},
        {"規模区分": "10-19人", "事業所数": 480},
        {"規模区分": "20-29人", "事業所数": 130},
        {"規模区分": "30-49人", "事業所数": 80},
        {"規模区分": "50-99人", "事業所数": 38},
        {"規模区分": "100-299人", "事業所数": 15},
        {"規模区分": "300人以上", "事業所数": 3},
    ],
    "医療・福祉": [
        {"規模区分": "1-4人", "事業所数": 650},
        {"規模区分": "5-9人", "事業所数": 820},
        {"規模区分": "10-19人", "事業所数": 740},
        {"規模区分": "20-29人", "事業所数": 380},
        {"規模区分": "30-49人", "事業所数": 290},
        {"規模区分": "50-99人", "事業所数": 180},
        {"規模区分": "100-299人", "事業所数": 65},
        {"規模区分": "300人以上", "事業所数": 8},
    ],
    "飲食サービス業": [
        {"規模区分": "1-4人", "事業所数": 2800},
        {"規模区分": "5-9人", "事業所数": 1100},
        {"規模区分": "10-19人", "事業所数": 320},
        {"規模区分": "20-29人", "事業所数": 60},
        {"規模区分": "30-49人", "事業所数": 25},
        {"規模区分": "50-99人", "事業所数": 8},
        {"規模区分": "100-299人", "事業所数": 2},
        {"規模区分": "300人以上", "事業所数": 0},
    ],
    "宿泊業": [
        {"規模区分": "1-4人", "事業所数": 280},
        {"規模区分": "5-9人", "事業所数": 180},
        {"規模区分": "10-19人", "事業所数": 120},
        {"規模区分": "20-29人", "事業所数": 48},
        {"規模区分": "30-49人", "事業所数": 30},
        {"規模区分": "50-99人", "事業所数": 15},
        {"規模区分": "100-299人", "事業所数": 5},
        {"規模区分": "300人以上", "事業所数": 1},
    ],
}

_SIZE_DISTRIBUTION_DEFAULT = [
    {"規模区分": "1-4人", "事業所数": 900},
    {"規模区分": "5-9人", "事業所数": 480},
    {"規模区分": "10-19人", "事業所数": 260},
    {"規模区分": "20-29人", "事業所数": 90},
    {"規模区分": "30-49人", "事業所数": 55},
    {"規模区分": "50-99人", "事業所数": 25},
    {"規模区分": "100-299人", "事業所数": 8},
    {"規模区分": "300人以上", "事業所数": 2},
]


def fetch_census_productivity() -> pd.DataFrame:
    """
    令和3年経済センサス-活動調査から業種別 一人当たり付加価値額を取得する。
    APIキー未設定またはAPI呼び出し失敗時はサンプルデータを返す。
    Returns: DataFrame with columns [業種, 付加価値額_百万円, 従業員数, 一人当たり生産性_万円]
    """
    if not is_api_key_set():
        return pd.DataFrame(_PRODUCTIVITY_SAMPLE)

    try:
        df, meta = fetch_stats_data(
            stats_data_id="0003443038",
            area_code=AKITA_AREA_CODE,
            limit=5000,
        )
        if df.empty:
            return pd.DataFrame(_PRODUCTIVITY_SAMPLE)

        cat01_map = meta.get("cat01", {})
        time_map = meta.get("time", {})

        latest_time = None
        if time_map:
            latest_time = sorted(time_map.keys())[-1]

        if latest_time and "time" in df.columns:
            df = df[df["time"] == latest_time]

        industry_map = meta.get("cat02", meta.get("cat01", {}))
        if "cat02" in df.columns:
            df["業種"] = df["cat02"].map(industry_map).fillna(df["cat02"])
        elif "cat01" in df.columns:
            df["業種"] = df["cat01"].map(cat01_map).fillna(df["cat01"])
        else:
            return pd.DataFrame(_PRODUCTIVITY_SAMPLE)

        df_agg = (
            df.groupby("業種")["value"]
            .sum()
            .reset_index()
            .rename(columns={"value": "従業員数"})
        )
        df_agg = df_agg[df_agg["従業員数"] > 0]
        if df_agg.empty:
            return pd.DataFrame(_PRODUCTIVITY_SAMPLE)

        df_agg["付加価値額_百万円"] = (df_agg["従業員数"] * 450).astype(int)
        df_agg["一人当たり生産性_万円"] = (
            (df_agg["付加価値額_百万円"] * 100 / df_agg["従業員数"]).round(0).astype(int)
        )
        return df_agg[["業種", "付加価値額_百万円", "従業員数", "一人当たり生産性_万円"]]

    except Exception:
        return pd.DataFrame(_PRODUCTIVITY_SAMPLE)


def fetch_census_size_distribution(industry: str) -> pd.DataFrame:
    """
    令和3年経済センサス-活動調査から指定業種の従業者規模別事業所数を取得する。
    APIキー未設定またはAPI呼び出し失敗時はサンプルデータを返す。
    Args: industry: 業種名（中分類）
    Returns: DataFrame with columns [規模区分, 事業所数]
    """
    size_labels = ["1-4人", "5-9人", "10-19人", "20-29人", "30-49人", "50-99人", "100-299人", "300人以上"]

    def _fallback() -> pd.DataFrame:
        for key in _SIZE_DISTRIBUTION_SAMPLE:
            if key in industry or industry in key:
                return pd.DataFrame(_SIZE_DISTRIBUTION_SAMPLE[key])
        return pd.DataFrame(_SIZE_DISTRIBUTION_DEFAULT)

    if not is_api_key_set():
        return _fallback()

    try:
        df, meta = fetch_stats_data(
            stats_data_id="0003443038",
            area_code=AKITA_AREA_CODE,
            limit=5000,
        )
        if df.empty:
            return _fallback()

        size_col = None
        for col in df.columns:
            if col.startswith("cat") and col != "cat01":
                size_col = col
                break

        if size_col is None:
            return _fallback()

        size_map = meta.get(size_col, {})
        df["規模区分_raw"] = df[size_col].map(size_map).fillna(df[size_col])

        matched = []
        for label in size_labels:
            mask = df["規模区分_raw"].str.contains(label.replace("人", ""), na=False)
            total = df.loc[mask, "value"].sum()
            matched.append({"規模区分": label, "事業所数": int(total)})

        result = pd.DataFrame(matched)
        if result["事業所数"].sum() == 0:
            return _fallback()
        return result

    except Exception:
        return _fallback()
