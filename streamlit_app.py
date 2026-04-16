import sys
from pathlib import Path

# akita_dashboard をsys.pathに追加
sys.path.insert(0, str(Path(__file__).parent))

# app.pyを実行
from akita_dashboard.app import *
