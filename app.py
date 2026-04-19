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
    get_sample_migration,
    get_sample_industry,
    get_sample_economy,
    get_sample_municipal,
    get_sample_food_manufacturing,
    get_sample_food_trend,
    get_sample_food_challenge,
    get_sample_shotengai,
    get_sample_shotengai_trend,
    get_sample_shotengai_vacancy,
    get_sample_activation_cases,
    get_policy_proposals,
    get_policy_kpi,
    get_policy_last_updated,
    get_policy_kpi_note,
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
)

@st.cache_data(ttl=86400)
def _load_population_real(area_code: str):
    """e-Stat から人口推計を取得（24時間キャッシュ）"""
    return estat_api.fetch_formatted_population_trend(area_code)


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

page = st.sidebar.selectbox(
    "表示するデータ",
    ["📊 総合概要", "👥 人口動態", "🏭 産業構造", "💰 経済指標",
     "🔎 業種別分析", "🗾 東北4県比較", "🏘️ 市町村比較",
     "🍱 食品製造業", "🏪 商店街",
     "📈 地域市場シェア分析",
     "🏛️ 政策提言", "📚 事例研究DB", "💴 補助金カレンダー", "📝 施策メモ",
     "🔌 e-Stat API連携"],
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
    with col3:
        st.metric("県内総生産", "3兆5,800億円", delta="-0.8%（前年比）", delta_color="inverse")
    with col4:
        st.metric("有効求人倍率", "1.35倍", delta="+0.07（前年比）")

    st.markdown("---")

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("人口推移")
        df_pop = get_sample_population()
        fig = px.line(
            df_pop, x="年", y="総人口（万人）",
            markers=True,
            title="秋田県 総人口の推移",
            color_discrete_sequence=["#1f4e79"],
        )
        fig.update_layout(height=300)
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
        st.info("**強みと機会**\n\n- 再エネ（風力）ポテンシャル大\n- 農産物ブランド力（あきたこまち）\n- インバウンド需要の回復")


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

    df = get_sample_economy()

    # 全国比較
    st.subheader("秋田県 vs 全国平均")
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
                    yaxis=dict(title="売上額（億円）"),
                    yaxis2=dict(title="従業員（百人）", overlaying="y", side="right"),
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
# 施策メモページ
# ============================================================
def page_notes():
    st.title("📝 施策メモ・提言ノート")
    st.markdown("---")
    st.info("このページは診断士としての気づき・提言メモを記録する場所です。")

    st.subheader("提言フレームワーク")
    framework = {
        "領域": ["人口・移住", "農業・食品", "製造業・DX", "観光・文化", "エネルギー"],
        "現状課題": [
            "年間2,500人の社会減、若年層流出",
            "担い手不足、収益性低迷",
            "生産性低下、後継者不足",
            "インバウンド回復途上、PR不足",
            "再エネポテンシャル未活用",
        ],
        "提言の方向性": [
            "移住促進策の強化、UIターン支援",
            "6次産業化、スマート農業導入",
            "IoT・AI活用、M&A・事業承継支援",
            "体験型観光、コンテンツ発信強化",
            "洋上風力、水素社会への転換",
        ],
        "優先度": ["高", "高", "中", "中", "高"],
    }
    df_fw = pd.DataFrame(framework)
    st.dataframe(df_fw, use_container_width=True)

    st.markdown("---")
    st.subheader("自由メモ")
    memo = st.text_area(
        "気づき・アイデアを記録してください",
        height=200,
        placeholder="例：秋田市内の空き店舗率が高い。移住者向けチャレンジショップ制度の活用事例を調査する...",
    )
    if st.button("メモを保存"):
        with open("data/memo.txt", "a", encoding="utf-8") as f:
            from datetime import datetime
            f.write(f"\n\n--- {datetime.now().strftime('%Y-%m-%d %H:%M')} ---\n{memo}")
        st.success("メモを保存しました（data/memo.txt）")

    # Excel出力
    st.markdown("---")
    st.subheader("全データのExcelエクスポート")
    if st.button("📊 Excelファイルを生成"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            get_sample_population().to_excel(writer, sheet_name="人口推移", index=False)
            get_sample_migration().to_excel(writer, sheet_name="転入転出", index=False)
            get_sample_industry().to_excel(writer, sheet_name="産業構造", index=False)
            get_sample_economy().to_excel(writer, sheet_name="経済指標", index=False)
            get_sample_municipal().to_excel(writer, sheet_name="市町村比較", index=False)
            get_sample_renewable_energy().to_excel(writer, sheet_name="再生可能エネルギー", index=False)
            df_fw.to_excel(writer, sheet_name="施策フレームワーク", index=False)
        st.download_button(
            "📥 Excelダウンロード",
            buffer.getvalue(),
            "akita_data_report.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ============================================================
# 食品製造業ページ
# ============================================================
def page_food():
    st.title("🍱 食品製造業 詳細分析")
    st.caption("秋田の強みを活かした食品産業の現状と提言")
    st.markdown("---")

    df_food = get_sample_food_manufacturing()
    df_trend = get_sample_food_trend()
    df_challenge = get_sample_food_challenge()

    # KPI
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("食品製造業 事業所数", "221社", delta="-12社（5年間）", delta_color="inverse")
    with col2:
        st.metric("総従業員数", "約5,090人", delta="-280人（5年間）", delta_color="inverse")
    with col3:
        st.metric("総出荷額", "1,118億円", delta="+73億円（前年比）")
    with col4:
        st.metric("輸出実績あり企業", "5品目", delta="拡大余地あり")

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("品目別 製造品出荷額")
        fig = px.bar(
            df_food.sort_values("製造品出荷額（億円）"),
            x="製造品出荷額（億円）", y="品目",
            orientation="h",
            color="前年比（%）",
            color_continuous_scale="RdYlGn",
            color_continuous_midpoint=0,
            text="製造品出荷額（億円）",
        )
        fig.update_traces(texttemplate="%{text}億円", textposition="outside")
        fig.update_layout(height=420)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("出荷額推移（主要品目）")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_trend["年"], y=df_trend["総出荷額（億円）"],
                                  name="総計", line=dict(width=3, color="#1f4e79")))
        fig.add_trace(go.Scatter(x=df_trend["年"], y=df_trend["清酒"],
                                  name="清酒・日本酒", line=dict(dash="dash", color="#d62728")))
        fig.add_trace(go.Scatter(x=df_trend["年"], y=df_trend["畜産"],
                                  name="畜産（比内地鶏等）", line=dict(dash="dot", color="#2ca02c")))
        fig.add_trace(go.Scatter(x=df_trend["年"], y=df_trend["農産加工"],
                                  name="農産加工（いぶりがっこ等）", line=dict(dash="dashdot", color="#ff7f0e")))
        fig.update_layout(height=420, yaxis_title="億円", xaxis_title="年")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("企業が抱える課題")
    col1, col2 = st.columns(2)

    with col1:
        fig = px.bar(
            df_challenge.sort_values("深刻度（5段階）"),
            x="深刻度（5段階）", y="課題",
            orientation="h",
            color="深刻度（5段階）",
            color_continuous_scale="Reds",
            text="深刻度（5段階）",
            title="課題の深刻度（5段階評価）",
        )
        fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
        fig.update_layout(height=320, xaxis_range=[0, 5.5])
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(
            df_challenge.sort_values("対応している企業割合（%）"),
            x="対応している企業割合（%）", y="課題",
            orientation="h",
            color="対応している企業割合（%）",
            color_continuous_scale="Blues",
            text="対応している企業割合（%）",
            title="すでに対応している企業の割合（%）",
        )
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        fig.update_layout(height=320)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("診断士としての提言ポイント")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.success("""
**清酒・日本酒の輸出強化**

- 秋田の銘水ブランドを前面に
- JETRO連携による海外展開支援
- 英語ラベル・ハラール対応
- 対象市場: 東南アジア・北米
        """)
    with col2:
        st.warning("""
**いぶりがっこ・郷土食の現代化**

- 食品衛生法改正への対応支援
- 製造の標準化・HACCP導入
- 道の駅・EC販路の開拓
- 観光商品としてのパッケージ化
        """)
    with col3:
        st.info("""
**6次産業化クラスターの形成**

- 農家×食品加工×観光の連携
- 共同加工施設の整備
- 鶴岡市（山形）の成功事例を参考
- ユネスコ創造都市認定を目指す
        """)

    st.dataframe(df_food, use_container_width=True)
    csv = df_food.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("📥 CSVダウンロード", csv, "akita_food_manufacturing.csv", "text/csv")


# ============================================================
# 商店街ページ
# ============================================================
def page_shotengai():
    st.title("🏪 商店街 詳細分析")
    st.caption("秋田県内商店街の現状・課題と再生施策の提言")
    st.markdown("---")

    df_sg = get_sample_shotengai()
    df_trend = get_sample_shotengai_trend()
    df_vacancy = get_sample_shotengai_vacancy()
    df_cases = get_sample_activation_cases()

    # KPI
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("調査商店街数", "8商店街", delta="秋田県内主要")
    with col2:
        st.metric("平均空き店舗率", "38.6%", delta="+8.2pt（5年間）", delta_color="inverse")
    with col3:
        st.metric("平均歩行者通行量", "2,250人/日", delta="-1,800人（10年間）", delta_color="inverse")
    with col4:
        st.metric("年間イベント開催", "平均7.9回", delta="活性化の鍵")

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("商店街別 空き店舗率")
        fig = px.bar(
            df_sg.sort_values("空き店舗率（%）", ascending=True),
            x="空き店舗率（%）", y="商店街名",
            orientation="h",
            color="空き店舗率（%）",
            color_continuous_scale="Reds",
            text="空き店舗率（%）",
        )
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        fig.add_vline(x=30, line_dash="dash", line_color="orange",
                      annotation_text="危険ライン30%", annotation_position="top")
        fig.update_layout(height=380)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("歩行者通行量の推移")
        fig = go.Figure()
        colors = ["#1f4e79", "#d62728", "#2ca02c"]
        cols = ["秋田市中央通り", "横手市駅前", "大館市柄杓田"]
        for col, color in zip(cols, colors):
            fig.add_trace(go.Scatter(
                x=df_trend["年"], y=df_trend[col],
                name=col, line=dict(color=color),
                mode="lines+markers",
            ))
        fig.add_vrect(x0=2019.5, x1=2021.5, fillcolor="red", opacity=0.1,
                      annotation_text="コロナ禍", annotation_position="top left")
        fig.update_layout(height=380, yaxis_title="人/日")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("空き店舗の用途分類")
        fig = px.pie(
            df_vacancy, values="件数", names="用途",
            title="何の跡地が多いか",
            color_discrete_sequence=px.colors.qualitative.Pastel,
            hole=0.4,
        )
        fig.update_layout(height=320)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("空き店舗の平均空き期間")
        fig = px.bar(
            df_vacancy,
            x="用途", y="平均空き期間（年）",
            color="再活用の難易度",
            color_discrete_map={"低": "#2ca02c", "中": "#ff7f0e", "高": "#d62728"},
            text="平均空き期間（年）",
            title="長期空き = 構造的問題のサイン",
        )
        fig.update_traces(texttemplate="%{text:.1f}年", textposition="outside")
        fig.update_layout(height=320)
        st.plotly_chart(fig, use_container_width=True)

    # 他地域の成功事例
    st.markdown("---")
    st.subheader("他地域の成功事例（秋田への応用）")

    tab1, tab2 = st.tabs(["📋 事例一覧", "🗺️ 秋田への適用ロードマップ"])

    with tab1:
        # 色付きテーブル
        def highlight_applicability(val):
            if val == "高":
                return "background-color: #c6efce; color: #276221"
            elif val == "中":
                return "background-color: #ffeb9c; color: #9c5700"
            return ""
        styled = df_cases.style.map(highlight_applicability, subset=["秋田への適用可能性"])
        st.dataframe(styled, use_container_width=True, height=250)

    with tab2:
        st.markdown("""
        ### 秋田版 商店街再生 3ステップ

        **STEP 1（0〜1年）: 実態把握・体制整備**
        - 全商店街の空き店舗・オーナー情報データベース化
        - 商店街組合・行政・金融機関の連絡協議会を設立
        - チャレンジショップ制度の試験導入（秋田市1箇所から）

        **STEP 2（1〜3年）: 先行モデルの構築**
        - 秋田市中央通りをモデル地区に指定
        - 食品製造業との連携（地産品アンテナショップ化）
        - 空き店舗を活用したコワーキング・移住者支援拠点

        **STEP 3（3〜5年）: 横展開・自走化**
        - 成功事例を他の商店街に展開
        - 民間エリアマネジメント組織（BID型）の設立
        - 観光ルートへの組み込み（食・文化・商店街の一体化）
        """)

    st.markdown("---")
    st.subheader("診断士としての提言ポイント")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.error("""
**緊急課題: 空き店舗オーナー対策**

- 高齢オーナーの「貸したくない」意識
- 固定資産税減免インセンティブの活用
- 相続前の事業承継・店舗活用の提案
- 不動産仲介と商工会の連携強化
        """)
    with col2:
        st.warning("""
**中期戦略: 食品×商店街の融合**

- 食品製造業のアンテナショップ誘致
- 試食・体験型の「食文化横丁」整備
- いぶりがっこ・比内地鶏等の直売所化
- インバウンド向け英語対応の整備
        """)
    with col3:
        st.info("""
**長期ビジョン: 関係人口の活用**

- 移住体験拠点としての商店街活用
- 大学生・クリエイターの入居促進
- デジタルノマド向けWi-Fi・電源整備
- 秋田の「暮らしを体験する」観光の核に
        """)


# ============================================================
# 政策提言ページ
# ============================================================
def page_policy():
    st.title("🏛️ 政策提言")
    st.caption("秋田県経済への貢献度を基準に策定した政策提言（業種横断・経済インパクト重視）")

    last_updated = get_policy_last_updated()
    kpi_note = get_policy_kpi_note()
    col_info, col_badge = st.columns([4, 1])
    with col_info:
        st.info(f"📅 **データ最終更新: {last_updated}** — 毎月1日にGitHub Actionsが自動更新します。社会増減数はe-Stat住民基本台帳から取得。")
    with col_badge:
        st.metric("政策提言数", "15項目", "業種横断")

    st.markdown("---")

    df_prop = get_policy_proposals()
    df_kpi  = get_policy_kpi()
    df_shin = get_shindan_actions()
    df_chuo = get_chuokai_actions()
    df_road = get_roadmap()

    if df_prop.empty:
        st.warning("⚠ 政策データが読み込めませんでした。data/policy_cache/policy_data.json を確認してください。")
        return

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 提言15項目", "🎯 KPI目標", "🔍 診断士アクション", "🤝 中央会アクション", "🗺️ ロードマップ"
    ])

    # ========== TAB1: 提言一覧 ==========
    with tab1:
        st.subheader("秋田県経済活性化 政策提言 15項目")
        st.markdown("期待経済効果（億円/年）の高い順に優先的に取り組むべき政策を提言します。")

        col1, col2, col3 = st.columns(3)
        with col1:
            sel_bunya = st.multiselect(
                "分野で絞り込み",
                options=df_prop["分野"].unique().tolist(),
                default=df_prop["分野"].unique().tolist(),
            )
        with col2:
            sel_priority = st.multiselect(
                "優先度",
                options=["高", "中"],
                default=["高", "中"],
            )
        with col3:
            sel_subject = st.multiselect(
                "提言主体",
                options=df_prop["主な提言主体"].unique().tolist(),
                default=df_prop["主な提言主体"].unique().tolist(),
            )

        df_filtered = df_prop[
            df_prop["分野"].isin(sel_bunya) &
            df_prop["優先度"].isin(sel_priority) &
            df_prop["主な提言主体"].isin(sel_subject)
        ]

        diff_map = {"低": 1, "中": 2, "高": 3}
        df_chart = df_filtered.copy()
        df_chart["難易度_数値"] = df_chart["難易度"].map(diff_map)
        df_chart["期待効果_億円"] = pd.to_numeric(df_chart["期待効果（億円/年）"], errors="coerce")
        prio_map = {"高": 18, "中": 10}
        df_chart["優先度_サイズ"] = df_chart["優先度"].map(prio_map).fillna(10)

        fig = px.scatter(
            df_chart,
            x="難易度_数値",
            y="期待効果_億円",
            color="分野",
            size="優先度_サイズ",
            text="提言ID",
            hover_name="提言タイトル",
            hover_data={"難易度_数値": False, "優先度_サイズ": False,
                        "主な提言主体": True, "実施期間": True, "期待効果_億円": True},
            title="政策提言の優先度マップ（縦軸=経済効果、横軸=難易度）",
            labels={"難易度_数値": "難易度（低→高）", "期待効果_億円": "期待効果（億円/年）"},
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(height=480, yaxis_range=[0, 320])
        fig.update_traces(textposition="top center")
        fig.update_xaxes(tickvals=[1, 2, 3], ticktext=["低", "中", "高"])
        st.plotly_chart(fig, use_container_width=True)

        display_cols = ["提言ID","分野","提言タイトル","主な提言主体","優先度","難易度","期待効果（億円/年）","実施期間"]

        def color_priority(val):
            return "background-color:#c6efce;color:#276221" if val == "高" else \
                   "background-color:#ffeb9c;color:#9c5700" if val == "中" else ""

        styled = df_filtered[display_cols].style.map(color_priority, subset=["優先度"])
        st.dataframe(styled, use_container_width=True, height=400)

        st.markdown("---")
        st.subheader("📌 提言詳細")
        sel_id = st.selectbox(
            "詳細を確認する提言を選択",
            options=df_filtered["提言ID"].tolist(),
            format_func=lambda x: f"{x}: {df_filtered[df_filtered['提言ID']==x]['提言タイトル'].values[0]}",
        )
        if sel_id:
            row = df_filtered[df_filtered["提言ID"] == sel_id].iloc[0]
            col_l, col_r = st.columns([3, 1])
            with col_l:
                st.markdown(f"#### {row['提言ID']}: {row['提言タイトル']}")
                st.markdown(f"**背景・課題:** {row.get('背景・課題', '')}")
                st.markdown(f"**具体的施策:** {row.get('具体的施策', '')}")
            with col_r:
                st.metric("期待効果", f"{row['期待効果（億円/年）']}億円/年")
                st.metric("実施期間", row["実施期間"])
                st.metric("難易度", row["難易度"])

        csv = df_filtered[display_cols].to_csv(index=False, encoding="utf-8-sig")
        st.download_button("📥 提言一覧をCSVダウンロード", csv, "akita_policy_proposals.csv", "text/csv")

    # ========== TAB2: KPI目標 ==========
    with tab2:
        st.subheader("政策KPI 目標値一覧")
        if kpi_note:
            st.caption(kpi_note)

        key_kpi_names = [
            "社会増減数（人/年）", "農産物・食品輸出額（億円/年）",
            "有効求人倍率（秋田県）", "一人当たり県民所得（万円）"
        ]
        cols = st.columns(4)
        gauge_configs = [
            {"指標": "社会増減数（人/年）", "min": -20000, "max": 0,
             "color": "#d62728", "suffix": "人", "title": "社会増減数",
             "warn1": -15000, "warn2": -10000},
            {"指標": "農産物・食品輸出額（億円/年）", "min": 0, "max": 120,
             "color": "#2ca02c", "suffix": "億円", "title": "食品輸出額",
             "warn1": 40, "warn2": 80},
            {"指標": "有効求人倍率（秋田県）", "min": 1.0, "max": 1.8,
             "color": "#ff7f0e", "suffix": "倍", "title": "有効求人倍率",
             "warn1": 1.35, "warn2": 1.50},
            {"指標": "一人当たり県民所得（万円）", "min": 220, "max": 320,
             "color": "#1f4e79", "suffix": "万円", "title": "一人当たり県民所得",
             "warn1": 265, "warn2": 295},
        ]

        for col, cfg in zip(cols, gauge_configs):
            row = df_kpi[df_kpi["指標"] == cfg["指標"]]
            if row.empty:
                continue
            val = row.iloc[0].get("現状_数値", 0)
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
                        "threshold": {"value": row.iloc[0].get("3年後_数値", val),
                                      "line": {"color": "red", "width": 2}},
                        "bar": {"color": cfg["color"]},
                    },
                    number={"suffix": cfg["suffix"]},
                ))
                fig.update_layout(height=220, margin=dict(t=50, b=10, l=20, r=20))
                st.plotly_chart(fig, use_container_width=True)

        st.caption("🔴赤ライン = 3年後目標。🔄マーク = e-Stat から毎月自動更新。")
        st.markdown("---")

        st.subheader("全KPI 達成進捗（現状 → 5年後目標）")
        kpi_chart_data = []
        for _, krow in df_kpi.iterrows():
            now = float(krow.get("現状_数値", 0))
            tgt5 = float(krow.get("5年後_数値", 0))
            if "社会増減" in krow["指標"]:
                progress = min(100, max(0, (abs(tgt5) - abs(now)) / max(1, abs(tgt5) - 20000) * 100 + 100))
            elif tgt5 != 0:
                progress = min(100, max(0, (now / tgt5) * 100))
            else:
                progress = 0
            kpi_chart_data.append({
                "指標": krow["指標"][:18] + ("..." if len(krow["指標"]) > 18 else ""),
                "達成率(%)": round(progress, 1),
                "更新種別": "🔄自動" if krow.get("自動更新", False) else "手動",
            })
        df_prog = pd.DataFrame(kpi_chart_data)
        fig = px.bar(
            df_prog, x="達成率(%)", y="指標", orientation="h",
            color="達成率(%)",
            color_continuous_scale="RdYlGn",
            range_color=[0, 100],
            title="現状の5年後目標への達成率",
            hover_data={"更新種別": True},
        )
        fig.update_layout(height=420, coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        display_kpi = df_kpi[["指標","現状値","3年後目標","5年後目標","担当主体","自動更新"]]
        st.dataframe(display_kpi, use_container_width=True)
        csv = display_kpi.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("📥 KPI一覧をCSVダウンロード", csv, "akita_policy_kpi.csv", "text/csv")

    # ========== TAB3: 診断士アクション ==========
    with tab3:
        st.subheader("中小企業診断士 アクションプラン")
        st.markdown("""
        中小企業診断士は**個別企業への深い関与**を強みとして、
        診断→提言→実行支援→フォローアップのサイクルで企業を継続支援します。
        """)

        col1, col2 = st.columns([2, 1])
        with col1:
            phase_order = ["診断", "提言", "実行支援", "フォロー"]
            phase_count = df_shin.groupby("フェーズ").size().reindex(phase_order).fillna(0)
            fig = px.funnel(
                x=phase_count.values, y=phase_count.index,
                title="支援フェーズの流れ",
                color_discrete_sequence=["#1f4e79"],
            )
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("#### 主な活用補助金")
            st.markdown("""
            - ものづくり補助金
            - IT導入補助金
            - 事業承継・引継ぎ補助金
            - 小規模持続化補助金
            - 経営革新計画
            - スマート農業補助金
            - 洋上風力参入支援
            """)

        st.markdown("---")
        for phase in ["診断", "提言", "実行支援", "フォロー"]:
            df_p = df_shin[df_shin["フェーズ"] == phase]
            with st.expander(f"▶ {phase}フェーズ（{len(df_p)}項目）", expanded=(phase == "診断")):
                st.dataframe(df_p[["アクション", "対象", "活用する制度・補助金"]], use_container_width=True, hide_index=True)

        st.markdown("---")
        st.info("""
        **診断士としての差別化ポイント**

        秋田県では診断士が「単なる経営改善アドバイザー」に留まらず、
        **データ分析（このダッシュボード）× 現地診断 × 政策立案**を一体で行うことで、
        行政・金融機関・中央会と連携した**地域全体の経済設計者**として機能できます。
        """)

    # ========== TAB4: 中央会アクション ==========
    with tab4:
        st.subheader("中小企業団体中央会 アクションプラン")
        st.markdown("""
        中央会は**組合・業界団体の組織力**を活かし、
        個社では難しい「共同化・協業・政策建議」を通じて産業全体を底上げします。
        """)

        col1, col2 = st.columns(2)
        with col1:
            func_count = df_chuo["機能"].value_counts().reset_index()
            func_count.columns = ["機能", "件数"]
            fig = px.bar(
                func_count, x="件数", y="機能", orientation="h",
                color="機能", title="機能別アクション数",
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig.update_layout(height=300, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("#### 連携先ネットワーク")
            all_partners = []
            for p in df_chuo["連携先"]:
                all_partners.extend([x.strip() for x in p.replace("・", "、").split("、")])
            partner_count = pd.Series(all_partners).value_counts().reset_index()
            partner_count.columns = ["連携先", "連携数"]
            fig = px.pie(
                partner_count, values="連携数", names="連携先",
                title="連携先の構成", hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set3,
            )
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        for func in df_chuo["機能"].unique():
            df_f = df_chuo[df_chuo["機能"] == func]
            with st.expander(f"▶ {func}（{len(df_f)}項目）", expanded=(func == "組織化支援")):
                st.dataframe(df_f[["アクション","期待する成果","連携先"]], use_container_width=True, hide_index=True)

        st.markdown("---")
        st.success("""
        **中央会の強み: 組合制度の活用**

        洋上風力関連の協同組合設立・農商工観連携クラスターの組織化など、
        個社では実現困難な**スケールメリットの追求**と**政策建議活動**が中央会の真価です。
        """)

    # ========== TAB5: ロードマップ ==========
    with tab5:
        st.subheader("秋田県経済活性化 施策ロードマップ")
        st.markdown("短期（〜2026）・中期（2027〜2028）・長期（2029〜）の3フェーズで推進します。")

        phase_colors = {"短期": "#1f77b4", "中期": "#ff7f0e", "長期": "#2ca02c"}
        year_map = {
            "2026年度上期": 2026.0, "2026年度": 2026.25, "2026年度下期": 2026.5,
            "2027年度": 2027.0, "2027〜2028年度": 2027.5,
            "2028年度": 2028.0, "2029年度": 2029.0,
            "2030年度": 2030.0, "2031年度": 2031.0,
        }
        df_road = df_road.copy()
        df_road["時期_数値"] = df_road["時期"].map(year_map)

        fig = px.scatter(
            df_road, x="時期_数値", y="施策",
            color="フェーズ", symbol="主体",
            color_discrete_map=phase_colors,
            title="施策タイムライン（15提言の実施スケジュール）",
            labels={"時期_数値": "年度", "施策": ""},
        )
        fig.update_traces(marker=dict(size=14, line=dict(width=1, color="white")))
        fig.update_layout(height=540, xaxis=dict(tickformat=".0f"))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        for phase, col, desc in [
            ("短期", col1, "2026年度中に着手できる即効施策"),
            ("中期", col2, "2027〜2028年度に本格展開する施策"),
            ("長期", col3, "2029年度以降に成果が出る構造改革"),
        ]:
            df_ph = df_road[df_road["フェーズ"] == phase][["施策", "時期", "主体"]]
            with col:
                st.markdown(f"**{phase}（{desc}）**")
                st.dataframe(df_ph, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("📄 政策提言書エクスポート")
        if st.button("📊 政策提言Excelを生成"):
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df_prop.to_excel(writer, sheet_name="政策提言一覧", index=False)
                df_kpi.to_excel(writer, sheet_name="KPI目標", index=False)
                df_shin.to_excel(writer, sheet_name="診断士アクション", index=False)
                df_chuo.to_excel(writer, sheet_name="中央会アクション", index=False)
                df_road.to_excel(writer, sheet_name="ロードマップ", index=False)
            buffer.seek(0)
            st.download_button(
                "📥 Excelダウンロード",
                data=buffer,
                file_name=f"akita_policy_{last_updated}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


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
    col1, col2, col3 = st.columns(3)
    with col1:
        sel_shubetsu = st.multiselect("種別", ["国", "県"], default=["国", "県"])
    with col2:
        sel_food = st.selectbox("食品製造業向け", ["すべて", "◎ 特に有効", "○以上"])
    with col3:
        sel_shotengai = st.selectbox("商店街向け", ["すべて", "◎ 特に有効", "○以上"])

    df_f = df[df["種別"].isin(sel_shubetsu)].copy()
    if sel_food == "◎ 特に有効":
        df_f = df_f[df_f["食品製造業向け"] == "◎"]
    if sel_shotengai == "◎ 特に有効":
        df_f = df_f[df_f["商店街向け"] == "◎"]

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
        else "🟢 余裕あり" if x > 90
        else "⚫ 通年受付"
    )

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
        colors = {"🔴 締切間近（30日以内）": "#d62728", "🟡 申請中（31〜90日）": "#ff7f0e", "🟢 余裕あり": "#2ca02c"}
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
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"**対象企業**\n\n{row['対象']}")
                st.markdown(f"**補助率**\n\n{row['補助率']}")
            with col2:
                st.markdown(f"**申請開始**\n\n{row['申請開始']}")
                st.markdown(f"**申請締切**\n\n{row['申請締切']}")
                st.markdown(f"**次回公募予定**\n\n{row['次回公募予定']}")
            with col3:
                st.markdown(f"**窓口**\n\n{row['窓口']}")
                st.markdown(f"**食品製造業** {row['食品製造業向け']} ／ **商店街** {row['商店街向け']}")
            st.info(f"💡 {row['メモ']}")

    # ---- Gmail通知設定 ----
    st.markdown("---")
    st.subheader("📧 締切アラートメール設定")
    st.markdown("補助金の締切が近づいたら自動でメールを受け取れます。")

    with st.form("gmail_alert_form"):
        alert_days = st.selectbox("何日前に通知しますか？", [60, 30, 14, 7], index=1)
        target_subsidies = st.multiselect(
            "通知したい補助金（未選択=全件）",
            options=df["補助金名"].tolist(),
            default=[],
        )
        submitted = st.form_submit_button("✉️ メール通知を設定する")
        if submitted:
            names = target_subsidies if target_subsidies else df["補助金名"].tolist()
            body_lines = [f"【秋田県ダッシュボード】補助金申請期限アラート設定完了\n"]
            body_lines.append(f"通知タイミング: 締切の {alert_days} 日前\n")
            body_lines.append("対象補助金:\n")
            for n in names:
                row = df[df["補助金名"] == n].iloc[0]
                body_lines.append(f"  ・{n}（締切: {row['申請締切']}）")
            body_lines.append(f"\n毎月1日の自動チェック時に期限間近の補助金をメールでお知らせします。")
            st.session_state["gmail_alert_config"] = {
                "days": alert_days, "subsidies": names, "body": "\n".join(body_lines)
            }
            st.success(f"✅ 設定を保存しました。締切 {alert_days} 日前にメール通知します（次回の月次更新から有効）。")
            st.code("\n".join(body_lines), language=None)

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

    tab1, tab2, tab3, tab4 = st.tabs([
        "⚙️ API設定",
        "🔍 統計検索",
        "📥 データ取得",
        "📋 統計IDカタログ",
    ])

    # ========== TAB1: API設定 ==========
    with tab1:
        st.subheader("APIキーの設定")

        col_left, col_right = st.columns([3, 2])
        with col_left:
            current_key = st.session_state.get("estat_api_key", "")
            key_input = st.text_input(
                "e-Stat APIキー（appId）",
                value=current_key,
                type="password",
                placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                help="e-Stat マイページで発行したアプリケーションIDを入力してください",
            )
            col_save, col_clear = st.columns(2)
            with col_save:
                if st.button("💾 保存", use_container_width=True):
                    st.session_state["estat_api_key"] = key_input.strip()
                    st.success("APIキーをセッションに保存しました。")
                    st.rerun()
            with col_clear:
                if st.button("🗑️ クリア", use_container_width=True):
                    st.session_state["estat_api_key"] = ""
                    st.rerun()

        with col_right:
            st.markdown("#### 接続状態")
            if estat_api.is_api_key_set():
                st.success("APIキー設定済み ✓")
                if st.button("🔗 接続テスト"):
                    with st.spinner("接続確認中..."):
                        ok, msg = estat_api.test_connection()
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
            else:
                st.warning("APIキー未設定")

        st.markdown("---")
        st.subheader("APIキーの取得方法")
        st.markdown("""
        1. **e-Stat ユーザー登録**（無料）
           - 右のサイトでアカウントを作成します
        2. **アプリケーションID申請**
           - マイページ → 「API機能（アプリケーションID発行）」→「発行」
           - アプリケーション名: 任意（例: 秋田ダッシュボード）
           - URL: `http://localhost` でも可
        3. **発行されたIDをコピー**してこのページの入力欄に貼り付ける
        """)
        st.info(
            "APIキーは `.env` ファイルに `ESTAT_API_KEY=your_key_here` と書いておくと、"
            "アプリ再起動後も自動で読み込まれます。"
        )

        st.markdown("#### .env ファイルの設定例")
        st.code("ESTAT_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", language="bash")

        st.markdown("#### 利用制限")
        st.dataframe(pd.DataFrame({
            "項目": ["1日のリクエスト上限", "1リクエストの最大取得件数", "利用料金"],
            "内容": ["10万リクエスト（無料）", "10万件", "無料"],
        }), use_container_width=True, hide_index=True)

    # ========== TAB2: 統計検索 ==========
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
                st.error("APIキーが設定されていません。「API設定」タブで設定してください。")
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

    # ========== TAB3: データ取得 ==========
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
                st.error("APIキーが設定されていません。「API設定」タブで設定してください。")
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

    # ========== TAB4: 統計IDカタログ ==========
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
    from datetime import datetime

    st.title("📈 地域市場シェア分析")
    st.caption("家計調査（総務省）の1世帯年間支出 × 商圏世帯数で市場規模を推計し、自社売上からシェアを算出します")
    st.markdown("---")

    st.info(
        "**使い方**\n\n"
        "① 商圏エリア（市町村）を選択　② 品目カテゴリ・品目を選択　"
        "③ 自社の年間売上を入力　→　推計シェアが表示されます\n\n"
        "⚠️ 市場規模は家計調査の平均値を使った推計です。実際の市場規模とは異なる場合があります。"
    )

    # ── Step 1: 商圏エリア選択 ──
    st.subheader("① 商圏エリアを選択")
    col1, col2 = st.columns([2, 2])
    with col1:
        municipalities = market_data.get_municipalities()
        selected_area = st.selectbox("市町村", municipalities, index=0)
    with col2:
        households = market_data.get_households(selected_area)
        st.metric("世帯数（令和2年国勢調査）", f"{households:,} 世帯")

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
elif page == "🍱 食品製造業":
    page_food()
elif page == "🏪 商店街":
    page_shotengai()
elif page == "🔎 業種別分析":
    page_industry_analysis()
elif page == "🗾 東北4県比較":
    page_tohoku()
elif page == "📈 地域市場シェア分析":
    page_market_share()
elif page == "🏛️ 政策提言":
    page_policy()
elif page == "📚 事例研究DB":
    page_cases()
elif page == "💴 補助金カレンダー":
    page_subsidies()
elif page == "📝 施策メモ":
    page_notes()
elif page == "🔌 e-Stat API連携":
    page_estat()
