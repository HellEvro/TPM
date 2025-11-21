#!/usr/bin/env bash
set -e
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Функция проверки наличия команды
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Функция определения менеджера пакетов
detect_package_manager() {
  if command_exists apt-get; then
    echo "apt"
  elif command_exists yum; then
    echo "yum"
  elif command_exists dnf; then
    echo "dnf"
  elif command_exists pacman; then
    echo "pacman"
  elif command_exists brew; then
    echo "brew"
  else
    echo ""
  fi
}

# Проверка Python
PYTHON_FOUND=0
if command_exists python3; then
  PYTHON_FOUND=1
elif command_exists python; then
  PYTHON_FOUND=1
fi

# Если Python не найден - пытаемся установить
if [ $PYTHON_FOUND -eq 0 ]; then
  PKG_MGR=$(detect_package_manager)
  case "$PKG_MGR" in
    apt)
      echo "[INFO] Установка Python через apt..."
      if sudo apt-get update -qq >/dev/null 2>&1 && sudo apt-get install -y python3 python3-venv >/dev/null 2>&1; then
        command_exists python3 && PYTHON_FOUND=1
      fi
      ;;
    yum)
      echo "[INFO] Установка Python через yum..."
      if sudo yum install -y python3 >/dev/null 2>&1; then
        command_exists python3 && PYTHON_FOUND=1
      fi
      ;;
    dnf)
      echo "[INFO] Установка Python через dnf..."
      if sudo dnf install -y python3 >/dev/null 2>&1; then
        command_exists python3 && PYTHON_FOUND=1
      fi
      ;;
    pacman)
      echo "[INFO] Установка Python через pacman..."
      if sudo pacman -S --noconfirm python >/dev/null 2>&1; then
        command_exists python3 && PYTHON_FOUND=1
      fi
      ;;
    brew)
      echo "[INFO] Установка Python через brew..."
      if brew install python3 >/dev/null 2>&1; then
        command_exists python3 && PYTHON_FOUND=1
      fi
      ;;
  esac
  
  # Если Python всё ещё не найден - выводим сообщение
  if [ $PYTHON_FOUND -eq 0 ]; then
    echo "[ERROR] Python не найден. Пожалуйста, установите Python 3.9+ вручную."
    if [[ "$OSTYPE" == "darwin"* ]]; then
      echo "Для macOS: https://www.python.org/downloads/macos/"
    else
      echo "Для Linux: используйте менеджер пакетов вашего дистрибутива"
    fi
    exit 1
  fi
fi

# Проверка Git (только если Python установлен)
# Git не критичен для запуска, поэтому ошибки установки игнорируем
if ! command_exists git; then
  PKG_MGR=$(detect_package_manager)
  case "$PKG_MGR" in
    apt)
      echo "[INFO] Установка Git через apt..."
      sudo apt-get install -y git >/dev/null 2>&1 || true
      ;;
    yum)
      echo "[INFO] Установка Git через yum..."
      sudo yum install -y git >/dev/null 2>&1 || true
      ;;
    dnf)
      echo "[INFO] Установка Git через dnf..."
      sudo dnf install -y git >/dev/null 2>&1 || true
      ;;
    pacman)
      echo "[INFO] Установка Git через pacman..."
      sudo pacman -S --noconfirm git >/dev/null 2>&1 || true
      ;;
    brew)
      echo "[INFO] Установка Git через brew..."
      brew install git >/dev/null 2>&1 || true
      ;;
  esac
fi

# Безопасная инициализация Git репозитория (если Git установлен)
# Инициализируем БЕЗ pull/fetch, чтобы не перезаписать существующие файлы
if command_exists git && [ ! -d ".git" ]; then
  git init >/dev/null 2>&1
  git branch -m main >/dev/null 2>&1
  # Проверяем, есть ли уже remote origin
  if ! git remote get-url origin >/dev/null 2>&1; then
    # Добавляем remote только если его нет
    git remote add origin git@github.com:HellEvro/TPM_Public.git >/dev/null 2>&1
  fi
fi

# Определение Python для запуска
if [[ -x ".venv/bin/activate" ]]; then
  source ".venv/bin/activate"
  PYTHON_BIN="python"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
  echo "[WARN] Virtual environment not found. Falling back to ${PYTHON_BIN}."
fi
exec "$PYTHON_BIN" launcher/infobot_manager.py "$@"

