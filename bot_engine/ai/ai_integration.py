#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль интеграции AI в bots.py

Применяет обученные стратегии AI в процессе принятия торговых решений
"""

import os
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger('AI.Integration')

# Глобальный экземпляр AI системы
_ai_system = None


def get_ai_system():
    """Получить экземпляр AI системы"""
    global _ai_system
    
    if _ai_system is None:
        try:
            # ai.py находится в корне проекта
            from ai import get_ai_system as _get_ai_system
            _ai_system = _get_ai_system()
        except Exception as e:
            logger.debug(f"AI система недоступна: {e}")
            return None
    
    return _ai_system


def should_use_ai_prediction(symbol: str, config: Dict = None) -> bool:
    """
    Проверяет, нужно ли использовать AI предсказания
    
    Args:
        symbol: Символ монеты
        config: Конфигурация бота
    
    Returns:
        True если нужно использовать AI
    """
    try:
        # Проверяем настройку в конфиге
        if config:
            ai_enabled = config.get('ai_enabled', False)
            if not ai_enabled:
                return False
        
        # Проверяем доступность AI системы
        ai_system = get_ai_system()
        if not ai_system:
            return False
        
        # Проверяем, обучены ли модели
        if not ai_system.trainer or not ai_system.trainer.signal_predictor:
            return False
        
        return True
        
    except Exception as e:
        logger.debug(f"Ошибка проверки использования AI: {e}")
        return False


def get_ai_prediction(symbol: str, market_data: Dict) -> Optional[Dict]:
    """
    Получить предсказание AI для символа
    
    Args:
        symbol: Символ монеты
        market_data: Рыночные данные (RSI, тренд, цена и т.д.)
    
    Returns:
        Предсказание AI или None
    """
    try:
        ai_system = get_ai_system()
        if not ai_system:
            return None
        
        prediction = ai_system.predict_signal(symbol, market_data)
        
        if 'error' in prediction:
            return None
        
        return prediction
        
    except Exception as e:
        logger.debug(f"Ошибка получения предсказания AI для {symbol}: {e}")
        return None


def apply_ai_prediction_to_signal(
    symbol: str,
    original_signal: str,
    market_data: Dict,
    config: Dict = None
) -> Dict:
    """
    Применяет предсказание AI к оригинальному сигналу
    
    Args:
        symbol: Символ монеты
        original_signal: Оригинальный сигнал (LONG/SHORT/WAIT)
        market_data: Рыночные данные
        config: Конфигурация бота
    
    Returns:
        Словарь с результирующим сигналом и информацией об AI
    """
    try:
        # Проверяем, нужно ли использовать AI
        if not should_use_ai_prediction(symbol, config):
            return {
                'signal': original_signal,
                'ai_used': False,
                'reason': 'AI disabled or not available'
            }
        
        # Получаем предсказание AI
        ai_prediction = get_ai_prediction(symbol, market_data)
        
        if not ai_prediction:
            return {
                'signal': original_signal,
                'ai_used': False,
                'reason': 'AI prediction not available'
            }
        
        ai_signal = ai_prediction.get('signal', 'WAIT')
        ai_confidence = ai_prediction.get('confidence', 0)
        
        # Минимальная уверенность для применения AI сигнала
        min_confidence = config.get('ai_min_confidence', 0.7) if config else 0.7
        
        # Если уверенность AI высокая, используем его сигнал
        if ai_confidence >= min_confidence:
            return {
                'signal': ai_signal,
                'ai_used': True,
                'ai_confidence': ai_confidence,
                'ai_prediction': ai_prediction,
                'original_signal': original_signal,
                'reason': f'AI signal used (confidence: {ai_confidence:.2%})'
            }
        
        # Если уверенность низкая, используем оригинальный сигнал
        return {
            'signal': original_signal,
            'ai_used': True,
            'ai_confidence': ai_confidence,
            'ai_prediction': ai_prediction,
            'reason': f'Original signal used (AI confidence too low: {ai_confidence:.2%})'
        }
        
    except Exception as e:
        logger.error(f"Ошибка применения AI предсказания для {symbol}: {e}")
        return {
            'signal': original_signal,
            'ai_used': False,
            'error': str(e)
        }


def get_optimized_bot_config(symbol: str) -> Optional[Dict]:
    """
    Получить оптимизированную конфигурацию бота от AI
    
    Args:
        symbol: Символ монеты
    
    Returns:
        Оптимизированная конфигурация или None
    """
    try:
        ai_system = get_ai_system()
        if not ai_system:
            return None
        
        optimized = ai_system.optimize_bot_config(symbol)
        
        if 'error' in optimized:
            return None
        
        return optimized
        
    except Exception as e:
        logger.debug(f"Ошибка получения оптимизированной конфигурации для {symbol}: {e}")
        return None


def should_open_position_with_ai(
    symbol: str,
    direction: str,
    rsi: float,
    trend: str,
    price: float,
    config: Dict = None
) -> Dict:
    """
    Проверяет, нужно ли открывать позицию с учетом AI предсказания
    
    Использует обученные модели из data/ai/models/:
    - signal_predictor.pkl - предсказание сигналов
    - profit_predictor.pkl - предсказание прибыльности
    
    Args:
        symbol: Символ монеты
        direction: Направление (LONG/SHORT)
        rsi: Текущий RSI
        trend: Текущий тренд
        price: Текущая цена
        config: Конфигурация бота
    
    Returns:
        Словарь с решением и информацией об AI
    """
    try:
        # Проверяем наличие обученных моделей
        if not AI_SYSTEM_AVAILABLE or not ai_system_instance:
            return {'should_open': True, 'ai_used': False, 'reason': 'AI system not available'}
        
        if not ai_system_instance.trainer or not ai_system_instance.trainer.signal_predictor:
            logger.debug(f"🤖 AI модели не обучены для {symbol} - используем базовую логику")
            return {'should_open': True, 'ai_used': False, 'reason': 'AI models not trained yet'}
        
        # Подготавливаем рыночные данные
        market_data = {
            'rsi': rsi,
            'trend': trend,
            'price': price,
            'direction': direction
        }
        
        # Получаем предсказание от обученной модели
        prediction = ai_system_instance.predict_signal(symbol, market_data)
        
        if 'error' in prediction:
            logger.debug(f"⚠️ Ошибка предсказания AI для {symbol}: {prediction.get('error')}")
            return {'should_open': True, 'ai_used': False, 'reason': f"AI prediction error: {prediction.get('error')}"}
        
        signal = prediction.get('signal')
        confidence = prediction.get('confidence', 0)
        
        ai_confidence_threshold = config.get('ai_min_confidence', 0.65) if config else 0.65
        
        should_open = False
        reason = f"AI signal: {signal}, confidence: {confidence:.2%}"
        
        # Применяем логику AI
        if direction == 'LONG' and signal == 'LONG' and confidence >= ai_confidence_threshold:
            should_open = True
            logger.debug(f"🤖 AI подтверждает LONG для {symbol} (уверенность: {confidence:.2%})")
        elif direction == 'SHORT' and signal == 'SHORT' and confidence >= ai_confidence_threshold:
            should_open = True
            logger.debug(f"🤖 AI подтверждает SHORT для {symbol} (уверенность: {confidence:.2%})")
        elif signal == 'WAIT':
            should_open = False
            logger.debug(f"🤖 AI рекомендует WAIT для {symbol} (уверенность: {confidence:.2%})")
        elif confidence < ai_confidence_threshold:
            should_open = False
            reason = f"AI confidence too low: {confidence:.2%} < {ai_confidence_threshold:.2%}"
            logger.debug(f"🤖 AI блокирует {direction} для {symbol} (низкая уверенность: {confidence:.2%})")
        
        return {
            'should_open': should_open,
            'ai_used': True,
            'ai_confidence': confidence,
            'ai_signal': signal,
            'reason': reason,
            'model_used': 'signal_predictor.pkl'  # Указываем какая модель использовалась
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении AI предсказания для {symbol}: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return {'should_open': True, 'ai_used': False, 'reason': f'AI error: {e}'}

