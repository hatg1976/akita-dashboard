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

    def _parse_year(t: str) -> Optional[int]:
        try:
            return int(str(t)[:4])
        except Exception:
            return None

    df_work["年"] = df_work["time"].apply(_parse_year)
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
