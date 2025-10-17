"""
Менеджер ИИ модулей

Координирует работу всех ИИ модулей и объединяет их рекомендации.
Автоматически проверяет лицензию и загружает доступные модули.
"""

import logging
from typing import Dict, Any, Optional
from bot_engine.bot_config import AIConfig
from ._premium_loader import get_premium_loader

logger = logging.getLogger('AI')


class AIManager:
    """Управление всеми ИИ модулями"""
    
    def __init__(self):
        self.premium_loader = get_premium_loader()
        
        # ИИ модули (будут None если недоступны)
        self.anomaly_detector = None
        self.lstm_predictor = None
        self.pattern_detector = None
        self.risk_manager = None
        
        # Кэш предсказаний
        self._predictions_cache = {}
        
        # Кэш доступности (чтобы не проверять каждый раз)
        self._availability_cache = None
        
        # Загружаем модули
        self.load_modules()
    
    def load_modules(self):
        """Загружает ИИ модули согласно настройкам и лицензии"""
        
        if not AIConfig.AI_ENABLED:
            logger.info("[AI] ℹ️ ИИ модули отключены в конфигурации")
            logger.info("[AI] 💡 Для включения установите AIConfig.AI_ENABLED = True")
            return
        
        # Проверяем наличие premium модулей
        if not self.premium_loader.premium_available:
            logger.warning("[AI] ⚠️ Premium модули не установлены")
            logger.info("[AI] 💡 Для использования ИИ функций:")
            logger.info("[AI]    1. Приобретите лицензию")
            logger.info("[AI]    2. Установите модуль: pip install infobot-ai-premium")
            logger.info("[AI]    3. Активируйте: python scripts/activate_premium.py")
            logger.info("[AI] ⚠️ AI функции будут отключены до активации лицензии")
            return
        
        # Проверяем лицензию
        if not self.premium_loader.license_valid:
            logger.warning("[AI] ⚠️ Лицензия недействительна или отсутствует")
            logger.info("[AI] 💡 Активируйте лицензию: python scripts/activate_premium.py")
            logger.info("[AI] 💡 Или включите режим разработки: set AI_DEV_MODE=1")
            logger.info("[AI] ⚠️ AI функции будут отключены до активации лицензии")
            return
        
        # Получаем информацию о лицензии
        license_info = self.premium_loader.get_license_info()
        features = license_info.get('features', {})
        
        logger.info(f"[AI] 🎫 Лицензия: {license_info['type']}")
        logger.info(f"[AI] 📅 Действительна до: {license_info['expires_at']}")
        
        # Загружаем Anomaly Detector
        if AIConfig.AI_ANOMALY_DETECTION_ENABLED and features.get('anomaly_detection'):
            try:
                anomaly_module = self.premium_loader.get_ai_module('anomaly_detector')
                self.anomaly_detector = anomaly_module.AnomalyDetector()
                logger.info("[AI] ✅ Anomaly Detector загружен")
            except Exception as e:
                logger.error(f"[AI] ❌ Ошибка загрузки Anomaly Detector: {e}")
        elif AIConfig.AI_ANOMALY_DETECTION_ENABLED:
            logger.warning("[AI] ⚠️ Anomaly Detection недоступен в вашей лицензии")
        
        # Загружаем LSTM Predictor
        if AIConfig.AI_LSTM_ENABLED and features.get('lstm_predictor'):
            try:
                lstm_module = self.premium_loader.get_ai_module('lstm_predictor')
                self.lstm_predictor = lstm_module.LSTMPricePredictor()
                logger.info("[AI] ✅ LSTM Predictor загружен")
            except Exception as e:
                logger.error(f"[AI] ❌ Ошибка загрузки LSTM Predictor: {e}")
        elif AIConfig.AI_LSTM_ENABLED:
            logger.warning("[AI] ⚠️ LSTM Predictor недоступен в вашей лицензии")
        
        # Загружаем Pattern Detector
        if AIConfig.AI_PATTERN_ENABLED and features.get('pattern_recognition'):
            try:
                pattern_module = self.premium_loader.get_ai_module('pattern_detector')
                self.pattern_detector = pattern_module.PatternDetector()
                logger.info("[AI] ✅ Pattern Detector загружен")
            except Exception as e:
                logger.error(f"[AI] ❌ Ошибка загрузки Pattern Detector: {e}")
        elif AIConfig.AI_PATTERN_ENABLED:
            logger.warning("[AI] ⚠️ Pattern Recognition недоступен в вашей лицензии")
        
        # Загружаем Risk Manager
        if AIConfig.AI_RISK_MANAGEMENT_ENABLED and features.get('risk_management'):
            try:
                risk_module = self.premium_loader.get_ai_module('risk_manager')
                self.risk_manager = risk_module.DynamicRiskManager()
                logger.info("[AI] ✅ Risk Manager загружен")
            except Exception as e:
                logger.error(f"[AI] ❌ Ошибка загрузки Risk Manager: {e}")
        elif AIConfig.AI_RISK_MANAGEMENT_ENABLED:
            logger.warning("[AI] ⚠️ Risk Management недоступен в вашей лицензии")
        
        # Итоговая статистика
        loaded_count = sum([
            self.anomaly_detector is not None,
            self.lstm_predictor is not None,
            self.pattern_detector is not None,
            self.risk_manager is not None
        ])
        
        if loaded_count > 0:
            logger.info(f"[AI] 🎉 Загружено модулей: {loaded_count}/4")
        else:
            logger.warning("[AI] ⚠️ Ни один ИИ модуль не был загружен")
    
    def is_available(self) -> bool:
        """
        Проверяет доступность ИИ функций (кэшированная проверка)
        
        Returns:
            True если хотя бы один модуль доступен
        """
        # Используем кэш для быстрой проверки
        if self._availability_cache is None:
            self._availability_cache = (
                self.premium_loader.premium_available and 
                self.premium_loader.license_valid and
                any([
                    self.anomaly_detector is not None,
                    self.lstm_predictor is not None,
                    self.pattern_detector is not None,
                    self.risk_manager is not None
                ])
            )
        
        return self._availability_cache
    
    def analyze_coin(self, symbol: str, coin_data: dict, candles: list) -> Dict[str, Any]:
        """
        Комплексный анализ монеты всеми ИИ модулями
        
        Args:
            symbol: Символ монеты (например, 'BTC')
            coin_data: Данные монеты из системы
            candles: Список свечей
        
        Returns:
            Словарь с результатами анализа всех модулей
        """
        if not self.is_available():
            return {
                'available': False,
                'reason': 'AI modules not available or license invalid',
                'lstm_prediction': None,
                'pattern_analysis': None,
                'risk_analysis': None,
                'anomaly_score': None
            }
        
        analysis = {
            'available': True,
            'lstm_prediction': None,
            'pattern_analysis': None,
            'risk_analysis': None,
            'anomaly_score': None
        }
        
        # Anomaly Detection
        if self.anomaly_detector:
            try:
                anomaly = self.anomaly_detector.detect(candles)
                analysis['anomaly_score'] = anomaly
                
                if anomaly.get('is_anomaly') and AIConfig.AI_LOG_ANOMALIES:
                    severity = anomaly.get('severity', 0)
                    anomaly_type = anomaly.get('anomaly_type', 'UNKNOWN')
                    logger.warning(
                        f"[AI] {symbol} ⚠️ Аномалия: {anomaly_type} "
                        f"(severity: {severity:.2%})"
                    )
            except Exception as e:
                logger.error(f"[AI] Ошибка Anomaly Detection для {symbol}: {e}")
        
        # LSTM Prediction
        if self.lstm_predictor:
            try:
                # TODO: Реализовать LSTM предсказание
                # lstm_pred = self.lstm_predictor.predict(candles)
                # analysis['lstm_prediction'] = lstm_pred
                pass
            except Exception as e:
                logger.error(f"[AI] Ошибка LSTM для {symbol}: {e}")
        
        # Pattern Recognition
        if self.pattern_detector:
            try:
                # TODO: Реализовать распознавание паттернов
                # pattern = self.pattern_detector.detect(candles)
                # analysis['pattern_analysis'] = pattern
                pass
            except Exception as e:
                logger.error(f"[AI] Ошибка Pattern Detection для {symbol}: {e}")
        
        # Risk Management
        if self.risk_manager and coin_data.get('in_position'):
            try:
                # TODO: Реализовать динамический риск-менеджмент
                # risk = self.risk_manager.analyze(symbol, coin_data, candles)
                # analysis['risk_analysis'] = risk
                pass
            except Exception as e:
                logger.error(f"[AI] Ошибка Risk Management для {symbol}: {e}")
        
        return analysis
    
    def get_final_recommendation(self, 
                                 symbol: str, 
                                 system_signal: str, 
                                 ai_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Объединяет системный сигнал и ИИ анализ для финальной рекомендации
        
        Args:
            symbol: Символ монеты
            system_signal: Сигнал от основной системы (ENTER_LONG/ENTER_SHORT/WAIT)
            ai_analysis: Результаты ИИ анализа
        
        Returns:
            Словарь с финальной рекомендацией
        """
        if not ai_analysis.get('available'):
            return {
                'signal': system_signal,
                'confidence': 0.5,
                'source': 'SYSTEM',
                'ai_enabled': False
            }
        
        # Взвешенное голосование
        votes = {'ENTER_LONG': 0.0, 'ENTER_SHORT': 0.0, 'WAIT': 0.0}
        total_weight = 0.0
        
        # Системный сигнал (базовый вес = 1.0)
        votes[system_signal] += 1.0
        total_weight += 1.0
        
        # Anomaly Detection (вес = 2.0 - ОЧЕНЬ важно!)
        anomaly = ai_analysis.get('anomaly_score')
        if anomaly and anomaly.get('is_anomaly'):
            severity = anomaly.get('severity', 0)
            
            if severity > AIConfig.AI_ANOMALY_BLOCK_THRESHOLD:
                # Критическая аномалия - блокируем вход!
                votes['WAIT'] += 2.0
                total_weight += 2.0
                
                logger.warning(
                    f"[AI] {symbol} 🚫 Вход заблокирован из-за аномалии "
                    f"(severity: {severity:.2%})"
                )
        
        # TODO: Добавить голосование LSTM, Pattern, и т.д.
        
        # Определяем финальный сигнал
        final_signal = max(votes, key=votes.get)
        confidence = votes[final_signal] / total_weight if total_weight > 0 else 0.5
        
        result = {
            'signal': final_signal,
            'confidence': confidence,
            'source': 'AI_ENSEMBLE',
            'votes': votes,
            'system_signal': system_signal,
            'ai_enabled': True
        }
        
        # Логируем если ИИ изменил сигнал
        if final_signal != system_signal and AIConfig.AI_LOG_PREDICTIONS:
            logger.info(
                f"[AI] {symbol} 🔄 Сигнал изменен: {system_signal} → {final_signal} "
                f"(уверенность: {confidence:.2%})"
            )
        
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """
        Возвращает статус ИИ системы
        
        Returns:
            Словарь со статусом всех компонентов
        """
        license_info = self.premium_loader.get_license_info()
        
        return {
            'enabled': AIConfig.AI_ENABLED,
            'available': self.is_available(),
            'license': {
                'valid': self.premium_loader.license_valid,
                'type': license_info.get('type'),
                'expires_at': license_info.get('expires_at')
            },
            'modules': {
                'anomaly_detector': self.anomaly_detector is not None,
                'lstm_predictor': self.lstm_predictor is not None,
                'pattern_detector': self.pattern_detector is not None,
                'risk_manager': self.risk_manager is not None
            }
        }


# Глобальный экземпляр AI Manager
_ai_manager: Optional[AIManager] = None


def get_ai_manager() -> AIManager:
    """
    Получает глобальный экземпляр AI Manager
    
    Returns:
        Экземпляр AIManager
    """
    global _ai_manager
    
    if _ai_manager is None:
        _ai_manager = AIManager()
    
    return _ai_manager

