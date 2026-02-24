"""
Заглушка: конфиг и ключи только в configs/.
  configs/app_config.example.py -> configs/app_config.py
  configs/keys.example.py -> configs/keys.py
app/config.py при копировании сюда реэкспортирует configs.app_config.
"""
# Реальный конфиг в configs/app_config.py (который импортирует configs/keys.py)
from configs.app_config import *  # noqa: F401, F403
