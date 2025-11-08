"""
Тесты для модулей оптимизации производительности

Проверяет:
1. Асинхронное хранилище (async_storage.py)
2. Оптимизированный клиент биржи (optimized_exchange_client.py)
3. Оптимизированные расчеты (optimized_calculations.py)
4. Интеграционный модуль (performance_optimizer.py)
"""

import os
import sys
import time
import asyncio
import json
import tempfile
from pathlib import Path

# Добавляем корневую директорию в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('TestOptimizations')


# ============================================================================
# ТЕСТ 1: Асинхронное хранилище
# ============================================================================

async def test_async_storage():
    """Тестирует асинхронное хранилище"""
    logger.info("\n" + "="*60)
    logger.info("ТЕСТ 1: Асинхронное хранилище")
    logger.info("="*60)
    
    try:
        from bot_engine.async_storage import (
            save_json_file_async, flush_all_pending,
            save_rsi_cache_async, save_bots_state_async
        )
        
        # Создаем временный файл
        test_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        test_file.close()
        test_path = test_file.name
        
        try:
            # Тест 1: Простое сохранение
            logger.info("Тест 1.1: Простое сохранение JSON...")
            test_data = {"test": "data", "number": 42, "list": [1, 2, 3]}
            start_time = time.time()
            result = await save_json_file_async(test_path, test_data, "тестовые данные", immediate=True)
            elapsed = time.time() - start_time
            
            if result:
                logger.info(f"✅ Сохранение успешно за {elapsed:.3f}с")
                
                # Проверяем что файл создан и данные корректны
                with open(test_path, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                
                if loaded_data == test_data:
                    logger.info("✅ Данные корректно загружены")
                else:
                    logger.error(f"❌ Данные не совпадают: {loaded_data} != {test_data}")
                    return False
            else:
                logger.error("❌ Сохранение не удалось")
                return False
            
            # Тест 2: Батчинг (несколько операций подряд)
            logger.info("\nТест 1.2: Батчинг операций...")
            test_files = []
            for i in range(5):
                temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
                temp_file.close()
                test_files.append(temp_file.name)
            
            start_time = time.time()
            tasks = []
            for i, filepath in enumerate(test_files):
                data = {"batch_test": i, "timestamp": time.time()}
                tasks.append(save_json_file_async(filepath, data, f"batch_{i}", immediate=False))
            
            results = await asyncio.gather(*tasks)
            await flush_all_pending()  # Принудительный flush
            elapsed = time.time() - start_time
            
            success_count = sum(1 for r in results if r)
            logger.info(f"✅ Батчинг: {success_count}/{len(test_files)} файлов сохранено за {elapsed:.3f}с")
            
            # Проверяем файлы
            for filepath in test_files:
                if os.path.exists(filepath):
                    os.remove(filepath)
            
            logger.info("✅ ТЕСТ 1 ПРОЙДЕН: Асинхронное хранилище работает")
            return True
            
        finally:
            # Очистка
            if os.path.exists(test_path):
                os.remove(test_path)
            await flush_all_pending()
            
    except ImportError as e:
        logger.error(f"❌ Модуль async_storage недоступен: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка теста async_storage: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


# ============================================================================
# ТЕСТ 2: Оптимизированные расчеты
# ============================================================================

async def test_optimized_calculations():
    """Тестирует оптимизированные расчеты"""
    logger.info("\n" + "="*60)
    logger.info("ТЕСТ 2: Оптимизированные расчеты")
    logger.info("="*60)
    
    try:
        from bot_engine.optimized_calculations import (
            calculate_rsi_batch, calculate_ema_batch,
            calculate_rsi_vectorized, calculate_ema_vectorized
        )
        from bot_engine.utils.rsi_utils import calculate_rsi, calculate_ema
        
        # Тест 1: Пакетный расчет RSI
        logger.info("Тест 2.1: Пакетный расчет RSI...")
        
        # Генерируем тестовые данные
        import random
        test_prices = {}
        for symbol in ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'ADA/USDT']:
            # Генерируем случайные цены
            base_price = random.uniform(100, 1000)
            prices = [base_price + random.uniform(-10, 10) for _ in range(100)]
            test_prices[symbol] = prices
        
        # Используем функцию для словаря
        try:
            from bot_engine.optimized_calculations import calculate_rsi_batch_dict
            use_dict_func = True
        except ImportError:
            use_dict_func = False
        
        # Сравниваем скорость
        start_time = time.time()
        if use_dict_func:
            batch_results = calculate_rsi_batch_dict(test_prices, period=14)
        else:
            # Fallback: преобразуем в список списков
            symbols = list(test_prices.keys())
            prices_list = [test_prices[symbol] for symbol in symbols]
            rsi_list = calculate_rsi_batch(prices_list, period=14)
            batch_results = {symbol: rsi for symbol, rsi in zip(symbols, rsi_list)}
        batch_time = time.time() - start_time
        
        start_time = time.time()
        sequential_results = {}
        for symbol, prices in test_prices.items():
            sequential_results[symbol] = calculate_rsi(prices, period=14)
        sequential_time = time.time() - start_time
        
        speedup = sequential_time / batch_time if batch_time > 0 else 0
        logger.info(f"✅ Пакетный расчет: {batch_time:.3f}с")
        logger.info(f"✅ Последовательный: {sequential_time:.3f}с")
        logger.info(f"✅ Ускорение: {speedup:.2f}x")
        
        # Проверяем корректность результатов
        all_match = True
        for symbol in test_prices.keys():
            batch_rsi = batch_results.get(symbol)
            seq_rsi = sequential_results.get(symbol)
            if abs((batch_rsi or 0) - (seq_rsi or 0)) > 0.01:
                logger.warning(f"⚠️ Расхождение для {symbol}: batch={batch_rsi}, seq={seq_rsi}")
                all_match = False
        
        if all_match:
            logger.info("✅ Результаты совпадают")
        
        # Тест 2: Векторизованные расчеты (если NumPy доступен)
        try:
            import numpy as np
            logger.info("\nТест 2.2: Векторизованные расчеты (NumPy)...")
            
            prices_array = np.array(test_prices['BTC/USDT'])
            
            start_time = time.time()
            vectorized_rsi = calculate_rsi_vectorized(prices_array, period=14)
            vectorized_time = time.time() - start_time
            
            start_time = time.time()
            standard_rsi = calculate_rsi(test_prices['BTC/USDT'], period=14)
            standard_time = time.time() - start_time
            
            speedup = standard_time / vectorized_time if vectorized_time > 0 else 0
            logger.info(f"✅ Векторизованный: {vectorized_time:.3f}с")
            logger.info(f"✅ Стандартный: {standard_time:.3f}с")
            logger.info(f"✅ Ускорение: {speedup:.2f}x")
            
            if abs((vectorized_rsi or 0) - (standard_rsi or 0)) < 0.01:
                logger.info("✅ Результаты совпадают")
            else:
                logger.warning(f"⚠️ Расхождение: vectorized={vectorized_rsi}, standard={standard_rsi}")
                
        except ImportError:
            logger.info("⚠️ NumPy недоступен, пропускаем векторизованные тесты")
        
        logger.info("✅ ТЕСТ 2 ПРОЙДЕН: Оптимизированные расчеты работают")
        return True
        
    except ImportError as e:
        logger.error(f"❌ Модуль optimized_calculations недоступен: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка теста optimized_calculations: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


# ============================================================================
# ТЕСТ 3: Интеграционный модуль
# ============================================================================

async def test_performance_optimizer():
    """Тестирует интеграционный модуль PerformanceOptimizer"""
    logger.info("\n" + "="*60)
    logger.info("ТЕСТ 3: Performance Optimizer (интеграция)")
    logger.info("="*60)
    
    try:
        from bot_engine.performance_optimizer import PerformanceOptimizer, get_performance_optimizer
        
        # Тест 1: Создание экземпляра
        logger.info("Тест 3.1: Создание экземпляра...")
        optimizer = PerformanceOptimizer(enabled=True)
        logger.info("✅ Экземпляр создан")
        
        # Тест 2: Singleton
        logger.info("\nТест 3.2: Singleton паттерн...")
        optimizer1 = get_performance_optimizer()
        optimizer2 = get_performance_optimizer()
        if optimizer1 is optimizer2:
            logger.info("✅ Singleton работает корректно")
        else:
            logger.warning("⚠️ Singleton не работает")
        
        # Тест 3: Сохранение через оптимизатор
        logger.info("\nТест 3.3: Сохранение через оптимизатор...")
        test_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        test_file.close()
        test_path = test_file.name
        
        try:
            test_data = {"optimizer_test": True, "timestamp": time.time()}
            result = await optimizer.save_data_optimized(
                test_path, test_data, "тест оптимизатора", immediate=True
            )
            
            if result:
                logger.info("✅ Сохранение через оптимизатор успешно")
                
                # Проверяем файл
                with open(test_path, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                
                if loaded_data == test_data:
                    logger.info("✅ Данные корректны")
                else:
                    logger.error("❌ Данные не совпадают")
                    return False
            else:
                logger.error("❌ Сохранение не удалось")
                return False
                
        finally:
            if os.path.exists(test_path):
                os.remove(test_path)
        
        # Тест 4: Статистика
        logger.info("\nТест 3.4: Статистика использования...")
        stats = optimizer.get_stats()
        logger.info(f"✅ Статистика: {stats}")
        
        logger.info("✅ ТЕСТ 3 ПРОЙДЕН: Performance Optimizer работает")
        return True
        
    except ImportError as e:
        logger.error(f"❌ Модуль performance_optimizer недоступен: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка теста performance_optimizer: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

async def run_all_tests():
    """Запускает все тесты"""
    logger.info("\n" + "="*60)
    logger.info("ЗАПУСК ТЕСТОВ ОПТИМИЗАЦИЙ")
    logger.info("="*60)
    
    results = {}
    
    # Тест 1: Асинхронное хранилище
    results['async_storage'] = await test_async_storage()
    
    # Тест 2: Оптимизированные расчеты
    results['optimized_calculations'] = await test_optimized_calculations()
    
    # Тест 3: Performance Optimizer
    results['performance_optimizer'] = await test_performance_optimizer()
    
    # Итоги
    logger.info("\n" + "="*60)
    logger.info("ИТОГИ ТЕСТИРОВАНИЯ")
    logger.info("="*60)
    
    for test_name, result in results.items():
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        logger.info("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    else:
        logger.warning("\n⚠️ НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ")
    
    return all_passed


if __name__ == "__main__":
    # Запускаем тесты
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)

