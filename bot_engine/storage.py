"""
Управление хранением данных (RSI кэш, состояние ботов, зрелые монеты)

✅ МИГРАЦИЯ В БД: Все данные теперь хранятся в базе данных (data/bots_data.db)
JSON файлы используются только как fallback для обратной совместимости
"""

import os
import json
import logging
import time
import threading
import importlib
from datetime import datetime

logger = logging.getLogger('Storage')

# Инициализация БД (ленивая загрузка)
_bots_db = None
_bots_db_lock = threading.Lock()

def _get_bots_database():
    """Получает экземпляр базы данных Bots (ленивая инициализация)"""
    global _bots_db
    
    with _bots_db_lock:
        if _bots_db is None:
            try:
                from bot_engine.bots_database import get_bots_database
                _bots_db = get_bots_database()
                logger.debug("✅ Bots Database подключена для storage")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось инициализировать Bots Database: {e}")
                logger.warning("⚠️ Будет использован fallback на JSON файлы")
                _bots_db = None
        
        return _bots_db

# Блокировки файлов для предотвращения одновременной записи
_file_locks = {}
_lock_lock = threading.Lock()

def _get_file_lock(filepath):
    """Получить блокировку для файла"""
    with _lock_lock:
        if filepath not in _file_locks:
            _file_locks[filepath] = threading.Lock()
        return _file_locks[filepath]

# Пути к файлам
RSI_CACHE_FILE = 'data/rsi_cache.json'
BOTS_STATE_FILE = 'data/bots_state.json'
INDIVIDUAL_COIN_SETTINGS_FILE = 'data/individual_coin_settings.json'
MATURE_COINS_FILE = 'data/mature_coins.json'
# ❌ ОТКЛЮЧЕНО: optimal_ema удален (EMA фильтр убран)
# OPTIMAL_EMA_FILE = 'data/optimal_ema.json'
PROCESS_STATE_FILE = 'data/process_state.json'
SYSTEM_CONFIG_FILE = 'data/system_config.json'


def save_json_file(filepath, data, description="данные", max_retries=3):
    """Универсальная функция сохранения JSON с retry логикой"""
    file_lock = _get_file_lock(filepath)
    
    with file_lock:  # Блокируем файл для этого процесса
        for attempt in range(max_retries):
            try:
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                
                # Атомарная запись через временный файл
                temp_file = filepath + '.tmp'
                
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                # Заменяем оригинальный файл
                if os.name == 'nt':  # Windows
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    os.rename(temp_file, filepath)
                else:  # Unix/Linux
                    os.rename(temp_file, filepath)
                
                return True
                
            except (OSError, PermissionError) as e:
                if attempt < max_retries - 1:
                    wait_time = 0.1 * (2 ** attempt)  # Экспоненциальная задержка
                    logger.warning(f" Попытка {attempt + 1} неудачна, повторяем через {wait_time}с: {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f" Ошибка сохранения {description} после {max_retries} попыток: {e}")
                    # Удаляем временный файл
                    if 'temp_file' in locals() and os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                    return False
            except Exception as e:
                logger.error(f" Неожиданная ошибка сохранения {description}: {e}")
                # Удаляем временный файл
                if 'temp_file' in locals() and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                return False


def load_json_file(filepath, default=None, description="данные"):
    """Универсальная функция загрузки JSON с блокировкой"""
    file_lock = _get_file_lock(filepath)
    
    with file_lock:  # Блокируем файл для чтения
        try:
            if not os.path.exists(filepath):
                logger.info(f" Файл {filepath} не найден")
                return default
            
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.debug(f" {description} загружены из {filepath}")
            return data
            
        except Exception as e:
            logger.error(f" Ошибка загрузки {description}: {e}")
            return default


# RSI Cache
def save_rsi_cache(coins_data, stats):
    """Сохраняет RSI кэш в БД (с fallback на JSON)"""
    db = _get_bots_database()
    
    # ПРИОРИТЕТ: Сохраняем в БД
    if db:
        try:
            if db.save_rsi_cache(coins_data, stats):
                logger.debug("💾 RSI кэш сохранен в БД")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения RSI кэша в БД: {e}, используем fallback")
    
    # FALLBACK: Сохраняем в JSON (для обратной совместимости)
    cache_data = {
        'timestamp': datetime.now().isoformat(),
        'coins': coins_data,
        'stats': stats
    }
    return save_json_file(RSI_CACHE_FILE, cache_data, "RSI кэш")


def load_rsi_cache():
    """Загружает RSI кэш из БД (с fallback на JSON)"""
    db = _get_bots_database()
    
    # ПРИОРИТЕТ: Загружаем из БД
    if db:
        try:
            cache_data = db.load_rsi_cache(max_age_hours=6.0)
            if cache_data:
                logger.debug(f"✅ RSI кэш загружен из БД")
                return cache_data
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки RSI кэша из БД: {e}, используем fallback")
    
    # FALLBACK: Загружаем из JSON (для обратной совместимости)
    cache_data = load_json_file(RSI_CACHE_FILE, description="RSI кэш")
    
    if not cache_data:
        return None
    
    # Проверяем возраст кэша (не старше 6 часов)
    try:
        cache_timestamp = datetime.fromisoformat(cache_data['timestamp'])
        age_hours = (datetime.now() - cache_timestamp).total_seconds() / 3600
        
        if age_hours > 6:
            logger.warning(f" RSI кэш устарел ({age_hours:.1f} часов)")
            return None
        
        logger.info(f" RSI кэш загружен (возраст: {age_hours:.1f}ч)")
        return cache_data
        
    except Exception as e:
        logger.error(f" Ошибка проверки возраста кэша: {e}")
        return None


def clear_rsi_cache():
    """Очищает RSI кэш в БД (с fallback на JSON)"""
    db = _get_bots_database()
    
    # ПРИОРИТЕТ: Очищаем в БД
    if db:
        try:
            if db.clear_rsi_cache():
                logger.info("✅ RSI кэш очищен в БД")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Ошибка очистки RSI кэша в БД: {e}, используем fallback")
    
    # FALLBACK: Удаляем JSON файл (для обратной совместимости)
    try:
        if os.path.exists(RSI_CACHE_FILE):
            os.remove(RSI_CACHE_FILE)
            logger.info(" RSI кэш очищен (JSON)")
            return True
        return False
    except Exception as e:
        logger.error(f" Ошибка очистки RSI кэша: {e}")
        return False


# Bots State
def save_bots_state(bots_data, auto_bot_config):
    """Сохраняет состояние ботов в БД (с fallback на JSON)"""
    db = _get_bots_database()
    
    # ПРИОРИТЕТ: Сохраняем в БД
    if db:
        try:
            if db.save_bots_state(bots_data, auto_bot_config):
                logger.info(f"💾 Состояние {len(bots_data)} ботов сохранено в БД")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения состояния ботов в БД: {e}, используем fallback")
    
    # FALLBACK: Сохраняем в JSON (для обратной совместимости)
    state_data = {
        'bots': bots_data,
        'auto_bot_config': auto_bot_config,
        'last_saved': datetime.now().isoformat(),
        'version': '1.0'
    }
    success = save_json_file(BOTS_STATE_FILE, state_data, "состояние ботов")
    if success:
        logger.info(f" Состояние {len(bots_data)} ботов сохранено (JSON)")
    return success


def load_bots_state():
    """Загружает состояние ботов из БД (с fallback на JSON)"""
    db = _get_bots_database()
    
    # ПРИОРИТЕТ: Загружаем из БД
    if db:
        try:
            state_data = db.load_bots_state()
            if state_data:
                logger.debug("✅ Состояние ботов загружено из БД")
                return state_data
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки состояния ботов из БД: {e}, используем fallback")
    
    # FALLBACK: Загружаем из JSON (для обратной совместимости)
    return load_json_file(BOTS_STATE_FILE, default={}, description="состояние ботов")


# Auto Bot Config
def save_auto_bot_config(config):
    """Больше не сохраняет конфигурацию автобота в JSON.
    
    Настройки хранятся только в bot_engine/bot_config.py
    """
    logger.debug(" Пропуск сохранения конфигурации автобота (используется bot_config.py)")
    return True


def load_auto_bot_config():
    """Не загружает конфигурацию автобота из JSON.
    
    Настройки читаются напрямую из bot_engine/bot_config.py
    """
    logger.debug(" Пропуск загрузки конфигурации автобота из JSON (используется bot_config.py)")
    return {}


# Individual coin settings
def save_individual_coin_settings(settings):
    """Сохраняет индивидуальные настройки монет в БД (с fallback на JSON)"""
    settings_to_save = settings or {}
    
    db = _get_bots_database()
    
    # ПРИОРИТЕТ: Сохраняем в БД
    if db:
        try:
            if not settings_to_save:
                # Очищаем настройки в БД
                if db.remove_all_individual_coin_settings():
                    logger.info("✅ Индивидуальные настройки монет очищены в БД")
                    return True
            else:
                if db.save_individual_coin_settings(settings_to_save):
                    logger.info(f"💾 Индивидуальные настройки монет сохранены в БД ({len(settings_to_save)} записей)")
                    return True
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения индивидуальных настроек в БД: {e}, используем fallback")
    
    # FALLBACK: Сохраняем в JSON (для обратной совместимости)
    if not settings_to_save:
        if os.path.exists(INDIVIDUAL_COIN_SETTINGS_FILE):
            try:
                os.remove(INDIVIDUAL_COIN_SETTINGS_FILE)
                logger.info(" Индивидуальные настройки монет очищены (JSON)")
            except OSError as error:
                logger.warning(f" Не удалось удалить файл индивидуальных настроек: {error}")
                return False
        else:
            logger.debug(" Индивидуальных настроек монет нет — файл не создаем")
        return True

    success = save_json_file(
        INDIVIDUAL_COIN_SETTINGS_FILE,
        settings_to_save,
        "индивидуальные настройки монет"
    )
    if success:
        logger.info(f" Индивидуальные настройки монет сохранены ({len(settings_to_save)} записей) в JSON")
    return success


def load_individual_coin_settings():
    """Загружает индивидуальные настройки монет из БД (с fallback на JSON)"""
    db = _get_bots_database()
    
    # ПРИОРИТЕТ: Загружаем из БД
    if db:
        try:
            settings = db.load_individual_coin_settings()
            if settings:
                logger.info(f"✅ Загружено индивидуальных настроек монет из БД: {len(settings)}")
                return settings
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки индивидуальных настроек из БД: {e}, используем fallback")
    
    # FALLBACK: Загружаем из JSON (для обратной совместимости)
    data = load_json_file(
        INDIVIDUAL_COIN_SETTINGS_FILE,
        default={},
        description="индивидуальные настройки монет"
    )
    if not data:
        return {}
    logger.info(f" Загружено индивидуальных настроек монет: {len(data)} (JSON)")
    return data


# Mature Coins
def save_mature_coins(storage):
    """Сохраняет хранилище зрелых монет в БД (с fallback на JSON)"""
    db = _get_bots_database()
    
    # ПРИОРИТЕТ: Сохраняем в БД
    if db:
        try:
            if db.save_mature_coins(storage):
                logger.debug(f"💾 Зрелые монеты сохранены в БД ({len(storage)} монет)")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения зрелых монет в БД: {e}, используем fallback")
    
    # FALLBACK: Сохраняем в JSON (для обратной совместимости)
    success = save_json_file(MATURE_COINS_FILE, storage, "зрелые монеты")
    return success


def load_mature_coins():
    """Загружает хранилище зрелых монет из БД (с fallback на JSON)"""
    db = _get_bots_database()
    
    # ПРИОРИТЕТ: Загружаем из БД
    if db:
        try:
            data = db.load_mature_coins()
            if data:
                logger.info(f"✅ Загружено {len(data)} зрелых монет из БД")
                return data
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки зрелых монет из БД: {e}, используем fallback")
    
    # FALLBACK: Загружаем из JSON (для обратной совместимости)
    data = load_json_file(MATURE_COINS_FILE, default={}, description="зрелые монеты")
    if data:
        logger.info(f" Загружено {len(data)} зрелых монет (JSON)")
    return data


# ❌ ОТКЛЮЧЕНО: Optimal EMA удален (EMA фильтр убран из системы)
# def save_optimal_ema(ema_data):
#     """Сохраняет оптимальные EMA периоды"""
#     return True
# 
# def load_optimal_ema():
#     """Загружает оптимальные EMA периоды"""
#     return {}


# Process State
def save_process_state(process_state):
    """Сохраняет состояние процессов в БД (с fallback на JSON)"""
    db = _get_bots_database()
    
    # ПРИОРИТЕТ: Сохраняем в БД
    if db:
        try:
            if db.save_process_state(process_state):
                logger.debug("💾 Состояние процессов сохранено в БД")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения состояния процессов в БД: {e}, используем fallback")
    
    # FALLBACK: Сохраняем в JSON (для обратной совместимости)
    state_data = {
        'process_state': process_state,
        'last_saved': datetime.now().isoformat(),
        'version': '1.0'
    }
    return save_json_file(PROCESS_STATE_FILE, state_data, "состояние процессов")


def load_process_state():
    """Загружает состояние процессов из БД (с fallback на JSON)"""
    db = _get_bots_database()
    
    # ПРИОРИТЕТ: Загружаем из БД
    if db:
        try:
            process_state_data = db.load_process_state()
            if process_state_data:
                logger.debug("✅ Состояние процессов загружено из БД")
                return process_state_data
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки состояния процессов из БД: {e}, используем fallback")
    
    # FALLBACK: Загружаем из JSON (для обратной совместимости)
    data = load_json_file(PROCESS_STATE_FILE, description="состояние процессов")
    return data.get('process_state', {}) if data else {}


# System Config
def save_system_config(config):
    """Сохраняет системную конфигурацию в bot_config.py"""
    try:
        from bots_modules.config_writer import save_system_config_to_py
        attrs = {}
        for key, value in config.items():
            attrs[key.upper()] = value
        success = save_system_config_to_py(attrs)
        if success:
            logger.info(" Системная конфигурация сохранена (bot_config.py)")
        return success
    except Exception as e:
        logger.error(f" Ошибка сохранения системной конфигурации: {e}")
        return False


def load_system_config():
    """Перезагружает SystemConfig из bot_config.py"""
    try:
        module = importlib.import_module('bot_engine.bot_config')
        importlib.reload(module)
        return module.SystemConfig
    except Exception as e:
        logger.error(f" Ошибка загрузки системной конфигурации: {e}")
        return None


# Bot Positions Registry
def save_bot_positions_registry(registry):
    """Сохраняет реестр позиций ботов в БД (с fallback на JSON)"""
    db = _get_bots_database()
    
    # ПРИОРИТЕТ: Сохраняем в БД
    if db:
        try:
            if db.save_bot_positions_registry(registry):
                logger.debug(f"💾 Реестр позиций сохранен в БД ({len(registry)} записей)")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения реестра позиций в БД: {e}, используем fallback")
    
    # FALLBACK: Сохраняем в JSON (для обратной совместимости)
    try:
        BOTS_POSITIONS_REGISTRY_FILE = 'data/bot_positions_registry.json'
        os.makedirs(os.path.dirname(BOTS_POSITIONS_REGISTRY_FILE), exist_ok=True)
        with open(BOTS_POSITIONS_REGISTRY_FILE, 'w', encoding='utf-8') as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)
        logger.debug(f" Реестр позиций сохранен (JSON): {len(registry)} записей")
        return True
    except Exception as e:
        logger.error(f" Ошибка сохранения реестра позиций: {e}")
        return False


def load_bot_positions_registry():
    """Загружает реестр позиций ботов из БД (с fallback на JSON)"""
    db = _get_bots_database()
    
    # ПРИОРИТЕТ: Загружаем из БД
    if db:
        try:
            registry = db.load_bot_positions_registry()
            if registry:
                logger.debug(f"✅ Реестр позиций загружен из БД ({len(registry)} записей)")
                return registry
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки реестра позиций из БД: {e}, используем fallback")
    
    # FALLBACK: Загружаем из JSON (для обратной совместимости)
    try:
        BOTS_POSITIONS_REGISTRY_FILE = 'data/bot_positions_registry.json'
        if os.path.exists(BOTS_POSITIONS_REGISTRY_FILE):
            with open(BOTS_POSITIONS_REGISTRY_FILE, 'r', encoding='utf-8') as f:
                registry = json.load(f)
                logger.info(f" Реестр позиций загружен (JSON): {len(registry)} записей")
                return registry
        return {}
    except Exception as e:
        logger.error(f" Ошибка загрузки реестра позиций: {e}")
        return {}


# Maturity Check Cache
def save_maturity_check_cache(coins_count: int, config_hash: str = None) -> bool:
    """Сохраняет кэш проверки зрелости в БД (с fallback на JSON)"""
    db = _get_bots_database()
    
    # ПРИОРИТЕТ: Сохраняем в БД
    if db:
        try:
            if db.save_maturity_check_cache(coins_count, config_hash):
                logger.debug("💾 Кэш проверки зрелости сохранен в БД")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения кэша проверки зрелости в БД: {e}, используем fallback")
    
    # FALLBACK: Сохраняем в JSON (для обратной совместимости)
    try:
        MATURITY_CHECK_CACHE_FILE = 'data/maturity_check_cache.json'
        os.makedirs(os.path.dirname(MATURITY_CHECK_CACHE_FILE), exist_ok=True)
        cache_data = {
            'coins_count': coins_count,
            'config_hash': config_hash
        }
        with open(MATURITY_CHECK_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f" Ошибка сохранения кэша проверки зрелости: {e}")
        return False


def load_maturity_check_cache() -> dict:
    """Загружает кэш проверки зрелости из БД (с fallback на JSON)"""
    db = _get_bots_database()
    
    # ПРИОРИТЕТ: Загружаем из БД
    if db:
        try:
            cache_data = db.load_maturity_check_cache()
            if cache_data:
                logger.debug("✅ Кэш проверки зрелости загружен из БД")
                return cache_data
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки кэша проверки зрелости из БД: {e}, используем fallback")
    
    # FALLBACK: Загружаем из JSON (для обратной совместимости)
    try:
        MATURITY_CHECK_CACHE_FILE = 'data/maturity_check_cache.json'
        if os.path.exists(MATURITY_CHECK_CACHE_FILE):
            with open(MATURITY_CHECK_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'coins_count': 0, 'config_hash': None}
    except Exception as e:
        logger.error(f" Ошибка загрузки кэша проверки зрелости: {e}")
        return {'coins_count': 0, 'config_hash': None}


# Delisted Coins
def save_delisted_coins(delisted: list) -> bool:
    """Сохраняет делистированные монеты в БД (с fallback на JSON)"""
    db = _get_bots_database()
    
    # ПРИОРИТЕТ: Сохраняем в БД
    if db:
        try:
            if db.save_delisted_coins(delisted):
                logger.debug(f"💾 Делистированные монеты сохранены в БД ({len(delisted)} монет)")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения делистированных монет в БД: {e}, используем fallback")
    
    # FALLBACK: Сохраняем в JSON (для обратной совместимости)
    try:
        DELISTED_FILE = 'data/delisted.json'
        os.makedirs(os.path.dirname(DELISTED_FILE), exist_ok=True)
        with open(DELISTED_FILE, 'w', encoding='utf-8') as f:
            json.dump(delisted, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f" Ошибка сохранения делистированных монет: {e}")
        return False


def load_delisted_coins() -> list:
    """Загружает делистированные монеты из БД (с fallback на JSON)"""
    db = _get_bots_database()
    
    # ПРИОРИТЕТ: Загружаем из БД
    if db:
        try:
            delisted = db.load_delisted_coins()
            if delisted:
                logger.debug(f"✅ Делистированные монеты загружены из БД ({len(delisted)} монет)")
                return delisted
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки делистированных монет из БД: {e}, используем fallback")
    
    # FALLBACK: Загружаем из JSON (для обратной совместимости)
    try:
        DELISTED_FILE = 'data/delisted.json'
        if os.path.exists(DELISTED_FILE):
            with open(DELISTED_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f" Ошибка загрузки делистированных монет: {e}")
        return []


def is_coin_delisted(symbol: str) -> bool:
    """Проверяет, делистирована ли монета (из БД или JSON)"""
    db = _get_bots_database()
    
    # ПРИОРИТЕТ: Проверяем в БД
    if db:
        try:
            return db.is_coin_delisted(symbol)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка проверки делистирования в БД: {e}, используем fallback")
    
    # FALLBACK: Проверяем в JSON (для обратной совместимости)
    try:
        delisted = load_delisted_coins()
        return symbol in delisted
    except Exception as e:
        logger.error(f" Ошибка проверки делистирования: {e}")
        return False

