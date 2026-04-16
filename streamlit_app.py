import sys
import os
from pathlib import Path

# akita_dashboard のディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

# app.py を実行
exec(open(os.path.join(os.path.dirname(__file__), 'akita_dashboard', 'app.py')).read())
