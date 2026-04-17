import sys
from pathlib import Path

# akita_dashboard をパスに追加
sys.path.insert(0, str(Path(__file__).parent / "akita_dashboard"))

# アプリを実行
from app import *
