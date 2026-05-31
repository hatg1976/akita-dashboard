"""
秋田県経済活性化 基本データダッシュボード
中小企業診断士向け 施策提言支援ツール
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io

import estat_api
import market_data
from collector import (
    get_sample_population,
    get_national_population,
    get_sample_migration,
    get_sample_industry,
    get_sample_worker_trend,
    get_sample_economy,
    get_sample_municipal,
    get_policy_proposals,
    get_policy_kpi,
    get_policy_last_updated,
    get_policy_kpi_note,
    get_policy_cache_raw,
    get_shindan_actions,
    get_chuokai_actions,
    get_roadmap,
    get_case_studies,
    get_subsidies,
    get_tohoku_population,
    get_tohoku_population_trend,
    get_tohoku_economy,
    get_tohoku_industry,
    get_tohoku_winlose,
    TOHOKU_COLORS,
    get_industry_hierarchy,
    get_industry_detail,
    get_industry_extended_detail,
    # 後継者問題・廃業
    get_successor_absence_rate,
    get_closure_trend,
    get_closure_profile,
    # 労働市場
    get_minimum_wage_akita,
    get_job_opening_ratio_akita,
    load_cached_minimum_wage,
)

@st.cache_data(ttl=86400)
def _load_population_real(area_code: str):
    """e-Stat から人口推計を取得（24時間キャッシュ）"""
    return estat_api.fetch_formatted_population_trend(area_code)


@st.cache_data(ttl=86400)
def _load_industry_matrix():
    """産業×市町村マトリックスを取得（ローカルJSONキャッシュ優先）
    毎月1日の GitHub Actions でローカルJSONを更新済みの場合は即座に返す。
    JSONがない場合のみ e-Stat API から直接取得する（初回・キャッシュ未生成時）。"""
    df, source = estat_api.load_cached_industry_matrix()
    if not df.empty:
        return df, source
    # ローカルキャッシュがなければ API から直接取得
    return estat_api.fetch_industry_municipal_matrix()


@st.cache_data(ttl=86400)  # 1日キャッシュ（JSONキャッシュ優先、APIフォールバック）
def _load_openclose_stats():
    """開業・廃業統計（最新2021年）を取得
    優先順位: ローカルJSONキャッシュ → e-Stat API直接取得
    """
    # 1. ローカルJSONキャッシュ（GitHub Actions による月次更新）
    df, source = estat_api.load_cached_openclose_stats("2021年")
    if not df.empty:
        return df, source
    # 2. APIキーがあれば直接取得
    if estat_api.is_api_key_set():
        return estat_api.fetch_openclose_stats()
    return df, source  # 空DataFrame


@st.cache_data(ttl=86400)
def _load_openclose_trend():
    """2012・2016・2021年 3調査年分の開廃業データを取得
    優先順位: ローカルJSONキャッシュ → e-Stat API直接取得
    """
    # 1. ローカルJSONキャッシュ
    trend = estat_api.load_cached_openclose_trend()
    if trend:
        return trend
    # 2. APIキーがあれば直接取得
    if estat_api.is_api_key_set():
        return estat_api.fetch_openclose_trend()
    return {}


def _get_population(area_code: str) -> tuple[pd.DataFrame, str, str]:
    """
    人口データを取得する（優先順位: キャッシュ → 実API → サンプル）

    Returns:
        (df, source_label, fetched_at)
        fetched_at: "YYYY-MM-DD" 取得日（サンプルは空文字）
    """
    # 1. ローカルキャッシュ（GitHub Actions による月次更新）
    df, fetched_at = estat_api.load_cached_population(area_code)
    if not df.empty:
        return df, "e-Stat 人口推計", fetched_at

    # 2. 実API（APIキー設定済みの場合）
    if estat_api.is_api_key_set():
        try:
            df, source = _load_population_real(area_code)
            if not df.empty:
                from datetime import date
                return df, source, date.today().isoformat()
        except Exception:
            pass

    # 3. サンプルデータ（秋田県のみ対応）
    return get_sample_population(), "サンプルデータ", ""


def _fmt_date(iso_date: str) -> str:
    """'2024-01-01' → '2024年1月1日' に変換する"""
    if not iso_date:
        return ""
    try:
        from datetime import date
        d = date.fromisoformat(iso_date)
        return f"{d.year}年{d.month}月{d.day}日"
    except Exception:
        return iso_date


# ページ設定
st.set_page_config(
    page_title="秋田県経済データダッシュボード",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# スタイル
st.markdown("""
<style>
.metric-card {
    background-color: #f0f2f6;
    border-radius: 8px;
    padding: 16px;
    margin: 8px 0;
}
.section-title {
    color: #1f4e79;
    border-bottom: 2px solid #1f4e79;
    padding-bottom: 4px;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# サイドバー
# ============================================================
st.sidebar.title("🌾 秋田県ダッシュボード")
st.sidebar.markdown("---")

# ── グループ別ナビゲーション ──────────────────────────────────
_MENU_GROUPS = [
    ("📌 概要", [
        "📊 総合概要",
    ]),
    ("👥 人口・労働", [
        "👥 人口動態",
        "👷 労働市場（最低賃金・求人倍率）",
    ]),
    ("🏭 産業・経済", [
        "🏭 産業構造",
        "📉 開業・廃業動態",
        "💰 経済指標",
        "👴 後継者問題・廃業リスク",
    ]),
    ("🔎 業種・地域", [
        "🔎 業種別分析",
        "📋 特定業種支援ガイド",
        "📊 業種別生産性分析",
        "🗺️ 産業×市町村マトリックス",
        "🔗 川上・川下フロー分析",
        "🗾 東北4県比較",
        "🏘️ 市町村比較",
        "📈 地域市場シェア分析",
    ]),
    ("🏛️ 政策・支援", [
        "🏛️ 政策提言",
        "💴 補助金カレンダー",
        "🏢 組織成熟度診断",
    ]),
    ("⚙️ 設定", [
        "🔌 e-Stat API連携",
    ]),
]

if "current_page" not in st.session_state:
    st.session_state.current_page = "📊 総合概要"

# ── ボタン方式ナビゲーション ──
st.sidebar.markdown("""
<style>
[data-testid="stSidebar"] button[kind="secondary"] {
    text-align: left !important;
    justify-content: flex-start !important;
    background: transparent !important;
    border: none !important;
    color: inherit !important;
    padding: 2px 4px !important;
}
[data-testid="stSidebar"] button[kind="primary"] {
    text-align: left !important;
    justify-content: flex-start !important;
    padding: 2px 4px !important;
}
</style>
""", unsafe_allow_html=True)

for _group_name, _items in _MENU_GROUPS:
    st.sidebar.markdown(
        f"<p style='color:#aaa;font-size:0.70em;font-weight:700;"
        f"text-transform:uppercase;letter-spacing:0.06em;"
        f"margin:14px 0 2px 4px;padding:0;'>{_group_name}</p>",
        unsafe_allow_html=True,
    )
    for _item in _items:
        _is_active = (st.session_state.current_page == _item)
        if st.sidebar.button(
            _item,
            key=f"btn__{_item}",
            use_container_width=True,
            type="primary" if _is_active else "secondary",
        ):
            st.session_state.current_page = _item
            st.rerun()

page = st.session_state.current_page

st.sidebar.markdown("---")
_pptx_path = "downloads/清水さん_秋田県賃上げ緊急支援事業事務局_修正済み.pptx"
if __import__("os").path.exists(_pptx_path):
    with open(_pptx_path, "rb") as _f:
        st.sidebar.download_button(
            label="📥 賃上げ支援申請ガイド（PPTX）",
            data=_f,
            file_name="賃上げ緊急支援事業_申請書類記載例.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
st.sidebar.markdown("---")
st.sidebar.markdown("**データ出典**")
st.sidebar.markdown("- 国勢調査（総務省）")
st.sidebar.markdown("- 住民基本台帳人口移動報告")
st.sidebar.markdown("- 経済センサス（経産省）")
st.sidebar.markdown("- 秋田県統計課")
st.sidebar.markdown("---")
if estat_api.is_api_key_set():
    st.sidebar.success("e-Stat API: 接続済み ✓")
else:
    st.sidebar.info("※ 現在はサンプルデータを表示。\n「🔌 e-Stat API連携」ページでAPIキーを設定すると実データを取得できます。")


# ============================================================
# 総合概要ページ
# ============================================================
def page_overview():
    st.title("📊 秋田県 経済活性化ダッシュボード")
    st.markdown("中小企業診断士による施策提言のための基礎データ集")

    st.info(
        "**このダッシュボードについて**\n\n"
        "🔗 **公的統計データを自動取得** ｜ "
        "総務省・政府統計ポータル「e-Stat」が公開する人口推計などの公的統計データを自動で取得・表示しています。"
        "手作業による転記ミスをなくし、常に一次情報に基づいた正確なデータをご覧いただけます。\n\n"
        "🔄 **毎月1日に自動更新** ｜ "
        "e-Stat に新しいデータが公表されると、毎月1日に自動で取得・反映します。"
        "人口推計は年1回（10月基準）の公表ですが、公表のタイミングに合わせて自動的に最新値へ切り替わります。\n\n"
        "⚙️ **常に最新の状態を維持** ｜ "
        "データの更新からWeb公開まで全自動で行う仕組みを構築しています。"
        "担当者が手動で作業しなくても、ダッシュボードが常に最新の状態に保たれます。\n\n"
        "🌾 **秋田県に特化した分析** ｜ "
        "秋田県に実在する産業を16大分類・52中分類で網羅し、東北4県との比較や地域固有の課題・提言を中小企業診断士の視点でまとめています。"
    )
    st.warning(
        "⚠️ **免責事項**\n\n"
        "本ダッシュボードは、中小企業診断士が学習・研究・情報提供を目的として個人的に作成したものです。"
        "掲載しているデータ・分析・提言の正確性・完全性・最新性については万全を期していますが、"
        "その内容を保証するものではありません。\n\n"
        "掲載情報に基づいて行われた判断・行動により生じたいかなる損害についても、作成者は責任を負いかねます。"
        "補助金の申請期限・要件等の重要事項については、必ず各機関の公式情報をご確認ください。"
    )
    st.markdown("---")

    # KPIカード（人口はキャッシュ or サンプルから取得）
    _ov_df, _ov_source, _ov_fetched = _get_population(estat_api.AKITA_AREA_CODE)
    if not _ov_df.empty:
        _latest = _ov_df.sort_values("年").iloc[-1]
        _pop_val  = f"{_latest['総人口（万人）']}万人"
        _pop_year = f"（{int(_latest['年'])}年推計）"
        _pop_delta_note = f"出典: {_ov_source}" + (f" | 取得: {_fmt_date(_ov_fetched)}" if _ov_fetched else "")
    else:
        _pop_val, _pop_year, _pop_delta_note = "92.0万人", "（2023年推計）", "サンプルデータ"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("総人口" + _pop_year, _pop_val, delta="-3.9万人（5年間）", delta_color="inverse")
        if _ov_fetched:
            st.caption(_pop_delta_note)
    with col2:
        st.metric("高齢化率", "38.8%", delta="+2.1pt（5年間）", delta_color="inverse")
        st.caption("出典: 国勢調査（2020年）")
    with col3:
        st.metric("県内総生産", "3兆5,800億円", delta="-0.8%（前年比）", delta_color="inverse")
        st.caption("出典: 内閣府 県民経済計算（2021年度）")
    with col4:
        st.metric("有効求人倍率", "1.35倍", delta="+0.07（前年比）")
        st.caption("出典: 厚生労働省（2023年）")

    st.markdown("---")

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("人口推移")
        df_pop     = get_sample_population()
        df_nat_pop = get_national_population()
        fig = go.Figure()
        # 左軸：秋田県
        fig.add_trace(go.Scatter(
            x=df_pop["年"], y=df_pop["総人口（万人）"],
            name="秋田県（左軸）", mode="lines+markers",
            line=dict(color="#1f4e79", width=2),
            marker=dict(size=6),
            yaxis="y1",
        ))
        # 右軸：全国
        fig.add_trace(go.Scatter(
            x=df_nat_pop["年"], y=df_nat_pop["総人口（万人）"],
            name="全国（右軸）", mode="lines+markers",
            line=dict(color="#e05a24", width=2, dash="dot"),
            marker=dict(size=6),
            yaxis="y2",
        ))
        fig.update_layout(
            height=300,
            title="秋田県 vs 全国 総人口の推移",
            legend=dict(orientation="h", y=-0.25, x=0),
            yaxis=dict(title="秋田県（万人）", color="#1f4e79",
                       tickformat=",", rangemode="tozero"),
            yaxis2=dict(title="全国（万人）", color="#e05a24",
                        tickformat=",", overlaying="y", side="right", rangemode="tozero"),
            margin=dict(t=40, b=60, r=60),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("産業別就業者構成")
        df_ind = get_sample_industry()
        fig = px.pie(
            df_ind, values="就業者数（千人）", names="産業",
            title="産業別就業者数の構成",
            color_discrete_sequence=px.colors.qualitative.Set3,
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

    # 課題サマリー
    st.markdown("---")
    st.subheader("主要課題サマリー")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.error("**人口流出・少子化**\n\n- 毎年約2,500人の社会減\n- 若年層（20代）の流出が深刻\n- 合計特殊出生率 1.15（全国最低水準）")
    with col2:
        st.warning("**産業構造の課題**\n\n- 製造業の空洞化\n- 農業の担い手不足\n- 観光業のポテンシャル未活用")
    with col3:
        st.info("**強みと機会**\n\n- 再エネ資源（太陽光・地熱等）の賦存\n- 農産物ブランド力（あきたこまち）\n- インバウンド需要の回復")


# ============================================================
# 人口動態ページ
# ============================================================
def page_population():
    st.title("👥 人口動態分析")
    st.markdown("---")

    df_pop_real, pop_source, pop_fetched = _get_population(estat_api.AKITA_AREA_CODE)
    df_mig = get_sample_migration()

    # データソース表示
    if pop_fetched:
        st.success(
            f"✅ 人口推計: **{pop_source}** を使用　"
            f"データ取得日: **{_fmt_date(pop_fetched)}**"
        )
    else:
        st.info("※ 人口推計はサンプルデータです。「🔌 e-Stat API連携」でAPIキーを設定すると実データに切り替わります。")
    st.caption("転入・転出データ（下グラフ）は住民基本台帳人口移動報告をベースにした参考推計値です。")

    # 実データがある場合は総人口の時系列グラフに使用（他のグラフはサンプルのまま）
    df_pop = get_sample_population()

    # 実データがある場合は総人口グラフを実データで表示
    if pop_fetched and not df_pop_real.empty:
        st.subheader("総人口の推移（e-Stat 実データ）")
        fig = px.line(
            df_pop_real, x="年", y="総人口（万人）",
            markers=True,
            title=f"秋田県 総人口の推移　（{pop_source} | 取得: {_fmt_date(pop_fetched)}）",
            color_discrete_sequence=["#1f4e79"],
        )
        fig.update_layout(height=320, yaxis_title="万人")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("---")

    # 人口構造の推移（積み上げ面グラフ）
    st.subheader("人口構造の変化（年齢3区分）")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_pop["年"], y=df_pop["老年人口（万人）"],
        name="老年人口（65歳以上）", fill="tozeroy",
        stackgroup="one", line_color="#d62728",
    ))
    fig.add_trace(go.Scatter(
        x=df_pop["年"], y=df_pop["生産年齢人口（万人）"],
        name="生産年齢人口（15-64歳）", fill="tonexty",
        stackgroup="one", line_color="#1f77b4",
    ))
    fig.add_trace(go.Scatter(
        x=df_pop["年"], y=df_pop["年少人口（万人）"],
        name="年少人口（0-14歳）", fill="tonexty",
        stackgroup="one", line_color="#2ca02c",
    ))
    fig.update_layout(title="年齢3区分別人口の推移", height=400, yaxis_title="万人")
    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        # 転入・転出
        st.subheader("転入・転出の推移")
        fig = go.Figure()
        fig.add_bar(x=df_mig["年"], y=df_mig["転入者数（人）"], name="転入", marker_color="#2ca02c")
        fig.add_bar(x=df_mig["年"], y=df_mig["転出者数（人）"], name="転出", marker_color="#d62728")
        fig.add_trace(go.Scatter(
            x=df_mig["年"], y=df_mig["社会増減（人）"],
            name="社会増減", line=dict(color="black", dash="dash"),
        ))
        fig.update_layout(barmode="group", height=350, yaxis_title="人")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # 高齢化率の推移
        st.subheader("高齢化率の推移")
        df_pop["高齢化率（%）"] = (df_pop["老年人口（万人）"] / df_pop["総人口（万人）"] * 100).round(1)
        fig = px.bar(
            df_pop, x="年", y="高齢化率（%）",
            color="高齢化率（%）",
            color_continuous_scale="Reds",
            text="高齢化率（%）",
        )
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    # ── 生産年齢人口・従業者数の推移 ────────────────────────────
    st.markdown("---")
    st.subheader("生産年齢人口と従業者数の推移")
    st.caption("出典: 国勢調査（総務省）・経済センサス（経産省）| サンプルデータ")

    df_wt = get_sample_worker_trend()

    col1, col2 = st.columns(2)

    with col1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_pop["年"], y=df_pop["生産年齢人口（万人）"],
            name="生産年齢人口（15-64歳）",
            mode="lines+markers",
            line=dict(color="#1f77b4", width=3),
            marker=dict(size=8),
            fill="tozeroy",
            fillcolor="rgba(31,119,180,0.10)",
        ))
        fig.update_layout(
            title="生産年齢人口の推移",
            height=360,
            yaxis=dict(title="万人", range=[0, 90]),
            xaxis_title="年",
            margin=dict(b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
        chg_pop = (df_pop["生産年齢人口（万人）"].iloc[-1] / df_pop["生産年齢人口（万人）"].iloc[0] - 1) * 100
        st.metric(
            "1990年→2023年",
            f"{df_pop['生産年齢人口（万人）'].iloc[-1]}万人",
            delta=f"{chg_pop:.1f}%（1990年比）",
            delta_color="inverse",
        )

    with col2:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_wt["年"], y=df_wt["第一次産業（万人）"],
            name="第一次産業（農林水産）", marker_color="#2ca02c",
        ))
        fig.add_trace(go.Bar(
            x=df_wt["年"], y=df_wt["第二次産業（万人）"],
            name="第二次産業（建設・製造）", marker_color="#1f4e79",
        ))
        fig.add_trace(go.Bar(
            x=df_wt["年"], y=df_wt["第三次産業（万人）"],
            name="第三次産業（サービス等）", marker_color="#ff7f0e",
        ))
        fig.update_layout(
            title="従業者数の推移（産業別）",
            barmode="stack",
            height=360,
            yaxis_title="万人",
            xaxis_title="年",
            legend=dict(orientation="h", y=-0.28, font=dict(size=10)),
            margin=dict(b=60),
        )
        st.plotly_chart(fig, use_container_width=True)
        chg_wt = (df_wt["従業者数合計（万人）"].iloc[-1] / df_wt["従業者数合計（万人）"].iloc[0] - 1) * 100
        st.metric(
            "1990年→2023年",
            f"{df_wt['従業者数合計（万人）'].iloc[-1]}万人",
            delta=f"{chg_wt:.1f}%（1990年比）",
            delta_color="inverse",
        )

    # 両指標の並走比較グラフ
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_pop["年"], y=df_pop["生産年齢人口（万人）"],
        name="生産年齢人口（15-64歳）",
        mode="lines+markers",
        line=dict(color="#1f77b4", width=2),
        marker=dict(size=6),
    ))
    fig.add_trace(go.Scatter(
        x=df_wt["年"], y=df_wt["従業者数合計（万人）"],
        name="従業者数合計",
        mode="lines+markers",
        line=dict(color="#d62728", width=2, dash="dot"),
        marker=dict(size=6),
    ))
    fig.update_layout(
        title="生産年齢人口 vs 従業者数（推移比較）",
        height=300,
        yaxis=dict(title="万人", rangemode="tozero"),
        legend=dict(orientation="h", y=-0.30, font=dict(size=11)),
        margin=dict(b=70),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.info(
        "💡 **診断士の着眼点** — "
        "生産年齢人口（15-64歳）は1990年の79.5万人から2023年には43.5万人へと約**45%減少**。"
        "従業者数も同期間に約**33%減少**しており、労働力供給の構造的縮小が秋田県経済の根本課題です。"
        "第一次・第二次産業の落ち込みが特に顕著で、第三次産業への雇用シフトも限界に近づいています。"
    )

    # データテーブル
    st.subheader("人口データ一覧")
    st.dataframe(df_pop, use_container_width=True)

    # CSV ダウンロード
    csv = df_pop.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("📥 CSVダウンロード", csv, "akita_population.csv", "text/csv")


# ============================================================
# 産業構造ページ
# ============================================================
def page_industry():
    st.title("🏭 産業構造分析")
    st.markdown("---")
    st.info("📊 このページのデータは **参考推計値（経済センサス・国勢調査ベース）** です。就業者数・前回比は統計を基にした推計であり、公式統計と異なる場合があります。")

    df = get_sample_industry()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("産業別就業者数")
        fig = px.bar(
            df.sort_values("就業者数（千人）"),
            x="就業者数（千人）", y="産業",
            orientation="h",
            color="就業者数（千人）",
            color_continuous_scale="Blues",
            text="就業者数（千人）",
        )
        fig.update_traces(texttemplate="%{text:.1f}千人", textposition="outside")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("前回調査比（増減率）")
        df["色"] = df["前回比（%）"].apply(lambda x: "#2ca02c" if x > 0 else "#d62728")
        fig = go.Figure(go.Bar(
            x=df["前回比（%）"],
            y=df["産業"],
            orientation="h",
            marker_color=df["色"],
            text=df["前回比（%）"].apply(lambda x: f"{x:+.1f}%"),
            textposition="outside",
        ))
        fig.add_vline(x=0, line_dash="solid", line_color="black")
        fig.update_layout(height=400, xaxis_title="前回比（%）")
        st.plotly_chart(fig, use_container_width=True)

    # 注目産業の分析
    st.markdown("---")
    st.subheader("注目産業のポイント")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.success("**医療・福祉（+8.5%）**\n\n高齢化に伴い最大の成長産業。地域包括ケアの担い手確保が課題。")
    with col2:
        st.error("**宿泊・飲食（-12.3%）**\n\nコロナ禍の影響が継続。インバウンド回復でV字回復の可能性あり。")
    with col3:
        st.warning("**農林水産（-5.2%）**\n\nあきたこまちの競争優位を活かした6次産業化・輸出強化が鍵。")

    st.dataframe(df, use_container_width=True)


# ============================================================
# 経済指標ページ
# ============================================================
def page_economy():
    st.title("💰 経済指標")
    st.markdown("---")
    st.info(
        "📊 このページのデータは **参考推計値** です。\n\n"
        "- 一人当たり県民所得: 内閣府 県民経済計算（2020年度）\n"
        "- 完全失業率: 総務省 労働力調査（2023年）\n"
        "- 有効求人倍率: 厚生労働省（2023年）\n"
        "- 製造品出荷額・農業産出額: 経産省・農水省（2022年）\n\n"
        "最新値は各機関の公式統計を必ずご確認ください。"
    )

    df = get_sample_economy()

    # 全国比較
    st.subheader("秋田県 vs 全国平均")
    st.caption("出典: 内閣府 県民経済計算（2020年度）、厚生労働省（2023年）｜参考推計値")
    comparison_data = {
        "指標": ["一人当たり県民所得（万円）", "完全失業率（%）", "有効求人倍率"],
        "秋田県": [244, 2.8, 1.35],
        "全国平均": [344, 2.6, 1.28],
    }
    df_comp = pd.DataFrame(comparison_data)

    fig = go.Figure()
    fig.add_bar(x=df_comp["指標"], y=df_comp["秋田県"], name="秋田県", marker_color="#1f4e79")
    fig.add_bar(x=df_comp["指標"], y=df_comp["全国平均"], name="全国平均", marker_color="#d9d9d9")
    fig.update_layout(barmode="group", height=350, title="秋田県と全国平均の比較")
    st.plotly_chart(fig, use_container_width=True)

    # 指標一覧
    st.subheader("主要経済指標一覧")
    st.dataframe(df, use_container_width=True)

    # インサイト
    st.markdown("---")
    st.subheader("診断士としての着眼点")
    st.markdown("""
    | 課題 | 現状 | 提言の方向性 |
    |------|------|-------------|
    | 所得水準の低さ | 全国平均比 -100万円 | 高付加価値産業の誘致・育成 |
    | 製造業の空洞化 | 出荷額減少傾向 | IoT・DX活用による競争力強化 |
    | 農業の低収益性 | 産出額維持だが担い手減 | 6次産業化・輸出促進 |
    | 観光ポテンシャル | 温泉・文化資源豊富 | インバウンド対応強化 |
    """)


# ============================================================
# 市町村比較ページ
# ============================================================
def page_municipal():
    st.title("🏘️ 市町村比較")
    st.markdown("---")
    st.info("📊 このページのデータは **国勢調査（2020年）をベースにした参考推計値** です。人口・高齢化率・人口増減率は最新値と異なる場合があります。最新データは秋田県統計課の公式資料をご確認ください。")

    df = get_sample_municipal()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("市町村別人口")
        fig = px.bar(
            df.sort_values("人口（万人）", ascending=True),
            x="人口（万人）", y="市町村",
            orientation="h",
            color="高齢化率（%）",
            color_continuous_scale="Reds",
            text="人口（万人）",
        )
        fig.update_traces(texttemplate="%{text:.1f}万人", textposition="outside")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("高齢化率 vs 人口増減率")
        fig = px.scatter(
            df,
            x="高齢化率（%）",
            y="人口増減率（%）",
            text="市町村",
            size="人口（万人）",
            color="高齢化率（%）",
            color_continuous_scale="Reds",
            title="高齢化率が高いほど人口減少が加速",
        )
        fig.update_traces(textposition="top center")
        fig.add_hline(y=df["人口増減率（%）"].mean(), line_dash="dash", annotation_text="平均")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("📥 CSVダウンロード", csv, "akita_municipal.csv", "text/csv")


# ============================================================
# 業種別分析ページ
# ============================================================
def page_industry_analysis():
    st.title("🔎 業種別分析")
    st.caption("日本標準産業分類の中分類で業種を選択し、秋田県内の動向・課題・診断士向け提言を確認する")
    st.warning(
        "⚠️ **このページのデータは参考推計値です**\n\n"
        "事業所数・従業員数・売上額・5年推移・東北4県比較の数値は、"
        "経済センサス（2021年）・工業統計・商業統計等の公的統計をもとに推計したものです。"
        "実際の値と異なる場合があります。最新の正確な数値は各統計の原典をご確認ください。"
    )
    st.markdown("---")

    hierarchy = get_industry_hierarchy()

    # ── 大分類タブ ────────────────────────────────────────────
    tab_labels = [f"{v['icon']} {k}" for k, v in hierarchy.items()]
    tabs = st.tabs(tab_labels)

    for tab, (major, major_info) in zip(tabs, hierarchy.items()):
        with tab:
            cats = major_info["categories"]

            # 中分類セレクター
            selected = st.radio(
                "中分類を選択",
                cats,
                horizontal=True,
                key=f"radio_{major}",
            )

            st.markdown("---")
            detail = get_industry_detail(selected)
            if not detail:
                st.warning("データがまだ登録されていません。")
                continue

            # ── KPI カード ─────────────────────────────────────
            col1, col2, col3, col4 = st.columns(4)
            yoy = detail["前年比_pct"]
            delta_color = "normal" if yoy >= 0 else "inverse"
            col1.metric("事業所数",   f"{detail['事業所数']:,}社")
            col2.metric("従業員数",   f"{detail['従業員数']:,}人")
            col3.metric("年間売上額", f"{detail['売上額_億円']:,}億円",
                        delta=f"{yoy:+.1f}%（前年比）", delta_color=delta_color)
            col4.metric("大分類",     detail["大分類"])

            # ── グラフ 2列 ──────────────────────────────────────
            col_l, col_r = st.columns(2)

            with col_l:
                # 5年推移
                trend = detail["trend"]
                df_trend = pd.DataFrame({
                    "年": trend["年"],
                    "売上額_億円": trend["売上"],
                    "従業員_百人": trend["従業員"],
                })
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=df_trend["年"], y=df_trend["売上額_億円"],
                    name="売上額（億円）", marker_color="#1f4e79",
                    yaxis="y",
                ))
                fig.add_trace(go.Scatter(
                    x=df_trend["年"], y=df_trend["従業員_百人"],
                    name="従業員（百人）", line=dict(color="#d62728", width=2),
                    mode="lines+markers", yaxis="y2",
                ))
                fig.update_layout(
                    title=f"{selected} — 5年間の推移",
                    height=340,
                    yaxis=dict(title="売上額（億円）", rangemode="tozero"),
                    yaxis2=dict(title="従業員（百人）", overlaying="y", side="right", rangemode="tozero"),
                    legend=dict(orientation="h", y=-0.2),
                )
                st.plotly_chart(fig, use_container_width=True)

            with col_r:
                # 東北4県比較
                tohoku = detail["tohoku"]
                prefs  = list(tohoku.keys())
                vals   = list(tohoku.values())
                colors = ["#d62728" if p == "秋田県" else "#aec7e8" for p in prefs]
                fig = go.Figure(go.Bar(
                    x=prefs, y=vals,
                    marker_color=colors,
                    text=vals,
                    texttemplate="%{text:,}億円",
                    textposition="outside",
                ))
                fig.update_layout(
                    title=f"東北4県比較（売上額 億円）",
                    height=340,
                    yaxis_title="億円",
                )
                st.plotly_chart(fig, use_container_width=True)

            # ── 課題・強み・提言 ────────────────────────────────
            st.markdown("---")
            col_a, col_b, col_c = st.columns([2, 2, 3])

            with col_a:
                st.markdown("#### ⚠️ 主な課題")
                for item in detail.get("課題", []):
                    st.error(f"• {item}")

            with col_b:
                st.markdown("#### ✅ 強み・機会")
                for item in detail.get("強み", []):
                    st.success(f"• {item}")

            with col_c:
                st.markdown("#### 💡 診断士としての提言")
                st.info(detail.get("提言", ""))

                # 関連補助金
                subsidies = detail.get("関連補助金", [])
                if subsidies:
                    st.markdown("**関連補助金・支援制度**")
                    for s in subsidies:
                        st.markdown(f"- {s}")


# ============================================================
# ============================================================
# 食品製造業ページ（廃止 → 業種別分析の「食料品製造業」を参照）
# ============================================================
def page_food(show_title=True):
    if show_title:
        st.title("🍱 食品製造業 詳細分析")
    st.markdown("---")

    st.info("🔧 このページは現在データ整備中です。食料品製造業の統計データは「🔎 業種別分析」→「製造業」→「食料品製造業」でご確認ください。")


# ============================================================
# 商店街ページ
# ============================================================
def page_shotengai(show_title=True):
    if show_title:
        st.title("🏪 商店街 詳細分析")
    st.caption("秋田県内商店街の現状・課題と再生施策の提言")
    st.markdown("---")

    st.info("🔧 このページは現在データ整備中です。商店街に関する公的統計（空き店舗率・通行量）の収集・整備が完了次第、公開します。")


# ============================================================
# 特定業種支援ガイドページ
# ============================================================
def page_industry_detail():
    st.title("📋 特定業種支援ガイド")
    st.caption("特定業種の現状・課題・診断士提言・関連補助金を詳しく確認できます")
    st.markdown("---")

    INDUSTRIES = [
        "🔨 職別工事業・設備工事業",
        "🏨 宿泊業",
        "🍽️ 飲食サービス業",
        "🥡 持ち帰り・配達飲食サービス業",
        "✈️ 旅行業",
        "💐 冠婚葬祭業",
        "🤝 事業協同組合",
        "♻️ 廃棄物処理業",
        "🔧 自動車整備業",
    ]

    selected = st.selectbox("業種を選択", INDUSTRIES, label_visibility="collapsed")
    industry_key = selected.split(" ", 1)[1]  # アイコンを除いた業種名
    st.markdown("---")

    detail = get_industry_extended_detail(industry_key)
    if not detail:
        st.warning("データがまだ登録されていません。")
        return

    # KPIカード
    yoy = detail["前年比_pct"]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("事業所数",   f"{detail['事業所数']:,}社")
    col2.metric("従業員数",   f"{detail['従業員数']:,}人")
    col3.metric("年間売上額", f"{detail['売上額_億円']:,}億円",
                delta=f"{yoy:+.1f}%（前年比）",
                delta_color="normal" if yoy >= 0 else "inverse")
    col4.metric("大分類",     detail["大分類"])

    # グラフ 2列
    col_l, col_r = st.columns(2)
    with col_l:
        trend = detail["trend"]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=trend["年"], y=trend["売上"],
            name="売上額（億円）", marker_color="#1f4e79", yaxis="y",
        ))
        fig.add_trace(go.Scatter(
            x=trend["年"], y=trend["従業員"],
            name="従業員（百人）", line=dict(color="#d62728", width=2),
            mode="lines+markers", yaxis="y2",
        ))
        fig.update_layout(
            title=f"{industry_key} — 5年間の推移", height=340,
            yaxis=dict(title="売上額（億円）", rangemode="tozero"),
            yaxis2=dict(title="従業員（百人）", overlaying="y", side="right", rangemode="tozero"),
            legend=dict(orientation="h", y=-0.2),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        tohoku = detail["tohoku"]
        prefs = list(tohoku.keys())
        vals  = list(tohoku.values())
        colors = ["#d62728" if p == "秋田県" else "#aec7e8" for p in prefs]
        fig = go.Figure(go.Bar(
            x=prefs, y=vals, marker_color=colors,
            text=vals, texttemplate="%{text:,}億円", textposition="outside",
        ))
        fig.update_layout(title="東北4県比較（売上額 億円）", height=340, yaxis_title="億円")
        st.plotly_chart(fig, use_container_width=True)

    # 課題・強み
    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### ⚠️ 主な課題")
        for item in detail.get("課題", []):
            st.error(f"• {item}")
    with col_b:
        st.markdown("#### ✅ 強み・機会")
        for item in detail.get("強み", []):
            st.success(f"• {item}")

    # 診断士提言（3項目）
    st.markdown("---")
    st.markdown("#### 💡 診断士としての提言")
    提言s = detail.get("提言_詳細", [])
    if 提言s:
        cols = st.columns(len(提言s))
        for col, (title, body) in zip(cols, 提言s):
            with col:
                st.info(f"**{title}**\n\n{body}")

    # 関連補助金
    subsidies = detail.get("関連補助金", [])
    if subsidies:
        st.markdown("**関連補助金・支援制度**")
        for s in subsidies:
            st.markdown(f"- {s}")

    # 事例セクション（共通）
    detail_for_cases = get_industry_extended_detail(industry_key)
    cases = detail_for_cases.get("事例", [])
    if cases:
        st.markdown("---")
        st.markdown("#### 📖 参考事例（他地域・中小企業白書）")
        for case in cases:
            with st.expander(f"**{case['タイトル']}** ― {case['地域']}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**取り組み:** {case['取り組み']}")
                    st.markdown(f"**成果:** {case['成果']}")
                with col2:
                    st.info(f"**秋田への示唆**\n\n{case['示唆']}")


# ============================================================
# 政策提言ページ
# ============================================================
def page_policy():
    st.title("🏛️ 政策提言")
    st.caption("秋田県経済の成長・持続策")

    last_updated = get_policy_last_updated()
    kpi_note = get_policy_kpi_note()
    col_info, col_badge = st.columns([4, 1])
    with col_info:
        st.info(f"📅 **データ最終更新: {last_updated}** — 毎月1日にGitHub Actionsが自動更新します。")
    with col_badge:
        st.metric("政策提言数", "4提言", "2柱構造")

    st.markdown("---")

    df_prop = get_policy_proposals()
    df_kpi  = get_policy_kpi()
    df_shin = get_shindan_actions()
    df_chuo = get_chuokai_actions()
    df_road = get_roadmap()
    _policy_cache = get_policy_cache_raw()

    if df_prop.empty:
        st.warning("⚠ 政策データが読み込めませんでした。data/policy_cache/policy_data.json を確認してください。")
        return

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🎯 戦略的枠組み", "🌏 第1柱：成長戦略", "🏗️ 第2柱：持続戦略", "📊 KPI・成果指標", "🗺️ ロードマップ"
    ])

    # ========== TAB1: 戦略的枠組み ==========
    with tab1:
        st.subheader("2柱戦略の全体像")

        col_g, col_s = st.columns(2)
        with col_g:
            st.markdown("### 🌏 第1柱：成長戦略（県外へ売る）")
            st.success("""
            **目標:** 秋田の強みを活かして域外収入を増やす

            - 農業・食品加工の付加価値化と販路拡大
            - 事業承継を産業集約・強化の機会として活用

            **前提:** 内需縮小は不可逆。需要は県外・海外に求める。
            """)
        with col_s:
            st.markdown("### 🏗️ 第2柱：持続戦略（今ある産業を守る）")
            st.info("""
            **目標:** 既存産業が縮小均衡に陥らないよう下支え

            - 省力化投資の徹底活用と効果測定
            - 高齢経営者の円滑な出口支援

            **前提:** 衰退を遅らせるだけでなく、次の担い手へつなぐ。
            """)

        st.markdown("---")
        st.subheader("前提認識（構造制約）")
        col1, col2 = st.columns(2)
        with col1:
            st.warning("**人口減少は不可逆**\n\n内需縮小前提で戦略を組む。国内需要増は見込まない。")
        with col2:
            st.warning("**大企業の自然誘致は期待しない**\n\n政策誘致なき大企業立地はない。既存中小企業の強化を優先。")

        st.markdown("---")
        st.subheader("横断的視点：継続的な伴走支援の重視")
        st.markdown("""
        補助金申請の場面だけでなく、**その前後を含めた継続的な関与**が支援の効果を高める。
        意欲ある経営者を能動的に発見し、経営課題に応じた深い伴走支援を行うことで、
        地域経済への波及効果を最大化していく。
        """)

        st.markdown("---")
        st.subheader("なぜ秋田か：固有の優位性")
        st.markdown("秋田の中小企業が県外・海外と戦える根拠は、**他地域では代替できない固有性**にあります。")

        advantages = _policy_cache.get("akita_advantages", [])
        if advantages:
            adv_cols = st.columns(len(advantages))
            for col, adv in zip(adv_cols, advantages):
                with col:
                    st.markdown(f"### {adv['アイコン']} {adv['分野']}")
                    st.success(f"**強み**\n\n{adv['強み']}")
                    st.warning(f"**現状の課題**\n\n{adv['課題']}")
                    st.caption(f"優位の根拠：{adv['優位の根拠']}")

        st.markdown("---")
        vcg = _policy_cache.get("value_chain_gap", {})
        if vcg:
            st.subheader("優位性が収益に結びついていない構造的原因")
            st.markdown(vcg.get("説明", ""))
            gaps = vcg.get("ギャップ", [])
            if gaps:
                評価色 = {"強い": "🟢", "中程度": "🟡", "弱い": "🔴"}
                for g in gaps:
                    badge = 評価色.get(g["評価"], "⚪")
                    st.markdown(f"**{badge} {g['段階']}**　{g['評価']}　— {g['コメント']}")
            st.info("💡 支援機関の役割は「生産」から「加工・販売・ブランド管理」へのつなぎ役にある。")

        st.markdown("---")
        st.subheader("提言一覧（2柱別）")
        diff_map = {"低": 1, "中": 2, "高": 3}
        df_chart = df_prop.copy()
        df_chart["難易度_数値"] = df_chart["難易度"].map(diff_map)
        df_chart["期待効果_億円"] = pd.to_numeric(df_chart["期待効果（億円/年）"], errors="coerce")
        prio_map = {"高": 18, "中": 10}
        df_chart["優先度_サイズ"] = df_chart["優先度"].map(prio_map).fillna(10)

        pillar_colors = {"第1柱：成長戦略": "#2ca02c", "第2柱：持続戦略": "#1f77b4"}
        fig = px.scatter(
            df_chart,
            x="難易度_数値", y="期待効果_億円",
            color="柱", size="優先度_サイズ", text="提言ID",
            hover_name="提言タイトル",
            hover_data={"難易度_数値": False, "優先度_サイズ": False,
                        "主な提言主体": True, "実施期間": True, "期待効果_億円": True},
            title="政策提言 優先度マップ（縦軸=期待経済効果、横軸=難易度）",
            labels={"難易度_数値": "難易度（低→高）", "期待効果_億円": "期待効果（億円/年）", "柱": "戦略柱"},
            color_discrete_map=pillar_colors,
        )
        fig.update_layout(height=400, yaxis_range=[0, 60])
        fig.update_traces(textposition="top center")
        fig.update_xaxes(tickvals=[1, 2, 3], ticktext=["低", "中", "高"])
        st.plotly_chart(fig, use_container_width=True)

        display_cols = ["提言ID", "柱", "分野", "提言タイトル", "主な提言主体", "優先度", "難易度", "期待効果（億円/年）", "実施期間"]

        def color_priority(val):
            return "background-color:#c6efce;color:#276221" if val == "高" else \
                   "background-color:#ffeb9c;color:#9c5700" if val == "中" else ""

        styled = df_prop[display_cols].style.map(color_priority, subset=["優先度"])
        st.dataframe(styled, use_container_width=True)

    # ========== TAB2: 第1柱：成長戦略 ==========
    with tab2:
        st.subheader("第1柱：成長戦略（県外へ売る）")
        st.markdown("秋田の強みを活かした域外収入の拡大。内需縮小が不可逆的に進む中、需要は県外・海外に求める。")

        df_p1 = df_prop[df_prop["柱"] == "第1柱：成長戦略"]
        for _, row in df_p1.iterrows():
            with st.expander(f"**{row['提言ID']}: {row['提言タイトル']}**　（期待効果: {row['期待効果（億円/年）']}億円/年）", expanded=True):
                col_l, col_r = st.columns([3, 1])
                with col_l:
                    st.markdown(f"**背景・課題:** {row.get('背景・課題', '')}")
                    st.markdown("---")
                    施策リスト = row.get('具体的施策', '').split('／')
                    st.markdown("**具体的施策:**")
                    for s in 施策リスト:
                        if s.strip():
                            st.markdown(f"- {s.strip()}")
                with col_r:
                    st.metric("期待効果", f"{row['期待効果（億円/年）']}億円/年")
                    st.metric("実施期間", row["実施期間"])
                    st.metric("難易度", row["難易度"])
                    st.metric("提言主体", row["主な提言主体"])

        st.markdown("---")
        st.subheader("診断士・支援機関 アクション（成長支援）")
        if "場面" in df_shin.columns:
            df_growth = df_shin[df_shin["場面"].isin(["企業発掘", "成長支援"])]
            scene_order = ["企業発掘", "成長支援"]
            for scene in scene_order:
                df_s = df_growth[df_growth["場面"] == scene]
                if not df_s.empty:
                    with st.expander(f"▶ {scene}（{len(df_s)}項目）", expanded=True):
                        st.dataframe(df_s[["アクション", "対象", "活用する制度・補助金"]], use_container_width=True, hide_index=True)
        else:
            st.dataframe(df_shin, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.info("""
        **行政への要望（第1柱）**

        - 専門家謝金規程の市場実態への引き上げ（外部専門家との協働強化のため）
        - 農業・食品加工事業者向け輸出補助（HACCP等）の直接補助スキーム
        - 第三者承継支援の予算拡充（M&A費用補助の継続・拡大）
        """)

    # ========== TAB3: 第2柱：持続戦略 ==========
    with tab3:
        st.subheader("第2柱：持続戦略（今ある産業を守る）")
        st.markdown("既存産業の縮小均衡を防ぎ、次の担い手へつなぐ。省力化と円滑な出口支援が両輪。")

        df_p2 = df_prop[df_prop["柱"] == "第2柱：持続戦略"]
        for _, row in df_p2.iterrows():
            with st.expander(f"**{row['提言ID']}: {row['提言タイトル']}**　（期待効果: {row['期待効果（億円/年）']}億円/年）", expanded=True):
                col_l, col_r = st.columns([3, 1])
                with col_l:
                    st.markdown(f"**背景・課題:** {row.get('背景・課題', '')}")
                    st.markdown("---")
                    施策リスト = row.get('具体的施策', '').split('／')
                    st.markdown("**具体的施策:**")
                    for s in 施策リスト:
                        if s.strip():
                            st.markdown(f"- {s.strip()}")
                with col_r:
                    st.metric("期待効果", f"{row['期待効果（億円/年）']}億円/年")
                    st.metric("実施期間", row["実施期間"])
                    st.metric("難易度", row["難易度"])
                    st.metric("提言主体", row["主な提言主体"])

        st.markdown("---")
        st.subheader("支援機関の運用転換（現状 → あるべき姿）")
        if "転換カテゴリ" in df_chuo.columns:
            diff_color = {"低": "#c6efce", "中": "#ffe699", "高": "#ffc7ce"}
            for cat in df_chuo["転換カテゴリ"].unique():
                df_c = df_chuo[df_chuo["転換カテゴリ"] == cat]
                with st.expander(f"▶ {cat}（{len(df_c)}項目）", expanded=True):
                    for _, crow in df_c.iterrows():
                        col_now, col_arrow, col_ideal = st.columns([2, 0.3, 2])
                        with col_now:
                            st.markdown(f"**現状:** {crow['現状']}")
                        with col_arrow:
                            st.markdown("→")
                        with col_ideal:
                            badge = diff_color.get(crow.get("難易度", "中"), "#ffe699")
                            st.markdown(f"**あるべき姿:** {crow['あるべき姿']}")
                        st.caption(f"実施主体: {crow.get('実施主体', '')}　難易度: {crow.get('難易度', '')}")
                        st.markdown("---")
        else:
            st.dataframe(df_chuo, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("診断士・支援機関 アクション（持続・成果測定）")
        if "場面" in df_shin.columns:
            df_sus = df_shin[df_shin["場面"].isin(["持続支援", "成果測定"])]
            for scene in ["持続支援", "成果測定"]:
                df_s = df_sus[df_sus["場面"] == scene]
                if not df_s.empty:
                    with st.expander(f"▶ {scene}（{len(df_s)}項目）", expanded=True):
                        st.dataframe(df_s[["アクション", "対象", "活用する制度・補助金"]], use_container_width=True, hide_index=True)
        else:
            st.dataframe(df_shin, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.info("""
        **行政への要望（第2柱）**

        - 省力化投資補助金の継続・拡充（特に中小製造業・サービス業向け）
        - 廃業支援・雇用調整助成金の活用促進と手続き簡素化
        - 補助金フォローアップを支援機関が組織的に実施できる仕組みづくり（専門家派遣予算）
        """)

    # ========== TAB4: KPI・成果指標 ==========
    with tab4:
        st.subheader("政策KPI 目標値一覧")
        if kpi_note:
            st.caption(kpi_note)

        cols = st.columns(4)
        gauge_configs = [
            {"指標": "食品製造業 輸出額（億円/年）", "min": 0, "max": 60,
             "color": "#2ca02c", "suffix": "億円", "title": "食品輸出額",
             "warn1": 20, "warn2": 40},
            {"指標": "第三者承継成立件数（年間）", "min": 0, "max": 60,
             "color": "#1f4e79", "suffix": "件", "title": "第三者承継件数",
             "warn1": 20, "warn2": 40},
            {"指標": "補助金活用後フォローアップ実施率", "min": 0, "max": 100,
             "color": "#ff7f0e", "suffix": "%", "title": "フォロー実施率",
             "warn1": 40, "warn2": 65},
            {"指標": "一人当たり県民所得（万円）", "min": 220, "max": 300,
             "color": "#9467bd", "suffix": "万円", "title": "一人当たり所得",
             "warn1": 255, "warn2": 272},
        ]

        for col, cfg in zip(cols, gauge_configs):
            row = df_kpi[df_kpi["指標"] == cfg["指標"]]
            if row.empty:
                continue
            val = float(row.iloc[0].get("現状_数値", 0))
            auto_badge = " 🔄" if row.iloc[0].get("自動更新", False) else ""
            with col:
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=val,
                    title={"text": cfg["title"] + auto_badge, "font": {"size": 13}},
                    gauge={
                        "axis": {"range": [cfg["min"], cfg["max"]]},
                        "steps": [
                            {"range": [cfg["min"], cfg["warn1"]], "color": "#ffc7ce"},
                            {"range": [cfg["warn1"], cfg["warn2"]], "color": "#ffe699"},
                            {"range": [cfg["warn2"], cfg["max"]], "color": "#c6efce"},
                        ],
                        "threshold": {"value": float(row.iloc[0].get("3年後_数値", val)),
                                      "line": {"color": "red", "width": 2}},
                        "bar": {"color": cfg["color"]},
                    },
                    number={"suffix": cfg["suffix"]},
                ))
                fig.update_layout(height=220, margin=dict(t=50, b=10, l=20, r=20))
                st.plotly_chart(fig, use_container_width=True)

        st.caption("🔴赤ライン = 3年後目標。")
        st.markdown("---")

        st.subheader("全KPI 達成進捗（現状 → 5年後目標）")
        kpi_chart_data = []
        for _, krow in df_kpi.iterrows():
            now = float(krow.get("現状_数値", 0))
            tgt5 = float(krow.get("5年後_数値", 0))
            if tgt5 != 0:
                progress = min(100, max(0, (now / tgt5) * 100))
            else:
                progress = 0
            kpi_chart_data.append({
                "指標": krow["指標"][:20] + ("..." if len(krow["指標"]) > 20 else ""),
                "達成率(%)": round(progress, 1),
                "柱": krow.get("柱", "総合"),
            })
        df_prog = pd.DataFrame(kpi_chart_data)
        pillar_bar_colors = {"第1柱：成長戦略": "#2ca02c", "第2柱：持続戦略": "#1f77b4", "総合": "#9467bd"}
        fig = px.bar(
            df_prog, x="達成率(%)", y="指標", orientation="h",
            color="柱",
            color_discrete_map=pillar_bar_colors,
            title="現状の5年後目標への達成率",
        )
        fig.update_layout(height=420)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        display_kpi_cols = [c for c in ["指標", "柱", "現状値", "3年後目標", "5年後目標", "担当主体", "備考"] if c in df_kpi.columns]
        st.dataframe(df_kpi[display_kpi_cols], use_container_width=True)
        csv = df_kpi[display_kpi_cols].to_csv(index=False, encoding="utf-8-sig")
        st.download_button("📥 KPI一覧をCSVダウンロード", csv, "akita_policy_kpi.csv", "text/csv")

    # ========== TAB5: ロードマップ ==========
    with tab5:
        st.subheader("施策ロードマップ")
        st.markdown("短期（〜2026）・中期（2027〜2028）・長期（2029〜）の3フェーズで推進します。")

        pillar_road_colors = {
            "第1柱：成長戦略": "#2ca02c",
            "第2柱：持続戦略": "#1f77b4",
            "支援機関改革": "#ff7f0e",
            "総合": "#9467bd",
        }
        year_map = {
            "2026年度上期": 2026.0, "2026年度": 2026.25, "2026年度下期": 2026.5,
            "2027年度": 2027.0, "2027〜2028年度": 2027.5,
            "2028年度": 2028.0, "2029年度": 2029.0,
            "2030年度": 2030.0, "2031年度": 2031.0,
        }
        df_road = df_road.copy()
        df_road["時期_数値"] = df_road["時期"].map(year_map)

        color_col = "柱" if "柱" in df_road.columns else "フェーズ"
        fig = px.scatter(
            df_road, x="時期_数値", y="施策",
            color=color_col, symbol="フェーズ",
            color_discrete_map=pillar_road_colors,
            title="施策タイムライン（2柱別 実施スケジュール）",
            labels={"時期_数値": "年度", "施策": ""},
        )
        fig.update_traces(marker=dict(size=14, line=dict(width=1, color="white")))
        fig.update_layout(height=540, xaxis=dict(tickformat=".0f"))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        for phase, col, desc in [
            ("短期", col1, "2026年度中に着手できる即効施策"),
            ("中期", col2, "2027〜2028年度に本格展開"),
            ("長期", col3, "2029年度以降に成果が出る施策"),
        ]:
            df_ph = df_road[df_road["フェーズ"] == phase][["施策", "時期", "主体"]]
            with col:
                st.markdown(f"**{phase}（{desc}）**")
                st.dataframe(df_ph, use_container_width=True, hide_index=True)


# ============================================================
# 事例研究データベースページ
# ============================================================
def page_cases():
    st.title("📚 事例研究データベース")
    st.caption("他県・他地域の成功事例を検索・比較し、秋田への施策応用を考える")
    st.markdown("---")

    df = get_case_studies()

    # ---- 検索・フィルター ----
    col1, col2, col3 = st.columns(3)
    with col1:
        keyword = st.text_input("🔍 キーワード検索", placeholder="例: 食品, 移住, 観光, 輸出")
    with col2:
        sel_bunya = st.multiselect(
            "分野で絞り込み",
            options=sorted(df["分野"].unique()),
            default=[],
        )
    with col3:
        sel_apply = st.multiselect(
            "秋田への適用可能性",
            options=["高", "中"],
            default=["高", "中"],
        )

    # フィルタリング
    df_filtered = df.copy()
    if keyword:
        mask = (
            df_filtered["事例タイトル"].str.contains(keyword, case=False, na=False) |
            df_filtered["施策内容"].str.contains(keyword, case=False, na=False) |
            df_filtered["キーワードタグ"].str.contains(keyword, case=False, na=False) |
            df_filtered["主な成果"].str.contains(keyword, case=False, na=False)
        )
        df_filtered = df_filtered[mask]
    if sel_bunya:
        df_filtered = df_filtered[df_filtered["分野"].isin(sel_bunya)]
    if sel_apply:
        df_filtered = df_filtered[df_filtered["秋田への適用可能性"].isin(sel_apply)]

    st.markdown(f"**{len(df_filtered)} 件**の事例が見つかりました")
    st.markdown("---")

    # ---- 事例カード表示 ----
    for _, row in df_filtered.iterrows():
        apply_color = "🟢" if row["秋田への適用可能性"] == "高" else "🟡"
        with st.expander(
            f"{apply_color} **{row['事例ID']}** | {row['地域']} — {row['事例タイトル']} 【{row['分野']}】",
            expanded=False,
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**📌 課題**")
                st.info(row["課題"])
                st.markdown("**🛠️ 施策内容**")
                st.write(row["施策内容"])
            with col2:
                st.markdown("**📈 主な成果**")
                st.success(row["主な成果"])
                st.markdown("**💡 秋田への参考ポイント**")
                st.warning(row["参考にすべき点"])

            tags = row["キーワードタグ"].split(",")
            st.markdown("**🏷️ タグ:** " + " ".join([f"`{t.strip()}`" for t in tags]))
            st.caption(f"🔎 検索キーワード: {row['参考URL_キーワード']}")

    st.markdown("---")

    # ---- 比較ビュー ----
    st.subheader("📊 事例比較ビュー")
    ids = df_filtered["事例ID"].tolist()
    if len(ids) >= 2:
        sel_ids = st.multiselect(
            "比較する事例を選択（2〜4件）",
            options=ids,
            default=ids[:2],
            format_func=lambda x: f"{x}: {df[df['事例ID']==x]['事例タイトル'].values[0][:20]}…",
        )
        if len(sel_ids) >= 2:
            df_cmp = df[df["事例ID"].isin(sel_ids)][
                ["事例ID","地域","分野","事例タイトル","課題","主な成果","秋田への適用可能性","参考にすべき点"]
            ].set_index("事例ID")
            st.dataframe(df_cmp.T, use_container_width=True)
    else:
        st.info("フィルター結果が2件以上になると比較ビューが使えます")

    st.markdown("---")

    # ---- 分野別マップ ----
    st.subheader("分野別 事例分布")
    bunya_count = df_filtered.groupby(["分野","秋田への適用可能性"]).size().reset_index(name="件数")
    if not bunya_count.empty:
        fig = px.bar(
            bunya_count, x="分野", y="件数",
            color="秋田への適用可能性",
            color_discrete_map={"高": "#2ca02c", "中": "#ff7f0e"},
            title="分野×適用可能性の分布",
            text="件数",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(height=320)
        st.plotly_chart(fig, use_container_width=True)

    # Excel出力
    csv = df_filtered.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("📥 事例一覧CSVダウンロード", csv, "akita_case_studies.csv", "text/csv")


# ============================================================
# 補助金カレンダーページ
# ============================================================
def page_subsidies():
    st.title("💴 補助金カレンダー")
    st.caption("主要補助金の申請期限・対象・活用ポイントを一覧管理")
    st.markdown("---")

    df = get_subsidies()
    from datetime import date, datetime

    today = date.today()

    # ---- フィルター ----
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        sel_shubetsu = st.multiselect("種別", ["国", "県"], default=["国", "県"])
    with col_f2:
        show_expired = st.checkbox("期限切れを含む", value=False)

    df_f = df[df["種別"].isin(sel_shubetsu)].copy()

    # ---- 締切までの日数を計算 ----
    def days_left(deadline_str):
        if deadline_str == "通年":
            return 9999
        try:
            d = datetime.strptime(deadline_str, "%Y-%m-%d").date()
            return (d - today).days
        except Exception:
            return 9999

    df_f["残り日数"] = df_f["申請締切"].apply(days_left)
    df_f["状態"] = df_f["残り日数"].apply(
        lambda x: "🔴 締切間近（30日以内）" if 0 <= x <= 30
        else "🟡 申請中（31〜90日）" if 31 <= x <= 90
        else "🟢 余裕あり" if 91 <= x < 9999
        else "⚫ 通年受付" if x == 9999
        else "⚫ 期限切れ（次回公募待ち）"
    )

    # 期限切れ（残り日数が負）はデフォルト非表示
    if not show_expired:
        df_f = df_f[df_f["残り日数"] >= 0]

    # ---- 緊急アラート ----
    urgent = df_f[df_f["残り日数"] <= 30]
    if not urgent.empty:
        st.error(f"⚠️ 締切30日以内の補助金が {len(urgent)} 件あります！")
        for _, r in urgent.iterrows():
            st.markdown(f"- **{r['補助金名']}** — 締切: {r['申請締切']}（残り{r['残り日数']}日）")
        st.markdown("---")

    # ---- タイムライン ----
    st.subheader("申請スケジュール タイムライン")
    df_timeline = df_f[df_f["残り日数"] < 9999].sort_values("残り日数")
    if not df_timeline.empty:
        fig = go.Figure()
        colors = {"🔴 締切間近（30日以内）": "#d62728", "🟡 申請中（31〜90日）": "#ff7f0e", "🟢 余裕あり": "#2ca02c", "⚫ 期限切れ（次回公募待ち）": "#aaaaaa"}
        for _, row in df_timeline.iterrows():
            try:
                start = datetime.strptime(row["申請開始"], "%Y-%m-%d")
                end   = datetime.strptime(row["申請締切"], "%Y-%m-%d")
                color = colors.get(row["状態"], "#aec7e8")
                fig.add_trace(go.Scatter(
                    x=[start, end],
                    y=[row["補助金名"], row["補助金名"]],
                    mode="lines+markers",
                    line=dict(color=color, width=10),
                    marker=dict(size=8),
                    name=row["状態"],
                    showlegend=False,
                    hovertemplate=f"<b>{row['補助金名']}</b><br>開始:{row['申請開始']}<br>締切:{row['申請締切']}<br>上限:{row['補助上限']}",
                ))
            except Exception:
                pass
        fig.add_vline(x=datetime.combine(date.today(), datetime.min.time()),
                      line_dash="dash", line_color="red", annotation=None)
        fig.update_layout(height=380, xaxis_title="期間", yaxis_title="",
                          margin=dict(l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)

    # ---- カード一覧 ----
    st.markdown("---")
    st.subheader("補助金一覧")
    for _, row in df_f.sort_values("残り日数").iterrows():
        header = f"{row['状態']} **{row['補助金名']}**　({row['種別']}) ｜ 上限: {row['補助上限']}"
        with st.expander(header, expanded=(row["残り日数"] <= 30)):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**対象企業**\n\n{row['対象']}")
                st.markdown(f"**補助率**\n\n{row['補助率']}")
                st.markdown(f"**窓口**\n\n{row['窓口']}")
            with col2:
                st.markdown(f"**申請開始**\n\n{row['申請開始']}")
                st.markdown(f"**申請締切**\n\n{row['申請締切']}")
                st.markdown(f"**次回公募予定**\n\n{row['次回公募予定']}")
            st.info(f"💡 {row['メモ']}")
            st.markdown(f"🔗 [公式サイトを開く]({row['URL']})")

    # Excel出力
    st.markdown("---")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_f.drop(columns=["残り日数"]).to_excel(writer, sheet_name="補助金一覧", index=False)
    st.download_button(
        "📥 補助金一覧をExcelダウンロード",
        buffer.getvalue(),
        "akita_subsidies.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ============================================================
# 東北4県比較ページ
# ============================================================
def page_tohoku():
    st.title("🗾 東北4県比較分析")
    st.caption("青森・岩手・秋田・山形の主要指標を比較し、秋田の強みと課題を浮き彫りにする")
    st.markdown("---")

    # キャッシュ更新日の表示
    cache_updated = estat_api.get_cache_last_updated()
    if cache_updated:
        st.success(f"✅ 人口データ: e-Stat 実データ（毎月1日自動更新）　最終更新: **{_fmt_date(cache_updated)}**")
    else:
        st.info("※ 人口推移グラフはサンプルデータです。GitHub Actions による月次更新後に実データに切り替わります。")

    tab1, tab2, tab3, tab4 = st.tabs([
        "👥 人口動態比較", "💰 経済指標比較", "🏭 産業構造比較", "🏆 総合評価"
    ])

    # ========== TAB1: 人口動態比較 ==========
    with tab1:
        df_pop = get_tohoku_population()
        df_trend = get_tohoku_population_trend()
        prefs = ["青森県", "岩手県", "秋田県", "山形県"]

        # KPI カード
        akita = df_pop[df_pop["都道府県"] == "秋田県"].iloc[0]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("秋田県 総人口", f"{akita['総人口（万人）']}万人")
        col2.metric("高齢化率", f"{akita['高齢化率（%）']}%", delta="東北最高", delta_color="inverse")
        col3.metric("5年間人口増減", f"{akita['5年間人口増減率（%）']}%", delta_color="inverse")
        col4.metric("合計特殊出生率", str(akita["合計特殊出生率"]), delta="東北最低", delta_color="inverse")

        st.markdown("---")
        col_l, col_r = st.columns(2)

        with col_l:
            # キャッシュがあれば実データで上書き
            area_map = {"青森県": "02000", "岩手県": "03000", "秋田県": "05000", "山形県": "06000"}
            fig = go.Figure()
            for pref, color in zip(prefs, TOHOKU_COLORS):
                lw = 3 if pref == "秋田県" else 1.5
                dash = "solid" if pref == "秋田県" else "dot"
                df_c, fa = estat_api.load_cached_population(area_map[pref])
                if not df_c.empty:
                    x_vals, y_vals = df_c["年"], df_c["総人口（万人）"]
                else:
                    x_vals, y_vals = df_trend["年"], df_trend[pref]
                fig.add_trace(go.Scatter(
                    x=x_vals, y=y_vals,
                    name=pref, mode="lines+markers",
                    line=dict(color=color, width=lw, dash=dash),
                ))
            src_note = f"（e-Stat 実データ | {_fmt_date(cache_updated)}）" if cache_updated else "（サンプルデータ）"
            fig.update_layout(
                title=f"総人口の推移（万人）{src_note}",
                height=360, yaxis_title="万人",
                legend=dict(orientation="h"),
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            st.subheader("高齢化率 vs 合計特殊出生率")
            df_plot = df_pop.copy()
            df_plot["マーカーサイズ"] = df_plot["総人口（万人）"] / 10
            fig = px.scatter(
                df_plot,
                x="高齢化率（%）",
                y="合計特殊出生率",
                text="都道府県",
                color="都道府県",
                size="マーカーサイズ",
                color_discrete_sequence=TOHOKU_COLORS,
                title="右下ほど課題が深刻",
            )
            fig.update_traces(textposition="top center")
            fig.update_layout(height=360, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        # 人口指標 棒グラフ比較
        st.subheader("主要人口指標の比較")
        metrics = ["総人口（万人）", "高齢化率（%）", "5年間人口増減率（%）", "合計特殊出生率"]
        cols = st.columns(len(metrics))
        for col, metric in zip(cols, metrics):
            with col:
                colors_bar = [
                    "#d62728" if p == "秋田県" else "#aec7e8" for p in df_pop["都道府県"]
                ]
                fig = go.Figure(go.Bar(
                    x=df_pop["都道府県"],
                    y=df_pop[metric],
                    marker_color=colors_bar,
                    text=df_pop[metric],
                    texttemplate="%{text}",
                    textposition="outside",
                ))
                fig.update_layout(
                    title=metric, height=280,
                    margin=dict(t=40, b=10, l=5, r=5),
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)

    # ========== TAB2: 経済指標比較 ==========
    with tab2:
        df_eco = get_tohoku_economy()
        prefs = ["青森県", "岩手県", "秋田県", "山形県"]

        # KPI カード
        akita_eco = df_eco[df_eco["都道府県"] == "秋田県"].iloc[0]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("一人当たり県民所得", f"{akita_eco['一人当たり県民所得（万円）']}万円")
        col2.metric("有効求人倍率", f"{akita_eco['有効求人倍率']}倍")
        col3.metric("製造品出荷額", f"{akita_eco['製造品出荷額（億円）']:,}億円")
        col4.metric("観光入込客数", f"{akita_eco['観光入込客数（万人）']:,}万人")

        st.markdown("---")

        # 一人当たり県民所得
        col_l, col_r = st.columns(2)
        with col_l:
            st.subheader("一人当たり県民所得（万円）")
            colors_bar = ["#d62728" if p == "秋田県" else "#1f77b4" for p in df_eco["都道府県"]]
            fig = go.Figure(go.Bar(
                x=df_eco["都道府県"],
                y=df_eco["一人当たり県民所得（万円）"],
                marker_color=colors_bar,
                text=df_eco["一人当たり県民所得（万円）"],
                texttemplate="%{text}万円",
                textposition="outside",
            ))
            fig.update_layout(height=340, yaxis_title="万円")
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            st.subheader("製造品出荷額（億円）")
            colors_bar = ["#d62728" if p == "秋田県" else "#ff7f0e" for p in df_eco["都道府県"]]
            fig = go.Figure(go.Bar(
                x=df_eco["都道府県"],
                y=df_eco["製造品出荷額（億円）"],
                marker_color=colors_bar,
                text=df_eco["製造品出荷額（億円）"],
                texttemplate="%{text:,}億円",
                textposition="outside",
            ))
            fig.update_layout(height=340, yaxis_title="億円")
            st.plotly_chart(fig, use_container_width=True)

        # レーダーチャート
        st.subheader("総合経済力 レーダーチャート（4県比較）")
        # 各指標を最大値で正規化（0〜1）
        radar_metrics = {
            "県民所得": "一人当たり県民所得（万円）",
            "求人倍率": "有効求人倍率",
            "農業産出": "農業産出額（億円）",
            "製造出荷": "製造品出荷額（億円）",
            "観光客数": "観光入込客数（万人）",
        }
        fig = go.Figure()
        for pref, color in zip(prefs, TOHOKU_COLORS):
            row = df_eco[df_eco["都道府県"] == pref].iloc[0]
            values = []
            for label, col_name in radar_metrics.items():
                max_val = df_eco[col_name].max()
                values.append(row[col_name] / max_val * 100)
            values.append(values[0])  # 閉じる
            labels = list(radar_metrics.keys()) + [list(radar_metrics.keys())[0]]
            lw = 3 if pref == "秋田県" else 1.5
            fig.add_trace(go.Scatterpolar(
                r=values, theta=labels, name=pref,
                line=dict(color=color, width=lw),
                fill="toself" if pref == "秋田県" else None,
                fillcolor=color if pref == "秋田県" else None,
                opacity=0.3 if pref == "秋田県" else 1.0,
            ))
        fig.update_layout(
            polar=dict(radialaxis=dict(range=[0, 100], ticksuffix="%")),
            height=420,
            legend=dict(orientation="h"),
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("経済指標データ一覧")
        st.dataframe(df_eco, use_container_width=True)

    # ========== TAB3: 産業構造比較 ==========
    with tab3:
        df_ind = get_tohoku_industry()

        st.subheader("産業別就業者数の比較（千人）")

        # 積み上げ横棒グラフ
        industries = df_ind["産業"].tolist()
        fig = go.Figure()
        for pref, color in zip(prefs, TOHOKU_COLORS):
            lw = 2 if pref == "秋田県" else 1
            fig.add_trace(go.Bar(
                name=pref,
                y=industries,
                x=df_ind[pref],
                orientation="h",
                marker_color=color,
                text=df_ind[pref],
                texttemplate="%{text}千人",
                textposition="inside",
            ))
        fig.update_layout(
            barmode="group",
            height=480,
            xaxis_title="就業者数（千人）",
            legend=dict(orientation="h"),
        )
        st.plotly_chart(fig, use_container_width=True)

        # 構成比パイチャート（4県並べて）
        st.subheader("産業構成比（%）")
        cols = st.columns(4)
        for col, pref, color in zip(cols, prefs, TOHOKU_COLORS):
            with col:
                fig = px.pie(
                    df_ind, values=pref, names="産業",
                    title=pref,
                    color_discrete_sequence=px.colors.qualitative.Pastel,
                    hole=0.35,
                )
                fig.update_traces(textinfo="percent", showlegend=False)
                fig.update_layout(height=280, margin=dict(t=40, b=10, l=5, r=5))
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.info("""
        **診断士視点のポイント**
        - 秋田は**医療・福祉**の割合が東北最高水準（高齢化の裏返し）
        - **製造業**は岩手（自動車）・山形（半導体）に大差。DX・再エネ分野での新たな製造業集積が課題
        - **農林水産業**は就業者比率が高いが産出額は4県最低。6次産業化と輸出で付加価値向上を
        """)

    # ========== TAB4: 総合評価 ==========
    with tab4:
        df_wl = get_tohoku_winlose()

        st.subheader("秋田県 東北内ランキング（勝ち負けマップ）")
        st.caption("各指標の東北4県中の順位と評価。◯=上位、△=中位、✗=下位")

        # 評価カラー
        eval_colors = {"○": "#c6efce", "△": "#ffe699", "✗": "#ffc7ce"}
        eval_text_colors = {"○": "#276221", "△": "#9c5700", "✗": "#9c0006"}

        # サマリーKPI
        wins = (df_wl["評価"] == "○").sum()
        mid  = (df_wl["評価"] == "△").sum()
        lose = (df_wl["評価"] == "✗").sum()
        col1, col2, col3 = st.columns(3)
        col1.metric("勝ち指標（東北上位）", f"{wins}項目", delta="強みを活かす")
        col2.metric("互角指標", f"{mid}項目", delta="改善余地あり")
        col3.metric("負け指標（東北最低水準）", f"{lose}項目", delta="重点課題", delta_color="inverse")

        st.markdown("---")

        # バブルチャート: 順位 vs 改善余地
        improve_map = {"大": 3, "中": 2, "小": 1}
        df_wl["改善余地_数値"] = df_wl["改善余地"].map(improve_map)
        eval_color_list = [eval_colors.get(e, "#aec7e8") for e in df_wl["評価"]]

        fig = go.Figure()
        for _, row in df_wl.iterrows():
            fig.add_trace(go.Scatter(
                x=[row["東北内順位（4県）"]],
                y=[row["改善余地_数値"]],
                mode="markers+text",
                marker=dict(
                    size=24,
                    color=eval_colors.get(row["評価"], "#aec7e8"),
                    line=dict(width=1.5, color="#555"),
                ),
                text=[row["指標"]],
                textposition="top center",
                name=row["指標"],
                showlegend=False,
                hovertemplate=(
                    f"<b>{row['指標']}</b><br>"
                    f"秋田の値: {row['秋田の値']}<br>"
                    f"東北内順位: {row['東北内順位（4県）']}位<br>"
                    f"評価: {row['評価']}<br>"
                    f"{row['コメント']}"
                ),
            ))
        fig.update_layout(
            height=440,
            title="順位（横軸: 右ほど下位）× 改善余地（縦軸: 上ほど大）",
            xaxis=dict(tickvals=[1, 2, 3, 4], ticktext=["1位（最良）", "2位", "3位", "4位（最下位）"],
                       title="東北4県内順位"),
            yaxis=dict(tickvals=[1, 2, 3], ticktext=["小", "中", "大"], title="改善余地"),
            annotations=[
                dict(x=1.3, y=3.2, text="優先投資ゾーン", showarrow=False,
                     font=dict(color="red", size=11)),
                dict(x=1.3, y=0.8, text="現状維持ゾーン", showarrow=False,
                     font=dict(color="green", size=11)),
            ],
        )
        st.plotly_chart(fig, use_container_width=True)

        # 凡例
        col1, col2, col3 = st.columns(3)
        with col1:
            st.success("🟢 ◯: 東北内上位（強みとして活用）")
        with col2:
            st.warning("🟡 △: 東北内中位（改善余地あり）")
        with col3:
            st.error("🔴 ✗: 東北内最低水準（重点課題）")

        # 詳細テーブル
        st.markdown("---")
        st.subheader("指標別詳細データ")

        def color_eval(val):
            bg = eval_colors.get(val, "")
            tc = eval_text_colors.get(val, "")
            return f"background-color:{bg};color:{tc}" if bg else ""

        def color_rank(val):
            if val == 1:
                return "background-color:#c6efce"
            elif val == 4:
                return "background-color:#ffc7ce"
            return ""

        styled = (
            df_wl[["指標", "秋田の値", "東北内順位（4県）", "評価", "改善余地", "コメント"]]
            .style
            .map(color_eval, subset=["評価"])
            .map(color_rank, subset=["東北内順位（4県）"])
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("診断士としての戦略示唆")
        col1, col2 = st.columns(2)
        with col1:
            st.success("""
**守り（強みの活用）**
- 完全失業率の低さ → 雇用安定を移住促進の訴求軸に
- 有効求人倍率 → 多様な就業機会を若者にアピール
- 農業産出 → あきたこまちブランドでの輸出拡大
            """)
        with col2:
            st.error("""
**攻め（弱点の克服）**
- 製造品出荷額 → DX・再エネ関連製造業の誘致・育成
- 合計特殊出生率 → 子育て支援の抜本強化・移住促進
- 観光入込客数 → インバウンド対応・体験型コンテンツ整備
            """)

        # CSVエクスポート
        csv = df_wl.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("📥 評価データCSVダウンロード", csv, "tohoku_comparison.csv", "text/csv")


# ============================================================
# e-Stat API連携ページ
# ============================================================
def page_estat():
    st.title("🔌 e-Stat API連携")
    st.caption("政府統計の総合窓口（e-Stat）から実データをリアルタイムに取得・分析する")
    st.markdown("---")

    tab2, tab3, tab4 = st.tabs([
        "🔍 統計検索",
        "📥 データ取得",
        "📋 統計IDカタログ",
    ])

    # ========== TAB: 統計検索 ==========
    with tab2:
        st.subheader("統計表を検索する")
        st.markdown("キーワードで e-Stat の統計表データベースを検索し、統計表IDを調べることができます。")

        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            keyword = st.text_input(
                "検索キーワード",
                placeholder="例: 人口 秋田 / 賃金 製造業 / 商業統計",
            )
        with col2:
            field_label = st.selectbox(
                "統計分野",
                options=list(estat_api.STATS_FIELD_OPTIONS.keys()),
            )
        with col3:
            st.markdown("　")
            search_btn = st.button("🔍 検索", use_container_width=True)

        if search_btn:
            if not keyword:
                st.warning("キーワードを入力してください。")
            elif not estat_api.is_api_key_set():
                st.error("APIキーが設定されていません。サーバーの環境変数 ESTAT_API_KEY を確認してください。")
            else:
                field_code = estat_api.STATS_FIELD_OPTIONS[field_label]
                with st.spinner(f"「{keyword}」を検索中..."):
                    try:
                        df_result = estat_api.search_statistics(keyword, field_code, limit=50)
                        st.session_state["search_result"] = df_result
                        st.session_state["search_keyword"] = keyword
                    except Exception as e:
                        st.error(f"検索エラー: {e}")

        if "search_result" in st.session_state:
            df_r = st.session_state["search_result"]
            kw = st.session_state.get("search_keyword", "")
            st.markdown(f"**「{kw}」の検索結果: {len(df_r)} 件**")

            if df_r.empty:
                st.info("該当する統計表が見つかりませんでした。キーワードを変えて試してください。")
            else:
                st.dataframe(df_r, use_container_width=True, height=350)

                st.markdown("---")
                st.markdown("##### 統計表IDを「データ取得」タブで使う")
                selected_id = st.selectbox(
                    "データ取得したい統計表IDを選択",
                    options=df_r["統計表ID"].tolist(),
                    format_func=lambda x: f"{x} — {df_r[df_r['統計表ID']==x]['表題'].values[0][:40]}…"
                    if x in df_r["統計表ID"].values else x,
                )
                if st.button("📥 このIDでデータ取得 →"):
                    st.session_state["fetch_stats_id"] = selected_id
                    st.info(f"統計表ID `{selected_id}` を「データ取得」タブにセットしました。タブを切り替えてください。")

    # ========== TAB: データ取得 ==========
    with tab3:
        st.subheader("統計データをリアルタイムに取得する")

        col1, col2 = st.columns([2, 1])
        with col1:
            # カタログから選ぶ or 直接入力
            input_mode = st.radio(
                "統計表の指定方法",
                ["カタログから選ぶ", "統計表IDを直接入力"],
                horizontal=True,
            )

            if input_mode == "カタログから選ぶ":
                catalog_key = st.selectbox(
                    "統計表",
                    options=list(estat_api.STAT_CATALOG.keys()),
                )
                stats_id = estat_api.STAT_CATALOG[catalog_key]["id"]
                st.caption(estat_api.STAT_CATALOG[catalog_key]["description"])
                st.code(f"統計表ID: {stats_id}", language=None)
            else:
                default_id = st.session_state.get("fetch_stats_id", "0003448237")
                stats_id = st.text_input(
                    "統計表ID（10桁）",
                    value=default_id,
                    placeholder="例: 0003448237",
                ).strip()

        with col2:
            area_code = st.text_input(
                "地域コード",
                value=estat_api.AKITA_AREA_CODE,
                help="秋田県=05000、東北全体=0500*、全国=空欄",
            ).strip()
            limit = st.number_input("最大取得件数", min_value=10, max_value=10000, value=500, step=100)

        fetch_btn = st.button("🔄 データを取得する", type="primary", use_container_width=False)

        if fetch_btn:
            if not stats_id:
                st.warning("統計表IDを入力してください。")
            elif not estat_api.is_api_key_set():
                st.error("APIキーが設定されていません。サーバーの環境変数 ESTAT_API_KEY を確認してください。")
            else:
                with st.spinner(f"統計表 `{stats_id}` を取得中..."):
                    try:
                        # メタ情報を先に取得
                        meta_info = estat_api.get_stats_meta(stats_id)
                        df_fetched, class_meta = estat_api.fetch_stats_data(
                            stats_data_id=stats_id,
                            area_code=area_code if area_code else None,
                            limit=int(limit),
                        )
                        st.session_state["fetched_df"] = df_fetched
                        st.session_state["fetched_meta"] = class_meta
                        st.session_state["fetched_meta_info"] = meta_info
                        st.session_state["fetched_stats_id"] = stats_id
                    except Exception as e:
                        st.error(f"取得エラー: {e}")
                        st.session_state.pop("fetched_df", None)

        # 取得結果の表示
        if "fetched_df" in st.session_state:
            df_show = st.session_state["fetched_df"]
            meta_info = st.session_state.get("fetched_meta_info", {})
            class_meta = st.session_state.get("fetched_meta", {})
            fetched_id = st.session_state.get("fetched_stats_id", "")

            st.markdown("---")

            # 統計表情報
            col_a, col_b, col_c, col_d = st.columns(4)
            col_a.metric("統計表ID", fetched_id)
            col_b.metric("調査機関", meta_info.get("gov_org", "—"))
            col_c.metric("調査年月", str(meta_info.get("survey_date", "—")))
            col_d.metric("総レコード数", str(meta_info.get("total_count", "—")))

            st.markdown(f"**{meta_info.get('title', '（タイトル取得中）')}**")

            # データプレビュー
            st.subheader(f"データプレビュー（{len(df_show)} 行取得）")

            if df_show.empty:
                st.warning("データが0件でした。地域コードや統計表IDを確認してください。")
            else:
                # 時系列チャートを試みる（time 列 × value 列があれば）
                if "time" in df_show.columns and "value" in df_show.columns:
                    df_chart = (df_show.dropna(subset=["value"])
                                       .groupby("time")["value"]
                                       .sum()
                                       .reset_index()
                                       .sort_values("time"))
                    if len(df_chart) > 1:
                        fig = px.line(
                            df_chart, x="time", y="value",
                            markers=True,
                            title=f"{meta_info.get('title', '')} — 時系列（秋田県）",
                            color_discrete_sequence=["#1f4e79"],
                        )
                        fig.update_layout(height=320, xaxis_title="時点", yaxis_title="値")
                        st.plotly_chart(fig, use_container_width=True)

                # カテゴリ列をラベルに変換して表示
                df_display = df_show.copy()
                for col in df_display.columns:
                    if col in class_meta:
                        df_display[col] = df_display[col].map(
                            class_meta[col]
                        ).fillna(df_display[col])

                st.dataframe(df_display, use_container_width=True, height=320)

                # CSVダウンロード
                csv = df_display.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    "📥 CSVダウンロード",
                    csv,
                    f"estat_{fetched_id}.csv",
                    "text/csv",
                )

                # カテゴリ定義を展開表示
                if class_meta:
                    with st.expander("📖 カテゴリ定義（CLASS_INF）"):
                        for obj_id, mapping in class_meta.items():
                            st.markdown(f"**{obj_id}**")
                            df_cls = pd.DataFrame(
                                list(mapping.items()), columns=["コード", "名称"]
                            )
                            st.dataframe(df_cls, use_container_width=True, hide_index=True, height=200)

    # ========== TAB: 統計IDカタログ ==========
    with tab4:
        st.subheader("よく使う統計表IDカタログ")
        st.markdown("このダッシュボードに関連する主要統計表の一覧です。統計表IDをコピーして「データ取得」タブで使用できます。")

        for name, info in estat_api.STAT_CATALOG.items():
            cat_icon = {
                "population": "👥",
                "migration": "🚶",
                "industry": "🏭",
                "wage": "💴",
            }.get(info.get("category", ""), "📊")

            with st.container():
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.markdown(f"**{cat_icon} {name}**")
                    st.caption(info["description"])
                with col2:
                    st.markdown(f"分野: `{info['stats_field']}`")
                with col3:
                    st.code(info["id"], language=None)
                    if st.button("取得 →", key=f"cat_{info['id']}"):
                        st.session_state["fetch_stats_id"] = info["id"]
                        st.info(f"ID `{info['id']}` をセットしました。「データ取得」タブへ移動してください。")
                st.markdown("---")

        st.markdown("#### e-Stat 地域コード早見表（秋田県関連）")
        area_data = {
            "地域": ["秋田県（全体）", "秋田市", "横手市", "大仙市", "能代市", "由利本荘市", "大館市", "湯沢市"],
            "e-Stat コード": ["05000", "05201", "05202", "05209", "05203", "05210", "05204", "05206"],
            "備考": ["都道府県", "県庁所在地", "横手盆地", "大曲花火", "木都・能代", "鳥海山麓", "比内鶏", "湯沢雄物川"],
        }
        st.dataframe(pd.DataFrame(area_data), use_container_width=True, hide_index=True)


# ============================================================
# ============================================================
# 地域市場シェア分析ページ
# ============================================================
def page_market_share():
    try:
        import folium
        import streamlit.components.v1 as _stc
        _folium_ok = True
    except ImportError:
        _folium_ok = False

    import jstat_api

    st.title("📈 地域市場シェア分析")
    st.caption("家計調査（総務省）の1世帯年間支出 × 商圏世帯数で市場規模を推計し、自社売上からシェアを算出します")
    st.warning(
        "⚠️ **データに関する重要な注意事項**\n\n"
        "- **1世帯年間支出**: 総務省 家計調査（2023年 二人以上世帯）の全国平均値を使用しています。"
        "東北・秋田の値は **参考推計値** であり、全国統計にない秋田特有品目（いぶりがっこ等）は独自推計です。\n"
        "- **世帯数**: 国勢調査（2020年）の市町村別世帯数を使用しています。最新値は2025年国勢調査後に更新予定です。\n"
        "- 推計市場規模はあくまで参考値です。実際の市場規模とは異なります。"
    )
    st.markdown("---")

    # ── Step 1: 商圏エリア選択 ──
    st.subheader("① 商圏エリアを選択")

    area_mode = st.radio(
        "商圏の決め方",
        ["🏘️ 市町村で選ぶ", "📍 住所と半径で商圏を描く（j-STAT MAP連携）"],
        horizontal=True,
    )

    municipalities = market_data.get_municipalities()
    households = 0
    selected_area = ""

    # ── モード A: 市町村選択 ──────────────────────────────────
    if area_mode == "🏘️ 市町村で選ぶ":
        st.info(
            "市町村を選択して、その市町村全体を商圏として市場規模を推計します。"
        )
        col1, col2 = st.columns([2, 2])
        with col1:
            selected_area = st.selectbox("市町村", municipalities, index=0)
        with col2:
            households = market_data.get_households(selected_area)
            st.metric("世帯数（令和2年国勢調査）", f"{households:,} 世帯")

    # ── モード B: 住所＋半径（j-STAT MAP連携）────────────────
    else:
        st.info(
            "**j-STAT MAP連携モード** — 住所を入力して半径を設定すると、"
            "国勢調査データから商圏内の推計世帯数を算出します。"
            "地図上に商圏円と市町村の重なりが表示されます。\n\n"
            "住所例: `秋田市大町3丁目` / `横手市前郷` / `大館市有浦`"
        )

        col1, col2 = st.columns([3, 1])
        with col1:
            address_input = st.text_input(
                "店舗・事業所の住所（秋田県内）",
                placeholder="例: 秋田市大町3丁目",
                help="「秋田県」は省略できます。国土地理院 Geocoding API で座標に変換します。",
            )
        with col2:
            radius_options = {
                "500m": 0.5, "1km": 1.0, "2km": 2.0,
                "3km": 3.0, "5km": 5.0, "10km": 10.0,
            }
            radius_label = st.selectbox("商圏半径", list(radius_options.keys()), index=2)
            radius_km = radius_options[radius_label]

        geocoded = False
        center_lat, center_lon = jstat_api.get_akita_center()
        areas_in_radius: list = []

        if address_input:
            with st.spinner("住所を検索中...（国土地理院 Geocoding API）"):
                result = jstat_api.geocode_gsi(address_input)

            if result:
                center_lat, center_lon = result
                geocoded = True
                st.success(f"📍 座標取得: 緯度 {center_lat:.4f}°N / 経度 {center_lon:.4f}°E")
            else:
                st.warning("住所が見つかりませんでした。より具体的な住所を入力してください。")

        # 住所未入力時は案内を表示して終了
        if not address_input:
            st.info("👆 上の住所欄に店舗・事業所の住所を入力すると、商圏地図と推計世帯数が表示されます。")
            households = 0
            selected_area = "（住所未入力）"
        else:
            # 世帯数推計
            hh_dict = {k: market_data.get_households(k)
                       for k in market_data.get_municipalities()
                       if k != "秋田県全体"}

            total_hh, areas_in_radius = jstat_api.estimate_market_area(
                center_lat, center_lon, radius_km, hh_dict
            )
            households = total_hh
            selected_area = f"{address_input} 半径{radius_label}"

            # ── Folium 地図 ──
            if _folium_ok and geocoded:
                try:
                    m = folium.Map(
                        location=[center_lat, center_lon],
                        zoom_start=11 if radius_km <= 2 else 9,
                        tiles="OpenStreetMap",
                    )
                    folium.Circle(
                        location=[center_lat, center_lon],
                        radius=radius_km * 1000,
                        color="#1f4e79",
                        fill=True,
                        fill_opacity=0.12,
                        weight=2,
                        tooltip=f"商圏半径 {radius_label}",
                    ).add_to(m)
                    folium.CircleMarker(
                        location=[center_lat, center_lon],
                        radius=10,
                        color="red",
                        fill=True,
                        fill_color="red",
                        fill_opacity=0.9,
                        tooltip=address_input,
                    ).add_to(m)
                    for area in areas_in_radius:
                        ratio = area["included_ratio"]
                        color = "green" if ratio >= 50 else "orange" if ratio >= 15 else "gray"
                        tooltip_text = (
                            f"{area['area_name']} | "
                            f"距離 {area['distance_km']}km | "
                            f"推計 {area['estimated_households']:,}世帯 | "
                            f"包含率 {area['included_ratio']}%"
                        )
                        folium.CircleMarker(
                            location=[area["lat"], area["lon"]],
                            radius=8,
                            color=color,
                            fill=True,
                            fill_opacity=0.8,
                            tooltip=tooltip_text,
                        ).add_to(m)
                    map_html = m._repr_html_()
                    st.components.v1.html(map_html, width=720, height=440)
                    leg1, leg2, leg3 = st.columns(3)
                    leg1.success("🟢 包含率 50%以上")
                    leg2.warning("🟠 包含率 15〜50%")
                    leg3.info("⚫ 包含率 15%未満")
                except Exception as e:
                    st.warning(f"地図の表示中にエラーが発生しました: {e}")

        # 商圏内訳テーブル
        if areas_in_radius:
            st.markdown("#### 商圏内 市町村別 推計世帯数")
            df_areas = pd.DataFrame(areas_in_radius)[
                ["area_name", "distance_km", "estimated_households", "included_ratio"]
            ].rename(columns={
                "area_name": "市町村",
                "distance_km": "中心からの距離(km)",
                "estimated_households": "推計世帯数",
                "included_ratio": "包含率(%)",
            })
            st.dataframe(df_areas, use_container_width=True, hide_index=True)

        col1, col2 = st.columns(2)
        col1.metric(
            f"商圏内 推計世帯数（半径{radius_label}）",
            f"{households:,} 世帯",
            help="面積密度法による推計。実際の世帯数とは異なります。",
        )
        col2.metric(
            "含まれる市町村数",
            f"{len(areas_in_radius)} 市町村",
        )

        st.caption(
            "📊 **データ出典**: 世帯数 = 総務省 令和2年国勢調査 / "
            "座標 = 国土地理院 基盤地図情報 / "
            "j-STAT MAP（https://jstatmap.e-stat.go.jp/）と同一の国勢調査データを使用"
        )

    st.markdown("---")

    # ── Step 2: 品目選択 ──
    st.subheader("② 品目を選択")
    col1, col2 = st.columns(2)
    with col1:
        categories = market_data.get_categories()
        selected_cat = st.selectbox("カテゴリ", categories)
    with col2:
        items = market_data.get_items(selected_cat)
        selected_item = st.selectbox("品目", items)

    exp_data = market_data.get_expenditure(selected_cat, selected_item)
    if exp_data:
        st.caption(f"📋 {exp_data.get('説明', '')}")
        c1, c2, c3 = st.columns(3)
        c1.metric("全国平均（1世帯/年）", f"¥{exp_data['全国']:,}")
        c2.metric("東北平均（1世帯/年）", f"¥{exp_data['東北']:,}")
        c3.metric("秋田推計（1世帯/年）", f"¥{exp_data['秋田']:,}")

    st.markdown("---")

    # ── Step 3: 自社売上入力 ──
    st.subheader("③ 自社の年間売上を入力")
    col1, col2 = st.columns([2, 2])
    with col1:
        own_sales_man = st.number_input(
            "年間売上（万円）",
            min_value=0,
            max_value=100000,
            value=0,
            step=100,
            help="自社（または店舗・事業所）の当該品目の年間売上を入力してください",
        )
    own_sales = own_sales_man * 10000

    st.markdown("---")

    # ── 結果表示 ──
    st.subheader("④ 推計市場シェア")

    if not exp_data:
        st.warning("品目データが見つかりません。")
        return

    # 秋田推計値で市場規模計算
    market_size = market_data.calc_market_size(exp_data["秋田"], households)
    market_size_zenkoku = market_data.calc_market_size(exp_data["全国"], households)
    share = market_data.calc_share(own_sales, market_size) if own_sales > 0 else 0.0

    # KPI表示
    k1, k2, k3 = st.columns(3)
    k1.metric(
        f"推計市場規模（{selected_area}）",
        f"¥{market_size/10000:,.0f}万円",
        help="秋田推計単価 × 世帯数",
    )
    k2.metric(
        "自社年間売上",
        f"¥{own_sales/10000:,.0f}万円" if own_sales > 0 else "未入力",
    )
    k3.metric(
        "推計シェア",
        f"{share:.2f}%" if own_sales > 0 else "—",
        help="自社売上 ÷ 推計市場規模",
    )

    # ゲージチャート
    if own_sales > 0:
        gauge_max = max(100, share * 2)
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=share,
            number={"suffix": "%", "font": {"size": 36}},
            delta={"reference": 10, "increasing": {"color": "#2ca02c"}, "suffix": "%"},
            gauge={
                "axis": {"range": [0, gauge_max], "ticksuffix": "%"},
                "bar": {"color": "#1f4e79"},
                "steps": [
                    {"range": [0, gauge_max * 0.1], "color": "#ffe0e0"},
                    {"range": [gauge_max * 0.1, gauge_max * 0.3], "color": "#fff0cc"},
                    {"range": [gauge_max * 0.3, gauge_max], "color": "#e0ffe0"},
                ],
                "threshold": {
                    "line": {"color": "red", "width": 3},
                    "thickness": 0.75,
                    "value": 10,
                },
            },
            title={"text": f"推計市場シェア<br><sub>{selected_area}・{selected_item}</sub>"},
        ))
        fig_gauge.update_layout(height=280, margin=dict(t=60, b=20, l=40, r=40))
        st.plotly_chart(fig_gauge, use_container_width=True)

        # シェア評価コメント
        if share >= 30:
            st.success(f"🏆 推計シェア **{share:.1f}%** — 当該商圏で非常に高いシェアです。競合動向の継続監視を。")
        elif share >= 10:
            st.info(f"✅ 推計シェア **{share:.1f}%** — 商圏内で一定の存在感があります。さらなる深耕余地があります。")
        elif share >= 3:
            st.warning(f"📌 推計シェア **{share:.1f}%** — まだ伸びしろがあります。認知拡大・リピート促進が有効です。")
        else:
            st.error(f"⚠️ 推計シェア **{share:.1f}%** — シェアが低い状態です。ターゲット絞り込みや差別化を検討しましょう。")

    st.markdown("---")

    # ── 全国・東北・秋田 市場規模比較 ──
    st.subheader("市場規模の参考比較（1世帯年間支出）")
    ref_data = {
        "エリア": ["全国（平均）", "東北（参考）", "秋田（推計）"],
        "1世帯年間支出（円）": [exp_data["全国"], exp_data["東北"], exp_data["秋田"]],
    }
    fig_bar = px.bar(
        pd.DataFrame(ref_data),
        x="エリア", y="1世帯年間支出（円）",
        color="エリア",
        color_discrete_sequence=["#aec7e8", "#ff9896", "#1f4e79"],
        text_auto=True,
        title=f"{selected_item} の1世帯年間支出比較",
    )
    fig_bar.update_traces(texttemplate="¥%{y:,.0f}", textposition="outside")
    fig_bar.update_layout(height=320, showlegend=False, yaxis_tickprefix="¥", yaxis_tickformat=",")
    st.plotly_chart(fig_bar, use_container_width=True)

    # ── 購入額の年次推移 ──
    st.markdown("---")
    st.subheader("購入額の推移（全国 2019〜2023年）")

    # 品目名の表記ゆれ対応
    trend_key = selected_item
    # カッコ・再掲を除いた名前でも試す
    trend_key_clean = selected_item.replace("（再掲）", "").strip()
    trend = market_data.get_trend(trend_key) or market_data.get_trend(trend_key_clean)

    if trend:
        df_trend = pd.DataFrame(trend)
        fig_trend = px.line(
            df_trend, x="年", y="支出（円）",
            markers=True,
            title=f"{selected_item} — 1世帯年間支出の推移（全国平均）",
            color_discrete_sequence=["#1f4e79"],
        )
        fig_trend.update_traces(line_width=3, marker_size=8)
        fig_trend.update_layout(
            height=320,
            yaxis_tickprefix="¥", yaxis_tickformat=",",
            xaxis=dict(tickmode="array", tickvals=trend["年"]),
        )
        # コロナ影響を注記
        fig_trend.add_vline(x=2020, line_dash="dash", line_color="gray",
                            annotation_text="コロナ禍", annotation_position="top right")
        st.plotly_chart(fig_trend, use_container_width=True)

        # 変化率
        vals = trend["支出（円）"]
        chg_5yr = (vals[-1] - vals[0]) / vals[0] * 100
        chg_1yr = (vals[-1] - vals[-2]) / vals[-2] * 100
        t1, t2 = st.columns(2)
        t1.metric("5年間変化率（2019→2023）", f"{chg_5yr:+.1f}%")
        t2.metric("前年比（2022→2023）", f"{chg_1yr:+.1f}%")
        st.caption("出典: 総務省 家計調査（二人以上の世帯）。数値は参考値です。")
    else:
        st.info("この品目の年次推移データは準備中です。")

    # ── 複数商圏の比較 ──
    st.markdown("---")
    st.subheader("複数商圏の市場規模比較")
    compare_areas = st.multiselect(
        "比較する市町村を選択（複数可）",
        municipalities,
        default=["秋田市", "横手市", "大仙市", "由利本荘市"],
    )
    if compare_areas:
        comp_data = []
        for area in compare_areas:
            hh = market_data.get_households(area)
            ms = market_data.calc_market_size(exp_data["秋田"], hh)
            comp_data.append({"市町村": area, "推計市場規模（万円）": ms // 10000, "世帯数": hh})
        df_comp = pd.DataFrame(comp_data).sort_values("推計市場規模（万円）", ascending=False)
        fig_comp = px.bar(
            df_comp, x="市町村", y="推計市場規模（万円）",
            text_auto=True,
            color="推計市場規模（万円）",
            color_continuous_scale="Blues",
            title=f"{selected_item} の推計市場規模比較（万円）",
        )
        fig_comp.update_traces(texttemplate="%{y:,}万円", textposition="outside")
        fig_comp.update_layout(height=360, coloraxis_showscale=False,
                               yaxis_ticksuffix="万円", yaxis_tickformat=",")
        st.plotly_chart(fig_comp, use_container_width=True)

    st.markdown("---")
    st.caption(
        "**免責事項**: 本ページの市場規模推計は、総務省家計調査の全国平均値を参考に算出した推計値です。"
        "実際の市場規模・シェアとは異なります。経営判断にあたっては必ず一次情報をご確認ください。"
    )


# ============================================================
# 業種別生産性分析ページ
# ============================================================
def page_industry_census():
    st.title("📊 業種別生産性分析")
    st.caption("令和3年経済センサス-活動調査に基づく秋田県の業種別労働生産性と事業所規模分布")
    st.markdown("---")

    if estat_api.is_api_key_set():
        st.info("掲載データは令和3年経済センサス-活動調査（経済産業省・総務省、2021年）の秋田県実績値です。")
    else:
        st.info("掲載データは令和3年経済センサス-活動調査（経済産業省）に基づく秋田県の推計値です。APIキーを設定すると実データを取得できます。")

    tab1, tab2 = st.tabs(["💡 一人当たり労働生産性", "📊 従業者規模別分布"])

    with tab1:
        df_prod = estat_api.fetch_census_productivity()

        if df_prod.empty:
            st.warning("データを取得できませんでした。")
        else:
            df_sorted = df_prod.sort_values("一人当たり生産性_万円", ascending=True).reset_index(drop=True)

            avg_productivity = int(df_sorted["一人当たり生産性_万円"].mean())

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_sorted["一人当たり生産性_万円"],
                y=df_sorted["業種"],
                orientation="h",
                marker_color="#1f4e79",
                text=df_sorted["一人当たり生産性_万円"].apply(lambda v: f"{v:,}万円"),
                textposition="outside",
            ))
            fig.add_vline(
                x=avg_productivity,
                line_dash="dash",
                line_color="#d62728",
                annotation_text=f"秋田平均: {avg_productivity:,}万円",
                annotation_position="top right",
                annotation_font_color="#d62728",
            )
            fig.update_layout(
                height=450,
                xaxis_title="一人当たり労働生産性（万円/人）",
                yaxis_title="",
                margin=dict(l=10, r=80, t=30, b=40),
                plot_bgcolor="white",
                xaxis=dict(gridcolor="#e0e0e0"),
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "**指標の定義**: 一人当たり労働生産性 ＝ 付加価値額 ÷ 従業員数（単位: 万円/人）。"
                "付加価値額は売上高から外部購入費（原材料・仕入費等）を差し引いた値。"
                "**出典**: 令和3年経済センサス-活動調査（経済産業省）"
            )

            st.markdown("---")
            st.subheader("業種別データ一覧")
            df_display = df_sorted[["業種", "一人当たり生産性_万円", "付加価値額_百万円", "従業員数"]].sort_values(
                "一人当たり生産性_万円", ascending=False
            ).reset_index(drop=True)
            df_display.index = df_display.index + 1
            st.dataframe(
                df_display.rename(columns={
                    "一人当たり生産性_万円": "労働生産性（万円/人）",
                    "付加価値額_百万円": "付加価値額（百万円）",
                }),
                use_container_width=True,
            )

    with tab2:
        selected_industry = st.selectbox(
            "業種を選択（大分類）",
            estat_api.CENSUS_DAIBUNSHU_LIST,
            key="census_size_industry",
        )

        df_size = estat_api.fetch_census_size_distribution(selected_industry)

        if df_size.empty:
            st.warning("データを取得できませんでした。")
        else:
            total_establishments = df_size["事業所数"].sum()
            df_size["累積割合_%"] = (df_size["事業所数"].cumsum() / total_establishments * 100).round(1)

            fig = make_subplots(specs=[[{"secondary_y": True}]])

            fig.add_trace(
                go.Bar(
                    x=df_size["規模区分"],
                    y=df_size["事業所数"],
                    name="事業所数",
                    marker_color="#1f4e79",
                    text=df_size["事業所数"],
                    textposition="outside",
                ),
                secondary_y=False,
            )
            fig.add_trace(
                go.Scatter(
                    x=df_size["規模区分"],
                    y=df_size["累積割合_%"],
                    name="累積割合（%）",
                    mode="lines+markers",
                    line=dict(color="#d62728", width=2),
                    marker=dict(size=7),
                ),
                secondary_y=True,
            )
            fig.update_layout(
                height=420,
                title_text=f"{selected_industry} — 従業者規模別事業所数",
                plot_bgcolor="white",
                xaxis=dict(title="従業者規模", gridcolor="#e0e0e0"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=60, b=40),
            )
            fig.update_yaxes(
                title_text="事業所数（所）", secondary_y=False,
                gridcolor="#e0e0e0", range=[0, total_establishments * 1.05],
            )
            fig.update_yaxes(title_text="累積割合（%）", secondary_y=True, range=[0, 105])

            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                f"**{selected_industry}** の従業者規模別事業所分布。"
                f"合計 {total_establishments:,} 事業所。"
                "棒グラフ（左軸）は各規模区分の事業所数、折れ線グラフ（右軸）は累積割合を示す。"
                "**出典**: 令和3年経済センサス-活動調査（経済産業省）"
            )

            col1, col2 = st.columns(2)
            with col1:
                small_count = df_size[df_size["規模区分"].isin(["1-4人", "5-9人", "10-19人"])]["事業所数"].sum()
                small_pct = round(small_count / total_establishments * 100, 1) if total_establishments > 0 else 0
                st.metric("小規模事業所（1-19人）", f"{small_count:,}所", f"全体の{small_pct}%")
            with col2:
                large_count = df_size[df_size["規模区分"].isin(["100-299人", "300人以上"])]["事業所数"].sum()
                large_pct = round(large_count / total_establishments * 100, 1) if total_establishments > 0 else 0
                st.metric("大規模事業所（100人以上）", f"{large_count:,}所", f"全体の{large_pct}%")


# ============================================================
# 産業×市町村マトリックスページ
# ============================================================
def page_industry_matrix():
    st.title("🗺️ 産業×市町村マトリックス")
    st.caption("令和3年経済センサス-活動調査に基づく産業大分類別・市町村別の事業所数")
    st.markdown("---")

    with st.spinner("データを読み込み中..."):
        df_pivot, source_note = _load_industry_matrix()

    st.caption(source_note)

    if df_pivot.empty:
        if source_note == "no_key":
            st.info(
                "データを表示するには e-Stat APIキーの設定が必要です。\n\n"
                "「🔌 e-Stat API連携」ページでAPIキーを入力してください。"
            )
        else:
            st.warning("e-Stat APIからデータを取得できませんでした。しばらく待ってから再度お試しください。")
        return

    def _to_int(v):
        try:
            return int(v)
        except Exception:
            return 0

    # ---- スライサー ----
    all_industries  = list(df_pivot.index)
    all_cities      = list(df_pivot.columns)

    with st.expander("🔍 絞り込み（スライサー）", expanded=False):
        sel_cities = st.multiselect(
            "市町村を選択（空欄 = すべて）",
            options=all_cities,
            default=[],
            placeholder="すべての市町村を表示中",
        )
        sel_industries = st.multiselect(
            "業種を選択（空欄 = すべて）",
            options=all_industries,
            default=[],
            placeholder="すべての業種を表示中",
        )

    # フィルター適用
    row_sel = sel_industries if sel_industries else all_industries
    col_sel = sel_cities    if sel_cities    else all_cities
    df_base = df_pivot.loc[row_sel, col_sel].copy()

    # ---- 合計列・合計行を付加 ----
    df_base["合計"] = df_base.apply(lambda row: sum(_to_int(v) for v in row), axis=1)
    col_sums = {col: df_base[col].apply(_to_int).sum() for col in df_base.columns}
    total_row = pd.DataFrame([col_sums], index=["合計"])
    df_display = pd.concat([df_base, total_row])

    grand_total = int(col_sums["合計"])

    # ---- メトリクス ----
    m1, m2, m3 = st.columns(3)
    m1.metric("表示対象 総事業所数", f"{grand_total:,} 所")
    m2.metric("表示業種数", f"{len(row_sel)} 業種")
    m3.metric("表示市町村数", f"{len(col_sel)} 市町村")

    st.markdown("---")
    st.markdown("#### 産業大分類 × 市町村 事業所数マトリックス")

    tab_count, tab_pct, tab_heat = st.tabs(["📊 事業所数（実数）", "📈 構成比（%）", "🔥 ヒートマップ"])

    # ---- スタイル関数 ----
    def _style_count_row(row):
        if row.name == "合計":
            return ["font-weight: bold; background-color: #e8f0fe;" for _ in row]
        return ["" for _ in row]

    def _style_count_cell(val):
        if val == "-":
            return "color: #aaaaaa; background-color: #f5f5f5;"
        return ""

    # ---- タブ①：実数 ----
    with tab_count:
        styled_count = (
            df_display.style
            .apply(_style_count_row, axis=1)
            .map(_style_count_cell)
            .format(lambda v: v if isinstance(v, str) else f"{v:,}")
            .set_table_styles([
                {"selector": "th", "props": [("font-size", "11px"), ("white-space", "nowrap")]},
                {"selector": "td", "props": [("font-size", "11px"), ("text-align", "right")]},
            ])
        )
        st.dataframe(styled_count, use_container_width=True, height=min(50 + len(df_display) * 35, 700))
        st.caption("「-」は秘匿処理または事業所なし　※農林漁業は農林業センサスベースのため除外")

    # ---- タブ②：構成比 ----
    with tab_pct:
        pct_mode = st.radio(
            "割合の基準",
            ["全体（県全体合計を分母）", "行（業種）合計を分母", "列（市町村）合計を分母"],
            horizontal=True,
            label_visibility="collapsed",
        )

        # 数値マトリックスを作成（"-" → 0）
        df_num = df_display.apply(lambda col: col.map(_to_int))

        if pct_mode == "全体（県全体合計を分母）":
            denom = grand_total if grand_total > 0 else 1
            df_pct = df_num / denom * 100
        elif pct_mode == "行（業種）合計を分母":
            row_totals = df_num["合計"].replace(0, 1)
            df_pct = df_num.div(row_totals, axis=0) * 100
        else:  # 列（市町村）合計
            col_totals = df_num.loc["合計"].replace(0, 1)
            df_pct = df_num.div(col_totals, axis=1) * 100

        def _fmt_pct(v):
            if v == 0:
                return "-"
            return f"{v:.1f}%"

        def _style_pct_row(row):
            if row.name == "合計":
                return ["font-weight: bold; background-color: #e8f0fe;" for _ in row]
            return ["" for _ in row]

        def _style_pct_cell(val):
            if val == "-":
                return "color: #aaaaaa; background-color: #f5f5f5;"
            try:
                f = float(str(val).replace("%", ""))
                if f >= 20:
                    return "background-color: #1f4e79; color: white;"
                elif f >= 10:
                    return "background-color: #2e75b6; color: white;"
                elif f >= 5:
                    return "background-color: #9dc3e6;"
                elif f >= 1:
                    return "background-color: #deeaf1;"
            except Exception:
                pass
            return ""

        styled_pct = (
            df_pct.style
            .apply(_style_pct_row, axis=1)
            .map(_style_pct_cell)
            .format(_fmt_pct)
            .set_table_styles([
                {"selector": "th", "props": [("font-size", "11px"), ("white-space", "nowrap")]},
                {"selector": "td", "props": [("font-size", "11px"), ("text-align", "right")]},
            ])
        )
        st.dataframe(styled_pct, use_container_width=True, height=min(50 + len(df_display) * 35, 700))
        st.caption("色が濃いほど割合が高い（濃青≥20%、青≥10%、水色≥5%、薄水色≥1%）")

    # ---- タブ③：ヒートマップ ----
    with tab_heat:
        heat_col1, heat_col2, heat_col3 = st.columns(3)
        with heat_col1:
            heat_norm = st.selectbox(
                "表示方法",
                ["事業所数（実数）", "市町村内構成比（%）", "業種内シェア（%）"],
                key="heat_norm",
            )
        with heat_col2:
            heat_color = st.selectbox(
                "カラースケール",
                ["Blues", "YlOrRd", "Viridis", "RdYlGn"],
                key="heat_color",
            )
        with heat_col3:
            heat_annot = st.checkbox("数値を表示", value=True, key="heat_annot")

        # ヒートマップ用数値マトリックス（合計行・合計列を除く）
        # "-"（秘匿値）→ 0 に変換後、object 型が残らないよう int64 に明示キャスト
        df_heat_base = df_pivot.loc[row_sel, col_sel].copy()
        df_heat_num = df_heat_base.apply(lambda col: col.map(_to_int)).astype("int64")

        if heat_norm == "市町村内構成比（%）":
            col_totals_h = df_heat_num.sum(axis=0).replace(0, 1)
            df_heat_val = (df_heat_num.div(col_totals_h, axis=1) * 100).round(1)
            heat_label = "構成比（%）"
            heat_fmt = ".1f"
        elif heat_norm == "業種内シェア（%）":
            row_totals_h = df_heat_num.sum(axis=1).replace(0, 1)
            df_heat_val = (df_heat_num.div(row_totals_h, axis=0) * 100).round(1)
            heat_label = "業種内シェア（%）"
            heat_fmt = ".1f"
        else:
            df_heat_val = df_heat_num
            heat_label = "事業所数（所）"
            heat_fmt = "d"

        fig_heat = px.imshow(
            df_heat_val,
            color_continuous_scale=heat_color,
            aspect="auto",
            text_auto=heat_fmt if heat_annot else False,
            labels={"color": heat_label, "x": "市町村", "y": "産業大分類"},
            title=f"産業大分類 × 市町村  ―  {heat_label}",
        )
        fig_heat.update_layout(
            height=max(400, len(row_sel) * 30 + 120),
            xaxis_tickangle=-35,
            coloraxis_colorbar=dict(title=heat_label),
            font=dict(size=10),
        )
        fig_heat.update_traces(textfont_size=9)
        st.plotly_chart(fig_heat, use_container_width=True)
        st.caption("💡 セルにカーソルを当てると詳細値が表示されます。マウスドラッグでズーム可能です。")

    # ---- CSVダウンロード ----
    st.download_button(
        "📥 CSVダウンロード（実数）",
        df_display.to_csv(encoding="utf-8-sig"),
        "industry_municipal_matrix.csv",
        mime="text/csv",
    )

    st.markdown("---")

    # ---- 市区町村別合計棒グラフ（上位10）----
    df_no_total = df_display.drop(index="合計", errors="ignore")
    city_totals: dict[str, int] = {
        col: df_no_total[col].apply(_to_int).sum()
        for col in df_display.columns if col != "合計"
    }
    top_cities = sorted(city_totals.items(), key=lambda x: x[1], reverse=True)[:10]
    if top_cities:
        st.markdown("#### 市区町村別 事業所数（上位10）")
        fig = go.Figure(go.Bar(
            x=[c[0] for c in top_cities],
            y=[c[1] for c in top_cities],
            marker_color="#1f4e79",
            text=[f"{c[1]:,}" for c in top_cities],
            textposition="outside",
        ))
        fig.update_layout(
            height=380,
            xaxis_title="市区町村",
            yaxis_title="事業所数（所）",
            yaxis_tickformat=",",
            margin=dict(t=20, b=60),
        )
        st.plotly_chart(fig, use_container_width=True)


# ============================================================
# 川上・川下フロー分析ページ
# ============================================================

_SUPPLY_CHAIN_DATA: dict = {
    "🌲 木材・林業": {
        "color": "#2d6a4f",
        "layers": [
            {"label": "① 素材生産\n（川上）", "players": [
                {"name": "森林所有者",          "desc": "国有林・私有林・公有林"},
                {"name": "林業家・素材生産業者", "desc": "伐採・造材・集材"},
                {"name": "輸入業者・原木商",     "desc": "外材輸入・原木流通"},
            ]},
            {"label": "② 原木流通", "players": [
                {"name": "木材市場・原木市場",      "desc": "セリ・入札・相対取引"},
                {"name": "素材商・原木仲介業者",    "desc": "原木の卸・仲介"},
                {"name": "輸送・運送業者",          "desc": "山土場→市場→工場"},
            ]},
            {"label": "③ 一次加工", "players": [
                {"name": "製材業者",              "desc": "丸太→板材・角材"},
                {"name": "合板・集成材メーカー",  "desc": "構造用合板・LVL"},
                {"name": "チップ・バイオマス業者", "desc": "木質バイオマス燃料"},
            ]},
            {"label": "④ 二次加工", "players": [
                {"name": "木材製品メーカー",    "desc": "フローリング・パネル"},
                {"name": "家具・建具メーカー",  "desc": "家具・ドア・窓枠"},
            ]},
            {"label": "⑤ 流通", "players": [
                {"name": "木材商社・問屋",          "desc": "卸売・商社"},
                {"name": "建材店・ホームセンター",  "desc": "小売・販売"},
            ]},
            {"label": "⑥ 最終需要\n（川下）", "players": [
                {"name": "建設業・ゼネコン",  "desc": "建築・土木工事"},
                {"name": "住宅メーカー",      "desc": "注文・分譲住宅"},
                {"name": "一般消費者",        "desc": "DIY・インテリア"},
            ]},
        ],
    },
    "🌾 農業・食品加工": {
        "color": "#558b2f",
        "layers": [
            {"label": "① 農業生産\n（川上）", "players": [
                {"name": "農家（個人・法人）",  "desc": "米・野菜・果物・畜産"},
                {"name": "JA（農協）",          "desc": "営農指導・資材供給"},
                {"name": "農業資材業者",        "desc": "肥料・農薬・機械"},
            ]},
            {"label": "② 集荷・選別", "players": [
                {"name": "JA集荷施設・カントリーエレベーター", "desc": "集荷・乾燥・調製・保管"},
                {"name": "農産物卸売市場",      "desc": "セリ・相対取引"},
                {"name": "産直・直売所",        "desc": "道の駅・産直市場"},
            ]},
            {"label": "③ 食品加工", "players": [
                {"name": "食品加工業者",        "desc": "米菓・冷凍食品等"},
                {"name": "漬物・味噌・酒造業者","desc": "発酵食品・日本酒"},
                {"name": "冷凍・冷蔵加工業者",  "desc": "業務用食品加工"},
            ]},
            {"label": "④ 食品流通", "players": [
                {"name": "食品卸売業者",    "desc": "食品商社・問屋"},
                {"name": "物流・配送業者",  "desc": "低温物流・宅配"},
            ]},
            {"label": "⑤ 販売\n（川下）", "players": [
                {"name": "スーパー・量販店",    "desc": "小売・地元産品コーナー"},
                {"name": "飲食店・給食",        "desc": "外食・学校給食"},
                {"name": "EC・通販・輸出",      "desc": "ふるさと納税・海外展開"},
            ]},
        ],
    },
    "🏔️ 観光・宿泊": {
        "color": "#00695c",
        "layers": [
            {"label": "① 観光資源\n（川上）", "players": [
                {"name": "自然資源",            "desc": "山・温泉・雪・ラムサール"},
                {"name": "文化・歴史資産",      "desc": "祭り・伝統工芸・城址"},
                {"name": "農村・食文化",        "desc": "農家体験・きりたんぽ等"},
            ]},
            {"label": "② 体験・コンテンツ", "players": [
                {"name": "体験事業者・ガイド",  "desc": "アウトドア・農業体験"},
                {"name": "祭り・イベント主催",  "desc": "なまはげ・竿燈まつり"},
                {"name": "DMO・観光協会",       "desc": "広域観光マネジメント"},
            ]},
            {"label": "③ 宿泊", "players": [
                {"name": "ホテル・旅館",            "desc": "温泉旅館・シティホテル"},
                {"name": "民宿・民泊・グランピング","desc": "農家民宿・体験型宿泊"},
            ]},
            {"label": "④ 飲食・土産", "players": [
                {"name": "飲食店・居酒屋",      "desc": "郷土料理・地酒"},
                {"name": "土産物店・物産館",    "desc": "空港・道の駅・駅構内"},
            ]},
            {"label": "⑤ 交通・手配\n（川下）", "players": [
                {"name": "航空・新幹線",        "desc": "秋田空港・秋田新幹線"},
                {"name": "バス・タクシー・レンタカー","desc": "二次交通・観光周遊"},
                {"name": "旅行会社・OTA",       "desc": "楽天・じゃらん・HIS"},
            ]},
        ],
    },
    "🪨 砕石・建材": {
        "color": "#4e342e",
        "layers": [
            {"label": "① 採掘\n（川上）", "players": [
                {"name": "採石場・砕石業者",    "desc": "山岳・岩石採掘"},
                {"name": "砂利採取業者",        "desc": "河川・海浜砂利採取"},
                {"name": "砂採取業者",          "desc": "河砂・山砂採取"},
            ]},
            {"label": "② 一次製造", "players": [
                {"name": "砕石・砂利製造業者",  "desc": "破砕・篩い分け・粒調整"},
                {"name": "砂製造業者",          "desc": "洗砂・乾燥砂"},
            ]},
            {"label": "③ 二次製造", "players": [
                {"name": "生コンクリート製造業者",    "desc": "レディーミクストコンクリート"},
                {"name": "アスファルト合材製造業者",  "desc": "道路舗装用合材"},
                {"name": "セメント製品製造業者",      "desc": "ブロック・管・パイル"},
            ]},
            {"label": "④ 流通", "players": [
                {"name": "建材卸売業者",    "desc": "建材・資材商社"},
                {"name": "輸送・運送業者",  "desc": "ミキサー車・ダンプ"},
            ]},
            {"label": "⑤ 最終需要\n（川下）", "players": [
                {"name": "建設業・土木業者",    "desc": "一般土木・地盤改良"},
                {"name": "道路舗装業者",        "desc": "国道・県道・農道整備"},
                {"name": "建築業者",            "desc": "住宅・非住宅建築"},
            ]},
        ],
    },
    "🧵 縫製": {
        "color": "#6a1b9a",
        "layers": [
            {"label": "① 素材調達\n（川上）", "players": [
                {"name": "繊維・糸メーカー",    "desc": "綿・ポリ・ウール等"},
                {"name": "生地・織物業者",      "desc": "機屋・ニット・染色"},
                {"name": "副資材業者",          "desc": "ボタン・ファスナー・芯地"},
            ]},
            {"label": "② 企画・デザイン", "players": [
                {"name": "アパレルブランド・企画会社","desc": "MD・企画・デザイン"},
                {"name": "パターンメーカー",    "desc": "型紙作成・グレーディング"},
                {"name": "刺繍・プリント業者",  "desc": "加工・装飾・ネーム"},
            ]},
            {"label": "③ 縫製加工", "players": [
                {"name": "縫製工場（OEM・ODM）","desc": "裁断・縫製・仕上げ"},
                {"name": "検品・品質管理業者",  "desc": "検品・補修・荷造り"},
            ]},
            {"label": "④ 流通", "players": [
                {"name": "アパレル卸売業者",    "desc": "問屋・商社"},
                {"name": "物流・配送業者",      "desc": "アパレル物流センター"},
            ]},
            {"label": "⑤ 販売\n（川下）", "players": [
                {"name": "アパレル小売・百貨店","desc": "専門店・量販店・SC"},
                {"name": "EC・通販",            "desc": "ZOZOTOWN・自社EC"},
                {"name": "法人向け（ユニフォーム）","desc": "作業服・医療・学校"},
            ]},
        ],
    },
    "🚗 自動車": {
        "color": "#1565c0",
        "layers": [
            {"label": "① 製造・輸入\n（川上）", "players": [
                {"name": "自動車メーカー",          "desc": "トヨタ・ホンダ等"},
                {"name": "部品メーカー（Tier1・2）", "desc": "エンジン・電装・内装部品"},
                {"name": "輸入車ディーラー本部",    "desc": "輸入・配分・サポート"},
            ]},
            {"label": "② 新車販売", "players": [
                {"name": "正規ディーラー",  "desc": "新車販売・試乗・商談"},
                {"name": "地域販売店",      "desc": "系列外・独立系"},
            ]},
            {"label": "③ 中古車流通", "players": [
                {"name": "中古車販売店",                    "desc": "買取・販売・展示"},
                {"name": "自動車オークション（USS等）",     "desc": "業者間取引・価格形成"},
            ]},
            {"label": "④ 整備・修理・用品", "players": [
                {"name": "自動車整備業者",      "desc": "車検・定期点検・修理"},
                {"name": "板金・塗装業者",      "desc": "事故修理・外装補修"},
                {"name": "カー用品店・GSS",     "desc": "タイヤ・オイル・用品"},
            ]},
            {"label": "⑤ 解体・リサイクル\n（川下）", "players": [
                {"name": "解体業者・廃車業者",      "desc": "使用済自動車解体処理"},
                {"name": "中古部品販売（ヤード）",  "desc": "リユース部品・輸出"},
                {"name": "自動車リサイクル業者",    "desc": "金属・樹脂・フロン回収"},
            ]},
        ],
    },
    "🐟 水産業": {
        "color": "#0277bd",
        "layers": [
            {"label": "① 漁業・養殖\n（川上）", "players": [
                {"name": "漁業者・漁協",        "desc": "沿岸・沖合・遠洋漁業"},
                {"name": "養殖業者",            "desc": "魚・貝・海藻養殖"},
                {"name": "遊漁船・体験漁業",    "desc": "観光・体験型漁業"},
            ]},
            {"label": "② 水揚げ・集荷", "players": [
                {"name": "漁港・魚市場",        "desc": "セリ・相対取引"},
                {"name": "漁協・産地仲買人",    "desc": "集荷・仕分け・保冷"},
            ]},
            {"label": "③ 水産加工", "players": [
                {"name": "水産加工業者",        "desc": "塩干・燻製・練り製品"},
                {"name": "冷凍・冷蔵加工業者",  "desc": "フィレ・冷凍魚介"},
                {"name": "缶詰・瓶詰業者",      "desc": "水産缶詰・佃煮"},
            ]},
            {"label": "④ 流通", "players": [
                {"name": "水産卸売業者",        "desc": "魚問屋・商社"},
                {"name": "物流・低温配送業者",  "desc": "コールドチェーン"},
            ]},
            {"label": "⑤ 販売\n（川下）", "players": [
                {"name": "スーパー・鮮魚専門店","desc": "小売・対面販売"},
                {"name": "飲食店・料理旅館",    "desc": "外食・宿泊施設"},
                {"name": "EC・通販・輸出",      "desc": "産地直送・海外展開"},
            ]},
        ],
    },
    "🌸 花き（花卉）": {
        "color": "#ad1457",
        "layers": [
            {"label": "① 生産\n（川上）", "players": [
                {"name": "花き農家（個人・法人）","desc": "切り花・鉢物・球根"},
                {"name": "球根・種苗業者",      "desc": "種苗・育苗・資材供給"},
                {"name": "農業資材業者",        "desc": "肥料・農薬・温室設備"},
            ]},
            {"label": "② 集荷・市場", "players": [
                {"name": "花き市場（セリ・相対）","desc": "価格形成・取引"},
                {"name": "花き卸売業者",        "desc": "仕入れ・在庫・品質管理"},
            ]},
            {"label": "③ 加工・アレンジ", "players": [
                {"name": "フラワーデザイナー",  "desc": "アレンジ・ブーケ制作"},
                {"name": "ラッピング・包装業者","desc": "包装資材・ギフト加工"},
            ]},
            {"label": "④ 流通", "players": [
                {"name": "花き専用輸送業者",    "desc": "コールドチェーン・鮮度管理"},
                {"name": "花き問屋",            "desc": "小売店への卸売"},
            ]},
            {"label": "⑤ 販売\n（川下）", "players": [
                {"name": "生花店・フラワーショップ","desc": "小売・対面販売"},
                {"name": "量販店・ホームセンター","desc": "切り花・鉢物販売"},
                {"name": "EC・ブライダル・葬祭","desc": "ギフト・冠婚葬祭需要"},
            ]},
        ],
    },
    "🍶 酒造業": {
        "color": "#4a148c",
        "layers": [
            {"label": "① 原料調達\n（川上）", "players": [
                {"name": "酒米農家・JA",        "desc": "山田錦・秋田酒こまち等"},
                {"name": "麹菌・酵母メーカー",  "desc": "秋田酵母・醸造用微生物"},
                {"name": "水（地下水・湧水）",  "desc": "仕込み水・軟水・硬水"},
            ]},
            {"label": "② 醸造・製造", "players": [
                {"name": "酒蔵（日本酒・焼酎）","desc": "仕込み・発酵・搾り・熟成"},
                {"name": "麹製造業者",          "desc": "米麹・麦麹製造"},
            ]},
            {"label": "③ 瓶詰・包装", "players": [
                {"name": "瓶詰・ラベル業者",    "desc": "充填・ラベル貼り"},
                {"name": "包装・梱包業者",      "desc": "化粧箱・ギフト包装"},
            ]},
            {"label": "④ 流通", "players": [
                {"name": "酒類卸売業者",        "desc": "地酒卸・全国流通"},
                {"name": "物流業者",            "desc": "温度管理・配送"},
            ]},
            {"label": "⑤ 販売\n（川下）", "players": [
                {"name": "酒販店・百貨店",      "desc": "専門店・高級品販売"},
                {"name": "飲食店・居酒屋",      "desc": "地酒メニュー・観光消費"},
                {"name": "EC・蔵元直販",        "desc": "ふるさと納税・海外輸出"},
            ]},
        ],
    },
    "⚙️ 金属・機械加工": {
        "color": "#37474f",
        "layers": [
            {"label": "① 素材調達\n（川上）", "players": [
                {"name": "鉄鋼メーカー・商社",  "desc": "鋼材・鋳物・特殊鋼"},
                {"name": "アルミ・非鉄金属業者","desc": "アルミ・銅・チタン"},
                {"name": "原材料商社",          "desc": "金属素材の輸入・調達"},
            ]},
            {"label": "② 素材加工", "players": [
                {"name": "鋳造・鍛造業者",      "desc": "成形・鋳型・プレス"},
                {"name": "板金・プレス業者",    "desc": "板金加工・プレス成形"},
                {"name": "熱処理業者",          "desc": "焼入れ・焼戻し・浸炭"},
            ]},
            {"label": "③ 機械加工", "players": [
                {"name": "切削・研削加工業者",  "desc": "NC旋盤・マシニング加工"},
                {"name": "溶接・組立業者",      "desc": "溶接・ボルト締結・組立"},
                {"name": "表面処理業者",        "desc": "めっき・塗装・陽極酸化"},
            ]},
            {"label": "④ 検査・流通", "players": [
                {"name": "計測・検査業者",      "desc": "三次元測定・非破壊検査"},
                {"name": "金属製品卸売業者",    "desc": "商社・代理店"},
            ]},
            {"label": "⑤ 最終需要\n（川下）", "players": [
                {"name": "建設・土木業者",      "desc": "橋梁・鉄骨・インフラ"},
                {"name": "自動車・輸送機器メーカー","desc": "部品・ユニット供給"},
                {"name": "産業機械・電機メーカー","desc": "機械部品・装置"},
            ]},
        ],
    },
    "🖨️ 印刷業": {
        "color": "#bf360c",
        "layers": [
            {"label": "① 企画・デザイン\n（川上）", "players": [
                {"name": "クライアント（発注者）","desc": "企業・行政・個人"},
                {"name": "デザイン事務所",      "desc": "グラフィック・DTP"},
                {"name": "広告代理店",          "desc": "広告企画・制作管理"},
            ]},
            {"label": "② 製版・データ処理", "players": [
                {"name": "DTP・データ処理業者", "desc": "組版・色分解・面付け"},
                {"name": "製版業者",            "desc": "刷版・CTP出力"},
            ]},
            {"label": "③ 印刷", "players": [
                {"name": "印刷会社（オフセット）","desc": "商業印刷・出版印刷"},
                {"name": "デジタル印刷業者",    "desc": "オンデマンド・大判印刷"},
                {"name": "特殊印刷業者",        "desc": "シール・パッケージ・箔押し"},
            ]},
            {"label": "④ 加工・製本", "players": [
                {"name": "製本・後加工業者",    "desc": "断裁・折り・綴じ・PP"},
                {"name": "包装・梱包業者",      "desc": "梱包・出荷準備"},
            ]},
            {"label": "⑤ 納品・利用\n（川下）", "players": [
                {"name": "一般企業・官公庁",    "desc": "チラシ・帳票・カタログ"},
                {"name": "出版社・書店",        "desc": "書籍・雑誌・同人誌"},
                {"name": "EC・通販業者",        "desc": "梱包資材・ラベル"},
            ]},
        ],
    },
    "🏗️ 建設業": {
        "color": "#e65100",
        "layers": [
            {"label": "① 発注・企画\n（川上）", "players": [
                {"name": "発注者（行政・民間）", "desc": "公共工事・民間投資"},
                {"name": "建設コンサルタント",  "desc": "調査・計画・設計監理"},
                {"name": "不動産開発業者",      "desc": "宅地・マンション開発"},
            ]},
            {"label": "② 設計", "players": [
                {"name": "設計事務所",          "desc": "基本・実施設計"},
                {"name": "構造・設備設計事務所","desc": "構造・電気・機械設計"},
            ]},
            {"label": "③ 資材調達", "players": [
                {"name": "建材メーカー・商社",  "desc": "鉄骨・コンクリ・木材"},
                {"name": "設備機器メーカー",    "desc": "電気・空調・給排水設備"},
                {"name": "建設機械リース会社",  "desc": "重機・足場・型枠"},
            ]},
            {"label": "④ 施工", "players": [
                {"name": "元請（ゼネコン・工務店）","desc": "総合施工管理"},
                {"name": "専門工事業者",        "desc": "電気・管・鉄筋・左官等"},
                {"name": "下請・孫請業者",      "desc": "各種専門工事"},
            ]},
            {"label": "⑤ 完工・維持管理\n（川下）", "players": [
                {"name": "施主・発注者",        "desc": "引渡し・竣工検査"},
                {"name": "建物管理業者",        "desc": "ビル管理・清掃・保守"},
                {"name": "リフォーム・改修業者","desc": "修繕・耐震・省エネ改修"},
            ]},
        ],
    },
    "♻️ 廃棄物処理・リサイクル": {
        "color": "#2e7d32",
        "layers": [
            {"label": "① 廃棄物発生\n（川上）", "players": [
                {"name": "一般家庭",            "desc": "家庭ごみ・粗大ごみ"},
                {"name": "事業者・工場",        "desc": "産業廃棄物・事業系ごみ"},
                {"name": "建設現場",            "desc": "建設廃材・コンクリ殻"},
            ]},
            {"label": "② 収集・運搬", "players": [
                {"name": "一般廃棄物収集業者",  "desc": "市町村委託・許可業者"},
                {"name": "産業廃棄物収集運搬業者","desc": "マニフェスト管理"},
            ]},
            {"label": "③ 中間処理", "players": [
                {"name": "焼却処理施設",        "desc": "焼却・エネルギー回収"},
                {"name": "破砕・選別業者",      "desc": "資源分別・減容化"},
                {"name": "有機物堆肥化業者",    "desc": "コンポスト・バイオガス"},
            ]},
            {"label": "④ 資源化・リサイクル", "players": [
                {"name": "金属リサイクル業者",  "desc": "鉄・アルミ・銅スクラップ"},
                {"name": "プラスチックリサイクル業者","desc": "再生ペレット・RPF"},
                {"name": "建設廃材リサイクル業者","desc": "再生砕石・再生アスファルト"},
            ]},
            {"label": "⑤ 再利用・最終処分\n（川下）", "players": [
                {"name": "素材メーカー（再生原料）","desc": "再生資源の活用"},
                {"name": "最終処分場（埋立）",  "desc": "安定型・管理型処分場"},
                {"name": "再生品販売業者",      "desc": "リユース品・中古品販売"},
            ]},
        ],
    },
    "📦 物流・倉庫": {
        "color": "#f57f17",
        "layers": [
            {"label": "① 荷主\n（川上）", "players": [
                {"name": "製造業者",            "desc": "完成品・部品の出荷"},
                {"name": "小売・EC事業者",      "desc": "商品の仕入・発送"},
                {"name": "輸出入業者",          "desc": "貿易貨物・通関"},
            ]},
            {"label": "② 幹線輸送", "players": [
                {"name": "トラック輸送業者",    "desc": "長距離・チャーター便"},
                {"name": "鉄道・船舶輸送業者",  "desc": "コンテナ・フェリー"},
                {"name": "航空貨物業者",        "desc": "緊急・高付加価値品"},
            ]},
            {"label": "③ 保管・流通加工", "players": [
                {"name": "倉庫業者",            "desc": "保管・入出庫管理"},
                {"name": "3PL業者",             "desc": "一括物流アウトソーシング"},
                {"name": "流通加工業者",        "desc": "ピッキング・梱包・値付け"},
            ]},
            {"label": "④ ラスト1マイル配送", "players": [
                {"name": "宅配業者",            "desc": "ヤマト・佐川・日本郵便"},
                {"name": "地域配送業者",        "desc": "地場運送・共同配送"},
            ]},
            {"label": "⑤ 荷受人\n（川下）", "players": [
                {"name": "小売店・EC倉庫",      "desc": "店舗受取・センター入荷"},
                {"name": "一般消費者",          "desc": "在宅受取・コンビニ受取"},
                {"name": "製造工場（部品）",    "desc": "JIT・かんばん納品"},
            ]},
        ],
    },
    "🔌 電気・ガス・エネルギー": {
        "color": "#f9a825",
        "layers": [
            {"label": "① 発電・採掘\n（川上）", "players": [
                {"name": "火力・水力・原子力発電","desc": "大規模電力発電"},
                {"name": "燃料採掘・輸入業者",  "desc": "石炭・LNG・石油"},
                {"name": "都市ガス原料調達業者","desc": "LNG輸入・国産天然ガス"},
            ]},
            {"label": "② 送電・輸送", "players": [
                {"name": "送電事業者（東北電力等）","desc": "超高圧送電・系統管理"},
                {"name": "ガスパイプライン事業者","desc": "幹線・地域ガス網"},
            ]},
            {"label": "③ 変電・配電", "players": [
                {"name": "変電所・配電事業者",  "desc": "電圧変換・配電網管理"},
                {"name": "ガス供給設備業者",    "desc": "整圧・供給管理"},
            ]},
            {"label": "④ 小売・販売", "players": [
                {"name": "電力小売業者（新電力）","desc": "料金プラン・需要管理"},
                {"name": "ガス小売業者",        "desc": "都市ガス・LPガス販売"},
            ]},
            {"label": "⑤ 最終消費\n（川下）", "players": [
                {"name": "一般家庭",            "desc": "電気・ガス・暖房"},
                {"name": "工場・事業所",        "desc": "産業用電力・工業炉"},
                {"name": "EV・蓄電インフラ",    "desc": "EV充電・系統蓄電池"},
            ]},
        ],
    },
    "🎓 教育・人材育成": {
        "color": "#1a237e",
        "layers": [
            {"label": "① 教育機関\n（川上）", "players": [
                {"name": "幼稚園・保育園",      "desc": "幼児教育・保育"},
                {"name": "小中高校",            "desc": "義務教育・高校教育"},
                {"name": "大学・専門学校",      "desc": "高等教育・職業教育"},
            ]},
            {"label": "② 職業訓練・資格", "players": [
                {"name": "職業訓練校・ポリテク",  "desc": "技能習得・職業訓練"},
                {"name": "資格試験・検定機関",  "desc": "国家資格・民間検定"},
                {"name": "e-ラーニング事業者",  "desc": "オンライン学習・動画教材"},
            ]},
            {"label": "③ 就職支援・人材紹介", "players": [
                {"name": "ハローワーク・就職支援機関","desc": "求職者支援・マッチング"},
                {"name": "人材紹介・派遣会社",  "desc": "採用代行・人材派遣"},
            ]},
            {"label": "④ 職場・OJT", "players": [
                {"name": "企業（採用・育成）",  "desc": "新入社員研修・OJT"},
                {"name": "企業内研修・外部研修","desc": "スキルアップ・管理職研修"},
            ]},
            {"label": "⑤ 社会・産業\n（川下）", "players": [
                {"name": "地域産業界",          "desc": "即戦力人材の活用"},
                {"name": "行政・NPO",           "desc": "公共サービス・地域活動"},
                {"name": "U・Iターン促進",      "desc": "地方移住・定住促進"},
            ]},
        ],
    },
    "💻 IT・デジタルサービス": {
        "color": "#006064",
        "layers": [
            {"label": "① 基盤・インフラ\n（川上）", "players": [
                {"name": "半導体・サーバーメーカー","desc": "CPU・GPU・ストレージ"},
                {"name": "データセンター事業者","desc": "クラウド基盤・コロケーション"},
                {"name": "通信インフラ業者",    "desc": "光ファイバー・5G網"},
            ]},
            {"label": "② ソフトウェア開発", "players": [
                {"name": "ITベンダー・SIer",    "desc": "システム構築・受託開発"},
                {"name": "ソフトウェア開発会社","desc": "パッケージ・アプリ開発"},
                {"name": "フリーランス開発者",  "desc": "個人開発・業務委託"},
            ]},
            {"label": "③ SaaS・プラットフォーム", "players": [
                {"name": "クラウドサービス事業者","desc": "AWS・Azure・GCP"},
                {"name": "SaaS提供会社",        "desc": "業務SaaS・ECプラットフォーム"},
            ]},
            {"label": "④ 導入・運用支援", "players": [
                {"name": "ITコンサルタント",    "desc": "DX戦略・業務改革支援"},
                {"name": "システム保守・運用業者","desc": "監視・保守・ヘルプデスク"},
            ]},
            {"label": "⑤ エンドユーザー\n（川下）", "players": [
                {"name": "中小企業・地場産業",  "desc": "業務効率化・DX推進"},
                {"name": "行政・医療・教育機関","desc": "自治体DX・医療IT"},
                {"name": "一般消費者",          "desc": "スマホアプリ・EC利用"},
            ]},
        ],
    },
    "🌱 再生可能エネルギー": {
        "color": "#388e3c",
        "layers": [
            {"label": "① 資源・原料\n（川上）", "players": [
                {"name": "太陽光・風力・地熱資源","desc": "自然エネルギー賦存量"},
                {"name": "水力・バイオマス資源","desc": "河川・森林・農業残渣"},
                {"name": "土地・用地所有者",    "desc": "山林・農地・海域"},
            ]},
            {"label": "② 設備製造・建設", "players": [
                {"name": "太陽光パネルメーカー","desc": "モジュール・パワコン"},
                {"name": "風力タービンメーカー","desc": "陸上・洋上風力機器"},
                {"name": "EPC業者（建設）",     "desc": "設計・調達・施工一括"},
            ]},
            {"label": "③ 発電・運営", "players": [
                {"name": "発電事業者（FIT・FIP）","desc": "再エネ発電・売電"},
                {"name": "地域新電力",          "desc": "地域内エネルギー自給"},
                {"name": "自家発電・PPA事業者", "desc": "オンサイト・オフサイトPPA"},
            ]},
            {"label": "④ 系統連系・蓄電", "players": [
                {"name": "送配電事業者",        "desc": "系統接続・出力制御"},
                {"name": "蓄電池メーカー・業者","desc": "系統用・家庭用蓄電池"},
                {"name": "アグリゲーター",      "desc": "需給調整・VPP運用"},
            ]},
            {"label": "⑤ 販売・利用\n（川下）", "players": [
                {"name": "電力小売業者",        "desc": "再エネ電力メニュー販売"},
                {"name": "環境価値市場",        "desc": "J-クレジット・非化石証書"},
                {"name": "産業・家庭消費者",    "desc": "RE100・脱炭素経営"},
            ]},
        ],
    },
    "⚡ 電子部品": {
        "color": "#283593",
        "layers": [
            {"label": "① 原材料\n（川上）", "players": [
                {"name": "半導体素材メーカー",  "desc": "シリコンウェハ・ガス・薬液"},
                {"name": "レアメタル・レアアース業者","desc": "ネオジム・コバルト・リチウム"},
                {"name": "化学材料・樹脂業者",  "desc": "封止材・基板材料・フィルム"},
            ]},
            {"label": "② 部品製造", "players": [
                {"name": "半導体メーカー",      "desc": "CPU・メモリ・パワー半導体"},
                {"name": "電子部品メーカー",    "desc": "コンデンサ・抵抗・コイル"},
                {"name": "プリント基板メーカー","desc": "PCB・フレキシブル基板"},
            ]},
            {"label": "③ 組立・実装", "players": [
                {"name": "EMS（電子製造受託）業者","desc": "基板実装・組立・試験"},
                {"name": "検査・品質管理業者",  "desc": "AOI・X線・電気特性検査"},
            ]},
            {"label": "④ 流通", "players": [
                {"name": "電子部品商社・代理店","desc": "在庫・調達・技術サポート"},
                {"name": "物流・精密品輸送業者","desc": "静電気対策・精密梱包"},
            ]},
            {"label": "⑤ 最終製品\n（川下）", "players": [
                {"name": "自動車メーカー",      "desc": "EV・ADAS・車載電子"},
                {"name": "家電・情報機器メーカー","desc": "スマホ・PC・家電"},
                {"name": "産業機械・医療機器メーカー","desc": "FA・ロボット・医療"},
            ]},
        ],
    },
}


def _draw_supply_chain_fig(chain_data: dict) -> go.Figure:
    """川上→川下 縦型フロー図を Plotly で描画する。
    y 軸を反転（range=[n, 0]）し、layer 0 が最上段（川上）になるよう配置。
    axref='x'/ayref='y' でデータ座標系の矢印を描画する。"""
    layers = chain_data["layers"]
    base_color = chain_data["color"]
    n_layers = len(layers)
    max_players = max(len(layer["players"]) for layer in layers)

    label_w = 0.55      # 左側ラベル列の幅（x座標単位）※狭くして右側ボックスを広く
    gap_lr = 0.05       # ラベル列とボックス列の隙間
    margin_x = 0.06    # ボックス左右マージン
    margin_y = 0.12    # ボックス上下マージン

    # カラーグラデーション（川上=ベース色、川下=やや明るい）
    r0, g0, b0 = int(base_color[1:3], 16), int(base_color[3:5], 16), int(base_color[5:7], 16)
    def _lighten(step):
        f = 1 + (step / max(n_layers - 1, 1)) * 0.4
        return f"rgb({min(255, int(r0 * f))},{min(255, int(g0 * f))},{min(255, int(b0 * f))})"
    layer_colors = [_lighten(i) for i in range(n_layers)]

    fig = go.Figure()
    # 座標系確立のための不可視トレース
    fig.add_trace(go.Scatter(
        x=[-(label_w + gap_lr), max_players], y=[0, n_layers],
        mode="markers", marker=dict(opacity=0, size=1),
        showlegend=False, hoverinfo="none",
    ))

    for i, layer in enumerate(layers):
        yc = i + 0.5
        y0 = i + margin_y
        y1 = i + 1 - margin_y
        n_players = len(layer["players"])
        col = layer_colors[i]

        # ── 左側ラベルボックス ───────────────────────────
        fig.add_shape(
            type="rect", xref="x", yref="y",
            x0=-(label_w + gap_lr), x1=-gap_lr,
            y0=y0, y1=y1,
            fillcolor=col, opacity=0.9,
            line=dict(color="white", width=1),
        )
        fig.add_annotation(
            xref="x", yref="y",
            x=-(label_w / 2 + gap_lr), y=yc,
            text=layer["label"].replace("\n", "<br>"),
            showarrow=False,
            font=dict(color="white", size=12, family="sans-serif"),
            align="center",
        )

        # ── プレイヤーボックス ───────────────────────────
        offset = (max_players - n_players) / 2
        for j, player in enumerate(layer["players"]):
            px0 = j + offset + margin_x
            px1 = j + offset + 1 - margin_x
            pxc = j + offset + 0.5
            fig.add_shape(
                type="rect", xref="x", yref="y",
                x0=px0, x1=px1, y0=y0, y1=y1,
                fillcolor=col,
                line=dict(color="white", width=2),
            )
            fig.add_annotation(
                xref="x", yref="y",
                x=pxc, y=yc - 0.14,
                text=f"<b>{player['name']}</b>",
                showarrow=False,
                font=dict(color="white", size=12),
                align="center",
            )
            fig.add_annotation(
                xref="x", yref="y",
                x=pxc, y=yc + 0.19,
                text=player["desc"],
                showarrow=False,
                font=dict(color="rgba(255,255,255,0.88)", size=10),
                align="center",
            )

        # ── 次レイヤーへの下向き矢印 ─────────────────────
        if i < n_layers - 1:
            arr_x = max_players / 2
            fig.add_annotation(
                xref="x", yref="y", axref="x", ayref="y",
                x=arr_x, y=i + 1 + margin_y,      # 矢印先端（次レイヤー上端）
                ax=arr_x, ay=i + 1 - margin_y,    # 矢印根元（現レイヤー下端）
                arrowhead=3, arrowsize=1.4,
                arrowwidth=3, arrowcolor="#90a4ae",
                showarrow=True, text="",
            )

    fig.update_layout(
        height=max(380, n_layers * 115),
        margin=dict(l=5, r=5, t=8, b=8),
        xaxis=dict(visible=False, range=[-(label_w + gap_lr + 0.1), max_players + 0.1]),
        yaxis=dict(visible=False, range=[n_layers, 0]),  # 反転: 川上が上
        plot_bgcolor="white", paper_bgcolor="white",
        showlegend=False,
    )
    return fig


def page_supply_chain():
    st.title("🔗 川上・川下フロー分析")
    st.caption("業界別の原材料から最終消費までの川上・川下関係を図示します")
    st.markdown("---")

    selected = st.selectbox("業界を選択", list(_SUPPLY_CHAIN_DATA.keys()))
    chain = _SUPPLY_CHAIN_DATA[selected]

    st.plotly_chart(
        _draw_supply_chain_fig(chain),
        use_container_width=True,
    )

    # 凡例説明
    n = len(chain["layers"])
    with st.expander("📋 各プレイヤーの詳細", expanded=False):
        for layer in chain["layers"]:
            st.markdown(f"**{layer['label'].replace(chr(10), ' ')}**")
            cols = st.columns(len(layer["players"]))
            for col, p in zip(cols, layer["players"]):
                with col:
                    st.markdown(f"**{p['name']}**")
                    st.caption(p["desc"])
            st.markdown("---")


# ダミー: 旧関数名を残して routing エラーを防ぐ（下部 routing で置き換え済み）
def page_value_chain():
    page_supply_chain()


_VALUE_CHAIN_DATA: dict = {}   # 旧データ（未使用・互換性維持）



# ============================================================
# 組織成熟度診断ページ
# ============================================================

def page_openclose():
    """開業・廃業動態ページ（経済センサス 2012/2016/2021年 存続・新設・廃業別事業所数）"""
    st.title("📉 開業・廃業動態（秋田県）")
    st.markdown("経済センサス-活動調査をもとに、業種別の新設・廃業事業所数・開廃業率と推移を表示します。")

    # ── 計算式の説明 ─────────────────────────────────────────────────────
    with st.expander("📐 開業率・廃業率の計算式", expanded=False):
        st.markdown("""
**開業率**（新規参入の多さを示す指標）

$$
\\text{開業率 (\\%)} = \\frac{\\text{新設事業所数}}{\\text{存続事業所数} + \\text{新設事業所数}} \\times 100
$$

> 分母を「調査時点の全事業所数（存続＋新設）」とすることで、
> 調査期間中に新たに誕生した事業所の割合を表します。

**廃業率**（退出の多さを示す指標）

$$
\\text{廃業率 (\\%)} = \\frac{\\text{廃業事業所数}}{\\text{存続事業所数} + \\text{廃業事業所数}} \\times 100
$$

> 分母を「前回調査時点の全事業所数（存続＋廃業）」とすることで、
> 調査期間の始点に存在した事業所のうち廃業した割合を表します。

**データの性質**
- 出典：経済センサス-活動調査（総務省・経産省、5年ごと実施）
- 各調査は「前回調査との比較」で存続・新設・廃業を分類
  - 2012年調査：2007年→2012年の変化
  - 2016年調査：2012年→2016年の変化
  - 2021年調査：2016年→2021年の変化
        """)

    st.markdown("---")

    # ── データ取得 ────────────────────────────────────────────────────────
    # JSONキャッシュ優先（GitHub Actions が毎月更新）→ キャッシュなし時のみ API を使用
    with st.spinner("データ読み込み中（JSONキャッシュ → e-Stat API）…"):
        df_latest, source_latest = _load_openclose_stats()
        trend_dict = _load_openclose_trend()

    if df_latest.empty:
        if not estat_api.is_api_key_set():
            st.warning(
                "JSONキャッシュが見つかりません。"
                "「🔌 e-Stat API連携」ページでAPIキーを設定すると実データを取得できます。"
            )
        else:
            msg_map = {"no_key": "APIキーが設定されていません。", "no_data": "データが取得できませんでした。"}
            st.error(msg_map.get(source_latest, f"取得エラー: {source_latest}"))
        return

    st.caption(f"出典: {source_latest}　｜　取得済み調査年: {', '.join(trend_dict.keys())}")

    # ── 最新年（2021）のピボット作成 ─────────────────────────────────────
    def _make_pivot(df: pd.DataFrame) -> pd.DataFrame:
        """[産業, 区分, 事業所数] → ピボット＋開廃業率付き DataFrame"""
        pv = df.pivot_table(
            index="産業", columns="区分", values="事業所数", aggfunc="sum"
        ).fillna(0).astype(int)
        for col in ["存続事業所", "新設事業所", "廃業事業所"]:
            if col not in pv.columns:
                pv[col] = 0
        pv["開業率(%)"] = (
            pv["新設事業所"] / (pv["存続事業所"] + pv["新設事業所"]).replace(0, pd.NA) * 100
        ).round(1)
        pv["廃業率(%)"] = (
            pv["廃業事業所"] / (pv["存続事業所"] + pv["廃業事業所"]).replace(0, pd.NA) * 100
        ).round(1)
        return pv

    df_pivot = _make_pivot(df_latest)

    # ── KPI（2021年）────────────────────────────────────────────────────
    total_new   = int(df_pivot["新設事業所"].sum())
    total_close = int(df_pivot["廃業事業所"].sum())
    total_exist = int(df_pivot["存続事業所"].sum())
    net = total_new - total_close

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("存続事業所数（2021年）", f"{total_exist:,}")
    k2.metric("新設事業所数（開業）", f"{total_new:,}", delta=f"+{total_new:,}")
    k3.metric("廃業事業所数", f"{total_close:,}", delta=f"{-total_close:,}", delta_color="inverse")
    k4.metric(
        "純増減（新設－廃業）",
        f"{net:+,}",
        delta="増加" if net >= 0 else "減少",
        delta_color="normal" if net >= 0 else "inverse",
    )

    st.markdown("---")

    # ── タブ ─────────────────────────────────────────────────────────────
    tab_count, tab_rate, tab_trend, tab_data = st.tabs([
        "📊 業種別 新設・廃業数",
        "📈 業種別 開廃業率（2021年）",
        "📅 推移グラフ（2012→2016→2021年）",
        "🗒️ データ一覧",
    ])

    df_plot = df_pivot.reset_index()
    df_plot["産業短"] = df_plot["産業"].str[:22]

    # ── タブ①: 新設・廃業事業所数 ────────────────────────────────────────
    with tab_count:
        st.subheader("業種別 新設・廃業事業所数（2021年）")
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="新設事業所", x=df_plot["産業短"], y=df_plot["新設事業所"],
            marker_color="#1565C0", text=df_plot["新設事業所"], textposition="outside",
        ))
        fig.add_trace(go.Bar(
            name="廃業事業所", x=df_plot["産業短"], y=df_plot["廃業事業所"],
            marker_color="#C62828", text=df_plot["廃業事業所"], textposition="outside",
        ))
        fig.update_layout(
            barmode="group", height=480, xaxis_tickangle=-40,
            yaxis_title="事業所数（件）",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=40, b=120, l=60, r=20), plot_bgcolor="white",
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("業種別 純増減（新設－廃業）")
        df_plot["純増減"] = df_plot["新設事業所"] - df_plot["廃業事業所"]
        fig2 = go.Figure(go.Bar(
            x=df_plot["産業短"], y=df_plot["純増減"],
            marker_color=["#1565C0" if v >= 0 else "#C62828" for v in df_plot["純増減"]],
            text=df_plot["純増減"].apply(lambda v: f"{v:+d}"), textposition="outside",
        ))
        fig2.update_layout(
            height=380, xaxis_tickangle=-40, yaxis_title="純増減（件）",
            yaxis=dict(zeroline=True, zerolinecolor="#888"),
            margin=dict(t=20, b=120, l=60, r=20), plot_bgcolor="white",
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── タブ②: 開廃業率（2021年）────────────────────────────────────────
    with tab_rate:
        st.subheader("業種別 開業率・廃業率（2021年）")
        st.markdown(
            "**開業率** = 新設事業所 ÷（存続＋新設）× 100　　"
            "**廃業率** = 廃業事業所 ÷（存続＋廃業）× 100"
        )
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(
            name="開業率(%)", x=df_plot["産業短"], y=df_plot["開業率(%)"],
            marker_color="#1565C0",
            text=df_plot["開業率(%)"].apply(lambda v: f"{v:.1f}%" if pd.notna(v) else ""),
            textposition="outside",
        ))
        fig3.add_trace(go.Bar(
            name="廃業率(%)", x=df_plot["産業短"], y=df_plot["廃業率(%)"],
            marker_color="#C62828",
            text=df_plot["廃業率(%)"].apply(lambda v: f"{v:.1f}%" if pd.notna(v) else ""),
            textposition="outside",
        ))
        fig3.update_layout(
            barmode="group", height=480, xaxis_tickangle=-40, yaxis_title="率（%）",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=40, b=120, l=60, r=20), plot_bgcolor="white",
        )
        st.plotly_chart(fig3, use_container_width=True)

        # 散布図
        st.subheader("開業率 vs 廃業率 ポジショニング（2021年）")
        st.caption("右上ほど新陳代謝が活発、左下ほど固定的な業種構造。破線は開業率＝廃業率の均衡ライン。")
        fig4 = px.scatter(
            df_plot.dropna(subset=["開業率(%)", "廃業率(%)"]),
            x="廃業率(%)", y="開業率(%)", text="産業短",
            color="純増減", color_continuous_scale="RdYlBu",
        )
        fig4.update_traces(textposition="top center", marker_size=12)
        max_rate = max(
            df_plot["開業率(%)"].dropna().max(),
            df_plot["廃業率(%)"].dropna().max(),
        ) + 1
        fig4.add_shape(
            type="line", x0=0, y0=0, x1=max_rate, y1=max_rate,
            line=dict(color="#888", dash="dash", width=1),
        )
        fig4.update_layout(
            height=440, margin=dict(t=30, b=60, l=60, r=20), plot_bgcolor="white",
        )
        st.plotly_chart(fig4, use_container_width=True)

    # ── タブ③: 推移グラフ ────────────────────────────────────────────────
    with tab_trend:
        if len(trend_dict) < 2:
            st.warning("推移グラフには複数調査年のデータが必要です。現在取得できているのは1年分のみです。")
        else:
            # 年ごとのピボット作成・産業名を正規化してマッチング
            def _norm_ind(name: str) -> str:
                """産業名の表記揺れを正規化（調査年によって「，」「・」が混在）"""
                return (name.replace("，", "・").replace("、", "・")
                            .replace("（", "(").replace("）", ")").strip())

            # 各調査年の比較期間（年数）— JSONキャッシュの duration_years を動的に読み込む
            # 2026年頃の次回センサスが追加されてもコード変更不要
            _DURATION = estat_api.load_cached_openclose_duration_map()

            rate_rows = []
            for year, df_yr in trend_dict.items():
                pv = _make_pivot(df_yr)
                dur = _DURATION.get(year, 5)
                for ind_raw, row in pv.iterrows():
                    r_open = row.get("開業率(%)", pd.NA)
                    r_clos = row.get("廃業率(%)", pd.NA)
                    rate_rows.append({
                        "調査年": year,
                        "産業（原文）": ind_raw,
                        "産業": _norm_ind(str(ind_raw)),
                        "産業短": _norm_ind(str(ind_raw))[:20],
                        "開業率_累計(%)": r_open,
                        "廃業率_累計(%)": r_clos,
                        # 年換算：累計率 ÷ 比較期間年数（推移の比較に使用）
                        "開業率_年換算(%)": round(float(r_open) / dur, 2) if pd.notna(r_open) else pd.NA,
                        "廃業率_年換算(%)": round(float(r_clos) / dur, 2) if pd.notna(r_clos) else pd.NA,
                        "比較期間(年)": dur,
                        "新設事業所": int(row.get("新設事業所", 0)),
                        "廃業事業所": int(row.get("廃業事業所", 0)),
                        "存続事業所": int(row.get("存続事業所", 0)),
                    })

            df_rate = pd.DataFrame(rate_rows)

            # 全産業合計行を追加
            total_rows = []
            for year, grp in df_rate.groupby("調査年"):
                new_sum = grp["新設事業所"].sum()
                clo_sum = grp["廃業事業所"].sum()
                ext_sum = grp["存続事業所"].sum()
                dur = _DURATION.get(year, 5)
                ro = round(new_sum / (ext_sum + new_sum) * 100, 1) if (ext_sum + new_sum) > 0 else pd.NA
                rc = round(clo_sum / (ext_sum + clo_sum) * 100, 1) if (ext_sum + clo_sum) > 0 else pd.NA
                total_rows.append({
                    "調査年": year,
                    "産業": "【全産業合計】",
                    "産業短": "全産業",
                    "開業率_累計(%)": ro,
                    "廃業率_累計(%)": rc,
                    "開業率_年換算(%)": round(float(ro) / dur, 2) if pd.notna(ro) else pd.NA,
                    "廃業率_年換算(%)": round(float(rc) / dur, 2) if pd.notna(rc) else pd.NA,
                    "比較期間(年)": dur,
                    "新設事業所": new_sum, "廃業事業所": clo_sum, "存続事業所": ext_sum,
                })
            df_rate = pd.concat([df_rate, pd.DataFrame(total_rows)], ignore_index=True)

            # 業種選択
            all_industries = sorted(df_rate[df_rate["産業"] != "【全産業合計】"]["産業"].unique())
            default_sel = ["【全産業合計】"] + all_industries[:5]
            sel_industries = st.multiselect(
                "表示する業種を選択（複数可）",
                options=["【全産業合計】"] + all_industries,
                default=default_sel,
                key="trend_industry_sel",
            )

            if not sel_industries:
                st.info("業種を1つ以上選択してください。")
            else:
                df_sel = df_rate[df_rate["産業"].isin(sel_industries)].copy()

                # ── 比較期間の注意書き ──────────────────────────────────────
                st.info(
                    "⚠️ **比較期間が調査年ごとに異なります**\n\n"
                    "| 調査年 | 比較期間 | 実質年数 |\n"
                    "|--------|---------|--------|\n"
                    "| 2012年 | 2009年→2012年 | **3年間** |\n"
                    "| 2016年 | 2012年→2016年 | **4年間** |\n"
                    "| 2021年 | 2016年→2021年 | **5年間** |\n\n"
                    "累計値をそのまま比較すると期間が長い2021年が高く見えます。"
                    "下のグラフは**年換算値**（累計率 ÷ 比較年数）で統一しています。"
                )

                # 開業率推移（年換算）
                st.subheader("開業率の推移（年換算 %/年）")
                st.caption(
                    "開業率（年換算）= 累計開業率 ÷ 比較期間年数　　"
                    "年換算することで2012・2016・2021年を公平に比較できます"
                )
                fig_t1 = px.line(
                    df_sel.dropna(subset=["開業率_年換算(%)"]),
                    x="調査年", y="開業率_年換算(%)", color="産業短",
                    markers=True,
                    color_discrete_sequence=px.colors.qualitative.Set2,
                    hover_data={"開業率_累計(%)": True, "比較期間(年)": True},
                )
                fig_t1.update_layout(
                    height=420, yaxis_title="開業率（%/年）",
                    legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="left", x=0),
                    margin=dict(t=30, b=120, l=60, r=20), plot_bgcolor="white",
                    xaxis=dict(type="category"),
                )
                st.plotly_chart(fig_t1, use_container_width=True)

                # 廃業率推移（年換算）
                st.subheader("廃業率の推移（年換算 %/年）")
                st.caption(
                    "廃業率（年換算）= 累計廃業率 ÷ 比較期間年数　　"
                    "廃業率が上昇トレンドにある業種は後継者問題・市場縮小の懸念"
                )
                fig_t2 = px.line(
                    df_sel.dropna(subset=["廃業率_年換算(%)"]),
                    x="調査年", y="廃業率_年換算(%)", color="産業短",
                    markers=True,
                    color_discrete_sequence=px.colors.qualitative.Set2,
                    hover_data={"廃業率_累計(%)": True, "比較期間(年)": True},
                )
                fig_t2.update_layout(
                    height=420, yaxis_title="廃業率（%/年）",
                    legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="left", x=0),
                    margin=dict(t=30, b=120, l=60, r=20), plot_bgcolor="white",
                    xaxis=dict(type="category"),
                )
                st.plotly_chart(fig_t2, use_container_width=True)

                # 全産業 年換算事業所数の推移（新設・廃業 ÷ 比較年数）
                st.subheader("全産業 年間換算 新設・廃業事業所数の推移")
                st.caption("各期間の件数を年数で割って年換算。期間の長さによる差異を補正した比較値。")
                df_total = df_rate[df_rate["産業"] == "【全産業合計】"].copy()
                df_total["新設_年換算"] = (df_total["新設事業所"] / df_total["比較期間(年)"]).round(0).astype(int)
                df_total["廃業_年換算"] = (df_total["廃業事業所"] / df_total["比較期間(年)"]).round(0).astype(int)
                fig_t3 = go.Figure()
                fig_t3.add_trace(go.Bar(
                    name="新設（年換算）",
                    x=df_total["調査年"], y=df_total["新設_年換算"],
                    marker_color="#1565C0",
                    text=df_total["新設_年換算"].apply(lambda v: f"{v:,}/年"),
                    textposition="outside",
                ))
                fig_t3.add_trace(go.Bar(
                    name="廃業（年換算）",
                    x=df_total["調査年"], y=df_total["廃業_年換算"],
                    marker_color="#C62828",
                    text=df_total["廃業_年換算"].apply(lambda v: f"{v:,}/年"),
                    textposition="outside",
                ))
                fig_t3.update_layout(
                    barmode="group", height=380,
                    yaxis_title="事業所数（件/年）",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(t=40, b=60, l=60, r=20), plot_bgcolor="white",
                    xaxis=dict(type="category"),
                )
                st.plotly_chart(fig_t3, use_container_width=True)
                st.caption("次回調査（2026年予定）公開後、自動的に4点推移に更新されます。")

    # ── タブ④: データ一覧 ────────────────────────────────────────────────
    with tab_data:
        st.subheader("業種別 詳細データ（2021年）")
        display_df = df_pivot[["存続事業所", "新設事業所", "廃業事業所", "開業率(%)", "廃業率(%)"]].copy()
        display_df.index.name = "産業（大分類）"
        st.dataframe(
            display_df.style.format({
                "存続事業所": "{:,}", "新設事業所": "{:,}", "廃業事業所": "{:,}",
                "開業率(%)": "{:.1f}%", "廃業率(%)": "{:.1f}%",
            }),
            use_container_width=True,
        )
        csv = display_df.reset_index().to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "⬇ CSV ダウンロード（2021年）",
            data=csv, file_name="akita_openclose_2021.csv", mime="text/csv",
        )
        st.info(
            "💡 **読み方のヒント**\n"
            "- 廃業率が高い業種 → 後継者問題・経営難が深刻な可能性\n"
            "- 開業率が高い業種 → 新規参入が活発・競合増加の可能性\n"
            "- 廃業率が上昇トレンド → 業種の縮小局面（推移グラフで確認）\n"
            "- 純増減がマイナス → 業種全体の事業所数が減少傾向"
        )
def page_successor():
    """後継者問題・廃業リスク（実データのみ使用）"""
    st.title("👴 後継者問題・廃業リスク（秋田県）")
    st.markdown(
        "出典：**帝国データバンク「秋田県内企業後継者不在率動向調査」「秋田県内企業休廃業・解散動向調査」**"
        "（各年版）に基づく実データです。"
    )
    st.markdown("---")

    df_rate = get_successor_absence_rate()
    df_close = get_closure_trend()
    prof = get_closure_profile()

    # ── KPI ─────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "後継者不在率（秋田・2025年）",
        f"{df_rate['秋田県（%）'].iloc[-1]}%",
        delta="全国最高・全都道府県唯一の70%超",
        delta_color="inverse",
    )
    c2.metric(
        "後継者不在率（全国・2025年）",
        f"{df_rate['全国（%）'].iloc[-1]}%",
        delta="7年連続改善傾向",
    )
    c3.metric(
        "休廃業・解散件数（2024年）",
        f"{prof['最多業種件数'] + 466}件",  # 564件
        delta=f"前年比 +{prof['前年比増加率（%）']}%（2016年以降最多）",
        delta_color="inverse",
    )
    c4.metric(
        "うち黒字廃業（2024年）",
        f"{prof['黒字廃業率（%）']}%",
        delta="採算が取れていても廃業",
        delta_color="inverse",
    )

    st.markdown("---")

    col1, col2 = st.columns(2)

    # ── 廃業件数推移 ─────────────────────────────────────────────
    with col1:
        st.subheader("休廃業・解散件数の推移（秋田県）")
        fig = go.Figure()
        colors = [
            "#2980b9" if v < 400 else "#e74c3c"
            for v in df_close["休廃業・解散件数"]
        ]
        fig.add_trace(go.Bar(
            x=df_close["年"],
            y=df_close["休廃業・解散件数"],
            marker_color=colors,
            text=df_close["休廃業・解散件数"],
            textposition="outside",
        ))
        fig.update_layout(
            height=360,
            yaxis=dict(title="件", range=[0, 650]),
            xaxis=dict(title="年", dtick=1),
            margin=dict(t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "出典：帝国データバンク「秋田県内企業休廃業・解散動向調査」各年版｜"
            "2024年は2016年以降最多。全国でも増加率が最高水準。"
        )

    # ── 後継者不在率 比較 ────────────────────────────────────────
    with col2:
        st.subheader("後継者不在率：秋田県 vs 全国")
        fig2 = go.Figure()
        x_labels = [str(y) + "年" for y in df_rate["調査年"]]
        fig2.add_trace(go.Bar(
            name="秋田県",
            x=x_labels,
            y=df_rate["秋田県（%）"],
            marker_color="#c0392b",
            text=[f"{v}%" for v in df_rate["秋田県（%）"]],
            textposition="outside",
        ))
        fig2.add_trace(go.Bar(
            name="全国",
            x=x_labels,
            y=df_rate["全国（%）"],
            marker_color="#2980b9",
            text=[f"{v}%" for v in df_rate["全国（%）"]],
            textposition="outside",
        ))
        fig2.update_layout(
            height=360,
            barmode="group",
            yaxis=dict(title="%", range=[0, 90]),
            legend=dict(orientation="h", y=-0.2),
            margin=dict(t=10, b=50),
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.caption(
            "出典：帝国DB「全国企業後継者不在率調査」2024・2025年版｜"
            "秋田は全国最高。全国は7年連続改善だが秋田は2023年以降上昇。"
        )

    st.markdown("---")

    # ── 廃業企業の特性 ───────────────────────────────────────────
    st.subheader("廃業企業の特性（2024年・秋田県）")
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("経営者平均年齢", f"{prof['経営者平均年齢']}歳")
    c6.metric("黒字廃業の割合", f"{prof['黒字廃業率（%）']}%")
    c7.metric("資産超過での廃業", f"{prof['資産超過率（%）']}%")
    c8.metric("最多業種", f"{prof['最多業種']}（{prof['最多業種件数']}件）")

    st.info(
        "💡 **ポイント：** 廃業の4割超が黒字、7割超が資産超過での廃業です。"
        "経営不振ではなく**後継者不在・高齢による「やむを得ない廃業」**が主因であることを示しています。"
        "早期の事業承継対策が地域雇用・商圏の維持に直結します。"
    )

    st.markdown("---")

    st.subheader("📋 活用できる支援策")
    col3, col4 = st.columns(2)
    with col3:
        st.markdown("""
**秋田県内の相談窓口**
- 秋田県事業引継ぎ支援センター（無料相談）
- 秋田県よろず支援拠点
- 中小企業活力向上プロジェクトネクスト

**主な補助金・制度**
- 事業承継・引継ぎ補助金（最大250万円）
- 経営承継円滑化法（相続税・贈与税の猶予）
- 中小企業事業承継税制（株式等の猶予）
""")
    with col4:
        st.markdown("""
**第三者承継（M&A）の活用**
- 後継者がいなくても事業継続が可能
- 秋田県内のM&A仲介機関・金融機関が対応
- 事業引継ぎ補助金でマッチング費用を補助
""")


def page_labor_market():
    """労働市場ダッシュボード（実データのみ使用）"""
    st.title("👷 労働市場（最低賃金・求人倍率）")
    st.markdown(
        "出典：**厚生労働省「地域別最低賃金額改定状況」「一般職業紹介状況」**"
        "に基づく実データです。"
    )
    st.markdown("---")

    df_wage = get_minimum_wage_akita()
    df_ratio = get_job_opening_ratio_akita()

    latest_wage = df_wage["秋田県（円）"].iloc[-1]
    prev_wage   = df_wage["秋田県（円）"].iloc[-2]
    latest_ratio = df_ratio["秋田県（倍）"].iloc[-1]
    prev_ratio   = df_ratio["秋田県（倍）"].iloc[-2]

    # ── KPI ─────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "最低賃金（秋田・2025年度）",
        f"{latest_wage:,}円",
        delta=f"+{latest_wage - prev_wage}円（前年度比）",
    )
    c2.metric(
        "最低賃金（秋田・2024年度）",
        f"{prev_wage:,}円",
        delta=f"10年前（2015年）比 +{prev_wage - 695}円",
    )
    c3.metric(
        "有効求人倍率（秋田・2024年）",
        f"{latest_ratio:.2f}倍",
        delta=f"前年比 -{prev_ratio - latest_ratio:.2f}倍（3年連続低下）",
        delta_color="inverse",
    )
    c4.metric(
        "有効求人倍率（秋田・2025年）",
        f"{df_ratio['秋田県（倍）'].iloc[-1]:.2f}倍",
        delta="3年連続低下",
        delta_color="inverse",
    )

    st.markdown("---")

    col1, col2 = st.columns(2)

    # ── 最低賃金推移 ─────────────────────────────────────────────
    with col1:
        st.subheader("最低賃金の推移（秋田県）")
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_wage["年度"],
            y=df_wage["秋田県（円）"],
            marker_color=[
                "#c0392b" if y >= 2024 else "#2980b9"
                for y in df_wage["年度"]
            ],
            text=df_wage["秋田県（円）"],
            textposition="outside",
        ))
        fig.update_layout(
            height=380,
            yaxis=dict(title="円", range=[600, 1150]),
            xaxis=dict(title="年度", dtick=1),
            margin=dict(t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "出典：厚生労働省「地域別最低賃金額改定状況」・秋田労働局｜"
            "2025年度（1,031円）は令和8年3月31日発効。"
        )

    # ── 有効求人倍率 ─────────────────────────────────────────────
    with col2:
        st.subheader("有効求人倍率（秋田県・年平均）")
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=[f"{y}年" for y in df_ratio["年"]],
            y=df_ratio["秋田県（倍）"],
            marker_color=["#e67e22", "#c0392b"],
            text=[f"{v:.2f}倍" for v in df_ratio["秋田県（倍）"]],
            textposition="outside",
        ))
        fig2.add_hline(
            y=1.0,
            line_dash="dot",
            line_color="gray",
            annotation_text="均衡ライン（1.0倍）",
            annotation_position="right",
        )
        fig2.update_layout(
            height=380,
            yaxis=dict(title="倍", range=[0, 1.8]),
            margin=dict(t=10, b=10, r=120),
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.caption(
            "出典：厚生労働省「一般職業紹介状況（公共職業安定所業務統計）」｜"
            "2023年以降3年連続低下。ただし均衡ライン（1.0倍）は上回っており、"
            "引き続き求人超過の状態。2015〜2023年の年次データは未取得のため非表示。"
        )

    st.markdown("---")

    # ── 最低賃金の解説 ───────────────────────────────────────────
    st.subheader("📋 最低賃金 関連情報")
    col3, col4 = st.columns(2)
    with col3:
        wage_10y = df_wage["秋田県（円）"].iloc[-2] - df_wage["秋田県（円）"].iloc[0]
        st.markdown(f"""
**10年間の引き上げ幅（2015→2024年度）**
- **+{wage_10y}円**（695円 → 951円、+{wage_10y/695*100:.0f}%）
- 毎年平均 +{wage_10y/9:.0f}円のペース

**2025年度（1,031円）のポイント**
- 前年比 **+80円**（過去最大水準の引き上げ）
- 令和8年3月31日発効
- パート・アルバイト比率が高い小売・飲食は特に影響大
""")
    with col4:
        st.markdown("""
**活用できる賃上げ支援策**
- 業務改善助成金（最低賃金引上げ＋設備投資を支援）
- 賃上げ促進税制（法人税の税額控除）
- 中小企業省力化投資補助金（人手不足と人件費上昇を同時解決）
- キャリアアップ助成金（非正規→正規転換）

**業務改善助成金の概要**
- 最低賃金を30〜90円以上引き上げた場合に設備投資費用を補助
- 補助率：最大9/10、上限：最大600万円
""")

    st.markdown("---")

    # ── 都道府県別 最低賃金ランキング ────────────────────────────
    st.subheader("🗾 都道府県別 最低賃金ランキング（2025年度）")

    wage_data, wage_year, wage_fetched = load_cached_minimum_wage()
    if not wage_data:
        st.warning("最低賃金データが未取得です。fetch_labor_data.py を実行してください。")
    else:
        df_all = pd.DataFrame(wage_data).sort_values("最低賃金（円）", ascending=False).reset_index(drop=True)
        df_all["順位"] = df_all.index + 1
        df_all["色"] = df_all["都道府県"].apply(
            lambda x: "#c0392b" if x == "秋田県" else (
                "#e67e22" if x in ["青森県","岩手県","宮城県","山形県","福島県"] else "#2980b9"
            )
        )
        # 秋田の順位
        akita_rank = df_all[df_all["都道府県"] == "秋田県"]["順位"].iloc[0]
        akita_wage = df_all[df_all["都道府県"] == "秋田県"]["最低賃金（円）"].iloc[0]
        national_avg = 1121

        c1, c2, c3 = st.columns(3)
        c1.metric("秋田県の全国順位", f"{akita_rank}位 / 47都道府県",
                  delta=f"{akita_wage}円（全国加重平均比 ▲{national_avg - akita_wage}円）",
                  delta_color="inverse")
        c2.metric("全国最高（東京都）", "1,226円",
                  delta=f"秋田比 +{1226 - akita_wage}円", delta_color="off")
        c3.metric("全国加重平均", f"{national_avg:,}円",
                  delta=f"秋田比 ▲{national_avg - akita_wage}円", delta_color="off")

        # 全47都道府県 横棒グラフ（go.Bar で色グループ化を防ぐ）
        df_plot = df_all.sort_values("最低賃金（円）", ascending=True).reset_index(drop=True)
        fig_all = go.Figure(go.Bar(
            x=df_plot["最低賃金（円）"],
            y=df_plot["都道府県"],
            orientation="h",
            marker_color=df_plot["色"].tolist(),
            text=[f"{v:,}円" for v in df_plot["最低賃金（円）"]],
            textposition="outside",
        ))
        fig_all.add_vline(x=national_avg, line_dash="dash", line_color="#7f8c8d",
                          annotation_text=f"全国加重平均 {national_avg}円",
                          annotation_position="top right")
        fig_all.update_layout(
            height=1100,
            showlegend=False,
            xaxis=dict(range=[980, 1280], title="円"),
            margin=dict(r=80, t=10, b=10),
        )
        st.plotly_chart(fig_all, use_container_width=True)
        st.caption(
            f"出典：厚生労働省「地域別最低賃金額改定状況」（{wage_year}）｜"
            "赤：秋田県、橙：東北6県、青：その他。"
            f"データ更新日：{wage_fetched}"
        )



def page_maturity_diagnosis():
    st.title("🏢 組織成熟度診断")
    st.markdown("経営管理の現状を5項目でチェックし、組織の成熟度と財務状況を可視化します。")
    st.markdown("---")

    # ── 診断項目 ──────────────────────────────────────────────
    ITEMS = [
        {
            "label": "① 計画・目標",
            "checks": [
                "事業計画・収支予算はあるか",
                "プロセス目標（KPI）はあるか",
                "目標を立てただけになっていないか（機能しているか）",
            ],
        },
        {
            "label": "② 業務手順書",
            "checks": [
                "コア業務についての手順書やチェックリストがあるか",
                "担当者任せにせず、品質にバラつきがないか",
                "手順書が形骸化していないか",
            ],
        },
        {
            "label": "③ 状況の見える化",
            "checks": [
                "月次の試算表が翌月上旬にできているか",
                "KPIに対する実績が日常的にわかる状態になっているか",
            ],
        },
        {
            "label": "④ 定期的な振り返り",
            "checks": [
                "定期的に目標と実績の差異を比較する機会があるか",
                "振り返りにより改善すべき課題が抽出されているか",
            ],
        },
        {
            "label": "⑤ 改善のしくみ",
            "checks": [
                "抽出された課題に対して改善策が検討されているか",
                "改善策を行動に反映させるしくみがあるか",
                "手順書に手直しが加えられているか",
            ],
        },
    ]

    SCORE_LABELS = {"ある（十分）": 2, "不十分": 1, "ない": 0}

    st.subheader("STEP 1｜組織成熟度チェック")
    st.caption("各項目について最も近い状態を選んでください（ある＝2点、不十分＝1点、ない＝0点）")

    scores = []
    for item in ITEMS:
        with st.expander(item["label"], expanded=True):
            st.caption("チェックポイント：\n" + "\n".join(f"□ {c}" for c in item["checks"]))
            val = st.radio(
                "評価",
                list(SCORE_LABELS.keys()),
                index=1,
                key=f"maturity_{item['label']}",
                horizontal=True,
                label_visibility="collapsed",
            )
            scores.append(SCORE_LABELS[val])

    total = sum(scores)

    # 成熟度ランク判定
    if total >= 9:
        rank, rank_label, rank_color = "a", "継続的な改善が生まれ続けている状態", "#1b5e20"
    elif total >= 7:
        rank, rank_label, rank_color = "b", "経営管理を行い、改善が生まれている状態", "#388e3c"
    elif total >= 5:
        rank, rank_label, rank_color = "c", "経営管理を行っているが、まだ不十分な状態", "#f9a825"
    elif total >= 3:
        rank, rank_label, rank_color = "d", "経営管理の実行が不十分で、機能していない状態", "#e65100"
    else:
        rank, rank_label, rank_color = "e", "経営状況が分からず、何が問題かもわからない状態", "#b71c1c"

    st.markdown("---")
    st.subheader("STEP 2｜財務状況の確認")
    col1, col2 = st.columns(2)
    with col1:
        cf_ok = st.radio(
            "当期純利益＋減価償却費　vs　返済額",
            ["≧ 返済額（返済可能）", "＜ 返済額（返済困難）"],
            key="fin_cf",
        )
    with col2:
        equity_ok = st.radio(
            "純資産",
            ["≧ ０（債務超過なし）", "＜ ０（債務超過）"],
            key="fin_equity",
        )
    resche = st.checkbox("金融機関へのリスケ済み（借入返済猶予中）", key="fin_resche")

    # 財務区分
    cf_positive = cf_ok.startswith("≧")
    eq_positive = equity_ok.startswith("≧")
    if cf_positive and eq_positive:
        fin_rank, fin_label, fin_color = "Ⅳ", "良好（返済可能・純資産プラス）", "#1b5e20"
    elif not cf_positive and eq_positive:
        fin_rank, fin_label, fin_color = "Ⅲ", "要注意（返済困難・純資産プラス）", "#f9a825"
    elif cf_positive and not eq_positive:
        fin_rank, fin_label, fin_color = "Ⅱ", "要注意（返済可能・債務超過）", "#e65100"
    else:
        fin_rank, fin_label, fin_color = "Ⅰ", "危機的（返済困難・債務超過）", "#b71c1c"

    st.markdown("---")
    st.subheader("📊 診断結果")

    res_col1, res_col2 = st.columns(2)
    with res_col1:
        st.metric("組織成熟度スコア", f"{total} / 10点", delta=None)
        st.markdown(
            f"<div style='padding:12px;border-radius:8px;background:{rank_color}22;border-left:4px solid {rank_color}'>"
            f"<b style='color:{rank_color}'>ランク {rank.upper()}：{total}点</b><br>{rank_label}</div>",
            unsafe_allow_html=True,
        )
    with res_col2:
        st.metric("財務状況区分", fin_rank)
        flag = "　⚠️ リスケ済み" if resche else ""
        st.markdown(
            f"<div style='padding:12px;border-radius:8px;background:{fin_color}22;border-left:4px solid {fin_color}'>"
            f"<b style='color:{fin_color}'>区分 {fin_rank}：{fin_label}</b>{flag}</div>",
            unsafe_allow_html=True,
        )

    # ── マトリックス可視化 ──────────────────────────────────
    st.markdown("---")
    st.subheader("📈 ポジショニングマトリックス")

    fin_x = {"Ⅰ": 1, "Ⅱ": 2, "Ⅲ": 3, "Ⅳ": 4}[fin_rank]

    fig = go.Figure()

    # 背景色ゾーン（4象限）
    zone_colors = [
        # (x0, x1, y0, y1, color, label)
        (0.5, 2.5, 0, 5, "rgba(183,28,28,0.08)", ""),
        (2.5, 4.5, 0, 5, "rgba(249,168,37,0.08)", ""),
        (0.5, 2.5, 5, 10, "rgba(249,168,37,0.08)", ""),
        (2.5, 4.5, 5, 10, "rgba(27,94,32,0.08)", ""),
    ]
    for x0, x1, y0, y1, color, _ in zone_colors:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                      fillcolor=color, line_width=0, layer="below")

    # ゾーンラベル
    fig.add_annotation(x=1.5, y=2.5, text="危機ゾーン", font=dict(color="#b71c1c", size=11), showarrow=False)
    fig.add_annotation(x=3.5, y=2.5, text="財務優先ゾーン", font=dict(color="#e65100", size=11), showarrow=False)
    fig.add_annotation(x=1.5, y=7.5, text="組織改善ゾーン", font=dict(color="#e65100", size=11), showarrow=False)
    fig.add_annotation(x=3.5, y=7.5, text="成長ゾーン", font=dict(color="#1b5e20", size=11), showarrow=False)

    # 企業プロット
    fig.add_trace(go.Scatter(
        x=[fin_x], y=[total],
        mode="markers+text",
        marker=dict(size=22, color=rank_color, symbol="star",
                    line=dict(color="white", width=2)),
        text=["貴社"],
        textposition="top center",
        textfont=dict(size=13, color=rank_color),
        name="診断結果",
    ))

    fig.update_layout(
        height=420,
        xaxis=dict(
            title="財務状況",
            tickvals=[1, 2, 3, 4],
            ticktext=["Ⅰ 危機的", "Ⅱ 要注意\n(債務超過)", "Ⅲ 要注意\n(CF不足)", "Ⅳ 良好"],
            range=[0.5, 4.5],
            showgrid=True, gridcolor="#eeeeee",
        ),
        yaxis=dict(
            title="組織成熟度スコア（点）",
            range=[0, 10],
            showgrid=True, gridcolor="#eeeeee",
            dtick=2,
        ),
        plot_bgcolor="white",
        margin=dict(t=20, b=60, l=60, r=20),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── アドバイス ────────────────────────────────────────────
    st.markdown("---")
    st.subheader("💡 優先して取り組むべきこと")

    advice_map = {
        ("e", "Ⅰ"): "まず月次試算表の整備と資金繰り表の作成を最優先に。外部専門家（中小企業診断士・税理士）への相談を強く推奨します。",
        ("e", "Ⅱ"): "財務は黒字基調ですが、経営管理が機能していません。事業計画の策定と月次モニタリングの仕組みを作ることが急務です。",
        ("e", "Ⅲ"): "売上・利益は出ていますが、見える化がなければ持続できません。KPI設定と月次振り返りの習慣化から始めましょう。",
        ("e", "Ⅳ"): "財務は良好。今こそ組織の仕組み化に投資する好機です。手順書整備とKPI管理から着手しましょう。",
        ("d", "Ⅰ"): "財務改善と同時に、業務手順の最低限の文書化に着手してください。一つのコア業務から始めることを推奨します。",
        ("d", "Ⅱ"): "手順書の整備と月次決算の早期化に取り組みましょう。債務超過の解消に向けた財務計画も同時進行で。",
        ("d", "Ⅲ"): "経営管理の基盤が弱い状態。手順書整備と月次振り返りを定着させ、CF改善につなげることが重要です。",
        ("d", "Ⅳ"): "財務は安定。業務手順書の整備とKPI管理を進め、組織力を高めましょう。",
        ("c", "Ⅰ"): "財務危機の中でも組織の基盤はあります。資金繰りを最優先にしながら、見える化による早期異常検知を強化してください。",
        ("c", "Ⅱ"): "手順書はあるが活用しきれていません。財務改善と並行して、振り返り会議の定例化に取り組みましょう。",
        ("c", "Ⅲ"): "組織管理はある程度機能しています。CF不足の原因を月次で追跡し、改善アクションを明確化しましょう。",
        ("c", "Ⅳ"): "財務・組織ともに中間段階。KPIの精度向上と改善サイクルの仕組み化で次のステージへ進めます。",
        ("b", "Ⅰ"): "経営管理は機能していますが、財務が危機的。データに基づいた迅速な財務改善アクションが求められます。",
        ("b", "Ⅱ"): "管理体制は良好。債務超過解消に向けた計画的な利益積み上げと資本増強策を検討しましょう。",
        ("b", "Ⅲ"): "組織力は高い。キャッシュフロー不足の原因を特定し、収益構造の改善に経営資源を集中させましょう。",
        ("b", "Ⅳ"): "優良ステージです。さらなる成長に向けて、新規事業開発や人材育成への投資を検討する段階です。",
        ("a", "Ⅰ"): "組織能力は最高ランクですが財務が危機的。組織力を活かして財務立て直しに全集中してください。",
        ("a", "Ⅱ"): "管理体制は完成度が高い。債務超過解消に向けた戦略的な資本政策に取り組みましょう。",
        ("a", "Ⅲ"): "組織は優秀。CF不足の根本原因を分析し、収益モデルの転換や価格戦略を検討してください。",
        ("a", "Ⅳ"): "理想的なポジションです。持続的成長と事業承継・拡大投資を視野に入れた経営計画を策定しましょう。",
    }

    advice = advice_map.get((rank, fin_rank), "引き続き経営管理の仕組みを強化し、継続的な改善サイクルを維持してください。")
    resche_note = "\n\n⚠️ **リスケ中のため、金融機関との返済計画の再交渉・条件変更が急務です。**" if resche else ""

    st.info(advice + resche_note)

    # ── 各項目スコア内訳 ────────────────────────────────────
    st.markdown("---")
    st.subheader("📋 項目別スコア内訳")
    labels = [item["label"] for item in ITEMS]
    fig2 = go.Figure(go.Bar(
        x=scores,
        y=labels,
        orientation="h",
        marker_color=[
            "#1b5e20" if s == 2 else "#f9a825" if s == 1 else "#b71c1c"
            for s in scores
        ],
        text=[{2: "ある（2点）", 1: "不十分（1点）", 0: "ない（0点）"}[s] for s in scores],
        textposition="inside",
    ))
    fig2.update_layout(
        height=260,
        xaxis=dict(range=[0, 2.5], dtick=1, title="スコア"),
        yaxis=dict(autorange="reversed"),
        margin=dict(t=10, b=40, l=10, r=10),
        plot_bgcolor="white",
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.caption("※ 本診断はあくまで簡易的な自己評価ツールです。詳細な経営診断は専門家にご相談ください。")


# ルーティング
# ============================================================
if page == "📊 総合概要":
    page_overview()
elif page == "👥 人口動態":
    page_population()
elif page == "🏭 産業構造":
    page_industry()
elif page == "💰 経済指標":
    page_economy()
elif page == "🏘️ 市町村比較":
    page_municipal()
elif page == "🔎 業種別分析":
    page_industry_analysis()
elif page == "📋 特定業種支援ガイド":
    page_industry_detail()
elif page == "📊 業種別生産性分析":
    page_industry_census()
elif page == "🗺️ 産業×市町村マトリックス":
    page_industry_matrix()
elif page == "🔗 川上・川下フロー分析":
    page_supply_chain()
elif page == "🗾 東北4県比較":
    page_tohoku()
elif page == "📈 地域市場シェア分析":
    page_market_share()
elif page == "🏛️ 政策提言":
    page_policy()
elif page == "💴 補助金カレンダー":
    page_subsidies()
elif page == "🏢 組織成熟度診断":
    page_maturity_diagnosis()
elif page == "📉 開業・廃業動態":
    page_openclose()
elif page == "👴 後継者問題・廃業リスク":
    page_successor()
elif page == "👷 労働市場（最低賃金・求人倍率）":
    page_labor_market()
elif page == "🔌 e-Stat API連携":
    page_estat()
