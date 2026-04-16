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

from collector import (
    get_sample_population,
    get_sample_migration,
    get_sample_industry,
    get_sample_economy,
    get_sample_municipal,
    get_sample_renewable_energy,
    get_sample_food_manufacturing,
    get_sample_food_trend,
    get_sample_food_challenge,
    get_sample_shotengai,
    get_sample_shotengai_trend,
    get_sample_shotengai_vacancy,
    get_sample_activation_cases,
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
     "🍱 食品製造業", "🏪 商店街", "⚡ 再生可能エネルギー", "📝 施策メモ"],
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
        styled = df_cases.style.applymap(highlight_applicability, subset=["秋田への適用可能性"])
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
elif page == "⚡ 再生可能エネルギー":
    page_renewable()
elif page == "📝 施策メモ":
    page_notes()
