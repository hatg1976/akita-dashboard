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

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from financial_diagram import page_financial

from collector import (
    get_sample_population,
    get_sample_migration,
    get_sample_industry,
    get_sample_economy,
    get_sample_municipal,
    get_sample_industry_municipal,
    get_sample_renewable_energy,
    get_sample_food_manufacturing,
    get_sample_food_trend,
    get_sample_food_challenge,
    get_sample_shotengai,
    get_sample_shotengai_trend,
    get_sample_shotengai_vacancy,
    get_sample_activation_cases,
    get_policy_proposals,
    get_policy_kpi,
    get_shindan_actions,
    get_chuokai_actions,
    get_roadmap,
    get_case_studies,
    get_subsidies,
)

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
    ["📊 総合概要", "👥 人口動態", "🏭 産業構造", "💰 経済指標", "🏘️ 市町村比較",
     "🗺️ 業種別ヒートマップ",
     "🍱 食品製造業", "🏪 商店街", "⚡ 再生可能エネルギー",
     "🏛️ 政策提言", "📚 事例研究DB", "💴 補助金カレンダー", "📝 施策メモ",
     "💹 決算書図解"],
)

st.sidebar.markdown("---")

# 市町村比較ページのみスライサーを表示
if page == "🏘️ 市町村比較":
    _df_im_sidebar = get_sample_industry_municipal()
    _all_muni = list(_df_im_sidebar["市町村"].unique())
    _all_ind  = list(_df_im_sidebar["産業大分類"].unique())
    st.sidebar.markdown("### 🗂️ マトリックス絞り込み")
    st.sidebar.multiselect(
        "市町村を選択",
        options=_all_muni,
        default=_all_muni,
        key="matrix_muni",
    )
    st.sidebar.multiselect(
        "業種（産業大分類）を選択",
        options=_all_ind,
        default=_all_ind,
        key="matrix_ind",
    )
    st.sidebar.markdown("---")

st.sidebar.markdown("**データ出典**")
st.sidebar.markdown("- 国勢調査（総務省）")
st.sidebar.markdown("- 住民基本台帳人口移動報告")
st.sidebar.markdown("- 経済センサス（経産省）")
st.sidebar.markdown("- 秋田県統計課")
st.sidebar.markdown("---")
st.sidebar.info("※ 現在はサンプルデータを表示しています。\ne-Stat APIキーを設定すると実データを取得できます。")


# ============================================================
# 総合概要ページ
# ============================================================
def page_overview():
    st.title("📊 秋田県 経済活性化ダッシュボード")
    st.markdown("中小企業診断士による施策提言のための基礎データ集")
    st.markdown("---")

    # KPIカード
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("総人口", "92.0万人", delta="-3.9万人（5年間）", delta_color="inverse")
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

    df_pop = get_sample_population()
    df_mig = get_sample_migration()

    # 人口構造の推移（積み上げ面グラフ）
    st.subheader("人口構造の変化")
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
def _build_matrix(df_raw: pd.DataFrame, sel_muni: list, sel_ind: list) -> pd.DataFrame:
    """ピボットテーブルを作成し、合計行・列に事業所数と構成比を付与して返す。"""
    df = df_raw.copy()
    if sel_muni:
        df = df[df["市町村"].isin(sel_muni)]
    if sel_ind:
        df = df[df["産業大分類"].isin(sel_ind)]

    if df.empty:
        return pd.DataFrame()

    # 選択順を保持したい → 元データ順でソート
    muni_order = [m for m in df_raw["市町村"].unique() if m in df["市町村"].unique()]
    ind_order  = [i for i in df_raw["産業大分類"].unique() if i in df["産業大分類"].unique()]

    pivot = df.pivot_table(
        index="産業大分類", columns="市町村",
        values="事業所数", aggfunc="sum", fill_value=0,
    )
    pivot = pivot.reindex(index=ind_order, columns=muni_order, fill_value=0)

    grand_total = pivot.values.sum()

    # --- 表示用に文字列テーブルへ変換 ---
    display = pivot.astype(str)

    # 横計列（各産業の行合計）
    row_totals = pivot.sum(axis=1)
    display["合計（横計）"] = row_totals.apply(
        lambda v: f"{int(v):,}  ({v / grand_total * 100:.1f}%)" if grand_total else "0"
    )

    # 縦計行（各市町村の列合計）
    col_totals = pivot.sum(axis=0)
    totals_dict = {
        col: f"{int(col_totals[col]):,}  ({col_totals[col] / grand_total * 100:.1f}%)"
        for col in pivot.columns
    }
    totals_dict["合計（横計）"] = f"{int(grand_total):,}  (100%)"
    totals_row = pd.DataFrame(totals_dict, index=["合計（縦計）"])

    result = pd.concat([display, totals_row])
    result.index.name = "産業大分類"
    return result


def page_municipal():
    st.title("🏘️ 市町村比較")
    st.markdown("---")

    df_im = get_sample_industry_municipal()
    sel_muni = st.session_state.get("matrix_muni", list(df_im["市町村"].unique()))
    sel_ind  = st.session_state.get("matrix_ind",  list(df_im["産業大分類"].unique()))

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
    # 産業大分類 × 市町村 事業所数マトリックス
    # ============================================================
    st.markdown("---")
    st.subheader("🏭 産業大分類 × 市町村 事業所数マトリックス")
    st.caption(
        "右端「合計（横計）」= 業種ごとの合計事業所数と全体構成比　"
        "／　最下行「合計（縦計）」= 市町村ごとの合計事業所数と全体構成比"
    )

    if not sel_muni or not sel_ind:
        st.warning("市町村または業種が未選択です。サイドバーで1つ以上選択してください。")
    else:
        matrix_df = _build_matrix(df_im, sel_muni, sel_ind)
        if matrix_df.empty:
            st.warning("該当データがありません。")
        else:
            st.dataframe(
                matrix_df.style.apply(
                    lambda col: [
                        "background-color: #dce6f1; font-weight: bold;"
                        if col.name == "合計（横計）"
                        else ""
                        for _ in col
                    ],
                    axis=0,
                ).apply(
                    lambda row: [
                        "background-color: #dce6f1; font-weight: bold;"
                        if row.name == "合計（縦計）"
                        else ""
                        for _ in row
                    ],
                    axis=1,
                ),
                use_container_width=True,
            )

        # CSVダウンロード（数値版）
        df_num = df_im.copy()
        if sel_muni:
            df_num = df_num[df_num["市町村"].isin(sel_muni)]
        if sel_ind:
            df_num = df_num[df_num["産業大分類"].isin(sel_ind)]
        csv_matrix = df_num.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "📥 マトリックスCSVダウンロード",
            csv_matrix,
            "akita_industry_municipal_matrix.csv",
            "text/csv",
        )


# ============================================================
# 業種別ヒートマップページ
# ============================================================
def page_heatmap():
    st.title("🗺️ 業種別ヒートマップ")
    st.caption("産業大分類 × 市町村の事業所分布をインタラクティブに可視化")
    st.markdown("---")

    df_im = get_sample_industry_municipal()

    # --- コントロール ---
    col1, col2, col3 = st.columns(3)
    with col1:
        normalize = st.selectbox(
            "表示方法",
            ["事業所数（実数）", "市町村内構成比（%）", "業種内シェア（%）"],
        )
    with col2:
        color_scale = st.selectbox(
            "カラースケール",
            ["Blues", "YlOrRd", "Viridis", "RdYlGn"],
        )
    with col3:
        show_values = st.checkbox("数値を表示", value=True)

    # --- ピボット ---
    pivot = df_im.pivot_table(
        index="産業大分類", columns="市町村",
        values="事業所数", aggfunc="sum",
    )

    if normalize == "市町村内構成比（%）":
        pivot_display = (pivot / pivot.sum(axis=0) * 100).round(1)
        color_label = "構成比（%）"
        fmt = ".1f"
    elif normalize == "業種内シェア（%）":
        pivot_display = (pivot.T / pivot.sum(axis=1) * 100).T.round(1)
        color_label = "業種内シェア（%）"
        fmt = ".1f"
    else:
        pivot_display = pivot
        color_label = "事業所数"
        fmt = "d"

    # --- ヒートマップ本体 ---
    fig = px.imshow(
        pivot_display,
        color_continuous_scale=color_scale,
        aspect="auto",
        text_auto=fmt if show_values else False,
        title=f"産業大分類 × 市町村  ―  {color_label}",
        labels={"color": color_label, "x": "市町村", "y": "産業大分類"},
    )
    fig.update_layout(
        height=520,
        xaxis_tickangle=-30,
        coloraxis_colorbar=dict(title=color_label),
        font=dict(size=11),
    )
    fig.update_traces(textfont_size=10)
    st.plotly_chart(fig, use_container_width=True)

    st.caption("💡 セルにカーソルを当てると詳細値が表示されます。列や行を選択してズームも可能です。")

    # --- 担当業種フォーカスビュー ---
    st.markdown("---")
    st.subheader("担当6業種フォーカス")
    st.caption("商業振興課担当業種（小売・卸・飲食・サービス・運送）の市町村別集中度")

    # 担当業種に該当する大分類
    TARGET_INDUSTRIES = [
        "卸売業・小売業",
        "宿泊業・飲食サービス業",
        "運輸業・郵便業",
        "その他サービス業",
    ]
    df_target = df_im[df_im["産業大分類"].isin(TARGET_INDUSTRIES)].copy()

    col1, col2 = st.columns(2)

    with col1:
        # 市町村別の担当業種合計
        df_muni_total = (
            df_target.groupby("市町村")["事業所数"]
            .sum()
            .reset_index()
            .sort_values("事業所数", ascending=True)
        )
        fig2 = px.bar(
            df_muni_total,
            x="事業所数", y="市町村",
            orientation="h",
            color="事業所数",
            color_continuous_scale="Blues",
            text="事業所数",
            title="市町村別 担当業種 合計事業所数",
        )
        fig2.update_traces(texttemplate="%{text:,}件", textposition="outside")
        fig2.update_layout(height=360, coloraxis_showscale=False, xaxis_title="事業所数（件）")
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        # 業種別内訳の積み上げ棒グラフ
        df_stack = df_target.pivot_table(
            index="市町村", columns="産業大分類",
            values="事業所数", aggfunc="sum", fill_value=0,
        ).reset_index()
        df_stack_long = df_target.copy()
        # 市町村を合計順に並べる
        muni_order = df_muni_total.sort_values("事業所数", ascending=False)["市町村"].tolist()
        df_stack_long["市町村"] = pd.Categorical(df_stack_long["市町村"], categories=muni_order, ordered=True)
        df_stack_long = df_stack_long.sort_values("市町村")

        fig3 = px.bar(
            df_stack_long,
            x="市町村", y="事業所数",
            color="産業大分類",
            title="市町村別 業種内訳（担当業種）",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig3.update_layout(height=360, xaxis_tickangle=-30, legend=dict(orientation="h", y=-0.3))
        st.plotly_chart(fig3, use_container_width=True)

    # --- インサイト ---
    st.markdown("---")
    st.subheader("巡回訪問の優先度ヒント")

    # 事業所数上位3市町村を自動算出
    top3 = df_muni_total.sort_values("事業所数", ascending=False).head(3)["市町村"].tolist()
    top_industry_by_muni = (
        df_target.sort_values("事業所数", ascending=False)
        .groupby("市町村")
        .first()
        .reset_index()[["市町村", "産業大分類", "事業所数"]]
    )

    col1, col2, col3 = st.columns(3)
    for col, muni in zip([col1, col2, col3], top3):
        top_ind = top_industry_by_muni[top_industry_by_muni["市町村"] == muni]
        ind_name = top_ind["産業大分類"].values[0] if not top_ind.empty else "—"
        ind_cnt  = int(top_ind["事業所数"].values[0]) if not top_ind.empty else 0
        total_cnt = int(df_muni_total[df_muni_total["市町村"] == muni]["事業所数"].values[0])
        with col:
            st.info(f"**{muni}**\n\n担当業種合計: **{total_cnt:,}件**\n\n最多: {ind_name}（{ind_cnt:,}件）")

    st.dataframe(
        df_target.pivot_table(
            index="産業大分類", columns="市町村",
            values="事業所数", aggfunc="sum", fill_value=0,
        ).style.background_gradient(cmap="Blues", axis=None),
        use_container_width=True,
    )


# ============================================================
# 再生可能エネルギーページ
# ============================================================
def page_renewable():
    st.title("⚡ 再生可能エネルギー")
    st.markdown("---")

    df = get_sample_renewable_energy()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("エネルギー種別 導入量（MW）")
        fig = px.bar(
            df, x="エネルギー種別", y="導入量（MW）",
            color="エネルギー種別",
            text="導入量（MW）",
        )
        fig.update_traces(texttemplate="%{text}MW", textposition="outside")
        fig.update_layout(height=350, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("全国順位")
        fig = go.Figure(go.Bar(
            x=df["全国順位"],
            y=df["エネルギー種別"],
            orientation="h",
            marker_color=["#d62728" if r <= 5 else "#1f77b4" for r in df["全国順位"]],
            text=[f"全国{r}位" for r in df["全国順位"]],
            textposition="outside",
        ))
        fig.update_layout(
            height=350, xaxis_title="全国順位（小さいほど上位）",
            xaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.info("**注目ポイント**: 秋田県の風力発電は全国3位。洋上風力の開発が進めば、エネルギー産業が新たな雇用創出の柱になる可能性があります。")
    st.dataframe(df, use_container_width=True)


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
        from datetime import datetime
        if "memo_log" not in st.session_state:
            st.session_state["memo_log"] = []
        st.session_state["memo_log"].append(
            f"--- {datetime.now().strftime('%Y-%m-%d %H:%M')} ---\n{memo}"
        )
        st.success("メモを保存しました（このセッション中有効）")

    if st.session_state.get("memo_log"):
        st.markdown("**保存済みメモ**")
        for m in reversed(st.session_state["memo_log"]):
            st.text(m)

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
    st.caption("秋田県庁・行政担当者向け戦略提言｜秋田県中小企業団体中央会")
    st.markdown("---")

    df_prop = get_policy_proposals()
    df_kpi  = get_policy_kpi()
    df_action = get_shindan_actions()
    df_reform = get_chuokai_actions()
    df_road = get_roadmap()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🎯 戦略的枠組み", "🌏 第1柱：成長戦略", "🏗️ 第2柱：持続戦略", "📊 KPI・成果指標", "🗺️ ロードマップ"
    ])

    # ========== TAB1: 戦略的枠組み ==========
    with tab1:
        st.subheader("前提認識：直視すべき構造的制約")
        st.error("""
        **以下はすべて政策が制御できない所与の条件である**

        - 人口減少・超高齢化は不可逆的に進行し、内需は縮小し続ける
        - 再生可能エネルギーは収益の県外流出・設備の海外依存・安定供給問題があり地域経済の柱にはなりえない
        - 大企業の自発的立地は期待薄
        - 農業・食品加工の担い手は農業者・農協が中心であり中小企業政策として介入できる範囲は限られる
        - 設備投資も補助金も、使う経営者次第で効果が全く変わる
        """)

        st.subheader("選択肢の絞り込み")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.error("❌ **新産業の創出**\n\n担い手となる人材・企業・資本が不足しており現実的ではない")
        with col2:
            st.error("❌ **全企業への均等支援**\n\n効果が経営者の意欲に大きく左右される以上、資源の分散につながり全体の効果が薄れる")
        with col3:
            st.success("✅ **限られた資源の集中**\n\n効果が出る領域に政策資源を絞ることが秋田の現実に即した唯一の戦略")

        st.markdown("---")
        st.subheader("政策の2本柱＋横断的視点")
        col1, col2 = st.columns(2)
        with col1:
            st.success("""
            ### 第1柱：成長戦略
            **外に売る力をつける**

            内需縮小への根本的な対応として、
            県外・海外に売る力をつけることが核心。

            ● 農業・食品加工の付加価値化と販路拡大
            ● 事業承継による産業集約と強化
            """)
        with col2:
            st.info("""
            ### 第2柱：持続戦略
            **今ある産業を効率化し支え続ける**

            建設・小売・サービス等が地域雇用・
            生活インフラを支え続けられる構造への転換。

            ● 省力化投資の徹底活用と効果測定
            ● 高齢経営者の円滑な出口支援
            """)

        st.markdown("---")
        st.subheader("横断的視点：意欲的な経営者を優先的に深く支援する")
        st.warning("これは公式な選別ではなく、支援機関職員が現場で判断する運用方針である")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.info("**STEP 1 発見**\n\n能動的訪問の中で意欲的な経営者を見つける")
        with col2:
            st.info("**STEP 2 深関与**\n\n深く・長く関わり成功事例を作る")
        with col3:
            st.info("**STEP 3 横展開**\n\n同業・同地域への刺激で波及させる")
        with col4:
            st.info("**STEP 4 循環**\n\n意欲的な経営者が増えるサイクルへ")

    # ========== TAB2: 第1柱：成長戦略 ==========
    with tab2:
        st.subheader("第1柱：成長戦略（外に売る力をつける）")
        st.info("内需が縮小し続ける秋田において、県内市場だけを相手にしている企業の生産性向上には構造的な限界がある。**県外・海外に売る力をつけること**が内需縮小への根本的な対応である。")

        st.markdown("### P01：農業・食品加工の付加価値化と販路拡大")
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("""
            秋田米・比内地鶏等の全国ブランドは実績がある。
            ただし6次産業化は全国的に失敗事例も多く、
            **「加工・販売まで一体でやる」より「得意な段階に集中して連携する」**発想が現実的。
            """)
        with col2:
            st.metric("現状の輸出額", "12億円/年", "目標：25億円（3年後）")

        with st.expander("▶ 具体的な政策", expanded=True):
            st.markdown("""
            1. **加工・販売を担う中小企業と農業者の連携モデルの構築支援**
            2. **首都圏・アジア向け既存販路を持つ企業への輸出対応補助（HACCP等）**
            3. **EC・直販に取り組む事業者への実務的な伴走支援**
            """)

        st.warning("**留意点**：支援対象を「すでに販路開拓に動いている企業」に絞ることが効果を高める。意欲のない事業者への補助は効果が出にくい。")

        st.markdown("---")
        st.markdown("### P02：事業承継を産業集約・強化の機会として活用する")
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("""
            廃業による産業空洞化を防ぐだけでなく、
            **承継のタイミングを「業務を再構築し強い企業に集約する機会」**として活用する。

            特に**第三者承継で外部から来た後継者は、しがらみが少なく意欲的な場合が多く**、
            承継支援が経営者の質の向上にもつながる。
            """)
        with col2:
            st.metric("目標承継件数", "30件/年（3年後）", "現状：15件/年")

        with st.expander("▶ 具体的な政策", expanded=True):
            st.markdown("""
            1. **支援機関・商工団体が後継者不在企業を早期に把握し継続的に関与する**
            2. **第三者承継のマッチングは民間M&A業者と連携して進める**
               （支援機関は案件発掘・関係構築を担い、専門的な財務・法務は外部に委ねる）
            3. **承継を機とした不採算事業の整理・業務の仕組み化を支援する**
            4. **承継後の新経営者への継続的な経営支援をセットで提供する**
            5. **廃業を選択する場合も従業員・取引先への影響を最小化する支援を行う**
            """)

        with st.expander("▶ 成果指標"):
            col1, col2 = st.columns(2)
            with col1:
                st.info("**第三者承継成立件数（年間）**\n現状：15件 → 3年後：30件 → 5年後：50件")
            with col2:
                st.info("**承継後3年間の企業存続率**\n現状：65% → 3年後：80% → 5年後：85%")

    # ========== TAB3: 第2柱：持続戦略 ==========
    with tab3:
        st.subheader("第2柱：持続戦略（今ある産業を効率化し支え続ける）")
        st.info("建設・小売・サービス等は県内雇用・地域生活インフラを支えており、その効率化は不可欠。求めるのは「成長」ではなく、**人口減少・人手不足の中でも地域を支え続けられる構造への転換**である。")

        st.markdown("### P03：省力化投資の徹底活用と効果測定")
        st.markdown("""
        補助金を使って設備を導入することが目的ではなく、
        **「導入後に実際に工数が減ったか」を確認し次につなげること**が目的である。
        """)

        with st.expander("▶ 具体的な政策", expanded=True):
            st.markdown("""
            1. **省力化投資補助金の活用促進**
            2. **導入後の効果測定・フォローアップを支援機関が組織的に実施する**
            3. **成功事例を業種・規模ごとに整理し、類似企業への横展開を図る**
            """)

        with st.expander("▶ 成果指標"):
            col1, col2 = st.columns(2)
            with col1:
                st.info("**省力化投資後の工数削減率**\n現状：未測定 → 3年後：-15%以上 → 5年後：-25%以上")
            with col2:
                st.info("**補助金活用後フォローアップ実施率**\n現状：20% → 3年後：60% → 5年後：80%")

        st.markdown("---")
        st.markdown("### P04：高齢経営者の円滑な出口支援")
        st.markdown("""
        意欲・体力ともに限界を迎えた経営者に対し、
        成長投資を促すより**円滑な事業終了・承継を支援する**方が現実的かつ有効である。
        """)

        with st.expander("▶ 具体的な政策", expanded=True):
            st.markdown("""
            1. **廃業・承継の意思決定を早める働きかけ（5年先を見越した早期接触）**
            2. **廃業時の雇用・取引先への影響を最小化する支援**
            """)

        with st.expander("▶ 成果指標"):
            st.info("**廃業に伴う雇用喪失数の推移**\n現状：未把握 → 3年後：前年比減 → 5年後：減少傾向の確立")

    # ========== TAB4: KPI・成果指標 ==========
    with tab4:
        st.subheader("政策KPI 目標値一覧")
        st.markdown("提言の効果を測るための指標。**実績データの積み上げが行政への予算要請の最も有力な根拠**になる。")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=12, delta={"reference": 0, "suffix": "億円"},
                title={"text": "食品輸出額"},
                gauge={"axis": {"range": [0, 50]},
                       "steps": [{"range": [0, 25], "color": "#ffe699"},
                                  {"range": [25, 50], "color": "#c6efce"}],
                       "threshold": {"value": 25, "line": {"color": "red", "width": 2}},
                       "bar": {"color": "#1f4e79"}},
                number={"suffix": "億円"},
            ))
            fig.update_layout(height=220, margin=dict(t=40, b=10, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=15,
                title={"text": "第三者承継件数/年"},
                gauge={"axis": {"range": [0, 60]},
                       "steps": [{"range": [0, 20], "color": "#ffc7ce"},
                                  {"range": [20, 40], "color": "#ffe699"},
                                  {"range": [40, 60], "color": "#c6efce"}],
                       "threshold": {"value": 30, "line": {"color": "green", "width": 2}},
                       "bar": {"color": "#2ca02c"}},
                number={"suffix": "件"},
            ))
            fig.update_layout(height=220, margin=dict(t=40, b=10, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True)
        with col3:
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=20,
                title={"text": "フォローアップ実施率"},
                gauge={"axis": {"range": [0, 100]},
                       "steps": [{"range": [0, 40], "color": "#ffc7ce"},
                                  {"range": [40, 65], "color": "#ffe699"},
                                  {"range": [65, 100], "color": "#c6efce"}],
                       "threshold": {"value": 60, "line": {"color": "green", "width": 2}},
                       "bar": {"color": "#ff7f0e"}},
                number={"suffix": "%"},
            ))
            fig.update_layout(height=220, margin=dict(t=40, b=10, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True)
        with col4:
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=244,
                title={"text": "一人当たり県民所得"},
                gauge={"axis": {"range": [200, 300]},
                       "steps": [{"range": [200, 260], "color": "#ffc7ce"},
                                  {"range": [260, 275], "color": "#ffe699"},
                                  {"range": [275, 300], "color": "#c6efce"}],
                       "threshold": {"value": 260, "line": {"color": "green", "width": 2}},
                       "bar": {"color": "#1f4e79"}},
                number={"suffix": "万円"},
            ))
            fig.update_layout(height=220, margin=dict(t=40, b=10, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("全指標の目標値")

        def color_pillar(val):
            if val == "第1柱：成長戦略":
                return "background-color:#c6efce;color:#276221"
            elif val == "第2柱：持続戦略":
                return "background-color:#dce6f1;color:#1f4e79"
            return ""

        styled = df_kpi.style.map(color_pillar, subset=["柱"])
        st.dataframe(styled, use_container_width=True)

        csv = df_kpi.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("📥 KPI一覧をCSVダウンロード", csv, "akita_policy_kpi.csv", "text/csv")

        st.markdown("---")
        st.subheader("財源論：支援予算拡充の正当化ロジック")
        col1, col2 = st.columns(2)
        with col1:
            st.success("""
            **投資の論理**

            支援予算の拡充（コスト）
            ↓ 質の高い専門家による支援
            ↓ 企業の生産性向上・売上増加
            ↓ 法人税・事業所税等の税収増加
            ↓ **支援予算を上回る税収増 → 投資として正当化**
            """)
        with col2:
            st.info("""
            **試算の考え方**

            ● 支援前後の売上変化額 × 対象企業数 × 実効税率
            ● 廃業抑制による雇用維持数 × 雇用者1人あたりの税・社会保険収入

            この試算を実績データとして積み上げることが
            予算拡充要請の最も有力な根拠になる。
            """)

    # ========== TAB5: ロードマップ ==========
    with tab5:
        st.subheader("秋田県中小企業政策 施策ロードマップ")
        st.markdown("短期（〜2026）・中期（2027〜2028）・長期（2029〜）の3フェーズで推進する。")

        pillar_colors = {
            "第1柱：成長戦略": "#2ca02c",
            "第2柱：持続戦略": "#1f4e79",
            "支援機関改革": "#ff7f0e",
            "総合": "#9467bd",
        }
        year_map = {
            "2026年度上期": 2026.0, "2026年度": 2026.25, "2026年度下期": 2026.5,
            "2027年度": 2027.0, "2027〜2028年度": 2027.5,
            "2028年度": 2028.0, "2029年度": 2029.0,
            "2030年度": 2030.0, "2031年度": 2031.0,
        }
        df_road["時期_数値"] = df_road["時期"].map(year_map)

        fig = px.scatter(
            df_road,
            x="時期_数値",
            y="施策",
            color="柱",
            symbol="フェーズ",
            size_max=15,
            color_discrete_map=pillar_colors,
            title="施策タイムライン（色：柱、形：フェーズ）",
            labels={"時期_数値": "年度", "施策": ""},
            hover_data={"時期": True, "主体": True, "柱": True, "時期_数値": False},
        )
        fig.update_traces(marker=dict(size=14, line=dict(width=1, color="white")))
        fig.update_layout(height=500, xaxis=dict(tickformat=".0f"))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        for phase, col, desc in [
            ("短期", col1, "2026年度中に着手できる即効施策"),
            ("中期", col2, "2027〜2028年度に本格展開する施策"),
            ("長期", col3, "2029年度以降に成果が出る構造改革"),
        ]:
            df_ph = df_road[df_road["フェーズ"] == phase][["施策", "時期", "主体", "柱"]]
            with col:
                st.markdown(f"**{phase}（{desc}）**")
                st.dataframe(df_ph, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("支援機関の運用転換")
        st.markdown("支援機関は従来の経営指導機能を維持しながら、以下の転換を自らの判断で進める。")

        def color_difficulty(val):
            if val == "低":
                return "background-color:#c6efce;color:#276221"
            elif val == "高":
                return "background-color:#ffc7ce;color:#9c0006"
            return ""

        styled_reform = df_reform[["現状", "あるべき姿", "実施主体", "難易度"]].style.map(
            color_difficulty, subset=["難易度"]
        )
        st.dataframe(styled_reform, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("行政（県庁）への要請事項")
        requests_data = {
            "要請事項": [
                "専門家単価適正化に伴う支援予算の拡充",
                "企業への直接補助スキームの検討",
                "事業承継支援への予算措置",
                "農業・食品加工の販路開拓支援",
            ],
            "内容": [
                "単価引き上げは1件あたりコスト増を招き、同一予算では支援件数が減少する。質の向上を維持しながら支援規模を確保するには予算の裏付けが不可欠",
                "企業が専門家を直接委託し県が補助する仕組み。市場単価での取引が成立し支援の質が上がる",
                "M&A仲介費用補助・承継後経営支援への継続的な予算確保",
                "輸出対応・EC展開に取り組む事業者への集中補助",
            ],
            "備考": [
                "支援機関の実績積み上げ後に説得力を持つ",
                "支援機関の実績積み上げ後に説得力を持つ",
                "即時対応可能",
                "即時対応可能",
            ],
        }
        df_req = pd.DataFrame(requests_data)
        st.dataframe(df_req, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("📄 政策提言書エクスポート")
        if st.button("📊 政策提言Excelを生成"):
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df_prop.to_excel(writer, sheet_name="政策提言一覧", index=False)
                df_kpi.to_excel(writer, sheet_name="KPI目標", index=False)
                df_action.to_excel(writer, sheet_name="能動的支援アクション", index=False)
                df_reform.to_excel(writer, sheet_name="支援機関運用転換", index=False)
                df_road.to_excel(writer, sheet_name="ロードマップ", index=False)
            st.download_button(
                "📥 政策提言書ダウンロード（Excel）",
                buffer.getvalue(),
                "akita_policy_proposal.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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
elif page == "🗺️ 業種別ヒートマップ":
    page_heatmap()
elif page == "🍱 食品製造業":
    page_food()
elif page == "🏪 商店街":
    page_shotengai()
elif page == "⚡ 再生可能エネルギー":
    page_renewable()
elif page == "🏛️ 政策提言":
    page_policy()
elif page == "📚 事例研究DB":
    page_cases()
elif page == "💴 補助金カレンダー":
    page_subsidies()
elif page == "📝 施策メモ":
    page_notes()
elif page == "💹 決算書図解":
    page_financial()
