"""
決算書図解ツール - BSとP/Lブロック図可視化
Excelテンプレート「財務分析（Ver.5.2）.xlsx」のブロック図シートを再現
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd


# ============================================================
# カラーパレット
# ============================================================
BS_COLORS = {
    "流動資産": "#4472C4",
    "固定資産": "#2E4D8A",
    "繰延資産": "#A9C4E8",
    "流動負債": "#FF6B6B",
    "固定負債": "#C0392B",
    "純資産": "#27AE60",
}

PL_COLORS = {
    "変動費": "#F4A460",
    "固定費": "#CD853F",
    "経常利益": "#27AE60",
    "経常損失": "#E74C3C",
}


# ============================================================
# デフォルトデータ（Excelサンプル値）
# ============================================================
def default_bs():
    return {
        "流動資産": [650444, 660373, 567365],
        "固定資産": [398050, 392020, 389148],
        "繰延資産": [0, 0, 0],
        "流動負債": [509000, 508291, 371681],
        "固定負債": [408000, 406190, 444266],
        "純資産": [131494, 137912, 140566],
    }


def default_pl():
    return {
        "売上高": [1321456, 1322205, 1326906],
        "変動費": [857745, 836013, 860135],
        "固定費": [491300, 490661, 483706],
        "営業外収益": [15445, 11144, 22940],
        "営業外費用": [54355, 57319, 60437],
        "特別利益": [2100, 2135, 500],
        "特別損失": [0, 0, 0],
        "法人税等": [2544, 6704, 3851],
    }


# ============================================================
# 指標計算
# ============================================================
def calc_metrics(pl, n_years):
    rows = []
    for i in range(n_years):
        rev = pl["売上高"][i] or 0
        var = pl["変動費"][i] or 0
        fix = pl["固定費"][i] or 0
        non_rev = pl["営業外収益"][i] or 0
        non_exp = pl["営業外費用"][i] or 0
        sp_gain = pl["特別利益"][i] or 0
        sp_loss = pl["特別損失"][i] or 0
        tax = pl["法人税等"][i] or 0

        gross = rev - var
        gross_ratio = gross / rev if rev else 0
        op_profit = rev - var - fix
        ord_profit = op_profit + non_rev - non_exp
        pre_tax = ord_profit + sp_gain - sp_loss
        net = pre_tax - tax
        bep = fix / gross_ratio if gross_ratio else float("inf")
        bep_ratio = bep / rev if rev else float("inf")

        rows.append({
            "粗利益": gross,
            "粗利益率": gross_ratio,
            "営業利益": op_profit,
            "経常利益": ord_profit,
            "税引前当期純利益": pre_tax,
            "当期純利益": net,
            "損益分岐点売上高": bep,
            "損益分岐点比率": bep_ratio,
        })
    return rows


# ============================================================
# BSブロック図
# ============================================================
def make_bs_chart(bs, year_labels, n_years, unit_label):
    asset_items = ["流動資産", "固定資産", "繰延資産"]
    liab_items = ["流動負債", "固定負債", "純資産"]

    # グループ化バー: 各年に (資産バー, 負債純資産バー) を並べる
    x_positions = []
    for i in range(n_years):
        x_positions += [f"{year_labels[i]}<br>資産", f"{year_labels[i]}<br>負債・純資産"]

    fig = go.Figure()

    for item in asset_items:
        vals = []
        for i in range(n_years):
            vals.append(bs[item][i])
            vals.append(None)  # 負債側は空
        fig.add_trace(go.Bar(
            name=item,
            x=x_positions,
            y=vals,
            marker_color=BS_COLORS[item],
            text=[f"{v:,.0f}" if v else "" for v in vals],
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color="white", size=10),
            showlegend=True,
        ))

    for item in liab_items:
        vals = []
        for i in range(n_years):
            vals.append(None)  # 資産側は空
            vals.append(bs[item][i])
        fig.add_trace(go.Bar(
            name=item,
            x=x_positions,
            y=vals,
            marker_color=BS_COLORS[item],
            text=[f"{v:,.0f}" if v else "" for v in vals],
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color="white", size=10),
            showlegend=True,
        ))

    fig.update_layout(
        barmode="stack",
        title=dict(text="貸借対照表（BS）ブロック図", font=dict(size=16)),
        yaxis_title=f"金額（{unit_label}）",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=480,
        plot_bgcolor="white",
        yaxis=dict(gridcolor="#e0e0e0"),
    )
    return fig


# ============================================================
# P/Lブロック図
# ============================================================
def make_pl_chart(pl, metrics, year_labels, n_years, unit_label):
    fig = go.Figure()

    colors_items = [
        ("変動費", PL_COLORS["変動費"]),
        ("固定費", PL_COLORS["固定費"]),
    ]

    for item_name, color in colors_items:
        vals = [pl[item_name][i] for i in range(n_years)]
        fig.add_trace(go.Bar(
            name=item_name,
            x=year_labels[:n_years],
            y=vals,
            marker_color=color,
            text=[f"{v:,.0f}" for v in vals],
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color="white", size=10),
        ))

    # 経常利益（正＝緑、負＝赤）
    profit_vals = [metrics[i]["経常利益"] for i in range(n_years)]
    profit_colors = [PL_COLORS["経常利益"] if v >= 0 else PL_COLORS["経常損失"] for v in profit_vals]
    fig.add_trace(go.Bar(
        name="経常利益",
        x=year_labels[:n_years],
        y=profit_vals,
        marker_color=profit_colors,
        text=[f"{v:,.0f}" for v in profit_vals],
        textposition="outside",
        textfont=dict(size=10),
    ))

    # 売上高ラインをアノテーションで追加
    for i, yr in enumerate(year_labels[:n_years]):
        rev = pl["売上高"][i]
        fig.add_annotation(
            x=yr,
            y=rev,
            text=f"売上高<br>{rev:,.0f}",
            showarrow=True,
            arrowhead=2,
            ax=40,
            ay=-30,
            font=dict(size=9, color="#1f4e79"),
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="#1f4e79",
        )

    fig.update_layout(
        barmode="stack",
        title=dict(text="損益計算書（P/L）コスト構造ブロック図", font=dict(size=16)),
        yaxis_title=f"金額（{unit_label}）",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=480,
        plot_bgcolor="white",
        yaxis=dict(gridcolor="#e0e0e0"),
    )
    return fig


# ============================================================
# P/L構成比チャート（売上高=100%）
# ============================================================
def make_pl_ratio_chart(pl, metrics, year_labels, n_years):
    fig = go.Figure()

    def pct(val, rev):
        return val / rev * 100 if rev else 0

    items = [
        ("変動費", PL_COLORS["変動費"]),
        ("固定費", PL_COLORS["固定費"]),
    ]

    for item_name, color in items:
        vals = [pct(pl[item_name][i], pl["売上高"][i]) for i in range(n_years)]
        fig.add_trace(go.Bar(
            name=item_name,
            x=year_labels[:n_years],
            y=vals,
            marker_color=color,
            text=[f"{v:.1f}%" for v in vals],
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color="white", size=11),
        ))

    profit_vals = [pct(metrics[i]["経常利益"], pl["売上高"][i]) for i in range(n_years)]
    profit_colors = [PL_COLORS["経常利益"] if v >= 0 else PL_COLORS["経常損失"] for v in profit_vals]
    fig.add_trace(go.Bar(
        name="経常利益率",
        x=year_labels[:n_years],
        y=profit_vals,
        marker_color=profit_colors,
        text=[f"{v:.1f}%" for v in profit_vals],
        textposition="outside",
        textfont=dict(size=11),
    ))

    fig.update_layout(
        barmode="stack",
        title=dict(text="P/L構成比（対売上高）", font=dict(size=16)),
        yaxis_title="売上高比（%）",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=380,
        plot_bgcolor="white",
        yaxis=dict(gridcolor="#e0e0e0"),
    )
    return fig


# ============================================================
# 指標テーブル
# ============================================================
def make_metrics_table(pl, bs, metrics, year_labels, n_years, unit_label):
    rows = {}
    labels = year_labels[:n_years]

    def fmt_num(v):
        if abs(v) == float("inf") or v != v:
            return "―"
        return f"{v:,.0f}"

    def fmt_pct(v):
        if abs(v) == float("inf") or v != v:
            return "―"
        return f"{v:.1%}"

    rows["売上高"] = [fmt_num(pl["売上高"][i]) for i in range(n_years)]
    rows["変動費"] = [fmt_num(pl["変動費"][i]) for i in range(n_years)]
    rows["粗利益"] = [fmt_num(metrics[i]["粗利益"]) for i in range(n_years)]
    rows["粗利益率"] = [fmt_pct(metrics[i]["粗利益率"]) for i in range(n_years)]
    rows["固定費"] = [fmt_num(pl["固定費"][i]) for i in range(n_years)]
    rows["営業利益"] = [fmt_num(metrics[i]["営業利益"]) for i in range(n_years)]
    rows["経常利益"] = [fmt_num(metrics[i]["経常利益"]) for i in range(n_years)]
    rows["当期純利益"] = [fmt_num(metrics[i]["当期純利益"]) for i in range(n_years)]
    rows["損益分岐点売上高"] = [fmt_num(metrics[i]["損益分岐点売上高"]) for i in range(n_years)]
    rows["損益分岐点比率"] = [fmt_pct(metrics[i]["損益分岐点比率"]) for i in range(n_years)]

    # BS指標
    total_assets = [bs["流動資産"][i] + bs["固定資産"][i] + bs["繰延資産"][i] for i in range(n_years)]
    equity = [bs["純資産"][i] for i in range(n_years)]
    total_debt = [bs["流動負債"][i] + bs["固定負債"][i] for i in range(n_years)]
    rows["総資産"] = [fmt_num(v) for v in total_assets]
    rows["自己資本比率"] = [fmt_pct(equity[i] / total_assets[i]) if total_assets[i] else "―" for i in range(n_years)]
    rows["負債比率"] = [fmt_pct(total_debt[i] / equity[i]) if equity[i] else "―" for i in range(n_years)]
    roa = [metrics[i]["当期純利益"] / total_assets[i] if total_assets[i] else 0 for i in range(n_years)]
    roe = [metrics[i]["当期純利益"] / equity[i] if equity[i] else 0 for i in range(n_years)]
    rows["ROA（当期純利益÷総資産）"] = [fmt_pct(v) for v in roa]
    rows["ROE（当期純利益÷純資産）"] = [fmt_pct(v) for v in roe]

    df = pd.DataFrame(rows, index=["指標"]).T.reset_index()
    df.columns = ["指標"] + labels
    df.insert(1, "単位", "")
    unit_map = {
        "売上高": unit_label, "変動費": unit_label, "粗利益": unit_label,
        "粗利益率": "%", "固定費": unit_label, "営業利益": unit_label,
        "経常利益": unit_label, "当期純利益": unit_label,
        "損益分岐点売上高": unit_label, "損益分岐点比率": "%",
        "総資産": unit_label, "自己資本比率": "%", "負債比率": "%",
        "ROA（当期純利益÷総資産）": "%", "ROE（当期純利益÷純資産）": "%",
    }
    df["単位"] = df["指標"].map(unit_map)
    return df


# ============================================================
# メインページ関数
# ============================================================
def page_financial():
    st.title("📊 決算書図解ツール")
    st.markdown("BS・P/Lデータを入力して財務構造をブロック図で可視化します")
    st.markdown("---")

    # --------------------------------------------------------
    # 入力セクション
    # --------------------------------------------------------
    with st.expander("📝 基本設定・データ入力", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        company_name = col1.text_input("会社名", "○○株式会社")
        unit_label = col2.selectbox("単位", ["千円", "百万円", "億円"])
        n_years = col3.selectbox("決算期数", [1, 2, 3], index=2)
        yr_prefix = col4.text_input("期名プレフィックス", "X")

        year_cols = st.columns(3)
        year_labels = []
        for i in range(3):
            lbl = year_cols[i].text_input(f"第{i+1}期ラベル", f"{yr_prefix}{i+1}年度",
                                           disabled=(i >= n_years))
            year_labels.append(lbl)

        st.markdown("---")
        tab_bs, tab_pl = st.tabs(["📋 貸借対照表（BS）", "📈 損益計算書（P/L）"])

        bs = default_bs()
        pl = default_pl()

        with tab_bs:
            st.markdown("#### 資産の部")
            bs_cols = st.columns(n_years)
            for yr_i, col in enumerate(bs_cols):
                col.markdown(f"**{year_labels[yr_i]}**")
                bs["流動資産"][yr_i] = col.number_input("流動資産", value=bs["流動資産"][yr_i],
                    step=1000, key=f"ca_{yr_i}", format="%d")
                bs["固定資産"][yr_i] = col.number_input("固定資産", value=bs["固定資産"][yr_i],
                    step=1000, key=f"fa_{yr_i}", format="%d")
                bs["繰延資産"][yr_i] = col.number_input("繰延資産", value=bs["繰延資産"][yr_i],
                    step=1000, key=f"da_{yr_i}", format="%d")
                total_a = bs["流動資産"][yr_i] + bs["固定資産"][yr_i] + bs["繰延資産"][yr_i]
                col.metric("資産合計", f"{total_a:,.0f}")

            st.markdown("#### 負債・純資産の部")
            bs_cols2 = st.columns(n_years)
            for yr_i, col in enumerate(bs_cols2):
                col.markdown(f"**{year_labels[yr_i]}**")
                bs["流動負債"][yr_i] = col.number_input("流動負債", value=bs["流動負債"][yr_i],
                    step=1000, key=f"cl_{yr_i}", format="%d")
                bs["固定負債"][yr_i] = col.number_input("固定負債", value=bs["固定負債"][yr_i],
                    step=1000, key=f"fl_{yr_i}", format="%d")
                bs["純資産"][yr_i] = col.number_input("純資産", value=bs["純資産"][yr_i],
                    step=1000, key=f"eq_{yr_i}", format="%d")
                total_l = bs["流動負債"][yr_i] + bs["固定負債"][yr_i] + bs["純資産"][yr_i]
                col.metric("負債・純資産合計", f"{total_l:,.0f}")

        with tab_pl:
            st.markdown("#### 損益計算書")
            pl_cols = st.columns(n_years)
            pl_fields = [
                ("売上高", "売上高", 1321456),
                ("変動費", "変動費合計（製造原価変動費＋販管費変動費）", 857745),
                ("固定費", "固定費合計（製造原価固定費＋販管費固定費）", 491300),
                ("営業外収益", "営業外収益", 15445),
                ("営業外費用", "営業外費用（支払利息等）", 54355),
                ("特別利益", "特別利益", 2100),
                ("特別損失", "特別損失", 0),
                ("法人税等", "法人税等", 2544),
            ]
            defaults = default_pl()
            for yr_i, col in enumerate(pl_cols):
                col.markdown(f"**{year_labels[yr_i]}**")
                for key, label, _ in pl_fields:
                    pl[key][yr_i] = col.number_input(
                        label, value=defaults[key][yr_i],
                        step=1000, key=f"pl_{key}_{yr_i}", format="%d"
                    )

    # --------------------------------------------------------
    # 計算
    # --------------------------------------------------------
    metrics = calc_metrics(pl, n_years)

    st.markdown(f"## {company_name} 財務分析ブロック図")
    st.caption(f"単位：{unit_label}")

    # --------------------------------------------------------
    # BSブロック図
    # --------------------------------------------------------
    st.subheader("貸借対照表（BS）ブロック図")
    bs_fig = make_bs_chart(bs, year_labels, n_years, unit_label)
    st.plotly_chart(bs_fig, use_container_width=True)

    # --------------------------------------------------------
    # P/Lブロック図（金額 + 構成比）
    # --------------------------------------------------------
    st.subheader("損益計算書（P/L）ブロック図")
    col_pl1, col_pl2 = st.columns(2)
    with col_pl1:
        pl_fig = make_pl_chart(pl, metrics, year_labels, n_years, unit_label)
        st.plotly_chart(pl_fig, use_container_width=True)
    with col_pl2:
        ratio_fig = make_pl_ratio_chart(pl, metrics, year_labels, n_years)
        st.plotly_chart(ratio_fig, use_container_width=True)

    # --------------------------------------------------------
    # 主要指標テーブル
    # --------------------------------------------------------
    st.subheader("主要財務指標")
    df_metrics = make_metrics_table(pl, bs, metrics, year_labels, n_years, unit_label)
    st.dataframe(df_metrics, use_container_width=True, hide_index=True)

    # --------------------------------------------------------
    # MQ分析サマリー（粗利益分析）
    # --------------------------------------------------------
    st.subheader("MQ分析（限界利益分析）")
    mq_data = []
    for i in range(n_years):
        rev = pl["売上高"][i]
        m = metrics[i]
        mq_data.append({
            "期": year_labels[i],
            f"売上高（{unit_label}）": f"{rev:,.0f}",
            f"変動費（{unit_label}）": f"{pl['変動費'][i]:,.0f}",
            f"粗利益=MQ（{unit_label}）": f"{m['粗利益']:,.0f}",
            "粗利益率=M（%）": f"{m['粗利益率']:.1%}",
            f"固定費=F（{unit_label}）": f"{pl['固定費'][i]:,.0f}",
            f"経常利益=P（{unit_label}）": f"{m['経常利益']:,.0f}",
            f"損益分岐点（{unit_label}）": f"{m['損益分岐点売上高']:,.0f}" if m['損益分岐点売上高'] != float('inf') else "―",
            "安全余裕率（%）": f"{(1 - m['損益分岐点比率']):.1%}" if m['損益分岐点比率'] != float('inf') else "―",
        })
    df_mq = pd.DataFrame(mq_data)
    st.dataframe(df_mq, use_container_width=True, hide_index=True)

    # --------------------------------------------------------
    # 損益分岐点チャート
    # --------------------------------------------------------
    if n_years >= 2:
        st.subheader("損益分岐点分析チャート")
        bep_fig = go.Figure()
        bep_vals = [metrics[i]["損益分岐点売上高"] for i in range(n_years)
                    if metrics[i]["損益分岐点売上高"] != float("inf")]
        rev_vals = [pl["売上高"][i] for i in range(n_years)]
        labels_used = year_labels[:n_years]

        bep_fig.add_trace(go.Bar(
            name="売上高",
            x=labels_used,
            y=rev_vals,
            marker_color="#4472C4",
            opacity=0.8,
        ))
        if len(bep_vals) == n_years:
            bep_fig.add_trace(go.Scatter(
                name="損益分岐点売上高",
                x=labels_used,
                y=bep_vals,
                mode="lines+markers",
                line=dict(color="#E74C3C", width=2, dash="dash"),
                marker=dict(size=8),
            ))
        bep_fig.update_layout(
            title="売上高 vs 損益分岐点",
            yaxis_title=f"金額（{unit_label}）",
            height=350,
            plot_bgcolor="white",
            yaxis=dict(gridcolor="#e0e0e0"),
        )
        st.plotly_chart(bep_fig, use_container_width=True)

    # --------------------------------------------------------
    # CSV ダウンロード
    # --------------------------------------------------------
    st.markdown("---")
    csv = df_metrics.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "📥 指標テーブルをCSVダウンロード",
        csv,
        "financial_metrics.csv",
        "text/csv",
    )
