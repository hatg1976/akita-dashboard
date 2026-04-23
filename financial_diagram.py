"""
決算書図解ツール - BSとP/Lブロック図（Plotly shapes版）
Excelテンプレート「財務分析（Ver.5.2）.xlsx」のブロック図シートを再現
"""

import streamlit as st
import plotly.graph_objects as go


# ─────────────────────────────────────────────────────────────────
# X レイアウト定数
#   BS_A ─ BS_L（隙間なし） ─ [ギャップ] ─ REV ─ MAIN ─ FIX ─ SUB ─ RT ─ CF
# ─────────────────────────────────────────────────────────────────
BS_A  = (0,   95)     # 資産列
BS_L  = (95,  190)    # 負債・純資産列（隙間なし）
# ← ここに BS/PL ギャップ（40px）→
REV   = (230, 275)    # 売上高ラベル列（薄い色付き）
MAIN  = (275, 465)    # 変動費 / 粗利益
FIX   = (465, 615)    # 固定費（隙間なし）
SUB   = (615, 755)    # 人件費・営業外費用・減価償却費（隙間なし）
RT    = (755, 855)    # 経常利益（隙間なし）
CF    = (855, 955)    # 当期純利益＋減価償却費（隙間なし）
W     = 970


# ─────────────────────────────────────────────────────────────────
# ブロック図描画コア
# ─────────────────────────────────────────────────────────────────

def _draw_block_diagram(bs, pl, year_label, unit_label):
    """1年分のブロック図を Plotly Figure で返す。"""

    # ── 値の取り出し ──────────────────────────────────────────────
    curr_a = bs["流動資産"]
    fix_a  = bs["固定資産"]
    def_a  = bs["繰延資産"]
    curr_l = bs["流動負債"]
    fix_l  = bs["固定負債"]
    eqy    = bs["純資産"]
    total_a = curr_a + fix_a + def_a

    rev     = pl["売上高"]
    var     = pl["変動費"]
    fix     = pl["固定費"]
    non_rev = pl["営業外収益"]
    non_exp = pl["営業外費用"]
    sp_gn   = pl["特別利益"]
    sp_ls   = pl["特別損失"]
    tax     = pl["法人税等"]
    jinken  = pl.get("人件費", 0)
    deprec  = pl.get("減価償却費", 0)

    gross   = rev - var
    gross_r = gross / rev if rev else 0
    ord_p   = gross - fix + non_rev - non_exp
    pre_tax = ord_p + sp_gn - sp_ls
    net     = pre_tax - tax
    bep     = fix / gross_r if gross_r > 0 else None
    rodo    = jinken / gross if gross > 0 else 0

    # ── Y 座標 ────────────────────────────────────────────────────
    # BS は P/L（売上高）と同じ高さになるようスケール
    sc = rev / total_a if total_a else 1.0

    ca_top = rev;     ca_bot = rev - curr_a * sc
    fa_top = ca_bot;  fa_bot = def_a * sc
    da_top = fa_bot;  da_bot = 0.0

    cl_top = rev;     cl_bot = rev - curr_l * sc
    fl_top = cl_bot;  fl_bot = eqy * sc
    eq_top = fl_bot;  eq_bot = 0.0

    var_top = rev;    var_bot = gross
    gro_top = gross;  gro_bot = 0.0

    # 固定費ブロック
    fc_top  = min(gross, fix)   # 粗利益超過分はクリップ
    fc_bot  = 0.0
    overflow = max(0.0, fix - gross)

    # 利益エリア（固定費が粗利益内に収まる場合）
    pr_top = gross if fix <= gross else 0.0
    pr_bot = fc_top

    # サブ項目（上から順に）
    sub_cur = fc_top

    def _sub(h):
        nonlocal sub_cur
        top = sub_cur
        bot = max(0.0, sub_cur - h)
        sub_cur = bot
        return top, bot

    j_top,  j_bot  = _sub(min(jinken,  fc_top))   if jinken  > 0 else (0, 0)
    ne_top, ne_bot = _sub(min(non_exp, sub_cur))   if non_exp > 0 else (0, 0)
    dp_top, dp_bot = _sub(min(deprec,  sub_cur))   if deprec  > 0 else (0, 0)

    # ── ヘルパー ──────────────────────────────────────────────────
    shapes, anns = [], []

    def rect(xs, y0, y1, fill, lclr="#444", lw=0.8):
        if y1 <= y0:
            return
        shapes.append(dict(
            type="rect", x0=xs[0], y0=y0, x1=xs[1], y1=y1,
            fillcolor=fill, line=dict(color=lclr, width=lw), layer="below",
        ))

    def ann(x, y, txt, sz=9, clr="#222", xa="center", ya="middle",
            bg=None, bc=None, bold=False):
        t = f"<b>{txt}</b>" if bold else txt
        a = dict(x=x, y=y, text=t, showarrow=False,
                 font=dict(size=sz, color=clr),
                 xanchor=xa, yanchor=ya, align="center")
        if bg:
            a.update(bgcolor=bg, bordercolor=bc or "#888", borderwidth=1, borderpad=3)
        anns.append(a)

    def box(xs, y0, y1, txt, sz=9, clr="#222", bold=False, min_r=0.04):
        if y1 - y0 < rev * min_r or y1 <= y0:
            return
        ann((xs[0]+xs[1])/2, (y0+y1)/2, txt, sz, clr, bold=bold)

    def hline(xs, y, clr="#444", lw=1.0):
        shapes.append(dict(type="line", x0=xs[0], y0=y, x1=xs[1], y1=y,
                           line=dict(color=clr, width=lw)))

    # ── BS 描画 ───────────────────────────────────────────────────
    rect(BS_A, ca_bot, ca_top, "#4472C4", "#2F528F")
    box( BS_A, ca_bot, ca_top, f"流動資産<br>{curr_a:,.0f}", 9, "white", True)

    rect(BS_A, fa_bot, fa_top, "#2E5A9E", "#1F3F72")
    box( BS_A, fa_bot, fa_top, f"固定資産<br>{fix_a:,.0f}",  9, "white", True)

    if def_a * sc > rev * 0.02:
        rect(BS_A, da_bot, da_top, "#A9C4E8", "#2F528F")
        box( BS_A, da_bot, da_top, f"繰延資産<br>{def_a:,.0f}", 8, "#1a1a1a")

    rect(BS_L, cl_bot, cl_top, "#FF6B6B", "#C0392B")
    box( BS_L, cl_bot, cl_top, f"流動負債<br>{curr_l:,.0f}", 9, "white", True)

    rect(BS_L, fl_bot, fl_top, "#C0392B", "#922B21")
    box( BS_L, fl_bot, fl_top, f"固定負債<br>{fix_l:,.0f}",  9, "white", True)

    rect(BS_L, eq_bot, eq_top, "#27AE60", "#1E8449")
    box( BS_L, eq_bot, eq_top, f"純資産<br>{eqy:,.0f}",      9, "white", True)

    # ── 売上高列（REV）────────────────────────────────────────────
    rect(REV, 0, rev, "#BDD7EE", "#2F528F")
    # 営業外収益があれば上に積む
    if non_rev > 0:
        rect(REV, rev, rev + non_rev, "#DDEEFF", "#2F528F")
        box( REV, rev, rev + non_rev, f"営外収益<br>{non_rev:,.0f}", 7, "#1a1a1a")
    ann((REV[0]+REV[1])/2, rev / 2,
        f"売上高<br>{rev:,.0f}", 9, "#1f4e79", bold=True)

    # ── P/L メインブロック（変動費 / 粗利益）────────────────────
    rect(MAIN, var_bot, var_top, "#F4A460", "#C87941")
    box( MAIN, var_bot, var_top, f"変動費<br>{var:,.0f}", 11, "white", True)

    rect(MAIN, gro_bot, gro_top, "#C8E6C9", "#4CAF50")
    box( MAIN, gro_bot, gro_top, f"粗利益<br>{gross:,.0f}", 11, "#1a1a1a", True)

    hline(MAIN, gross, "#333", 1.2)
    hline(MAIN, rev,   "#333", 1.5)

    # ── 固定費ブロック ────────────────────────────────────────────
    rect(FIX, fc_bot, fc_top, "#CD853F", "#8B5E3C")
    box( FIX, fc_bot, fc_top, f"固定費<br>{fix:,.0f}", 9, "white", True)

    if overflow > 0:
        # 固定費が粗利益を超えた分（赤字要因）
        rect(FIX, gross, gross + overflow, "#EF9A9A", "#C62828", 1.2)
        box( FIX, gross, gross + overflow, f"費用超過<br>{overflow:,.0f}", 8, "#7B0000")
    elif pr_top > pr_bot:
        p_clr  = "#66BB6A" if ord_p >= 0 else "#EF9A9A"
        p_tclr = "white"   if ord_p >= 0 else "#7B0000"
        rect(FIX, pr_bot, pr_top, p_clr)
        box( FIX, pr_bot, pr_top,
             f"{'経常利益' if ord_p >= 0 else '経常損失'}<br>{ord_p:,.0f}", 9, p_tclr)

    hline(FIX, gross, "#333", 1.2)
    hline(FIX, rev,   "#aaa", 0.5)

    # ── サブ項目列（人件費・営業外費用・減価償却費）──────────────
    if jinken > 0 and j_top > j_bot:
        rect(SUB, j_bot,  j_top,  "#FFC107", "#E6A800")
        box( SUB, j_bot,  j_top,  f"人件費<br>{jinken:,.0f}", 8, "#1a1a1a")

    if non_exp > 0 and ne_top > ne_bot:
        rect(SUB, ne_bot, ne_top, "#AB47BC", "#7B1FA2")
        box( SUB, ne_bot, ne_top, f"営業外費用<br>{non_exp:,.0f}", 8, "white")

    if deprec > 0 and dp_top > dp_bot:
        rect(SUB, dp_bot, dp_top, "#FF8A65", "#E64A19")
        box( SUB, dp_bot, dp_top, f"減価償却費<br>{deprec:,.0f}", 8, "white")

    hline(SUB, gross, "#aaa", 0.5)

    # ── 経常利益列 ────────────────────────────────────────────────
    if abs(ord_p) > rev * 0.002:
        p_clr  = "#2E7D32" if ord_p >= 0 else "#C62828"
        p_tclr = "white"
        rect(RT, 0, abs(ord_p), p_clr)
        box( RT, 0, abs(ord_p),
             f"{'経常利益' if ord_p >= 0 else '経常損失'}<br>{ord_p:,.0f}", 8, p_tclr)

    # ── 当期純利益＋減価償却費列 ──────────────────────────────────
    if abs(net) > rev * 0.001:
        n_clr = "#1565C0" if net >= 0 else "#BF360C"
        rect(CF, 0, abs(net), n_clr)
        box( CF, 0, abs(net),
             f"当期純利益<br>{net:,.0f}", 8, "white")

    if deprec > 0 and net >= 0:
        rect(CF, abs(net), abs(net) + deprec, "#29B6F6", "#0277BD")
        box( CF, abs(net), abs(net) + deprec, f"減価償却費<br>{deprec:,.0f}", 7, "white")

    # ── 指標アノテーション ────────────────────────────────────────
    ann((MAIN[0]+MAIN[1])/2, -rev * 0.09,
        f"粗利益率=粗利益÷売上高　{gross_r:.1%}",
        9, "#333", bg="#FFFACD", bc="#888")

    if jinken > 0 and gross > 0:
        ann((FIX[0]+SUB[1])/2, -rev * 0.09,
            f"労働分配率=人件費/粗利　{rodo:.1%}",
            9, "#333", bg="#E3F2FD", bc="#888")

    if bep is not None:
        ann(W, rev * 1.12,
            f"損益分岐点売上高=固定費÷粗利益率　{bep:,.0f} {unit_label}",
            9, "#B71C1C", xa="right", ya="top", bg="#FFF9C4", bc="#C00")

    # ── Figure ───────────────────────────────────────────────────
    y_max = rev + max(non_rev, 0)
    fig = go.Figure()
    fig.update_layout(
        shapes=shapes,
        annotations=anns,
        xaxis=dict(range=[-10, W + 10],
                   showgrid=False, showticklabels=False, zeroline=False, fixedrange=True),
        yaxis=dict(range=[-y_max * 0.22, y_max * 1.22],
                   showgrid=False, showticklabels=False, zeroline=False, fixedrange=True),
        title=dict(text=year_label, font=dict(size=15), x=0.5, xanchor="center"),
        height=630,
        margin=dict(l=10, r=10, t=50, b=90),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return fig


# ─────────────────────────────────────────────────────────────────
# Streamlit ページ本体
# ─────────────────────────────────────────────────────────────────

def page_financial():
    st.title("📊 決算書図解ツール")
    st.markdown("BS・P/Lデータを入力するとブロック図で財務構造を可視化します")
    st.markdown("---")

    with st.expander("📝 基本設定・データ入力", expanded=True):
        c1, c2 = st.columns(2)
        unit_label = c1.selectbox("単位", ["千円", "百万円", "億円"])
        n_years    = c2.selectbox("決算期数", [1, 2, 3], index=2)

        # 西暦入力（プレフィックス廃止）
        yr_cols = st.columns(3)
        years = []
        for i in range(3):
            y = yr_cols[i].number_input(
                f"第{i+1}期（西暦）", value=2022 + i,
                min_value=1900, max_value=2100, step=1,
                disabled=(i >= n_years), key=f"year_{i}")
            years.append(int(y))
        year_labels = [f"{years[i]}年度" for i in range(3)]

        st.markdown("---")
        tab_bs, tab_pl = st.tabs(["📋 貸借対照表（BS）", "📈 損益計算書（P/L）"])

        BS_DEF = {
            "流動資産": [650444, 660373, 567365],
            "固定資産": [398050, 392020, 389148],
            "繰延資産": [0, 0, 0],
            "流動負債": [509000, 508291, 371681],
            "固定負債": [408000, 406190, 444266],
            "純資産":   [131494, 137912, 140566],
        }
        PL_DEF = {
            "売上高":     [1321456, 1322205, 1326906],
            "変動費":     [857745,  836013,  860135],
            "固定費":     [491300,  490661,  483706],
            "営業外収益": [15445,   11144,   22940],
            "営業外費用": [54355,   57319,   60437],
            "特別利益":   [2100,    2135,    500],
            "特別損失":   [0,       0,       0],
            "法人税等":   [2544,    6704,    3851],
            "人件費":     [242058,  243446,  210261],
            "減価償却費": [49500,   48057,   47990],
        }

        bs = {k: list(v) for k, v in BS_DEF.items()}
        pl = {k: list(v) for k, v in PL_DEF.items()}

        with tab_bs:
            st.markdown("#### 資産の部")
            cols = st.columns(n_years)
            for i, col in enumerate(cols):
                col.markdown(f"**{year_labels[i]}**")
                for key in ["流動資産", "固定資産", "繰延資産"]:
                    bs[key][i] = col.number_input(
                        key, value=BS_DEF[key][i], step=1000,
                        key=f"bs_{key}_{i}", format="%d")
                ta = sum(bs[k][i] for k in ["流動資産", "固定資産", "繰延資産"])
                col.metric("資産合計", f"{ta:,.0f}")

            st.markdown("#### 負債・純資産の部")
            cols2 = st.columns(n_years)
            for i, col in enumerate(cols2):
                col.markdown(f"**{year_labels[i]}**")
                for key in ["流動負債", "固定負債", "純資産"]:
                    bs[key][i] = col.number_input(
                        key, value=BS_DEF[key][i], step=1000,
                        key=f"bs_{key}_{i}", format="%d")
                tl = sum(bs[k][i] for k in ["流動負債", "固定負債", "純資産"])
                col.metric("負債・純資産合計", f"{tl:,.0f}")

        with tab_pl:
            PL_FIELDS = [
                ("売上高",     "売上高"),
                ("変動費",     "変動費合計（製造原価＋販管費の変動費）"),
                ("固定費",     "固定費合計（製造原価＋販管費の固定費）"),
                ("営業外収益", "営業外収益"),
                ("営業外費用", "営業外費用（支払利息等）"),
                ("特別利益",   "特別利益"),
                ("特別損失",   "特別損失"),
                ("法人税等",   "法人税等"),
                ("人件費",     "人件費（固定費の内訳・任意）"),
                ("減価償却費", "減価償却費（固定費の内訳・任意）"),
            ]
            pl_cols = st.columns(n_years)
            for i, col in enumerate(pl_cols):
                col.markdown(f"**{year_labels[i]}**")
                for key, label in PL_FIELDS:
                    pl[key][i] = col.number_input(
                        label, value=PL_DEF[key][i], step=1000,
                        key=f"pl_{key}_{i}", format="%d")

    # ── ブロック図表示 ─────────────────────────────────────────────
    st.markdown(f"## 財務分析ブロック図　（単位：{unit_label}）")

    for i in range(n_years):
        bs_yr = {k: bs[k][i] for k in bs}
        pl_yr = {k: pl[k][i] for k in pl}
        fig = _draw_block_diagram(bs_yr, pl_yr, year_labels[i], unit_label)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("---")
