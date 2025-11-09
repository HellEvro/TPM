#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль оптимизации торговых стратегий

Анализирует результаты торговли и оптимизирует параметры стратегии
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import numpy as np

logger = logging.getLogger('AI.StrategyOptimizer')


class AIStrategyOptimizer:
    """
    Класс для оптимизации торговых стратегий
    """
    
    def __init__(self):
        """Инициализация оптимизатора"""
        self.results_dir = 'data/ai/optimization_results'
        self.data_dir = 'data/ai'
        
        # Создаем директории
        os.makedirs(self.results_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        
        logger.info("✅ AIStrategyOptimizer инициализирован")
    
    def _load_history_data(self) -> List[Dict]:
        """Загрузить историю трейдов"""
        try:
            history_file = os.path.join(self.data_dir, 'history_data.json')
            if not os.path.exists(history_file):
                return []
            
            with open(history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            trades = []
            latest = data.get('latest', {})
            history = data.get('history', [])
            
            if latest:
                trades.extend(latest.get('trades', []))
            
            for entry in history:
                trades.extend(entry.get('trades', []))
            
            # Фильтруем только закрытые сделки
            closed_trades = [
                t for t in trades
                if t.get('status') == 'CLOSED' and t.get('pnl') is not None
            ]
            
            return closed_trades
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки истории: {e}")
            return []
    
    def analyze_trade_patterns(self) -> Dict:
        """
        Анализ паттернов торговли
        
        Определяет какие условия приводят к прибыльным сделкам
        """
        logger.info("=" * 80)
        logger.info("🔍 АНАЛИЗ ПАТТЕРНОВ ТОРГОВЛИ")
        logger.info("=" * 80)
        
        try:
            trades = self._load_history_data()
            
            logger.info(f"📊 Загружено {len(trades)} сделок для анализа")
            
            if len(trades) < 10:
                logger.warning("⚠️ Недостаточно данных для анализа (нужно минимум 10 сделок)")
                logger.info("💡 Используем свечи для анализа паттернов...")
                return self._analyze_patterns_on_candles()
            
            # Анализируем прибыльные и убыточные сделки
            profitable_trades = [t for t in trades if t.get('pnl', 0) > 0]
            losing_trades = [t for t in trades if t.get('pnl', 0) < 0]
            
            patterns = {
                'total_trades': len(trades),
                'profitable_trades': len(profitable_trades),
                'losing_trades': len(losing_trades),
                'win_rate': len(profitable_trades) / len(trades) * 100 if trades else 0,
                'rsi_analysis': {},
                'trend_analysis': {},
                'time_analysis': {}
            }
            
            # Анализ по RSI
            profitable_rsi = []
            losing_rsi = []
            
            for trade in profitable_trades:
                entry_data = trade.get('entry_data', {})
                rsi = entry_data.get('rsi')
                if rsi:
                    profitable_rsi.append(rsi)
            
            for trade in losing_trades:
                entry_data = trade.get('entry_data', {})
                rsi = entry_data.get('rsi')
                if rsi:
                    losing_rsi.append(rsi)
            
            if profitable_rsi:
                patterns['rsi_analysis']['profitable_avg'] = np.mean(profitable_rsi)
                patterns['rsi_analysis']['profitable_min'] = np.min(profitable_rsi)
                patterns['rsi_analysis']['profitable_max'] = np.max(profitable_rsi)
            
            if losing_rsi:
                patterns['rsi_analysis']['losing_avg'] = np.mean(losing_rsi)
                patterns['rsi_analysis']['losing_min'] = np.min(losing_rsi)
                patterns['rsi_analysis']['losing_max'] = np.max(losing_rsi)
            
            # Анализ по тренду
            trend_stats = {}
            
            for trade in trades:
                entry_data = trade.get('entry_data', {})
                trend = entry_data.get('trend', 'NEUTRAL')
                pnl = trade.get('pnl', 0)
                
                if trend not in trend_stats:
                    trend_stats[trend] = {'trades': 0, 'profitable': 0, 'total_pnl': 0}
                
                trend_stats[trend]['trades'] += 1
                if pnl > 0:
                    trend_stats[trend]['profitable'] += 1
                trend_stats[trend]['total_pnl'] += pnl
            
            patterns['trend_analysis'] = trend_stats
            
            # Сохраняем результаты анализа
            analysis_file = os.path.join(self.results_dir, 'trade_patterns.json')
            with open(analysis_file, 'w', encoding='utf-8') as f:
                json.dump(patterns, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Анализ завершен: Win Rate={patterns['win_rate']:.2f}%")
            
            return patterns
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа паттернов: {e}")
            return {}
    
    def optimize_strategy(self) -> Dict:
        """
        Оптимизация параметров стратегии
        
        Returns:
            Оптимизированные параметры стратегии
        """
        logger.info("⚙️ Оптимизация стратегии...")
        
        try:
            # Анализируем паттерны
            patterns = self.analyze_trade_patterns()
            
            if not patterns:
                logger.warning("⚠️ Недостаточно данных для оптимизации")
                return {}
            
            # Определяем оптимальные параметры на основе анализа
            optimized_params = {
                'rsi_long_entry': 29,  # По умолчанию
                'rsi_long_exit': 65,
                'rsi_short_entry': 71,
                'rsi_short_exit': 35,
                'stop_loss_pct': 2.0,
                'take_profit_pct': 20.0
            }
            
            # Оптимизируем на основе RSI анализа
            rsi_analysis = patterns.get('rsi_analysis', {})
            
            if 'profitable_avg' in rsi_analysis:
                profitable_avg_rsi = rsi_analysis['profitable_avg']
                
                # Для LONG: если прибыльные сделки при низком RSI, используем его
                if profitable_avg_rsi < 30:
                    optimized_params['rsi_long_entry'] = max(20, int(profitable_avg_rsi - 5))
                    optimized_params['rsi_long_exit'] = min(70, int(profitable_avg_rsi + 35))
            
            if 'losing_avg' in rsi_analysis:
                losing_avg_rsi = rsi_analysis['losing_avg']
                
                # Избегаем параметров, которые приводят к убыткам
                if losing_avg_rsi < 30:
                    # Если убытки при низком RSI, повышаем порог входа
                    optimized_params['rsi_long_entry'] = max(optimized_params['rsi_long_entry'], 25)
            
            # Оптимизация на основе тренда
            trend_analysis = patterns.get('trend_analysis', {})
            
            if trend_analysis:
                # Определяем лучший тренд для торговли
                best_trend = None
                best_win_rate = 0
                
                for trend, stats in trend_analysis.items():
                    win_rate = stats['profitable'] / stats['trades'] * 100 if stats['trades'] > 0 else 0
                    if win_rate > best_win_rate:
                        best_win_rate = win_rate
                        best_trend = trend
                
                optimized_params['best_trend'] = best_trend
                optimized_params['trend_win_rate'] = best_win_rate
            
            # Сохраняем оптимизированные параметры
            optimization_file = os.path.join(self.results_dir, 'optimized_params.json')
            with open(optimization_file, 'w', encoding='utf-8') as f:
                json.dump(optimized_params, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Оптимизация завершена: {optimized_params}")
            
            return optimized_params
            
        except Exception as e:
            logger.error(f"❌ Ошибка оптимизации: {e}")
            return {}
    
    def optimize_bot_config(self, symbol: str) -> Dict:
        """
        Оптимизация конфигурации конкретного бота
        
        Args:
            symbol: Символ монеты
        
        Returns:
            Оптимизированная конфигурация бота
        """
        logger.info(f"⚙️ Оптимизация конфигурации для {symbol}...")
        
        try:
            trades = self._load_history_data()
            
            # Фильтруем сделки по символу
            symbol_trades = [t for t in trades if t.get('symbol') == symbol]
            
            if len(symbol_trades) < 5:
                logger.warning(f"⚠️ Недостаточно данных для {symbol}")
                return {}
            
            # Анализируем сделки для этого символа
            profitable = [t for t in symbol_trades if t.get('pnl', 0) > 0]
            
            # Определяем оптимальные параметры для символа
            optimized_config = {
                'symbol': symbol,
                'rsi_long_entry': 29,
                'rsi_long_exit': 65,
                'rsi_short_entry': 71,
                'rsi_short_exit': 35
            }
            
            # Анализ RSI для этого символа
            profitable_rsi = []
            for trade in profitable:
                entry_data = trade.get('entry_data', {})
                rsi = entry_data.get('rsi')
                if rsi:
                    profitable_rsi.append(rsi)
            
            if profitable_rsi:
                avg_rsi = np.mean(profitable_rsi)
                optimized_config['rsi_long_entry'] = max(20, int(avg_rsi - 5))
                optimized_config['rsi_long_exit'] = min(70, int(avg_rsi + 35))
            
            logger.info(f"✅ Оптимизация для {symbol} завершена")
            
            return optimized_config
            
        except Exception as e:
            logger.error(f"❌ Ошибка оптимизации для {symbol}: {e}")
            return {}

