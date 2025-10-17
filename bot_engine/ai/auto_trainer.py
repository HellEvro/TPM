"""
Автоматический тренер ИИ моделей

Автоматически обновляет исторические данные и переобучает модели по расписанию.
Запускается как фоновый процесс вместе с ботом.
"""

import logging
import threading
import time
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from bot_engine.bot_config import AIConfig

logger = logging.getLogger('AI.AutoTrainer')


class AutoTrainer:
    """Автоматический тренер для ИИ моделей"""
    
    def __init__(self):
        self.running = False
        self.thread = None
        self.last_data_update = None
        self.last_training = None
        
        # Путь к скриптам
        self.scripts_dir = Path('scripts/ai')
        self.collect_script = self.scripts_dir / 'collect_historical_data.py'
        self.train_script = self.scripts_dir / 'train_anomaly_on_real_data.py'
    
    def start(self):
        """Запускает автоматический тренер в фоновом режиме"""
        if self.running:
            logger.warning("[AutoTrainer] Уже запущен")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True, name="AI_AutoTrainer")
        self.thread.start()
        
        logger.info("[AutoTrainer] ✅ Запущен в фоновом режиме")
        logger.info(f"[AutoTrainer] Расписание:")
        logger.info(f"[AutoTrainer]   - Обновление данных: каждые {AIConfig.AI_DATA_UPDATE_INTERVAL/3600:.0f}ч")
        logger.info(f"[AutoTrainer]   - Переобучение: каждые {AIConfig.AI_RETRAIN_INTERVAL/3600:.0f}ч")
    
    def stop(self):
        """Останавливает автоматический тренер"""
        if not self.running:
            return
        
        logger.info("[AutoTrainer] Остановка...")
        self.running = False
        
        if self.thread:
            self.thread.join(timeout=5)
        
        logger.info("[AutoTrainer] ✅ Остановлен")
    
    def _run(self):
        """Основной цикл автоматического тренера"""
        logger.info("[AutoTrainer] 🔄 Фоновый процесс запущен")
        
        # Проверяем нужно ли обучение при старте
        self._check_initial_training()
        
        while self.running:
            try:
                current_time = time.time()
                
                # 1. Проверяем нужно ли обновить данные
                if self._should_update_data(current_time):
                    self._update_data()
                
                # 2. Проверяем нужно ли переобучить модель
                if self._should_retrain(current_time):
                    self._retrain()
                
                # Спим до следующей проверки (каждые 10 минут)
                time.sleep(600)
                
            except Exception as e:
                logger.error(f"[AutoTrainer] Ошибка в цикле: {e}")
                time.sleep(60)
    
    def _check_initial_training(self):
        """Проверяет нужно ли обучение при старте"""
        model_path = Path(AIConfig.AI_ANOMALY_MODEL_PATH)
        
        if not model_path.exists():
            logger.warning("[AutoTrainer] ⚠️ Модель не найдена, требуется первичное обучение")
            
            if AIConfig.AI_AUTO_TRAIN_ON_STARTUP:
                logger.info("[AutoTrainer] 🚀 Запускаем первичное обучение...")
                self._initial_setup()
        else:
            logger.info("[AutoTrainer] ✅ Модель найдена, первичное обучение не требуется")
    
    def _initial_setup(self):
        """Первичная настройка - сбор данных и обучение"""
        logger.info("[AutoTrainer] Первичная настройка...")
        
        # 1. Собираем данные
        logger.info("[AutoTrainer] Шаг 1/2: Сбор исторических данных...")
        success = self._update_data(initial=True)
        
        if not success:
            logger.error("[AutoTrainer] ❌ Не удалось собрать данные")
            return
        
        # 2. Обучаем модель
        logger.info("[AutoTrainer] Шаг 2/2: Обучение модели...")
        success = self._retrain()
        
        if success:
            logger.info("[AutoTrainer] ✅ Первичная настройка завершена")
        else:
            logger.error("[AutoTrainer] ❌ Ошибка первичного обучения")
    
    def _should_update_data(self, current_time: float) -> bool:
        """Проверяет нужно ли обновить данные"""
        if not AIConfig.AI_AUTO_UPDATE_DATA:
            return False
        
        if self.last_data_update is None:
            return True
        
        elapsed = current_time - self.last_data_update
        return elapsed >= AIConfig.AI_DATA_UPDATE_INTERVAL
    
    def _should_retrain(self, current_time: float) -> bool:
        """Проверяет нужно ли переобучить модель"""
        if not AIConfig.AI_AUTO_RETRAIN:
            return False
        
        if self.last_training is None:
            return True
        
        elapsed = current_time - self.last_training
        return elapsed >= AIConfig.AI_RETRAIN_INTERVAL
    
    def _update_data(self, initial: bool = False) -> bool:
        """
        Обновляет исторические данные
        
        Args:
            initial: True если это первичная настройка
        
        Returns:
            True если успешно
        """
        try:
            logger.info("[AutoTrainer] 📥 Обновление исторических данных...")
            
            # Определяем количество монет
            if initial:
                # Первичная настройка - собираем больше данных
                limit = AIConfig.AI_INITIAL_COINS_COUNT
                days = 730  # 2 года для первичной настройки
            else:
                # Обновление
                limit = AIConfig.AI_UPDATE_COINS_COUNT
                days = 30  # Обновляем только последние 30 дней
            
            # Запускаем скрипт сбора данных
            cmd = [
                sys.executable,
                str(self.collect_script),
                '--days', str(days)
            ]
            
            # Если limit=0, собираем все монеты (флаг --all)
            if limit == 0:
                cmd.append('--all')
                logger.info("[AutoTrainer] Режим: ВСЕ монеты с биржи")
            else:
                cmd.extend(['--limit', str(limit)])
                logger.info(f"[AutoTrainer] Режим: Топ {limit} монет")
            
            logger.info(f"[AutoTrainer] Запуск: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 час таймаут
            )
            
            if result.returncode == 0:
                logger.info("[AutoTrainer] ✅ Данные успешно обновлены")
                self.last_data_update = time.time()
                return True
            else:
                logger.error(f"[AutoTrainer] ❌ Ошибка обновления данных: {result.stderr}")
                return False
        
        except subprocess.TimeoutExpired:
            logger.error("[AutoTrainer] ❌ Таймаут при обновлении данных")
            return False
        except Exception as e:
            logger.error(f"[AutoTrainer] ❌ Ошибка обновления данных: {e}")
            return False
    
    def _retrain(self) -> bool:
        """
        Переобучает модель на обновленных данных
        
        Returns:
            True если успешно
        """
        try:
            logger.info("[AutoTrainer] 🧠 Переобучение модели...")
            
            # Запускаем скрипт обучения
            cmd = [
                sys.executable,
                str(self.train_script)
            ]
            
            logger.info(f"[AutoTrainer] Запуск: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 минут таймаут
            )
            
            if result.returncode == 0:
                logger.info("[AutoTrainer] ✅ Модель успешно переобучена")
                self.last_training = time.time()
                
                # Перезагружаем модель в AI Manager
                self._reload_model()
                
                return True
            else:
                logger.error(f"[AutoTrainer] ❌ Ошибка обучения: {result.stderr}")
                return False
        
        except subprocess.TimeoutExpired:
            logger.error("[AutoTrainer] ❌ Таймаут при обучении")
            return False
        except Exception as e:
            logger.error(f"[AutoTrainer] ❌ Ошибка обучения: {e}")
            return False
    
    def _reload_model(self):
        """Перезагружает модель в AI Manager без перезапуска бота"""
        try:
            from bot_engine.ai.ai_manager import get_ai_manager
            
            ai_manager = get_ai_manager()
            
            if ai_manager and ai_manager.anomaly_detector:
                # Перезагружаем модель
                model_path = AIConfig.AI_ANOMALY_MODEL_PATH
                scaler_path = AIConfig.AI_ANOMALY_SCALER_PATH
                
                success = ai_manager.anomaly_detector.load_model(model_path, scaler_path)
                
                if success:
                    logger.info("[AutoTrainer] ✅ Модель перезагружена (hot reload)")
                else:
                    logger.error("[AutoTrainer] ❌ Ошибка перезагрузки модели")
            else:
                logger.debug("[AutoTrainer] AI Manager не инициализирован")
        
        except Exception as e:
            logger.error(f"[AutoTrainer] Ошибка hot reload: {e}")
    
    def force_update(self) -> bool:
        """
        Принудительное обновление данных и переобучение
        
        Returns:
            True если успешно
        """
        logger.info("[AutoTrainer] 🔄 Принудительное обновление...")
        
        success = self._update_data()
        if success:
            success = self._retrain()
        
        return success
    
    def get_status(self) -> dict:
        """
        Возвращает статус автоматического тренера
        
        Returns:
            Словарь со статусом
        """
        return {
            'running': self.running,
            'last_data_update': datetime.fromtimestamp(self.last_data_update).isoformat() if self.last_data_update else None,
            'last_training': datetime.fromtimestamp(self.last_training).isoformat() if self.last_training else None,
            'next_data_update': datetime.fromtimestamp(self.last_data_update + AIConfig.AI_DATA_UPDATE_INTERVAL).isoformat() if self.last_data_update else None,
            'next_training': datetime.fromtimestamp(self.last_training + AIConfig.AI_RETRAIN_INTERVAL).isoformat() if self.last_training else None
        }


# Глобальный экземпляр
_auto_trainer: Optional[AutoTrainer] = None


def get_auto_trainer() -> AutoTrainer:
    """
    Получает глобальный экземпляр автоматического тренера
    
    Returns:
        Экземпляр AutoTrainer
    """
    global _auto_trainer
    
    if _auto_trainer is None:
        _auto_trainer = AutoTrainer()
    
    return _auto_trainer


def start_auto_trainer():
    """Запускает автоматический тренер"""
    if AIConfig.AI_AUTO_TRAIN_ENABLED:
        trainer = get_auto_trainer()
        trainer.start()
    else:
        logger.info("[AutoTrainer] Автоматическое обучение отключено в конфиге")


def stop_auto_trainer():
    """Останавливает автоматический тренер"""
    global _auto_trainer
    
    if _auto_trainer:
        _auto_trainer.stop()

