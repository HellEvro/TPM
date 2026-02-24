"""
Патч 013: лаунчер — не удалять configs при git clean и пересоздавать app/config.py после обновления.
Сохраняет configs при git clean; пересоздаёт заглушку app/config.py после обновления.
"""
from pathlib import Path

# Старый фрагмент (без исключений и без вызова _ensure_required_app_files после clean)
OLD_BLOCK = '''            try:
                self._stream_command("git clean", ["git", "clean", "-fd"])
            except subprocess.CalledProcessError:
                pass
        except subprocess.CalledProcessError:'''

# Новый фрагмент
NEW_BLOCK = '''            try:
                # Не удалять ключи и конфиги пользователя — иначе после обновления ключи обнуляются
                self._stream_command(
                    "git clean",
                    [
                        "git", "clean", "-fd",
                        "-e", "configs/keys.py",
                        "-e", "configs/app_config.py",
                        "-e", "configs/bot_config.py",
                    ],
                )
            except subprocess.CalledProcessError:
                pass
            # После clean пересоздать app/config.py (заглушку) и недостающие configs — без перезаписи ключей
            self._ensure_required_app_files()
        except subprocess.CalledProcessError:'''


def apply(project_root: Path) -> bool:
    path = project_root / "launcher" / "infobot_manager.py"
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    # Уже применён
    if "Не удалять ключи и конфиги пользователя" in text:
        return True
    if OLD_BLOCK not in text:
        return True
    text = text.replace(OLD_BLOCK, NEW_BLOCK, 1)
    path.write_text(text, encoding="utf-8")
    return True
