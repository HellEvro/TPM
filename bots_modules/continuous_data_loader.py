"""
🔄 НЕПРЕРЫВНЫЙ ЗАГРУЗЧИК ДАННЫХ
Независимый воркер который работает по кругу, постоянно обновляя все данные
Все остальные сервисы просто читают актуальные данные из глобального хранилища
"""

import threading
import time
from datetime import datetime
import logging

logger = logging.getLogger('BotsService')
# Добавляем префикс для легкого поиска в логах
class PrefixedLogger:
    def __init__(self, logger, prefix):
        self.logger = logger
        self.prefix = prefix

    def info(self, msg):
        self.logger.info(f"{self.prefix} {msg}")

    def warning(self, msg):
        self.logger.warning(f"{self.prefix} {msg}")

    def error(self, msg):
        self.logger.error(f"{self.prefix} {msg}")

    def debug(self, msg):
                pass

logger = PrefixedLogger(logger, "🔄")

# Таймаут этапа расчёта зрелости (сек). При большом числе монет и ТФ 1m 60с может не хватать.
MATURITY_CALCULATION_TIMEOUT = 120

class ContinuousDataLoader:
    def __init__(self, exchange_obj=None, update_interval=180):
        """
        Args:
            exchange_obj: Объект биржи
            update_interval: Интервал обновления в секундах (по умолчанию 180 = 3 минуты)
        """
        self.exchange = exchange_obj
        self.update_interval = update_interval
        self.is_running = False
        self.thread = None
        self.last_update_time = None
        self.update_count = 0
        self.error_count = 0

    def start(self):
        """🚀 Запускает воркер в отдельном потоке"""
        if self.is_running:
            logger.warning("⚠️ Воркер уже запущен")
            return

        self.is_running = True
        self.thread = threading.Thread(target=self._continuous_loop, daemon=True)
        self.thread.start()
        logger.info(f"Воркер запущен (интервал: {self.update_interval}с)")

    def stop(self):
        """🛑 Останавливает воркер"""
        if not self.is_running:
            return

        logger.warning("🛑 Останавливаем воркер...")
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.warning("✅ Воркер остановлен")

    def _continuous_loop(self):
        """🔄 Основной цикл обновления данных"""
        logger.info("🔄 Поток непрерывного загрузчика ЗАПУЩЕН (через 5 сек — первый раунд)")

        # ⚡ ТРЕЙСИНГ ОТКЛЮЧЕН - проблема решена (deadlock на bots_data_lock)
        # try:
        #     from trace_debug import enable_trace
        #     enable_trace()
        #     logger.info("🔍 [CONTINUOUS] Трейсинг включен для диагностики зависаний")
        # except Exception as e:
        #     logger.warning(f"⚠️ [CONTINUOUS] Не удалось включить трейсинг: {e}")

        # Получаем текущий таймфрейм при старте цикла
        try:
            from bot_engine.config_loader import get_current_timeframe
            startup_timeframe = get_current_timeframe()
            logger.info(f"⏱️ [CONTINUOUS] Таймфрейм при старте загрузчика: {startup_timeframe}")
        except Exception as tf_err:
            logger.warning(f"⚠️ [CONTINUOUS] Не удалось получить таймфрейм при старте: {tf_err}")

        # Небольшая задержка перед первым обновлением (даем системе запуститься)
        time.sleep(5)
        logger.info("🔄 Начинаем первый раунд обновления данных...")

        # Импортируем shutdown_flag для корректной остановки
        from bots_modules.imports_and_globals import shutdown_flag

        while self.is_running and not shutdown_flag.is_set():
            try:
                cycle_start = time.time()
                self.update_count += 1

                from bots_modules.imports_and_globals import coins_rsi_data
                coins_rsi_data['processing_cycle'] = True
                coins_rsi_data['candles_load_complete'] = False  # RSI только после полной загрузки свечей

                try:
                    from bot_engine.config_loader import get_current_timeframe, TIMEFRAME
                    current_timeframe = get_current_timeframe()
                except Exception:
                    current_timeframe = TIMEFRAME

                logger.info("=" * 80)
                logger.info(f"РАУНД #{self.update_count} НАЧАТ")
                logger.info(f"🕐 Время: {datetime.now().strftime('%H:%M:%S')}")
                logger.info(f"⏱️ Таймфрейм: {current_timeframe}")
                logger.info("=" * 80)

                from bots_modules.imports_and_globals import bots_data, BOT_STATUS
                from bot_engine.config_loader import get_current_timeframe, TIMEFRAME
                try:
                    from bots_modules.imports_and_globals import get_config_value
                except Exception:
                    get_config_value = lambda c, k: (c or {}).get(k)
                auto_bot_enabled = bots_data.get('auto_bot_config', {}).get('enabled', False)
                bots = bots_data.get('bots', {}) or {}
                auto_config = bots_data.get('auto_bot_config', {}) or {}
                active_bots_count = sum(
                    1 for b in bots.values()
                    if b.get('status') not in [BOT_STATUS.get('IDLE'), BOT_STATUS.get('PAUSED')]
                )
                try:
                    default_tf = get_current_timeframe() or TIMEFRAME
                except Exception:
                    default_tf = TIMEFRAME
                required_timeframes_set = {default_tf}
                position_symbols_to_tf = {}
                max_concurrent = int(get_config_value(auto_config, 'max_concurrent') or 0)
                if active_bots_count >= max_concurrent and max_concurrent > 0:
                    for _sym, bot_data in bots.items():
                        if bot_data.get('status') in [BOT_STATUS.get('IN_POSITION_LONG'), BOT_STATUS.get('IN_POSITION_SHORT')]:
                            entry_tf = bot_data.get('entry_timeframe') or default_tf
                            required_timeframes_set.add(entry_tf)
                            if _sym not in position_symbols_to_tf:
                                position_symbols_to_tf[_sym] = []
                            if entry_tf not in position_symbols_to_tf[_sym]:
                                position_symbols_to_tf[_sym].append(entry_tf)
                required_timeframes = sorted(required_timeframes_set)
                reduced_mode = bool(position_symbols_to_tf)
                if not auto_bot_enabled and active_bots_count == 0:
                    logger.info("⏹️ Автобот выключен, активных ботов нет — загружаем только свечи и RSI для UI")

                if not coins_rsi_data.get('coins') or len(coins_rsi_data.get('coins', {})) == 0:
                    self._seed_coins_placeholder()

                success_candles = self._load_candles()
                coins_rsi_data['candles_load_complete'] = True  # Этап свечей завершён (успех или нет) — можно запускать RSI
                if not success_candles:
                    logger.warning(
                        "⚠️ Загрузка свечей с биржи не удалась. "
                        "Пробуем расчёт RSI без кэша (каждый символ подгрузит свечи сам — будет медленнее)."
                    )
                    self.error_count += 1

                success_rsi = self._calculate_rsi(
                    required_timeframes=required_timeframes,
                    reduced_mode=reduced_mode,
                    position_symbols_to_tf=position_symbols_to_tf if reduced_mode else None,
                )
                if not success_rsi:
                    logger.error("КРИТИЧНО: расчёт RSI не выполнен. Данные для торговли отсутствуют. Проверьте логи, биржу и конфиг.")
                    self.error_count += 1
                    time.sleep(30)
                    continue

                if not coins_rsi_data.get('first_round_complete'):
                    coins_rsi_data['first_round_complete'] = True
                    logger.info("✅ ПЕРВАЯ ЗАГРУЗКА ЗАВЕРШЕНА: свечи + RSI готовы → запуск системы")

                # Этапы 3–7 в ФОНЕ — не блокируем следующий раунд 1→2
                # Этапы 3–6 выполняются ВСЕГДА (зрелость, тренды, фильтры нужны для UI).
                # Этап 7 (передача автоботу) — только при включённом автоботе.
                def _run_stages_3_to_7():
                    import traceback
                    try:
                        self._calculate_maturity()
                        self._analyze_trends()
                        self._apply_heavy_filters()
                        filtered_coins = self._process_filters()
                        if auto_bot_enabled:
                            self._set_filtered_coins_for_autobot(filtered_coins)
                        else:
                    except Exception as e:
                        logger.error(f"❌ Ошибка в этапах 3–7: {e}")
                        logger.error(f"❌ Traceback: {traceback.format_exc()}")
                threading.Thread(target=_run_stages_3_to_7, daemon=True, name="Stages3to7").start()

                cycle_duration = time.time() - cycle_start
                self.last_update_time = datetime.now()

                logger.info("=" * 80)
                logger.info(f"✅ РАУНД #{self.update_count} ЗАВЕРШЕН (этап 2 — RSI готов, 3–7 в фоне)")
                logger.info(f"⏱️ Длительность 1–2: {cycle_duration:.1f}с")
                logger.info(f"📊 Статистика: обновлений={self.update_count}, ошибок={self.error_count}")
                logger.info("=" * 80)

                # ✅ ЗАВЕРШАЕМ ОБРАБОТКУ - увеличиваем версию данных
                from bots_modules.imports_and_globals import coins_rsi_data
                coins_rsi_data['processing_cycle'] = False  # Снимаем флаг обработки
                coins_rsi_data['data_version'] += 1  # Увеличиваем версию данных
                logger.info(f"✅ Обработка завершена (версия данных: {coins_rsi_data['data_version']})")

                # 🚀 После полного цикла 1–6 запускаем следующий раунд (1 → 2 → 3–6)
                logger.info(f"🚀 Цикл 1–7 завершён — запускаем следующий раунд (загрузка свечей)...")

                # Минимальная пауза 0.05 сек только чтобы не крутить CPU впустую; при необходимости выхода — выходим
                if shutdown_flag.wait(0.05):
                    break

            except Exception as e:
                logger.error(f"❌ Ошибка в цикле обновления: {e}")
                self.error_count += 1

                # ✅ ЗАВЕРШАЕМ ОБРАБОТКУ даже при ошибке
                from bots_modules.imports_and_globals import coins_rsi_data
                coins_rsi_data['processing_cycle'] = False  # Снимаем флаг обработки даже при ошибке
                coins_rsi_data['data_version'] += 1  # Увеличиваем версию даже при ошибке
                logger.info(f"✅ Обработка завершена (после ошибки, версия данных: {coins_rsi_data['data_version']})")

                time.sleep(30)  # Пауза перед следующей попыткой
            except BaseException as be:
                # Не даём потоку завершиться при любом необработанном исключении — логируем и продолжаем цикл
                logger.error(f"❌ Критическая ошибка загрузчика (поток продолжает работу): {be}")
                self.error_count += 1
                try:
                    from bots_modules.imports_and_globals import coins_rsi_data
                    coins_rsi_data['processing_cycle'] = False
                    coins_rsi_data['data_version'] += 1
                except Exception:
                    pass
                time.sleep(30)

        logger.info("🏁 Выход из непрерывного цикла")

    def _seed_coins_placeholder(self):
        """Устанавливает total_coins по числу пар с биржи (без записи в coins — они заполнятся после расчёта RSI)."""
        try:
            from bots_modules.imports_and_globals import get_exchange, coins_rsi_data
            from bot_engine.config_loader import get_current_timeframe, TIMEFRAME
            exch = get_exchange()
            if not exch:
                return
            try:
                tf = get_current_timeframe()
            except Exception:
                tf = TIMEFRAME
            pairs = exch.get_all_pairs()
            if not pairs or not isinstance(pairs, list):
                return
            valid = [s for s in pairs if s and str(s).strip().upper() != 'ALL']
            if not valid:
                return
            coins_rsi_data['total_coins'] = len(valid)
            logger.info(
                f"📋 Готово {len(valid)} символов для первого раунда RSI (ТФ: {tf}, coins заполнятся после расчёта)"
            )
        except Exception as e:
            logger.warning(f"⚠️ Не удалось предзаполнить список монет: {e}")

    def _load_candles(self):
        """📦 Загружает свечи всех монет"""
        try:
            start = time.time()
            from bots_modules.filters import load_all_coins_candles_fast
            success = load_all_coins_candles_fast()
            duration = time.time() - start
            n = 0
            try:
                from bots_modules.imports_and_globals import coins_rsi_data
                n = len(coins_rsi_data.get('candles_cache') or coins_rsi_data.get('coins') or {})
            except Exception:
                pass
            if success:
                return True
            else:
                logger.error(f"❌ Этап 1/7: Не удалось загрузить свечи")
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки свечей: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False

    def _load_candles_non_blocking(self):
        """📦 Загружает свечи всех монет в отдельном потоке (НЕБЛОКИРУЮЩИЙ)"""
        try:
            start = time.time()

            # Проверяем, есть ли уже свечи в кэше с ПРАВИЛЬНЫМ таймфреймом
            from bots_modules.imports_and_globals import coins_rsi_data
            from bot_engine.config_loader import get_current_timeframe
            current_timeframe = get_current_timeframe()

            if 'candles_cache' in coins_rsi_data and coins_rsi_data['candles_cache']:
                # Проверяем таймфрейм первой монеты в кэше
                cache_sample = next(iter(coins_rsi_data['candles_cache'].values()), None)
                if cache_sample and cache_sample.get('timeframe') == current_timeframe:
                    last_update = coins_rsi_data.get('last_candles_update', '')
                    if last_update:
                        from datetime import datetime, timedelta
                        try:
                            last_update_time = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                            time_diff = datetime.now() - last_update_time.replace(tzinfo=None)
                            if time_diff.total_seconds() < 300:  # Если свечи обновлялись менее 5 минут назад
                                logger.info(f"✅ Используем свежие свечи из кэша (таймфрейм: {current_timeframe})")
                                return True
                        except:
                            pass
                else:
                    # Таймфрейм не совпадает - очищаем кэш
                    logger.info(f"🗑️ Таймфрейм кэша не совпадает (кэш: {cache_sample.get('timeframe') if cache_sample else 'нет'}, текущий: {current_timeframe}), очищаем кэш")
                    coins_rsi_data['candles_cache'] = {}
                    coins_rsi_data['last_candles_update'] = None

            # Запускаем загрузку в отдельном потоке
            import threading
            def load_candles_thread():
                try:
                    logger.info("Запускаем load_all_coins_candles_fast() в отдельном потоке...")
                    from bots_modules.filters import load_all_coins_candles_fast
                    success = load_all_coins_candles_fast()
                    logger.info(f"📊 load_all_coins_candles_fast() завершена: {success}")
                except Exception as e:
                    logger.error(f"❌ Ошибка в потоке загрузки свечей: {e}")

            # Запускаем поток
            candles_thread = threading.Thread(target=load_candles_thread, daemon=True)
            candles_thread.start()

            # Ждем максимум 2 секунды для инициализации
            candles_thread.join(timeout=2)

            duration = time.time() - start
            logger.info(f"✅ Загрузка свечей запущена в фоне за {duration:.1f}с")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка запуска загрузки свечей: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False

    def _calculate_rsi(self, required_timeframes=None, reduced_mode=None, position_symbols_to_tf=None):
        """📊 Рассчитывает RSI для всех монет. Данные из загрузчика передаются без блокировки в load_all_coins_rsi."""
        try:
            start = time.time()
            from bots_modules.filters import load_all_coins_rsi
            success = load_all_coins_rsi(
                required_timeframes=required_timeframes,
                reduced_mode=reduced_mode,
                position_symbols_to_tf=position_symbols_to_tf,
            )

            duration = time.time() - start
            n = 0
            try:
                from bots_modules.imports_and_globals import coins_rsi_data
                n = len(coins_rsi_data.get('coins') or {})
            except Exception:
                pass
            if success:
                return True
            else:
                logger.error(f"❌ Этап 2/7: Не удалось рассчитать RSI")
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка расчета RSI: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False

    def _calculate_rsi_non_blocking(self):
        """📊 Рассчитывает RSI для всех монет в отдельном потоке (НЕБЛОКИРУЮЩИЙ)"""
        try:
            start = time.time()

            # Проверяем, есть ли уже RSI данные в кэше
            from bots_modules.imports_and_globals import coins_rsi_data
            if 'rsi_data' in coins_rsi_data and coins_rsi_data['rsi_data']:
                last_update = coins_rsi_data.get('last_rsi_update', '')
                if last_update:
                    from datetime import datetime
                    try:
                        last_update_time = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                        time_diff = datetime.now() - last_update_time.replace(tzinfo=None)
                        if time_diff.total_seconds() < 600:  # Если RSI обновлялся менее 10 минут назад
                            logger.info("✅ Используем свежие RSI данные из кэша")
                            return True
                    except:
                        pass

            # Запускаем расчет в отдельном потоке
            import threading
            def calculate_rsi_thread():
                try:
                    logger.info("Запускаем load_all_coins_rsi() в отдельном потоке...")
                    from bots_modules.filters import load_all_coins_rsi
                    success = load_all_coins_rsi()
                    logger.info(f"📊 load_all_coins_rsi() завершена: {success}")
                except Exception as e:
                    logger.error(f"❌ Ошибка в потоке расчета RSI: {e}")

            # Запускаем поток
            rsi_thread = threading.Thread(target=calculate_rsi_thread, daemon=True)
            rsi_thread.start()

            # Ждем максимум 3 секунды для инициализации
            rsi_thread.join(timeout=3)

            duration = time.time() - start
            logger.info(f"✅ Расчет RSI запущен в фоне за {duration:.1f}с")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка запуска расчета RSI: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False

    def _calculate_maturity(self):
        """🧮 Рассчитывает зрелость монет (только незрелые)"""
        try:
            start = time.time()

            # Простой таймаут через threading (работает в Windows)
            from threading import Thread

            result = [None]
            exception = [None]

            def run_maturity():
                try:
                    from bots_modules.maturity import calculate_all_coins_maturity
                    calculate_all_coins_maturity()
                    result[0] = True
                except Exception as e:
                    exception[0] = e

            # Запускаем в отдельном потоке
            thread = Thread(target=run_maturity)
            thread.daemon = True
            thread.start()

            # Ждем до MATURITY_CALCULATION_TIMEOUT секунд
            thread.join(timeout=MATURITY_CALCULATION_TIMEOUT)

            if thread.is_alive():
                logger.error(f"✅ Этап 3/7: Таймаут зрелости ({MATURITY_CALCULATION_TIMEOUT}с)")
                return

            if exception[0]:
                raise exception[0]

            duration = time.time() - start

        except Exception as e:
            logger.error(f"✅ Этап 3/7: Ошибка зрелости — {e}")
            # Не критично, продолжаем

    def _analyze_trends(self):
        """📈 Определяет тренд для сигнальных монет"""
        try:
            start = time.time()

            from bots_modules.filters import analyze_trends_for_signal_coins
            analyze_trends_for_signal_coins()

            duration = time.time() - start

        except Exception as e:
            logger.error(f"✅ Этап 4/7: Ошибка трендов — {e}")

    def _apply_heavy_filters(self):
        """🔍 Этап 5/7: Применяет тяжёлые фильтры (time_filter, exit_scam, loss_reentry) — для UI и автобота"""
        try:
            start = time.time()
            from bots_modules.filters import apply_heavy_filters_to_coins
            apply_heavy_filters_to_coins()
            duration = time.time() - start
        except Exception as e:
            logger.error(f"✅ Этап 5/7: Ошибка тяжёлых фильтров — {e}")

    def _process_filters(self):
        """🔍 Этап 6/7: Обрабатывает лонг/шорт монеты фильтрами"""
        try:
            start = time.time()
            from bots_modules.filters import process_long_short_coins_with_filters
            filtered_coins = process_long_short_coins_with_filters()
            duration = time.time() - start
            return filtered_coins
        except Exception as e:
            logger.error(f"✅ Этап 6/7: Ошибка фильтров — {e}")
            return []

    def _set_filtered_coins_for_autobot(self, filtered_coins):
        """✅ Этап 7/7: Передаёт отфильтрованные монеты автоботу"""
        try:
            start = time.time()

            from bots_modules.filters import set_filtered_coins_for_autobot
            set_filtered_coins_for_autobot(filtered_coins)

            duration = time.time() - start

        except Exception as e:
            logger.error(f"✅ Этап 7/7: Ошибка передачи автоботу — {e}")

    def get_status(self):
        """📊 Возвращает статус воркера"""
        return {
            'is_running': self.is_running,
            'update_count': self.update_count,
            'error_count': self.error_count,
            'last_update': self.last_update_time.isoformat() if self.last_update_time else None,
            'update_interval': self.update_interval
        }

# Глобальный экземпляр воркера
_continuous_loader = None

def start_continuous_loader(exchange_obj=None, update_interval=180):
    """🚀 Запускает непрерывный загрузчик данных"""
    global _continuous_loader

    if _continuous_loader and _continuous_loader.is_running:
        logger.warning("⚠️ Загрузчик уже запущен")
        return _continuous_loader

    _continuous_loader = ContinuousDataLoader(exchange_obj, update_interval)
    _continuous_loader.start()
    return _continuous_loader

def stop_continuous_loader():
    """🛑 Останавливает непрерывный загрузчик данных"""
    global _continuous_loader

    if _continuous_loader:
        _continuous_loader.stop()
        _continuous_loader = None

def get_continuous_loader():
    """📊 Возвращает экземпляр загрузчика"""
    return _continuous_loader
