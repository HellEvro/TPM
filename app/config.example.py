"""
Устарело: пример конфигурации перенесён в configs/.
Используйте: configs/app_config.example.py -> configs/app_config.py
Ключи: configs/keys.example.py -> configs/keys.py

app/config.py — заглушка, реэкспортирующая из configs/ (НЕ используйте app/keys.py).
При копировании этого файла в app/config.py всё будет браться из configs/app_config.py и configs/keys.py.
"""
# Реальный конфиг в configs/app_config.py (который импортирует configs/keys.py)
from configs.app_config import *  # noqa: F401, F403
