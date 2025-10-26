"""
Менеджер ИИ модулей

Координирует работу всех ИИ модулей и объединяет их рекомендации.
Автоматически проверяет лицензию и загружает доступные модули.
"""

import logging
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from bot_engine.bot_config import AIConfig
from cryptography.fernet import Fernet
from base64 import urlsafe_b64encode
import hmac
import hashlib

logger = logging.getLogger('AI')


class AIManager:
    """Управление всеми ИИ модулями"""
    
    def __init__(self):
        # ИИ модули (будут None если недоступны)
        self.anomaly_detector = None
        self.lstm_predictor = None
        self.pattern_detector = None
        self.risk_manager = None
        
        # Кэш предсказаний
        self._predictions_cache = {}
        
        # Проверяем лицензию
        self._license_valid = False
        self._license_info = None
        self._check_license()
        
        # Загружаем модули
        self.load_modules()
    
    def _check_license(self):
        """Встроенная проверка лицензии (защищенная)"""
        if not AIConfig.AI_ENABLED:
            return
        
        # Проверяем .lic файл в корне
        root = Path(__file__).parent.parent.parent
        lic_files = [f for f in os.listdir(root) if f.endswith('.lic')]
        
        if not lic_files:
            self._license_valid = False
            return
        
        # Расшифровка и проверка лицензии
        try:
            lic_file = root / lic_files[0]
            with open(lic_file, 'rb') as f:
                d = f.read()
            
            # Ключи шифрования (обфусцированы)
            k1 = 'InfoBot' + 'AI2024'
            k2 = 'Premium' + 'License'
            k3 = 'Key_SECRET'
            sk = (k1 + k2 + k3 + '_DO_NOT_SHARE').encode()[:32]
            x = urlsafe_b64encode(sk)
            cf = Fernet(x)
            
            # Расшифровка
            dec = cf.decrypt(d)
            ld = json.loads(dec.decode())
            
            # Проверка подписи
            sk2 = 'SECRET' + '_SIGNATURE_' + 'KEY_2024_PREMIUM'
            dtv = json.dumps({k:v for k,v in ld.items() if k != 'signature'}, sort_keys=True)
            es = hmac.new(sk2.encode(), dtv.encode(), hashlib.sha256).hexdigest()
            
            if not hmac.compare_digest(ld.get('signature', ''), es):
                self._license_valid = False
                logger.warning("[AI] Invalid license signature")
                return
            
            # Проверка срока
            ea = datetime.fromisoformat(ld['expires_at'])
            if datetime.now() > ea:
                self._license_valid = False
                logger.warning("[AI] License expired")
                return
            
            # Лицензия валидна
            self._license_valid = True
            self._license_info = {
                'type': ld.get('type', 'premium'),
                'expires_at': ld['expires_at'],
                'features': ld.get('features', {
                    'anomaly_detection': True,
                    'lstm_predictor': True,
                    'pattern_recognition': True,
                    'risk_management': True,
                })
            }
            logger.info(f"[AI] License validated: {ld.get('type', 'premium')}")
            
        except Exception as e:
            self._license_valid = False
            logger.warning(f"[AI] License check failed: {e}")
    
    def load_modules(self):
        """Загружает ИИ модули согласно настройкам и лицензии"""
        
        if not AIConfig.AI_ENABLED:
            logger.info("[AI] ℹ️ ИИ модули отключены в конфигурации")
            return
        
        # Если нет лицензии - базовый функционал
        if not self._license_valid:
            logger.info("[AI] ⚠️ AI функции недоступны без лицензии")
            return
        
        features = self._license_info.get('features', {}) if self._license_info else {}
        
        if self._license_info:
            logger.info(f"[AI] 🎫 Лицензия: {self._license_info['type']}")
            logger.info(f"[AI] 📅 Действительна до: {self._license_info['expires_at']}")
        
        # Загружаем модули напрямую
        # Загружаем Anomaly Detector
        if AIConfig.AI_ANOMALY_DETECTION_ENABLED and features.get('anomaly_detection'):
            try:
                from bot_engine.ai.anomaly_detector import AnomalyDetector
                self.anomaly_detector = AnomalyDetector(
                    model_path=AIConfig.AI_ANOMALY_MODEL_PATH,
                    scaler_path=AIConfig.AI_ANOMALY_SCALER_PATH
                )
                logger.info("[AI] ✅ Anomaly Detector загружен")
            except Exception as e:
                logger.error(f"[AI] ❌ Ошибка загрузки Anomaly Detector: {e}")
        
        # Загружаем LSTM Predictor
        if AIConfig.AI_LSTM_ENABLED and features.get('lstm_predictor'):
            try:
                from bot_engine.ai.lstm_predictor import LSTMPredictor
                self.lstm_predictor = LSTMPredictor(
                    model_path=AIConfig.AI_LSTM_MODEL_PATH,
                    scaler_path=AIConfig.AI_LSTM_SCALER_PATH
                )
                logger.info("[AI] ✅ LSTM Predictor загружен")
            except Exception as e:
                logger.error(f"[AI] ❌ Ошибка загрузки LSTM Predictor: {e}")
        elif AIConfig.AI_LSTM_ENABLED:
            # Пробуем загрузить встроенную версию даже без premium
            try:
                from bot_engine.ai.lstm_predictor import LSTMPredictor
                self.lstm_predictor = LSTMPredictor(
                    model_path=AIConfig.AI_LSTM_MODEL_PATH,
                    scaler_path=AIConfig.AI_LSTM_SCALER_PATH
                )
                logger.info("[AI] ✅ LSTM Predictor загружен (встроенная версия, без premium)")
            except Exception as e:
                logger.warning("[AI] ⚠️ LSTM Predictor недоступен")
        
        # Загружаем Pattern Detector
        if AIConfig.AI_PATTERN_ENABLED and features.get('pattern_recognition'):
            try:
                from bot_engine.ai.pattern_detector import PatternDetector
                self.pattern_detector = PatternDetector()
                logger.info("[AI] ✅ Pattern Detector загружен")
            except Exception as e:
                logger.error(f"[AI] ❌ Ошибка загрузки Pattern Detector: {e}")
        elif AIConfig.AI_PATTERN_ENABLED:
            # Пробуем загрузить встроенную версию даже без premium
            try:
                from bot_engine.ai.pattern_detector import PatternDetector
                self.pattern_detector = PatternDetector()
                logger.info("[AI] ✅ Pattern Detector загружен (встроенная версия, без premium)")
            except Exception as e:
                logger.warning("[AI] ⚠️ Pattern Recognition недоступен")
        
        # Загружаем Risk Manager
        if AIConfig.AI_RISK_MANAGEMENT_ENABLED and features.get('risk_management'):
            try:
                from bot_engine.ai.risk_manager import DynamicRiskManager
                self.risk_manager = DynamicRiskManager()
                logger.info("[AI] ✅ Risk Manager загружен")
            except Exception as e:
                logger.error(f"[AI] ❌ Ошибка загрузки Risk Manager: {e}")
        elif AIConfig.AI_RISK_MANAGEMENT_ENABLED:
            # Пробуем загрузить встроенную версию даже без premium
            try:
                from bot_engine.ai.risk_manager import DynamicRiskManager
                self.risk_manager = DynamicRiskManager()
                logger.info("[AI] ✅ Risk Manager загружен (встроенная версия, без premium)")
            except Exception as e:
                logger.warning("[AI] ⚠️ Risk Management недоступен")
        
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
                current_price = coin_data.get('current_price') or (candles[-1].get('close') if candles else None)
                if current_price:
                    lstm_pred = self.lstm_predictor.predict(candles, current_price)
                    if lstm_pred and lstm_pred.get('confidence', 0) >= AIConfig.AI_LSTM_MIN_CONFIDENCE:
                        analysis['lstm_prediction'] = lstm_pred
                        
                        if AIConfig.AI_LOG_PREDICTIONS:
                            direction_str = "↑ ВВЕРХ" if lstm_pred['direction'] > 0 else "↓ ВНИЗ"
                            logger.info(
                                f"[AI] {symbol} 🧠 LSTM: {direction_str} "
                                f"({lstm_pred['change_percent']:+.2f}%, "
                                f"уверенность: {lstm_pred['confidence']:.1f}%)"
                            )
            except Exception as e:
                logger.error(f"[AI] Ошибка LSTM для {symbol}: {e}")
        
        # Pattern Recognition
        if self.pattern_detector:
            try:
                current_price = coin_data.get('current_price') or (candles[-1].get('close') if candles else None)
                if current_price:
                    pattern_result = self.pattern_detector.detect_patterns(candles, current_price)
                    
                    if pattern_result['patterns']:
                        analysis['pattern_analysis'] = pattern_result
                        
                        if AIConfig.AI_LOG_PREDICTIONS:
                            signal_icon = "🟢" if pattern_result['signal'] == 'BULLISH' else "🔴" if pattern_result['signal'] == 'BEARISH' else "⚪"
                            logger.info(
                                f"[AI] {symbol} 📊 Паттерны: {signal_icon} {pattern_result['signal']} "
                                f"(найдено: {len(pattern_result['patterns'])}, "
                                f"уверенность: {pattern_result['confidence']:.1f}%)"
                            )
                            
                            if pattern_result['strongest_pattern']:
                                strongest = pattern_result['strongest_pattern']
                                logger.info(
                                    f"[AI] {symbol}    └─ Сильнейший: {strongest['name']} "
                                    f"({strongest['confidence']:.1f}%)"
                                )
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

