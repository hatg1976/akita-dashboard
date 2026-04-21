"""
j-STAT MAP 連携モジュール
国土地理院 Geocoding API を使った商圏半径分析

主要機能:
  - 住所 → 緯度経度変換（国土地理院 Geocoding API: 認証不要・無料）
  - 指定半径内の推計世帯数計算（国勢調査 市町村別データ × 面積密度法）
  - Folium 地図データ生成

出典:
  座標: 国土地理院 基盤地図情報
  世帯数: 総務省 令和2年国勢調査
  面積: 総務省 令和2年全国都道府県市区町村別面積調
"""
import math
import requests
from typing import Optional

# ============================================================
# 秋田県 市町村 代表座標（役所・市街地中心）と面積（km²）
# ============================================================
AKITA_AREA_COORDS: dict[str, tuple[float, float]] = {
    "秋田市":     (39.7183, 140.1023),
    "横手市":     (39.3342, 140.5631),
    "大館市":     (40.2724, 140.5568),
    "湯沢市":     (39.1581, 140.4960),
    "大仙市":     (39.4590, 140.4784),
    "能代市":     (40.2128, 140.0255),
    "由利本荘市": (39.3855, 140.0479),
    "鹿角市":     (40.2063, 140.7924),
    "男鹿市":     (39.8805, 139.8446),
    "仙北市":     (39.6172, 140.5636),
    "北秋田市":   (40.2310, 140.5680),
    "にかほ市":   (39.0126, 139.9054),
    "潟上市":     (39.7867, 140.0154),
    "三種町":     (39.9600, 140.0949),
    "八郎潟町":   (39.9242, 140.1872),
    "五城目町":   (39.9015, 140.2215),
    "井川町":     (39.8432, 140.1900),
    "大潟村":     (39.9538, 140.0779),
    "美郷町":     (39.4538, 140.4786),
    "羽後町":     (39.2139, 140.5481),
    "東成瀬村":   (39.2143, 140.6490),
    "上小阿仁村": (40.0887, 140.3285),
    "藤里町":     (40.2073, 140.3204),
    "小坂町":     (40.3418, 140.7737),
    "八峰町":     (40.2022, 140.1081),
}

# 市町村面積（km²）— 令和2年全国都道府県市区町村別面積調
AKITA_AREA_KM2: dict[str, float] = {
    "秋田市": 906.0, "横手市": 692.1, "大館市": 913.3, "湯沢市": 790.4,
    "大仙市": 866.2, "能代市": 426.9, "由利本荘市": 2209.6, "鹿角市": 707.3,
    "男鹿市": 241.0, "仙北市": 1094.1, "北秋田市": 1152.7, "にかほ市": 235.8,
    "潟上市": 95.1, "三種町": 299.3, "八郎潟町": 17.2, "五城目町": 214.2,
    "井川町": 45.1, "大潟村": 172.0, "美郷町": 300.2, "羽後町": 300.5,
    "東成瀬村": 264.5, "上小阿仁村": 271.0, "藤里町": 279.8, "小坂町": 197.6,
    "八峰町": 314.1,
}

# ============================================================
# 国土地理院 Geocoding API
# ============================================================
_GSI_GEOCODE_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch"


def geocode_gsi(address: str) -> Optional[tuple[float, float]]:
    """
    国土地理院 Geocoding API で住所を緯度経度に変換する（認証不要）

    Parameters
    ----------
    address : str
        検索する住所（例: "秋田市大町3丁目"）

    Returns
    -------
    (lat, lon) のタプル。見つからない場合は None
    """
    # 秋田県が含まれていない場合は補完
    query = address if "秋田" in address else f"秋田県{address}"
    try:
        resp = requests.get(
            _GSI_GEOCODE_URL,
            params={"q": query},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data:
            lon, lat = data[0]["geometry"]["coordinates"]
            return float(lat), float(lon)
    except Exception:
        pass
    return None


# ============================================================
# 距離計算
# ============================================================

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """ハーバーサイン公式で2点間の距離（km）を計算する"""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


# ============================================================
# 主要都市の地区別データ（市町村内の人口集中を補正）
# 出典: 令和2年国勢調査 小地域集計（秋田県）を参考に推計
# ============================================================

# 秋田市を5地区に分割して中心集中を反映
# （市全体 144,000世帯 / 906km² を地区別密度で再配分）
AKITA_CITY_DISTRICTS: list[dict] = [
    # area_name, lat, lon, households, area_km2
    {"name": "秋田市（中央部）",  "lat": 39.7183, "lon": 140.1023, "households": 52000, "km2": 28.0},
    {"name": "秋田市（北部）",    "lat": 39.7620, "lon": 140.0900, "households": 36000, "km2": 90.0},
    {"name": "秋田市（南部）",    "lat": 39.6870, "lon": 140.1100, "households": 32000, "km2": 110.0},
    {"name": "秋田市（東部）",    "lat": 39.7350, "lon": 140.1650, "households": 16000, "km2": 322.0},
    {"name": "秋田市（西部）",    "lat": 39.6900, "lon": 140.0380, "households":  8000, "km2": 356.0},
]

# 横手市を2地区に分割
YOKOTE_CITY_DISTRICTS: list[dict] = [
    {"name": "横手市（中心部）", "lat": 39.3342, "lon": 140.5631, "households": 25000, "km2": 80.0},
    {"name": "横手市（周辺部）", "lat": 39.3000, "lon": 140.5200, "households": 12000, "km2": 612.1},
]

# 大仙市を2地区に分割
DAISEN_CITY_DISTRICTS: list[dict] = [
    {"name": "大仙市（中心部）", "lat": 39.4590, "lon": 140.4784, "households": 20000, "km2": 100.0},
    {"name": "大仙市（周辺部）", "lat": 39.4200, "lon": 140.4200, "households": 17000, "km2": 766.2},
]

# 地区展開が必要な市（市町村名 → 地区リスト）
DISTRICT_EXPANDED: dict[str, list[dict]] = {
    "秋田市": AKITA_CITY_DISTRICTS,
    "横手市": YOKOTE_CITY_DISTRICTS,
    "大仙市": DAISEN_CITY_DISTRICTS,
}

# ============================================================
# 商圏半径分析
# ============================================================

def _circle_overlap_area(r1: float, r2: float, d: float) -> float:
    """2円（半径 r1, r2、中心間距離 d）の重複面積を返す"""
    if d <= abs(r1 - r2):
        return math.pi * min(r1, r2) ** 2
    if d >= r1 + r2:
        return 0.0
    # 部分重複（2円の交差面積）
    a1 = math.acos(max(-1.0, min(1.0, (d**2 + r1**2 - r2**2) / (2 * d * r1))))
    a2 = math.acos(max(-1.0, min(1.0, (d**2 + r2**2 - r1**2) / (2 * d * r2))))
    return (r1**2 * a1 + r2**2 * a2
            - r1**2 * math.sin(2 * a1) / 2
            - r2**2 * math.sin(2 * a2) / 2)


def _estimate_one_unit(
    center_lat: float, center_lon: float, radius_km: float,
    unit_lat: float, unit_lon: float,
    unit_hh: int, unit_km2: float,
) -> tuple[int, float]:
    """1つのエリア単位の推計世帯数と包含率を返す"""
    if unit_hh <= 0 or unit_km2 <= 0:
        return 0, 0.0
    equiv_r = math.sqrt(unit_km2 / math.pi)
    dist = haversine_km(center_lat, center_lon, unit_lat, unit_lon)
    overlap = _circle_overlap_area(radius_km, equiv_r, dist)
    overlap = max(0.0, min(overlap, math.pi * radius_km ** 2, unit_km2))
    ratio = overlap / unit_km2
    return int(unit_hh * ratio), round(ratio * 100, 1)


def estimate_market_area(
    center_lat: float,
    center_lon: float,
    radius_km: float,
    households_dict: dict[str, int],
) -> tuple[int, list[dict]]:
    """
    指定した地点から半径 radius_km 以内の推計世帯数と市町村別内訳を返す。

    推計方法（面積密度法 + 地区分割補正）:
      秋田市・横手市・大仙市は地区データで人口集中を反映。
      その他市町村は「世帯密度 × 重複面積」で推計。

    Returns
    -------
    (total_households, areas_list)
    """
    areas: list[dict] = []
    # 地区展開済みの市町村は市町村単位でスキップ
    expanded_municipalities = set(DISTRICT_EXPANDED.keys())

    # ── 地区分割あり市町村 ──
    for muni_name, districts in DISTRICT_EXPANDED.items():
        muni_total_hh = 0
        muni_parts: list[dict] = []
        for d in districts:
            est_hh, ratio = _estimate_one_unit(
                center_lat, center_lon, radius_km,
                d["lat"], d["lon"], d["households"], d["km2"],
            )
            if est_hh < 1:
                continue
            dist = haversine_km(center_lat, center_lon, d["lat"], d["lon"])
            muni_parts.append({
                "area_name": d["name"],
                "distance_km": round(dist, 1),
                "estimated_households": est_hh,
                "total_households": d["households"],
                "included_ratio": ratio,
                "lat": d["lat"],
                "lon": d["lon"],
                "_parent": muni_name,
            })
            muni_total_hh += est_hh
        areas.extend(muni_parts)

    # ── 市町村単位（地区展開なし） ──
    for area_name, (area_lat, area_lon) in AKITA_AREA_COORDS.items():
        if area_name in expanded_municipalities:
            continue
        hh = households_dict.get(area_name, 0)
        area_km2 = AKITA_AREA_KM2.get(area_name, 100.0)
        est_hh, ratio = _estimate_one_unit(
            center_lat, center_lon, radius_km,
            area_lat, area_lon, hh, area_km2,
        )
        if est_hh < 1:
            continue
        dist = haversine_km(center_lat, center_lon, area_lat, area_lon)
        areas.append({
            "area_name": area_name,
            "distance_km": round(dist, 1),
            "estimated_households": est_hh,
            "total_households": hh,
            "included_ratio": ratio,
            "lat": area_lat,
            "lon": area_lon,
        })

    areas.sort(key=lambda x: x["distance_km"])
    total = sum(a["estimated_households"] for a in areas)
    return total, areas


def get_akita_center() -> tuple[float, float]:
    """秋田県の地理的中心（地図初期表示用）"""
    return (39.75, 140.18)
