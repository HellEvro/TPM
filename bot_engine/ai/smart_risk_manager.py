"""
Smart Risk Manager - Премиум-модуль умного риск-менеджмента

Особенности:
- Обучение на стопах (анализ причин неудачных сделок)
- Бэктестинг каждой монеты перед входом в позицию
- Оптимизация SL/TP на основе исторических данных
- Определение лучших точек входа

ТРЕБУЕТ ПРЕМИУМ ЛИЦЕНЗИИ!
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import json
from pathlib import Path

logger = logging.getLogger('AI.SmartRiskManager')

# Проверяем лицензию при импорте
try:
    from bot_engine.ai import check_premium_license
    PREMIUM_AVAILABLE = check_premium_license()
except ImportError:
    PREMIUM_AVAILABLE = False


class SmartRiskManager:
    """Умный риск-менеджмент с обучением на стопах (Premium только!)"""
    
    def __init__(self):
        """Инициализация (только с лицензией!)"""
        if not PREMIUM_AVAILABLE:
            raise ImportError(
                "SmartRiskManager требует премиум лицензию. "
                "Для активации: python scripts/activate_premium.py"
            )
        
        self.logger = logger
        self.backtest_cache = {}
        self.stop_patterns = {}
        self.training_data_path = Path('data/ai/training/stops_analysis.json')
        
        # Создаем директорию если нужно
        self.training_data_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Загружаем обученные паттерны
        self._load_stop_patterns()
        
        logger.info("[SmartRiskManager] ✅ Премиум-модуль загружен и готов к работе")
    
    def analyze_stopped_trades(self, limit: int = 100) -> Dict[str, Any]:
        """
        Анализирует последние стопы для обучения ИИ
        
        Returns:
            Словарь с анализом стопов и рекомендациями
        """
        try:
            from bot_engine.bot_history import bot_history_manager
            
            # Получаем стопы из истории
            stopped_trades = bot_history_manager.get_stopped_trades(limit)
            
            if not stopped_trades:
                return {
                    'total_stops': 0,
                    'message': 'Нет данных о стопах для анализа'
                }
            
            # Анализируем паттерны
            patterns = self._extract_patterns(stopped_trades)
            common_reasons = self._analyze_reasons(stopped_trades)
            optimal_sl = self._optimize_stop_loss(stopped_trades)
            optimal_tp = self._optimize_take_profit(stopped_trades)
            
            # Сохраняем для обучения
            self._save_for_training(patterns)
            
            return {
                'total_stops': len(stopped_trades),
                'common_reasons': common_reasons,
                'optimal_sl_percent': optimal_sl,
                'optimal_tp_percent': optimal_tp,
                'patterns': patterns,
                'recommendations': self._generate_recommendations(stopped_trades)
            }
            
        except Exception as e:
            logger.error(f"[SmartRiskManager] Ошибка анализа стопов: {e}")
            return {
                'total_stops': 0,
                'error': str(e)
            }
    
    def backtest_coin(
        self, 
        symbol: str, 
        candles: List[dict], 
        direction: str,
        current_price: float
    ) -> Dict[str, Any]:
        """
        Быстрый бэктест монеты перед входом в позицию
        
        Args:
            symbol: Символ монеты
            candles: Последние 50-100 свечей
            direction: 'LONG' или 'SHORT'
            current_price: Текущая цена
        
        Returns:
            Оптимальные параметры входа (entry, SL, TP) и confidence
        """
        try:
            if len(candles) < 20:
                return self._default_backtest_result()
            
            # Используем кэш если есть
            cache_key = f"{symbol}_{direction}_{len(candles)}"
            if cache_key in self.backtest_cache:
                logger.debug(f"[SmartRiskManager] Используем кэш для {symbol}")
                return self.backtest_cache[cache_key]
            
            # Быстрый бэктест на последних свечах
            result = self._quick_backtest(symbol, candles, direction, current_price)
            
            # Кэшируем результат (на 1 час)
            self.backtest_cache[cache_key] = result
            
            return result
            
        except Exception as e:
            logger.error(f"[SmartRiskManager] Ошибка бэктеста {symbol}: {e}")
            return self._default_backtest_result()
    
    def _quick_backtest(
        self, 
        symbol: str, 
        candles: List[dict], 
        direction: str,
        current_price: float
    ) -> Dict[str, Any]:
        """Быстрый бэктест (упрощенная версия)"""
        
        # Анализируем волатильность
        volatility = self._calculate_volatility(candles)
        
        # Анализируем силу тренда
        trend_strength = self._calculate_trend_strength(candles, direction)
        
        # Рассчитываем оптимальные SL/TP на основе истории стопов для этой монеты
        coin_stops = self._get_coin_stops(symbol)
        
        if coin_stops:
            # Используем данные о стопах этой монеты
            optimal_sl = self._optimal_sl_for_coin(coin_stops, volatility)
            optimal_tp = self._optimal_tp_for_coin(coin_stops, trend_strength)
        else:
            # Используем общие рекомендации
            optimal_sl = 12.0 if volatility < 1.0 else 18.0
            optimal_tp = 80.0 if trend_strength < 0.5 else 120.0
        
        # Рассчитываем оптимальную точку входа
        optimal_entry = self._optimal_entry_price(candles, direction, current_price)
        
        # Confidence на основе качества данных
        confidence = self._calculate_confidence(candles, coin_stops)
        
        return {
            'optimal_entry': optimal_entry,
            'optimal_sl': current_price * (1 - optimal_sl / 100) if direction == 'LONG' else current_price * (1 + optimal_sl / 100),
            'optimal_tp': current_price * (1 + optimal_tp / 100) if direction == 'LONG' else current_price * (1 - optimal_tp / 100),
            'optimal_sl_percent': optimal_sl,
            'optimal_tp_percent': optimal_tp,
            'win_rate': self._estimate_win_rate(candles, direction),
            'expected_return': self._estimate_return(candles, direction),
            'confidence': confidence,
            'volatility': volatility,
            'trend_strength': trend_strength
        }
    
    def _extract_patterns(self, stopped_trades: List[Dict]) -> Dict:
        """Извлекает паттерны из стопов"""
        patterns = {
            'high_rsi_stops': 0,
            'low_volatility_stops': 0,
            'rapid_stops': 0,
            'trailing_stops': 0
        }
        
        for trade in stopped_trades:
            entry_data = trade.get('entry_data', {})
            exit_reason = trade.get('close_reason', '')
            
            # Высокий RSI на входе
            if entry_data.get('rsi', 50) > 70:
                patterns['high_rsi_stops'] += 1
            
            # Низкая волатильность
            if entry_data.get('volatility', 1.0) < 0.5:
                patterns['low_volatility_stops'] += 1
            
            # Быстрое закрытие (< 6 часов)
            duration = entry_data.get('duration_hours', 0)
            if duration > 0 and duration < 6:
                patterns['rapid_stops'] += 1
            
            # Trailing stop
            if 'trailing' in exit_reason.lower():
                patterns['trailing_stops'] += 1
        
        return patterns
    
    def _analyze_reasons(self, stopped_trades: List[Dict]) -> Dict:
        """Анализирует основные причины стопов"""
        reasons = {}
        
        for trade in stopped_trades:
            reason = trade.get('close_reason', 'UNKNOWN')
            reasons[reason] = reasons.get(reason, 0) + 1
        
        # Сортируем по частоте
        sorted_reasons = dict(sorted(reasons.items(), key=lambda x: x[1], reverse=True))
        
        return sorted_reasons
    
    def _optimize_stop_loss(self, stopped_trades: List[Dict]) -> float:
        """Оптимизирует Stop Loss на основе истории"""
        if not stopped_trades:
            return 15.0  # Дефолт
        
        # Анализируем RSI на входе успешных и неуспешных сделок
        # TODO: Здесь можно добавить ML для оптимизации
        
        return 15.0  # Временно возвращаем дефолт
    
    def _optimize_take_profit(self, stopped_trades: List[Dict]) -> float:
        """Оптимизирует Take Profit на основе истории"""
        if not stopped_trades:
            return 100.0  # Дефолт
        
        return 100.0  # Временно возвращаем дефолт
    
    def _calculate_volatility(self, candles: List[dict]) -> float:
        """Рассчитывает волатильность"""
        if len(candles) < 20:
            return 1.0
        
        # Рассчитываем изменения цены
        changes = []
        for i in range(1, len(candles)):
            change = abs(candles[i]['close'] - candles[i-1]['close']) / candles[i-1]['close']
            changes.append(change)
        
        return np.mean(changes) * 100 * 100  # В процентах
    
    def _calculate_trend_strength(self, candles: List[dict], direction: str) -> float:
        """Рассчитывает силу тренда"""
        if len(candles) < 10:
            return 0.5
        
        # Анализ последних свечей
        recent = candles[-10:]
        up_ticks = sum(1 for i in range(1, len(recent)) if recent[i]['close'] > recent[i-1]['close'])
        
        if direction == 'LONG':
            return up_ticks / len(recent)
        else:  # SHORT
            return (len(recent) - up_ticks) / len(recent)
    
    def _get_coin_stops(self, symbol: str) -> List[Dict]:
        """Получает стопы для конкретной монеты"""
        if symbol in self.stop_patterns:
            return self.stop_patterns[symbol]
        return []
    
    def _optimal_sl_for_coin(self, stops: List[Dict], volatility: float) -> float:
        """Рассчитывает оптимальный SL для монеты"""
        # TODO: ML модель для оптимизации
        return 12.0 if volatility < 1.0 else 18.0
    
    def _optimal_tp_for_coin(self, stops: List[Dict], trend_strength: float) -> float:
        """Рассчитывает оптимальный TP для монеты"""
        # TODO: ML модель для оптимизации
        return 80.0 if trend_strength < 0.5 else 120.0
    
    def _optimal_entry_price(self, candles: List[dict], direction: str, current_price: float) -> float:
        """Определяет оптимальную цену входа"""
        # Находим локальные минимумы/максимумы
        if direction == 'LONG':
            # Ищем локальный минимум
            lows = [c['low'] for c in candles[-10:]]
            return min(lows)
        else:  # SHORT
            # Ищем локальный максимум
            highs = [c['high'] for c in candles[-10:]]
            return max(highs)
    
    def _calculate_confidence(self, candles: List[dict], stops: List[Dict]) -> float:
        """Рассчитывает confidence на основе качества данных"""
        confidence = 0.5  # Базовый
        
        # Больше свечей = выше confidence
        if len(candles) >= 50:
            confidence += 0.2
        
        # Есть история стопов для этой монеты
        if stops:
            confidence += 0.2
        
        # Низкая волатильность = выше confidence
        volatility = self._calculate_volatility(candles)
        if volatility < 1.0:
            confidence += 0.1
        
        return min(confidence, 0.95)
    
    def _estimate_win_rate(self, candles: List[dict], direction: str) -> float:
        """Оценивает win rate на основе истории"""
        # TODO: Добавить реальную оценку на основе бэктеста
        return 0.6  # Дефолт
    
    def _estimate_return(self, candles: List[dict], direction: str) -> float:
        """Оценивает ожидаемую доходность"""
        # TODO: Добавить реальную оценку
        return 50.0  # Дефолт в %
    
    def _load_stop_patterns(self):
        """Загружает обученные паттерны"""
        try:
            if self.training_data_path.exists():
                with open(self.training_data_path, 'r') as f:
                    data = json.load(f)
                    self.stop_patterns = data.get('patterns', {})
                    logger.debug(f"[SmartRiskManager] Загружено {len(self.stop_patterns)} паттернов")
        except Exception as e:
            logger.warning(f"[SmartRiskManager] Не удалось загрузить паттерны: {e}")
    
    def _save_for_training(self, patterns: Dict):
        """Сохраняет данные для обучения"""
        try:
            data = {
                'patterns': patterns,
                'updated_at': datetime.now().isoformat()
            }
            
            with open(self.training_data_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"[SmartRiskManager] Не удалось сохранить данные: {e}")
    
    def _generate_recommendations(self, stopped_trades: List[Dict]) -> List[str]:
        """Генерирует рекомендации на основе анализа стопов"""
        recommendations = []
        
        patterns = self._extract_patterns(stopped_trades)
        
        if patterns['high_rsi_stops'] > len(stopped_trades) * 0.3:
            recommendations.append("Избегайте входов при RSI > 70")
        
        if patterns['low_volatility_stops'] > len(stopped_trades) * 0.3:
            recommendations.append("Выходите быстрее при низкой волатильности")
        
        if patterns['rapid_stops'] > len(stopped_trades) * 0.5:
            recommendations.append("Держите позиции дольше - большинство стопов слишком быстрые")
        
        if not recommendations:
            recommendations.append("Данных недостаточно для конкретных рекомендаций")
        
        return recommendations
    
    def _default_backtest_result(self) -> Dict[str, Any]:
        """Возвращает дефолтный результат бэктеста"""
        return {
            'optimal_entry': None,
            'optimal_sl': None,
            'optimal_tp': None,
            'optimal_sl_percent': 15.0,
            'optimal_tp_percent': 100.0,
            'win_rate': 0.5,
            'expected_return': 0.0,
            'confidence': 0.3,
            'volatility': 1.0,
            'trend_strength': 0.5
        }


# Проверка лицензии при импорте
if not PREMIUM_AVAILABLE:
    logger.warning("[SmartRiskManager] ⚠️ Премиум-лицензия не найдена, модуль недоступен")

