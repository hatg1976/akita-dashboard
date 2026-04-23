"""
決算書図解ツール - BSとP/Lブロック図（Plotly shapes版）
"""

import streamlit as st
import plotly.graph_objects as go

# ── X レイアウト（均等 135px） ─────────────────────────────────────
BS_A = (0,   95)
BS_L = (95,  190)
REV  = (230, 365)
MAIN = (365, 500)
FIX  = (500, 635)
SUB  = (635, 770)
RT   = (770, 880)
CF   = (880, 990)
W    = 995


def _draw_block_diagram(bs, pl, year_label, unit_label):

    # ── 値の取り出し ────────────────────────────────────────────────
    curr_a  = bs["流動資産"];  fix_a  = bs["固定資産"];  def_a = bs["繰延資産"]
    curr_l  = bs["流動負債"];  fix_l  = bs["固定負債"];  eqy   = bs["純資産"]
    total_a = curr_a + fix_a + def_a

    rev     = pl["売上高"];    var    = pl["変動費"];    fix    = pl["固定費"]
    non_rev = pl["営業外収益"]; non_exp = pl["営業外費用"]
    sp_gn   = pl["特別利益"];  sp_ls  = pl["特別損失"];  tax    = pl["法人税等"]
    jinken  = pl.get("人件費", 0);  deprec = pl.get("減価償却費", 0)

    gross     = rev - var
    gross_r   = gross / rev if rev else 0
    ord_p     = gross - fix + non_rev - non_exp
    pre_tax   = ord_p + sp_gn - sp_ls
    net       = pre_tax - tax
    bep       = fix / gross_r if gross_r > 0 else None
    rodo      = jinken / gross if gross > 0 else 0
    other_fix = max(0.0, fix - jinken - deprec - non_exp)
    overflow  = max(0.0, fix - gross)   # 固定費が粗利益を超えた分

    # ── BS Y 座標（実額・スケールなし）────────────────────────────
    ca_top = total_a;   ca_bot = total_a - curr_a
    fa_top = ca_bot;    fa_bot = def_a
    da_top = def_a;     da_bot = 0.0
    cl_top = total_a;   cl_bot = total_a - curr_l
    fl_top = cl_bot;    fl_bot = eqy
    eq_top = eqy;       eq_bot = 0.0

    # ── P/L Y 座標（売上高=100%基準）──────────────────────────────
    var_top = rev;    var_bot = gross
    gro_top = gross;  gro_bot = 0.0

    # FIX列：固定費は gross まで（超過分は y<0 に表示）
    fc_in_top = gross;  fc_in_bot = 0.0          # 粗利益内の部分
    ov_top    = 0.0;    ov_bot    = -overflow     # 費用超過（y<0）

    # SUB列：上から 人件費 → 減価償却費 → その他固定費 → 営業外費用
    sy = gross
    def _take(h):
        nonlocal sy
        top = sy;  bot = sy - max(0.0, h);  sy = bot;  return top, bot

    j_top,  j_bot  = _take(jinken)
    dp_top, dp_bot = _take(deprec)
    ot_top, ot_bot = _take(other_fix)
    ne_top, ne_bot = _take(non_exp)
    # ne_bot ≈ gross - fix = -overflow ✓

    # RT列（経常利益/損失）：損失は y<0
    # 営業外収益は y=0 の一番下に表示
    # CF列（当期純利益/損失）：損失は y<0
    # 特別利益は y=0 の一番下に表示

    # Y 軸範囲
    y_neg = min(0.0, ov_bot, ord_p if ord_p < 0 else 0, net if net < 0 else 0)
    y_pos = max(rev + max(non_rev, 0.0), total_a)
    y_min = y_neg * 1.35 if y_neg < 0 else -rev * 0.05
    y_max = y_pos * 1.18

    # ── ヘルパー ────────────────────────────────────────────────────
    shapes, anns = [], []

    def rect(xs, y0, y1, fill, lclr="#444", lw=0.8):
        if y1 <= y0:
            return
        shapes.append(dict(type="rect", x0=xs[0], y0=y0, x1=xs[1], y1=y1,
                           fillcolor=fill, line=dict(color=lclr, width=lw), layer="below"))

    def hline(xs, y, clr="#444", lw=1.0):
        shapes.append(dict(type="line", x0=xs[0], y0=y, x1=xs[1], y1=y,
                           line=dict(color=clr, width=lw)))

    def _label(x, y, txt, sz, clr, xa="center", ya="middle",
               bg=None, bc=None, bold=False):
        t = f"<b>{txt}</b>" if bold else txt
        a = dict(x=x, y=y, text=t, showarrow=False,
                 font=dict(size=sz, color=clr),
                 xanchor=xa, yanchor=ya, align="center")
        if bg:
            a.update(bgcolor=bg, bordercolor=bc or "#888", borderwidth=1, borderpad=3)
        anns.append(a)

    def box(xs, y0, y1, txt, sz=9, clr="#222", bold=False, oneline=False):
        """
        ブロック内にラベルを表示。小さいブロックは縮小or引き出し線。
        oneline=True: <br> を空白に変換（横に長い文字列）
        """
        if y1 <= y0:
            return
        h  = y1 - y0
        cx = (xs[0] + xs[1]) / 2
        cy = (y0 + y1) / 2
        t  = txt.replace("<br>", " ") if oneline else txt

        if h >= rev * 0.025:
            _label(cx, cy, t, sz, clr, bold=bold)
        elif h >= rev * 0.008:
            _label(cx, cy, t, max(6, sz - 2), clr, bold=bold)
        else:
            # 極小：右外に引き出し線
            anns.append(dict(x=xs[1] + 3, y=cy,
                             text=t.replace("<br>", " "),
                             showarrow=True, arrowhead=2, arrowsize=0.5,
                             ax=25, ay=0, arrowcolor="#666",
                             font=dict(size=6, color=clr),
                             xanchor="left", yanchor="middle",
                             bgcolor="rgba(255,255,255,0.85)",
                             bordercolor="#aaa", borderwidth=0.5, borderpad=2))

    # ── BS 描画 ─────────────────────────────────────────────────────
    rect(BS_A, ca_bot, ca_top, "#4472C4", "#2F528F")
    box( BS_A, ca_bot, ca_top, f"流動資産<br>{curr_a:,.0f}", 9, "white", True)
    rect(BS_A, fa_bot, fa_top, "#2E5A9E", "#1F3F72")
    box( BS_A, fa_bot, fa_top, f"固定資産<br>{fix_a:,.0f}",  9, "white", True)
    if def_a > 0:
        rect(BS_A, da_bot, da_top, "#A9C4E8", "#2F528F")
        box( BS_A, da_bot, da_top, f"繰延資産<br>{def_a:,.0f}", 8, "#1a1a1a")

    rect(BS_L, cl_bot, cl_top, "#FF6B6B", "#C0392B")
    box( BS_L, cl_bot, cl_top, f"流動負債<br>{curr_l:,.0f}", 9, "white", True)
    rect(BS_L, fl_bot, fl_top, "#C0392B", "#922B21")
    box( BS_L, fl_bot, fl_top, f"固定負債<br>{fix_l:,.0f}",  9, "white", True)
    rect(BS_L, eq_bot, eq_top, "#27AE60", "#1E8449")
    box( BS_L, eq_bot, eq_top, f"純資産<br>{eqy:,.0f}",      9, "white", True)

    # ── REV 列（売上高 + 営業外収益を一番下に）───────────────────
    # 営業外収益（一番下）
    if non_rev > 0:
        rect(REV, 0, non_rev, "#A5D6A7", "#388E3C")
        box( REV, 0, non_rev, f"営業外収益<br>{non_rev:,.0f}", 8, "#1a1a1a")
    # 売上高（その上）
    rect(REV, non_rev, non_rev + rev, "#BDD7EE", "#2F528F")
    box( REV, non_rev, non_rev + rev, f"売上高<br>{rev:,.0f}", 10, "#1f4e79", True)
    hline(REV, non_rev + rev, "#2F528F", 1.5)
    hline(REV, non_rev,       "#2F528F", 1.0)

    # ── MAIN 列（変動費 / 粗利益）────────────────────────────────
    rect(MAIN, var_bot, var_top, "#F4A460", "#C87941")
    box( MAIN, var_bot, var_top, f"変動費<br>{var:,.0f}", 10, "white", True)
    rect(MAIN, gro_bot, gro_top, "#C8E6C9", "#4CAF50")
    box( MAIN, gro_bot, gro_top, f"粗利益<br>{gross:,.0f}", 10, "#1a1a1a", True)
    hline(MAIN, gross, "#333", 1.2)
    hline(MAIN, rev,   "#333", 1.5)

    # ── FIX 列（固定費 + 費用超過を y<0 に）──────────────────────
    rect(FIX, fc_in_bot, fc_in_top, "#CD853F", "#8B5E3C")
    box( FIX, fc_in_bot, fc_in_top, f"固定費<br>{fix:,.0f}", 9, "white", True)
    if overflow > 0:
        rect(FIX, ov_bot, ov_top, "#EF9A9A", "#C62828", 1.2)
        box( FIX, ov_bot, ov_top, f"費用超過<br>{overflow:,.0f}", 8, "#7B0000")
    hline(FIX, gross, "#333", 1.0)
    hline(FIX, rev,   "#aaa", 0.4)

    # ── SUB 列（人件費→減価償却費→その他固定費→営業外費用）──────
    if jinken > 0 and j_top > j_bot:
        rect(SUB, j_bot,  j_top,  "#FFC107", "#E6A800")
        box( SUB, j_bot,  j_top,  f"人件費 {jinken:,.0f}", 8, "#1a1a1a", oneline=True)

    if deprec > 0 and dp_top > dp_bot:
        rect(SUB, dp_bot, dp_top, "#FF8A65", "#E64A19")
        box( SUB, dp_bot, dp_top, f"減価償却費 {deprec:,.0f}", 8, "white", oneline=True)

    if other_fix > 0 and ot_top > ot_bot:
        rect(SUB, ot_bot, ot_top, "#78909C", "#546E7A")
        box( SUB, ot_bot, ot_top, f"その他固定費 {other_fix:,.0f}", 8, "white", oneline=True)

    if non_exp > 0:
        rect(SUB, ne_bot, ne_top, "#AB47BC", "#7B1FA2")
        box( SUB, ne_bot, ne_top, f"営業外費用 {non_exp:,.0f}", 8, "white", oneline=True)

    hline(SUB, gross, "#333", 1.0)
    hline(SUB, 0,     "#666", 0.8)
    hline(SUB, rev,   "#aaa", 0.4)

    # ── RT 列（経常利益/損失 + 営業外収益を一番下に）─────────────
    # 営業外収益（y=0 の一番下）
    if non_rev > 0:
        rect(RT, 0, non_rev, "#A5D6A7", "#388E3C")
        box( RT, 0, non_rev, f"営業外収益 {non_rev:,.0f}", 7, "#1a1a1a", oneline=True)

    if ord_p > 0:
        # 利益（営業外収益の上）
        if ord_p > non_rev:
            rect(RT, non_rev, ord_p, "#2E7D32")
        box( RT, max(0, non_rev), ord_p, f"経常利益 {ord_p:,.0f}", 8, "white", oneline=True)
    elif ord_p < 0:
        # 損失（y<0）
        rect(RT, ord_p, 0, "#C62828")
        box( RT, ord_p, 0, f"経常損失 {ord_p:,.0f}", 8, "white", oneline=True)

    hline(RT, 0, "#666", 0.8)

    # ── CF 列（当期純利益/損失 + 特別利益を一番下に）────────────
    # 特別利益（y=0 の一番下）
    if sp_gn > 0:
        rect(CF, 0, sp_gn, "#81D4FA", "#0288D1")
        box( CF, 0, sp_gn, f"特別利益 {sp_gn:,.0f}", 7, "#1a1a1a", oneline=True)

    if net > 0:
        # 利益（特別利益の上）
        if net > sp_gn:
            rect(CF, sp_gn, net, "#1565C0")
        box( CF, max(0, sp_gn), net, f"当期純利益 {net:,.0f}", 8, "white", oneline=True)
    elif net < 0:
        # 損失（y<0）
        rect(CF, net, 0, "#BF360C")
        box( CF, net, 0, f"当期純損失 {net:,.0f}", 8, "white", oneline=True)

    hline(CF, 0, "#666", 0.8)

    # ── 指標アノテーション ─────────────────────────────────────────
    # 粗利益率：REV列とMAIN列の下に
    ann_y = y_min + rev * 0.06
    _label((REV[0]+MAIN[1])/2, ann_y,
           f"粗利益率=粗利益÷売上高　{gross_r:.1%}",
           9, "#333", bg="#FFFACD", bc="#888")

    # 労働分配率：FIX〜SUB列の下に
    if jinken > 0 and gross > 0:
        _label((FIX[0]+SUB[1])/2, ann_y,
               f"労働分配率=人件費/粗利　{rodo:.1%}",
               9, "#333", bg="#E3F2FD", bc="#888")

    # 損益分岐点：右上
    if bep is not None:
        _label(W, y_max * 0.97,
               f"損益分岐点売上高=固定費÷粗利益率　{bep:,.0f} {unit_label}",
               9, "#B71C1C", xa="right", ya="top", bg="#FFF9C4", bc="#C00")

    # ── Figure ────────────────────────────────────────────────────
    fig = go.Figure()
    fig.update_layout(
        shapes=shapes, annotations=anns,
        xaxis=dict(range=[-10, W+10],
                   showgrid=False, showticklabels=False, zeroline=False, fixedrange=True),
        yaxis=dict(range=[y_min, y_max],
                   showgrid=False, showticklabels=False, zeroline=False, fixedrange=True),
        title=dict(text=year_label, font=dict(size=15), x=0.5, xanchor="center"),
        height=650, margin=dict(l=10, r=10, t=50, b=20),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    return fig


# ─────────────────────────────────────────────────────────────────
# Streamlit ページ
# ─────────────────────────────────────────────────────────────────

def page_financial():
    st.title("📊 決算書図解ツール")
    st.markdown("BS・P/Lデータを入力するとブロック図で財務構造を可視化します")
    st.markdown("---")

    with st.expander("📝 基本設定・データ入力", expanded=True):
        c1, c2 = st.columns(2)
        unit_label = c1.selectbox("単位", ["千円", "百万円", "億円"])
        n_years    = c2.selectbox("決算期数", [1, 2, 3], index=2)

        yr_cols = st.columns(3)
        years = []
        for i in range(3):
            y = yr_cols[i].number_input(f"第{i+1}期（西暦）", value=2022+i,
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
                    bs[key][i] = col.number_input(key, value=BS_DEF[key][i],
                        step=1000, key=f"bs_{key}_{i}", format="%d")
                col.metric("資産合計",
                    f"{sum(bs[k][i] for k in ['流動資産','固定資産','繰延資産']):,.0f}")

            st.markdown("#### 負債・純資産の部")
            cols2 = st.columns(n_years)
            for i, col in enumerate(cols2):
                col.markdown(f"**{year_labels[i]}**")
                for key in ["流動負債", "固定負債", "純資産"]:
                    bs[key][i] = col.number_input(key, value=BS_DEF[key][i],
                        step=1000, key=f"bs_{key}_{i}", format="%d")
                col.metric("負債・純資産合計",
                    f"{sum(bs[k][i] for k in ['流動負債','固定負債','純資産']):,.0f}")

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
                    pl[key][i] = col.number_input(label, value=PL_DEF[key][i],
                        step=1000, key=f"pl_{key}_{i}", format="%d")

    st.markdown(f"## 財務分析ブロック図　（単位：{unit_label}）")
    for i in range(n_years):
        bs_yr = {k: bs[k][i] for k in bs}
        pl_yr = {k: pl[k][i] for k in pl}
        fig = _draw_block_diagram(bs_yr, pl_yr, year_labels[i], unit_label)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("---")
