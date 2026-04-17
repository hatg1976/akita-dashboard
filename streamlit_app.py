import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "akita_dashboard"))

# app.py を直接インポート（ページのコンテンツを実行）
import app
