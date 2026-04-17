"""
補助金締切アラートチェックスクリプト
リモートエージェントが実行し、結果をJSON出力する

使い方:
  python check_subsidies.py [--days 30]

出力（標準出力にJSON）:
  {
    "checked_at": "2026-05-01",
    "alert_items": [...],   # 閾値以内の補助金
    "summary": "..."
  }
"""

import json
import sys
from datetime import date, datetime

# 補助金データ（collector.pyと同期）
SUBSIDIES = [
    {
        "name": "ものづくり・商業・サービス生産性向上促進補助金",
        "kind": "国", "limit": "最大1,250万円", "rate": "1/2〜2/3",
        "deadline": "2026-06-30", "next": "2026年秋頃",
        "window": "中小企業基盤整備機構",
        "food": "◎", "shotengai": "○",
        "memo": "設備投資・DX化に最適。秋田県内採択実績多数",
    },
    {
        "name": "IT導入補助金2025",
        "kind": "国", "limit": "最大450万円", "rate": "1/2〜3/4",
        "deadline": "2026-12-31", "next": "2027年春頃",
        "window": "IT導入補助金事務局",
        "food": "○", "shotengai": "◎",
        "memo": "POSシステム・受発注システム導入に最適",
    },
    {
        "name": "小規模事業者持続化補助金",
        "kind": "国", "limit": "最大250万円", "rate": "2/3",
        "deadline": "2026-05-15", "next": "2026年秋頃",
        "window": "商工会・商工会議所",
        "food": "◎", "shotengai": "◎",
        "memo": "商店街の新規出店・販路開拓に活用しやすい",
    },
    {
        "name": "事業再構築補助金",
        "kind": "国", "limit": "最大1.5億円", "rate": "1/2〜3/4",
        "deadline": "2026-07-31", "next": "未定",
        "window": "中小企業庁",
        "food": "○", "shotengai": "○",
        "memo": "新事業分野への進出・業態転換に対応",
    },
    {
        "name": "事業承継・引継ぎ補助金",
        "kind": "国", "limit": "最大800万円", "rate": "1/3〜2/3",
        "deadline": "2026-08-31", "next": "2027年春頃",
        "window": "中小企業庁",
        "food": "◎", "shotengai": "◎",
        "memo": "後継者不在企業のM&A費用・引継ぎ支援",
    },
    {
        "name": "地域未来投資促進補助金",
        "kind": "国", "limit": "補助率1/2以内", "rate": "1/3〜1/2",
        "deadline": "2026-10-31", "next": "2027年春頃",
        "window": "経済産業省",
        "food": "○", "shotengai": "○",
        "memo": "秋田県の重点分野（再エネ・食品等）に加点",
    },
]

ALWAYS_OPEN = [
    "秋田県中小企業設備近代化資金",
    "秋田県創業支援補助金",
    "農商工等連携事業計画",
    "雇用調整助成金（地域特例）",
    "キャリアアップ助成金",
    "秋田県UIターン就業支援補助金",
]


def check(threshold_days: int = 60) -> dict:
    today = date.today()
    alerts = []
    for s in SUBSIDIES:
        try:
            deadline = datetime.strptime(s["deadline"], "%Y-%m-%d").date()
            days_left = (deadline - today).days
            if 0 <= days_left <= threshold_days:
                alerts.append({
                    **s,
                    "days_left": days_left,
                    "urgency": "緊急" if days_left <= 14 else "要注意" if days_left <= 30 else "確認",
                })
        except ValueError:
            pass

    alerts.sort(key=lambda x: x["days_left"])

    lines = [f"【秋田県ダッシュボード】補助金申請期限アラート（{today}）\n"]
    if alerts:
        lines.append(f"⚠️ 申請期限まで {threshold_days} 日以内の補助金が {len(alerts)} 件あります。\n")
        for a in alerts:
            urgency_mark = "🔴" if a["urgency"] == "緊急" else "🟡" if a["urgency"] == "要注意" else "🟢"
            lines.append(f"{urgency_mark} {a['name']}")
            lines.append(f"   締切: {a['deadline']}（残り {a['days_left']} 日）")
            lines.append(f"   補助上限: {a['limit']} ／ 補助率: {a['rate']}")
            lines.append(f"   窓口: {a['window']}")
            lines.append(f"   ポイント: {a['memo']}\n")
        lines.append("通年受付の補助金:")
        for name in ALWAYS_OPEN:
            lines.append(f"  ・{name}")
    else:
        lines.append(f"✅ 現在、申請期限まで {threshold_days} 日以内の補助金はありません。")
        lines.append("\n通年受付の補助金:")
        for name in ALWAYS_OPEN:
            lines.append(f"  ・{name}")

    lines.append(f"\n詳細はダッシュボードでご確認ください。")

    return {
        "checked_at": str(today),
        "threshold_days": threshold_days,
        "alert_count": len(alerts),
        "alert_items": alerts,
        "summary": "\n".join(lines),
    }


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    days = 60
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--days" and i + 1 < len(sys.argv[1:]):
            days = int(sys.argv[i + 2])
    result = check(days)
    print(json.dumps(result, ensure_ascii=False, indent=2))
