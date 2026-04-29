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

# 中分類 → 大分類サンプルデータキーのマッピング
_INDUSTRY_TO_SAMPLE_KEY: dict[str, str] = {
    "職別工事業": "建設業",
    "設備工事業": "建設業",
    "食品製造業": "製造業",
    "飲食料品小売業": "小売業",
    "道路旅客運送業": "運輸業・郵便業",
    "道路貨物運送業": "運輸業・郵便業",
    "持ち帰り・配達飲食サービス業": "飲食サービス業",
    "旅行業": "生活関連サービス業",
    "冠婚葬祭業": "生活関連サービス業",
    "廃棄物処理業": "サービス業",
    "自動車整備業": "サービス業",
    "事業協同組合": "サービス業",
    "商店街": "小売業",
}

_SIZE_DISTRIBUTION_SAMPLE["運輸業・郵便業"] = [
    {"規模区分": "1-4人", "事業所数": 480},
    {"規模区分": "5-9人", "事業所数": 280},
    {"規模区分": "10-19人", "事業所数": 180},
    {"規模区分": "20-29人", "事業所数": 70},
    {"規模区分": "30-49人", "事業所数": 45},
    {"規模区分": "50-99人", "事業所数": 28},
    {"規模区分": "100-299人", "事業所数": 10},
    {"規模区分": "300人以上", "事業所数": 3},
]

_SIZE_DISTRIBUTION_SAMPLE["生活関連サービス業"] = [
    {"規模区分": "1-4人", "事業所数": 1100},
    {"規模区分": "5-9人", "事業所数": 480},
    {"規模区分": "10-19人", "事業所数": 180},
    {"規模区分": "20-29人", "事業所数": 40},
    {"規模区分": "30-49人", "事業所数": 18},
    {"規模区分": "50-99人", "事業所数": 6},
    {"規模区分": "100-299人", "事業所数": 1},
    {"規模区分": "300人以上", "事業所数": 0},
]

_SIZE_DISTRIBUTION_SAMPLE["サービス業"] = [
    {"規模区分": "1-4人", "事業所数": 750},
    {"規模区分": "5-9人", "事業所数": 380},
    {"規模区分": "10-19人", "事業所数": 200},
    {"規模区分": "20-29人", "事業所数": 65},
    {"規模区分": "30-49人", "事業所数": 35},
    {"規模区分": "50-99人", "事業所数": 15},
    {"規模区分": "100-299人", "事業所数": 4},
    {"規模区分": "300人以上", "事業所数": 1},
]


def fetch_census_productivity() -> pd.DataFrame:
    """
    令和3年経済センサス-活動調査に基づく業種別一人当たり付加価値額を取得する。
    APIキー未設定またはAPI呼び出し失敗時はサンプルデータを返す。
    Returns: DataFrame with columns [業種, 付加価値額_百万円, 従業員数, 一人当たり生産性_万円]
    """
    if not is_api_key_set():
        return pd.DataFrame(_PRODUCTIVITY_SAMPLE)

    try:
        df, meta = fetch_stats_data("0004006340", area_code="05000", limit=10000)

        if df.empty:
            return pd.DataFrame(_PRODUCTIVITY_SAMPLE)

        # tab 次元から各指標のコードを特定
        tab_meta = meta.get("tab", {})
        code_value_added = None      # 純付加価値額
        code_employees = None        # 事業従事者数
        code_productivity = None     # 1人当たり純付加価値額

        for code, name in tab_meta.items():
            # 「1人当たり」を最優先（「1事業所当たり」より先にチェック）
            if ("１人当たり" in name or "1人当たり" in name) and "事業所" not in name:
                code_productivity = code
            # 「純付加価値額」で「当たり」が付かないもの（合計値）
            elif "純付加価値額" in name and "当たり" not in name:
                code_value_added = code
            # 「事業従事者数」で「当たり」が付かないもの（合計人数）
            elif ("事業従事者数" in name or "従業者数" in name) and "当たり" not in name:
                code_employees = code

        # 業種次元を特定（cat01 が業種）
        cat01_meta = meta.get("cat01", {})
        if not cat01_meta:
            return pd.DataFrame(_PRODUCTIVITY_SAMPLE)

        # 各業種ごとに付加価値額・従業員数・生産性を集約
        rows = []
        for ind_code, ind_name in cat01_meta.items():
            # 合計・総数行はスキップ
            if ind_code in ("00", "000") or "合計" in ind_name or "総数" in ind_name or "計" in ind_name:
                continue

            df_ind = df[df["cat01"] == ind_code] if "cat01" in df.columns else df[df.iloc[:, 0] == ind_code]

            def _get_val(tab_code, _df=df_ind):
                if tab_code is None or "tab" not in _df.columns:
                    return None
                rows_tab = _df[_df["tab"] == tab_code]
                if rows_tab.empty:
                    return None
                v = rows_tab["value"].iloc[0]
                return float(v) if pd.notna(v) else None

            employees = _get_val(code_employees)
            value_added = _get_val(code_value_added)
            productivity = _get_val(code_productivity)

            # 1人当たり生産性をAPIから直接取得（最優先）
            # 単位変換: e-Stat は万円単位で返すことが多いが、千円の場合は変換
            if productivity is not None and productivity > 100_000:
                productivity = productivity / 100  # 千円 → 万円

            # 付加価値額が取得できなかった場合スキップ
            if value_added is None and productivity is None:
                continue

            # 従業員数が取れない or 明らかに1事業所当たり値の場合は付加価値額÷生産性で逆算
            if (employees is None or employees == 0 or employees < 50) and productivity and value_added:
                employees = int(value_added * 100 / productivity)

            if employees is None or employees == 0:
                continue

            # 生産性がAPIから取れなかった場合のみ計算
            if productivity is None:
                if value_added is None:
                    continue
                productivity = value_added * 100 / employees

            rows.append({
                "業種": ind_name,
                "付加価値額_百万円": round(value_added),
                "従業員数": int(employees),
                "一人当たり生産性_万円": round(productivity, 1),
            })

        if not rows:
            return pd.DataFrame(_PRODUCTIVITY_SAMPLE)

        result_df = pd.DataFrame(rows)
        # 業種名に「計」を含む行を除外（念のため）
        result_df = result_df[~result_df["業種"].str.contains("計", na=False)]
        result_df = result_df[result_df["従業員数"] > 0]

        if result_df.empty:
            return pd.DataFrame(_PRODUCTIVITY_SAMPLE)

        return result_df.reset_index(drop=True)

    except Exception:
        return pd.DataFrame(_PRODUCTIVITY_SAMPLE)


# 従業者規模別分布で使用する大分類リスト（表示順）
CENSUS_DAIBUNSHU_LIST = [
    "農林漁業",
    "鉱業・採石業・砂利採取業",
    "建設業",
    "製造業",
    "電気・ガス・熱供給・水道業",
    "情報通信業",
    "運輸業・郵便業",
    "卸売業・小売業",
    "金融業・保険業",
    "不動産業・物品賃貸業",
    "学術研究・専門・技術サービス業",
    "宿泊業・飲食サービス業",
    "生活関連サービス業・娯楽業",
    "教育・学習支援業",
    "医療・福祉",
    "複合サービス事業",
    "サービス業（他に分類されないもの）",
]

_SIZE_LABEL_MAP = {
    "1～4人": "1-4人", "1～4": "1-4人",
    "5～9人": "5-9人", "5～9": "5-9人",
    "10～29人": "10-29人", "10～29": "10-29人",
    "30～49人": "30-49人", "30～49": "30-49人",
    "50～99人": "50-99人", "50～99": "50-99人",
    "100～299人": "100-299人", "100～299": "100-299人",
    "300人以上": "300人以上", "300人～": "300人以上",
}
_SIZE_ORDER = ["1-4人", "5-9人", "10-29人", "30-49人", "50-99人", "100-299人", "300人以上"]


def fetch_census_size_distribution(industry: str) -> pd.DataFrame:
    """
    令和3年経済センサス-活動調査 産業(大分類)別・従業者規模別 事業所数（秋田県）。
    統計表ID: 0004005642
    Args: industry: 大分類業種名（CENSUS_DAIBUNSHU_LIST の値）
    Returns: DataFrame with columns [規模区分, 事業所数]
    """
    def _fallback() -> pd.DataFrame:
        for key in _SIZE_DISTRIBUTION_SAMPLE:
            if key in industry or industry in key:
                return pd.DataFrame(_SIZE_DISTRIBUTION_SAMPLE[key])
        return pd.DataFrame(_SIZE_DISTRIBUTION_DEFAULT)

    if not is_api_key_set():
        return _fallback()

    try:
        df, meta = fetch_stats_data("0004005642", area_code="05000", limit=10000)
        if df.empty:
            return _fallback()

        cat01_meta = meta.get("cat01", {})

        # 規模区分次元を探す
        size_dim_key = None
        size_dim_meta = {}
        for dim_key, dim_map in meta.items():
            if dim_key == "cat01":
                continue
            for name in dim_map.values():
                if "1～4" in name or "1-4" in name:
                    size_dim_key = dim_key
                    size_dim_meta = dim_map
                    break
            if size_dim_key:
                break

        if size_dim_key is None:
            return _fallback()

        # 大分類コードを特定（完全一致優先、部分一致でフォールバック）
        ind_code = None
        for code, name in cat01_meta.items():
            if code in ("00", "000") or any(s in name for s in ("合計", "総数")):
                continue
            if name == industry:
                ind_code = code
                break
            if industry in name or name in industry:
                ind_code = code

        if ind_code is None:
            return _fallback()

        df_ind = df[df["cat01"] == ind_code] if "cat01" in df.columns else df

        size_rows = []
        for size_code, size_name in size_dim_meta.items():
            if any(s in size_name for s in ("総数", "合計", "出向", "派遣")):
                continue
            std_label = _SIZE_LABEL_MAP.get(size_name)
            if std_label is None:
                continue
            rows_s = df_ind[df_ind[size_dim_key] == size_code] if size_dim_key in df_ind.columns else pd.DataFrame()
            if rows_s.empty:
                continue
            val = rows_s["value"].iloc[0]
            if pd.isna(val):
                continue
            size_rows.append({"規模区分": std_label, "事業所数": int(val)})

        if not size_rows:
            return _fallback()

        result = pd.DataFrame(size_rows)
        result["_ord"] = result["規模区分"].apply(lambda x: _SIZE_ORDER.index(x) if x in _SIZE_ORDER else 99)
        return result.sort_values("_ord").drop(columns=["_ord"]).reset_index(drop=True)

    except Exception:
        return _fallback()


# ---------------------------------------------------------------------------
# 産業(大分類)×市区町村別 事業所数マトリックス（秋田県）
# ---------------------------------------------------------------------------

# 秋田県市区町村コード → 名称
_AKITA_MUNICIPALITIES: dict[str, str] = {
    "05201": "秋田市",
    "05202": "能代市",
    "05203": "横手市",
    "05204": "大館市",
    "05205": "男鹿市",
    "05206": "湯沢市",
    "05207": "鹿角市",
    "05208": "由利本荘市",
    "05209": "潟上市",
    "05210": "大仙市",
    "05211": "北秋田市",
    "05213": "にかほ市",
    "05214": "仙北市",
    "05303": "小坂町",
    "05327": "上小阿仁村",
    "05346": "藤里町",
    "05348": "三種町",
    "05349": "八峰町",
    "05361": "五城目町",
    "05363": "八郎潟町",
    "05366": "井川町",
    "05368": "大潟村",
    "05434": "美郷町",
    "05463": "羽後町",
    "05464": "東成瀬村",
}

# サンプルデータ: 秋田市が全体の約40%を占めるリアルな比率
_INDUSTRY_MUNICIPAL_SAMPLE: dict[str, dict[str, int]] = {
    "農林漁業": {
        "秋田市": 180, "横手市": 310, "大館市": 220, "由利本荘市": 280,
        "能代市": 190, "大仙市": 350, "鹿角市": 150, "湯沢市": 160,
    },
    "鉱業・採石業・砂利採取業": {
        "秋田市": 8, "横手市": 5, "大館市": 6, "由利本荘市": 7,
        "能代市": 4, "大仙市": 6, "鹿角市": 5, "湯沢市": 3,
    },
    "建設業": {
        "秋田市": 1050, "横手市": 480, "大館市": 370, "由利本荘市": 420,
        "能代市": 310, "大仙市": 490, "鹿角市": 210, "湯沢市": 230,
    },
    "製造業": {
        "秋田市": 620, "横手市": 340, "大館市": 290, "由利本荘市": 260,
        "能代市": 200, "大仙市": 310, "鹿角市": 150, "湯沢市": 180,
    },
    "電気・ガス・熱供給・水道業": {
        "秋田市": 28, "横手市": 12, "大館市": 10, "由利本荘市": 11,
        "能代市": 9, "大仙市": 13, "鹿角市": 6, "湯沢市": 7,
    },
    "情報通信業": {
        "秋田市": 195, "横手市": 38, "大館市": 28, "由利本荘市": 22,
        "能代市": 18, "大仙市": 32, "鹿角市": 12, "湯沢市": 14,
    },
    "運輸業・郵便業": {
        "秋田市": 310, "横手市": 130, "大館市": 110, "由利本荘市": 120,
        "能代市": 90, "大仙市": 140, "鹿角市": 65, "湯沢市": 70,
    },
    "卸売業・小売業": {
        "秋田市": 3200, "横手市": 1050, "大館市": 850, "由利本荘市": 920,
        "能代市": 720, "大仙市": 1100, "鹿角市": 420, "湯沢市": 480,
    },
    "金融業・保険業": {
        "秋田市": 280, "横手市": 90, "大館市": 72, "由利本荘市": 78,
        "能代市": 58, "大仙市": 95, "鹿角市": 38, "湯沢市": 42,
    },
    "不動産業・物品賃貸業": {
        "秋田市": 680, "横手市": 160, "大館市": 130, "由利本荘市": 140,
        "能代市": 110, "大仙市": 170, "鹿角市": 65, "湯沢市": 75,
    },
    "学術研究・専門・技術サービス業": {
        "秋田市": 420, "横手市": 110, "大館市": 85, "由利本荘市": 90,
        "能代市": 68, "大仙市": 115, "鹿角市": 42, "湯沢市": 48,
    },
    "宿泊業・飲食サービス業": {
        "秋田市": 1850, "横手市": 580, "大館市": 480, "由利本荘市": 430,
        "能代市": 350, "大仙市": 560, "鹿角市": 280, "湯沢市": 290,
    },
    "生活関連サービス業・娯楽業": {
        "秋田市": 870, "横手市": 310, "大館市": 250, "由利本荘市": 240,
        "能代市": 190, "大仙市": 300, "鹿角市": 130, "湯沢市": 150,
    },
    "教育・学習支援業": {
        "秋田市": 420, "横手市": 130, "大館市": 105, "由利本荘市": 110,
        "能代市": 85, "大仙市": 135, "鹿角市": 55, "湯沢市": 62,
    },
    "医療・福祉": {
        "秋田市": 1420, "横手市": 490, "大館市": 390, "由利本荘市": 410,
        "能代市": 310, "大仙市": 480, "鹿角市": 210, "湯沢市": 230,
    },
    "複合サービス事業": {
        "秋田市": 85, "横手市": 48, "大館市": 38, "由利本荘市": 42,
        "能代市": 32, "大仙市": 52, "鹿角市": 22, "湯沢市": 25,
    },
    "サービス業（他に分類されないもの）": {
        "秋田市": 680, "横手市": 220, "大館市": 175, "由利本荘市": 185,
        "能代市": 140, "大仙市": 220, "鹿角市": 95, "湯沢市": 110,
    },
}


def fetch_industry_municipal_matrix() -> tuple[pd.DataFrame, str]:
    """
    令和3年経済センサス-活動調査 産業(大分類)×市区町村別 事業所数（秋田県）
    統計表ID: 0004005655

    Returns:
        (df_pivot, source_note)
          df_pivot: pivot table with 産業 as index, 市区町村 as columns, 事業所数 as values
                   "-" for suppressed/missing cells
          source_note: data source description string
    """
    def _no_data() -> tuple[pd.DataFrame, str]:
        return pd.DataFrame(), ""

    if not is_api_key_set():
        return _no_data()

    try:
        # 表ID: 産業(大分類)、開設時期、経営組織(4区分)別民営事業所数－全国、都道府県、市区町村
        # area_code なし → 秋田県の市区町村データをレスポンス側でフィルタ
        df, meta = fetch_stats_data(
            "0004005655",
            area_code=None,
            limit=100000,
            extra_params={"cdArea": "05"},  # 秋田県プレフィックスで絞り込み
        )

        if df.empty:
            return _no_data()

        # ---- 次元コードを特定 ----
        # area 次元（市区町村コード）
        area_meta = meta.get("area", {})
        # cat01 次元（産業大分類）
        cat01_meta = meta.get("cat01", {})
        # tab 次元（表章項目）→ 事業所数のコードを探す
        tab_meta = meta.get("tab", {})

        # 事業所数のコードを特定
        estab_code = None
        for code, name in tab_meta.items():
            if "事業所数" in name and "当たり" not in name:
                estab_code = code
                break

        # 開設時期・経営組織の「合計」コードを探す（総数 / 計）
        def _find_total_code(dim_meta: dict) -> Optional[str]:
            for code, name in dim_meta.items():
                if name in ("合計", "総数", "計", "総計") or code in ("00", "000", "0"):
                    return code
            # フォールバック: 最初のコード
            return next(iter(dim_meta), None)

        # 開設時期次元
        tclass_meta = meta.get("cat02", {}) or meta.get("tclass1", {})
        tclass_total = _find_total_code(tclass_meta) if tclass_meta else None

        # 経営組織次元
        org_meta = meta.get("cat03", {}) or meta.get("cat04", {})
        org_total = _find_total_code(org_meta) if org_meta else None

        # ---- 秋田県の市区町村コードでフィルタ ----
        akita_codes = set(_AKITA_MUNICIPALITIES.keys())
        if "area" in df.columns:
            df_akita = df[df["area"].isin(akita_codes)].copy()
        else:
            return _no_data()

        # ---- 事業所数のみ抽出 ----
        if estab_code and "tab" in df_akita.columns:
            df_akita = df_akita[df_akita["tab"] == estab_code]

        # ---- 開設時期の合計行のみ ----
        cat02_col = "cat02" if "cat02" in df_akita.columns else None
        if cat02_col and tclass_total:
            df_akita = df_akita[df_akita[cat02_col] == tclass_total]

        # ---- 経営組織の合計行のみ ----
        cat03_col = "cat03" if "cat03" in df_akita.columns else (
            "cat04" if "cat04" in df_akita.columns else None
        )
        if cat03_col and org_total:
            df_akita = df_akita[df_akita[cat03_col] == org_total]

        if df_akita.empty:
            return _no_data()

        # ---- 産業大分類コードを名称にマッピング ----
        # 合計・総数行を除外
        valid_ind_codes = {
            code: name for code, name in cat01_meta.items()
            if code not in ("00", "000") and "合計" not in name and "総数" not in name and "計" == name[-1:] is False
        }

        # ---- ピボット作成 ----
        rows_pivot = {}
        for ind_code, ind_name in valid_ind_codes.items():
            # CENSUS_DAIBUNSHU_LIST の表示名に合わせる
            display_name = ind_name
            for canon in CENSUS_DAIBUNSHU_LIST:
                if canon in ind_name or ind_name in canon:
                    display_name = canon
                    break

            df_ind = df_akita[df_akita["cat01"] == ind_code] if "cat01" in df_akita.columns else pd.DataFrame()
            if df_ind.empty:
                continue

            city_row: dict[str, object] = {}
            for _, row in df_ind.iterrows():
                area_code_val = row.get("area", "")
                city_name = _AKITA_MUNICIPALITIES.get(area_code_val, area_code_val)
                val = row.get("value")
                if pd.isna(val) or val is None:
                    city_row[city_name] = "-"
                elif val == 0:
                    city_row[city_name] = "-"
                else:
                    city_row[city_name] = int(val)

            if city_row:
                rows_pivot[display_name] = city_row

        if not rows_pivot:
            return _no_data()

        # CENSUS_DAIBUNSHU_LIST の順番で並べる
        ordered_rows = {}
        for ind in CENSUS_DAIBUNSHU_LIST:
            if ind in rows_pivot:
                ordered_rows[ind] = rows_pivot[ind]
        # リストにない名前はそのまま追加
        for ind in rows_pivot:
            if ind not in ordered_rows:
                ordered_rows[ind] = rows_pivot[ind]

        # 市区町村を人口規模順（秋田市を先頭）に並べる
        city_order = list(_AKITA_MUNICIPALITIES.values())
        all_cities_in_data = []
        for row in ordered_rows.values():
            for c in row.keys():
                if c not in all_cities_in_data:
                    all_cities_in_data.append(c)
        sorted_cities = sorted(
            all_cities_in_data,
            key=lambda c: city_order.index(c) if c in city_order else 999,
        )

        df_pivot = pd.DataFrame(ordered_rows).T.reindex(columns=sorted_cities)
        df_pivot.index.name = "産業大分類"

        return df_pivot, "令和3年経済センサス-活動調査（2021年）実績値"

    except Exception:
        return _no_data()
