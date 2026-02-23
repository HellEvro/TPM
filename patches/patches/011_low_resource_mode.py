"""
Патч 011: добавление LOW_RESOURCE_MODE в SystemConfig (configs/bot_config.py и bot_config.example.py).
Режим для слабых ПК — уменьшает параллелизм загрузки свечей (batch 25, 3 воркера вместо 100/10).
"""
from pathlib import Path

OLD = "\n    AI_MEMORY_PCT = "
NEW = "\n    LOW_RESOURCE_MODE = False   # True = режим для слабых ПК (меньше параллелизм загрузки)\n    AI_MEMORY_PCT = "


def _apply_to_file(path: Path) -> bool:
    """Добавляет LOW_RESOURCE_MODE в SystemConfig. Возвращает True если применили или уже есть."""
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if "LOW_RESOURCE_MODE" in text:
        return True
    if OLD not in text:
        return False
    path.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    return True


def apply(project_root: Path) -> bool:
    config_path = project_root / "configs" / "bot_config.py"
    example_path = project_root / "configs" / "bot_config.example.py"
    _apply_to_file(config_path)
    _apply_to_file(example_path)
    return True
