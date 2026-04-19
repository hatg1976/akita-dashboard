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
