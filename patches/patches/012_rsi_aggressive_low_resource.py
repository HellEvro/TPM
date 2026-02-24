"""
Патч 012: RSI_AGGRESSIVE_LOW_RESOURCE = True в SystemConfig.
Фикс таймаута RSI на слабых ПК: 2 воркера, батч 200, timeout 90с.
"""
from pathlib import Path

RSI_LINE = "    RSI_AGGRESSIVE_LOW_RESOURCE = True   # 2 воркера RSI, батч 200, timeout 90с (на слабых ПК)\n"


def _apply_to_file(path: Path, use_true: bool = True) -> bool:
    """Добавляет RSI_AGGRESSIVE_LOW_RESOURCE в SystemConfig. Возвращает True если применили или уже есть."""
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if "RSI_AGGRESSIVE_LOW_RESOURCE" in text:
        # Уже есть — если False, меняем на True (для bot_config)
        if use_true and "RSI_AGGRESSIVE_LOW_RESOURCE = False" in text:
            text = text.replace(
                "RSI_AGGRESSIVE_LOW_RESOURCE = False",
                "RSI_AGGRESSIVE_LOW_RESOURCE = True",
                1
            )
            path.write_text(text, encoding="utf-8")
        return True
    # Вставляем после LOW_RESOURCE_MODE
    if "LOW_RESOURCE_MODE" in text:
        # Ищем конец строки с LOW_RESOURCE_MODE
        idx = text.find("LOW_RESOURCE_MODE")
        if idx != -1:
            line_end = text.find("\n", idx) + 1
            new_text = text[:line_end] + RSI_LINE + text[line_end:]
            path.write_text(new_text, encoding="utf-8")
            return True
    # Fallback: перед AI_MEMORY_PCT
    if "AI_MEMORY_PCT" in text:
        idx = text.find("AI_MEMORY_PCT")
        new_text = text[:idx] + RSI_LINE + text[idx:]
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def apply(project_root: Path) -> bool:
    config_path = project_root / "configs" / "bot_config.py"
    example_path = project_root / "configs" / "bot_config.example.py"
    ok1 = _apply_to_file(config_path, use_true=True)
    ok2 = _apply_to_file(example_path, use_true=True)
    return ok1 or ok2
