#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Реляционная база данных для хранения ВСЕХ данных AI модуля

Хранит:
- AI симуляции (simulated_trades)
- Реальные сделки ботов (bot_trades)
- История биржи (exchange_trades)
- Решения AI (ai_decisions)
- Сессии обучения (training_sessions)
- Метрики производительности (performance_metrics)
- Связи между данными для сложных запросов

Позволяет:
- Хранить миллиарды записей
- Делать JOIN запросы между таблицами
- Сравнивать данные из разных источников
- Анализировать паттерны
- Обучать ИИ на огромных объемах данных
"""

import sqlite3
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from contextlib import contextmanager
import logging

logger = logging.getLogger('AI.Database')


class AIDatabase:
    """
    Реляционная база данных для всех данных AI модуля
    """
    
    def __init__(self, db_path: str = None):
        """
        Инициализация базы данных
        
        Args:
            db_path: Путь к файлу базы данных (если None, используется data/ai/ai_data.db)
        """
        if db_path is None:
            # Поддержка UNC путей: используем абсолютный путь относительно текущей рабочей директории
            base_dir = os.getcwd()
            db_path = os.path.join(base_dir, 'data', 'ai', 'ai_data.db')
            # Нормализуем путь (работает и с UNC путями)
            db_path = os.path.normpath(db_path)
        
        self.db_path = db_path
        self.lock = threading.RLock()
        
        # Создаем директорию если её нет (работает и с UNC путями)
        try:
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        except OSError as e:
            logger.error(f"❌ Ошибка создания директории для БД: {e}")
            raise
        
        # Инициализируем базу данных
        self._init_database()
        
        logger.info(f"✅ AI Database инициализирована: {db_path}")
    
    @contextmanager
    def _get_connection(self):
        """Контекстный менеджер для работы с БД"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_database(self):
        """Создает все таблицы и индексы"""
        # SQLite автоматически создает файл БД при первом подключении
        # Но убедимся, что файл будет создан явно
        if not os.path.exists(self.db_path):
            # Создаем пустой файл БД
            Path(self.db_path).touch()
            logger.debug(f"📁 Создан файл БД: {self.db_path}")
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Миграция: добавляем новые поля если их нет
            self._migrate_schema(cursor, conn)
            
            # ==================== ТАБЛИЦА: AI СИМУЛЯЦИИ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS simulated_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    entry_time INTEGER NOT NULL,
                    exit_time INTEGER NOT NULL,
                    entry_rsi REAL,
                    exit_rsi REAL,
                    entry_trend TEXT,
                    exit_trend TEXT,
                    entry_volatility REAL,
                    entry_volume_ratio REAL,
                    pnl REAL NOT NULL,
                    pnl_pct REAL NOT NULL,
                    roi REAL,
                    exit_reason TEXT,
                    is_successful INTEGER NOT NULL DEFAULT 0,
                    duration_candles INTEGER,
                    entry_idx INTEGER,
                    exit_idx INTEGER,
                    simulation_timestamp TEXT NOT NULL,
                    training_session_id INTEGER,
                    rsi_params_json TEXT,
                    risk_params_json TEXT,
                    config_params_json TEXT,
                    filters_params_json TEXT,
                    entry_conditions_json TEXT,
                    exit_conditions_json TEXT,
                    restrictions_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (training_session_id) REFERENCES training_sessions(id)
                )
            """)
            
            # Индексы для simulated_trades
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_trades_symbol ON simulated_trades(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_trades_entry_time ON simulated_trades(entry_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_trades_exit_time ON simulated_trades(exit_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_trades_pnl ON simulated_trades(pnl)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_trades_successful ON simulated_trades(is_successful)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_trades_session ON simulated_trades(training_session_id)")
            
            # ==================== ТАБЛИЦА: РЕАЛЬНЫЕ СДЕЛКИ БОТОВ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bot_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE,
                    bot_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT,
                    pnl REAL,
                    roi REAL,
                    status TEXT NOT NULL,
                    decision_source TEXT NOT NULL,
                    ai_decision_id TEXT,
                    ai_confidence REAL,
                    entry_rsi REAL,
                    exit_rsi REAL,
                    entry_trend TEXT,
                    exit_trend TEXT,
                    entry_volatility REAL,
                    entry_volume_ratio REAL,
                    close_reason TEXT,
                    position_size_usdt REAL,
                    position_size_coins REAL,
                    entry_data_json TEXT,
                    exit_market_data_json TEXT,
                    config_params_json TEXT,
                    filters_params_json TEXT,
                    entry_conditions_json TEXT,
                    exit_conditions_json TEXT,
                    restrictions_json TEXT,
                    is_simulated INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Индексы для bot_trades
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_symbol ON bot_trades(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_bot_id ON bot_trades(bot_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_status ON bot_trades(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_decision_source ON bot_trades(decision_source)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_pnl ON bot_trades(pnl)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_entry_time ON bot_trades(entry_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_ai_decision ON bot_trades(ai_decision_id)")
            
            # ==================== ТАБЛИЦА: ИСТОРИЯ БИРЖИ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS exchange_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT NOT NULL,
                    pnl REAL NOT NULL,
                    roi REAL NOT NULL,
                    position_size_usdt REAL,
                    position_size_coins REAL,
                    order_id TEXT,
                    source TEXT NOT NULL,
                    saved_timestamp TEXT NOT NULL,
                    is_real INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Индексы для exchange_trades
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_exchange_trades_symbol ON exchange_trades(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_exchange_trades_entry_time ON exchange_trades(entry_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_exchange_trades_exit_time ON exchange_trades(exit_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_exchange_trades_pnl ON exchange_trades(pnl)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_exchange_trades_order_id ON exchange_trades(order_id)")
            
            # ==================== ТАБЛИЦА: РЕШЕНИЯ AI ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    decision_id TEXT UNIQUE NOT NULL,
                    symbol TEXT NOT NULL,
                    decision_type TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    confidence REAL,
                    rsi REAL,
                    trend TEXT,
                    price REAL,
                    market_data_json TEXT,
                    decision_params_json TEXT,
                    created_at TEXT NOT NULL,
                    executed_at TEXT,
                    result_pnl REAL,
                    result_successful INTEGER
                )
            """)
            
            # Индексы для ai_decisions
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_decisions_symbol ON ai_decisions(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_decisions_decision_id ON ai_decisions(decision_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_decisions_created_at ON ai_decisions(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_decisions_result ON ai_decisions(result_successful)")
            
            # ==================== ТАБЛИЦА: СЕССИИ ОБУЧЕНИЯ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS training_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_type TEXT NOT NULL,
                    training_seed INTEGER,
                    coins_processed INTEGER DEFAULT 0,
                    models_saved INTEGER DEFAULT 0,
                    candles_processed INTEGER DEFAULT 0,
                    total_trades INTEGER DEFAULT 0,
                    successful_trades INTEGER DEFAULT 0,
                    failed_trades INTEGER DEFAULT 0,
                    win_rate REAL,
                    total_pnl REAL,
                    accuracy REAL,
                    mse REAL,
                    params_used INTEGER DEFAULT 0,
                    params_total INTEGER DEFAULT 0,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL DEFAULT 'RUNNING',
                    metadata_json TEXT
                )
            """)
            
            # Индексы для training_sessions
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_training_sessions_type ON training_sessions(session_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_training_sessions_started_at ON training_sessions(started_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_training_sessions_status ON training_sessions(status)")
            
            # ==================== ТАБЛИЦА: МЕТРИКИ ПРОИЗВОДИТЕЛЬНОСТИ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    metric_type TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    metric_data_json TEXT,
                    recorded_at TEXT NOT NULL,
                    training_session_id INTEGER,
                    FOREIGN KEY (training_session_id) REFERENCES training_sessions(id)
                )
            """)
            
            # Индексы для performance_metrics
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_perf_metrics_symbol ON performance_metrics(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_perf_metrics_type ON performance_metrics(metric_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_perf_metrics_recorded_at ON performance_metrics(recorded_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_perf_metrics_session ON performance_metrics(training_session_id)")
            
            # ==================== ТАБЛИЦА: ПАТТЕРНЫ И ИНСАЙТЫ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trading_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_type TEXT NOT NULL,
                    symbol TEXT,
                    rsi_range TEXT,
                    trend_condition TEXT,
                    volatility_range TEXT,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    avg_pnl REAL,
                    avg_duration REAL,
                    pattern_data_json TEXT,
                    discovered_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                )
            """)
            
            # Индексы для trading_patterns
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_type ON trading_patterns(pattern_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_symbol ON trading_patterns(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_rsi_range ON trading_patterns(rsi_range)")
            
            conn.commit()
            
            logger.debug("✅ Все таблицы и индексы созданы")
    
    def _migrate_schema(self, cursor, conn):
        """Миграция схемы БД: добавляет новые поля если их нет"""
        try:
            # Проверяем и добавляем entry_volatility и entry_volume_ratio в simulated_trades
            try:
                cursor.execute("SELECT entry_volatility FROM simulated_trades LIMIT 1")
            except sqlite3.OperationalError:
                logger.info("📦 Миграция: добавляем entry_volatility и entry_volume_ratio в simulated_trades")
                cursor.execute("ALTER TABLE simulated_trades ADD COLUMN entry_volatility REAL")
                cursor.execute("ALTER TABLE simulated_trades ADD COLUMN entry_volume_ratio REAL")
            
            # Проверяем и добавляем entry_volatility и entry_volume_ratio в bot_trades
            try:
                cursor.execute("SELECT entry_volatility FROM bot_trades LIMIT 1")
            except sqlite3.OperationalError:
                logger.info("📦 Миграция: добавляем entry_volatility и entry_volume_ratio в bot_trades")
                cursor.execute("ALTER TABLE bot_trades ADD COLUMN entry_volatility REAL")
                cursor.execute("ALTER TABLE bot_trades ADD COLUMN entry_volume_ratio REAL")
            
            # Проверяем и добавляем параметры конфига в simulated_trades
            new_fields_sim = [
                ('config_params_json', 'TEXT'),
                ('filters_params_json', 'TEXT'),
                ('entry_conditions_json', 'TEXT'),
                ('exit_conditions_json', 'TEXT'),
                ('restrictions_json', 'TEXT')
            ]
            for field_name, field_type in new_fields_sim:
                try:
                    cursor.execute(f"SELECT {field_name} FROM simulated_trades LIMIT 1")
                except sqlite3.OperationalError:
                    logger.info(f"📦 Миграция: добавляем {field_name} в simulated_trades")
                    cursor.execute(f"ALTER TABLE simulated_trades ADD COLUMN {field_name} {field_type}")
            
            # Проверяем и добавляем параметры конфига в bot_trades
            new_fields_bot = [
                ('config_params_json', 'TEXT'),
                ('filters_params_json', 'TEXT'),
                ('entry_conditions_json', 'TEXT'),
                ('exit_conditions_json', 'TEXT'),
                ('restrictions_json', 'TEXT')
            ]
            for field_name, field_type in new_fields_bot:
                try:
                    cursor.execute(f"SELECT {field_name} FROM bot_trades LIMIT 1")
                except sqlite3.OperationalError:
                    logger.info(f"📦 Миграция: добавляем {field_name} в bot_trades")
                    cursor.execute(f"ALTER TABLE bot_trades ADD COLUMN {field_name} {field_type}")
            
            conn.commit()
        except Exception as e:
            logger.debug(f"⚠️ Ошибка миграции схемы: {e}")
    
    # ==================== МЕТОДЫ ДЛЯ СИМУЛЯЦИЙ ====================
    
    def save_simulated_trades(self, trades: List[Dict[str, Any]], training_session_id: Optional[int] = None) -> int:
        """
        Сохраняет симулированные сделки в БД
        
        Args:
            trades: Список симулированных сделок
            training_session_id: ID сессии обучения (опционально)
        
        Returns:
            Количество сохраненных сделок
        """
        if not trades:
            return 0
        
        saved_count = 0
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                for trade in trades:
                    try:
                        cursor.execute("""
                            INSERT OR IGNORE INTO simulated_trades (
                                symbol, direction, entry_price, exit_price,
                                entry_time, exit_time, entry_rsi, exit_rsi,
                                entry_trend, exit_trend, entry_volatility, entry_volume_ratio,
                                pnl, pnl_pct, roi,
                                exit_reason, is_successful, duration_candles,
                                entry_idx, exit_idx, simulation_timestamp,
                                training_session_id, rsi_params_json, risk_params_json,
                                config_params_json, filters_params_json, entry_conditions_json,
                                exit_conditions_json, restrictions_json,
                                created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            trade.get('symbol'),
                            trade.get('direction'),
                            trade.get('entry_price'),
                            trade.get('exit_price'),
                            trade.get('entry_time'),
                            trade.get('exit_time'),
                            trade.get('entry_rsi'),
                            trade.get('exit_rsi'),
                            trade.get('entry_trend'),
                            trade.get('exit_trend'),
                            trade.get('entry_volatility'),
                            trade.get('entry_volume_ratio'),
                            trade.get('pnl'),
                            trade.get('pnl_pct'),
                            trade.get('roi'),
                            trade.get('exit_reason'),
                            1 if trade.get('is_successful', False) else 0,
                            trade.get('duration_candles'),
                            trade.get('entry_idx'),
                            trade.get('exit_idx'),
                            trade.get('simulation_timestamp', now),
                            training_session_id,
                            json.dumps(trade.get('rsi_params')) if trade.get('rsi_params') else None,
                            json.dumps(trade.get('risk_params')) if trade.get('risk_params') else None,
                            json.dumps(trade.get('config_params')) if trade.get('config_params') else None,
                            json.dumps(trade.get('filters_params')) if trade.get('filters_params') else None,
                            json.dumps(trade.get('entry_conditions')) if trade.get('entry_conditions') else None,
                            json.dumps(trade.get('exit_conditions')) if trade.get('exit_conditions') else None,
                            json.dumps(trade.get('restrictions')) if trade.get('restrictions') else None,
                            now
                        ))
                        if cursor.rowcount > 0:
                            saved_count += 1
                    except Exception as e:
                        logger.debug(f"⚠️ Ошибка сохранения симуляции: {e}")
                        continue
                
                conn.commit()
        
        if saved_count > 0:
            logger.debug(f"💾 Сохранено {saved_count} симулированных сделок в БД")
        
        return saved_count
    
    def get_simulated_trades(self, 
                            symbol: Optional[str] = None,
                            min_pnl: Optional[float] = None,
                            max_pnl: Optional[float] = None,
                            is_successful: Optional[bool] = None,
                            limit: Optional[int] = None,
                            offset: int = 0) -> List[Dict[str, Any]]:
        """
        Получает симулированные сделки с фильтрацией
        
        Args:
            symbol: Фильтр по символу
            min_pnl: Минимальный PnL
            max_pnl: Максимальный PnL
            is_successful: Фильтр по успешности
            limit: Лимит записей
            offset: Смещение
        
        Returns:
            Список сделок
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM simulated_trades WHERE 1=1"
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            if min_pnl is not None:
                query += " AND pnl >= ?"
                params.append(min_pnl)
            
            if max_pnl is not None:
                query += " AND pnl <= ?"
                params.append(max_pnl)
            
            if is_successful is not None:
                query += " AND is_successful = ?"
                params.append(1 if is_successful else 0)
            
            query += " ORDER BY entry_time DESC"
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            if offset:
                query += " OFFSET ?"
                params.append(offset)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    def count_simulated_trades(self, symbol: Optional[str] = None) -> int:
        """Подсчитывает количество симуляций"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if symbol:
                cursor.execute("SELECT COUNT(*) FROM simulated_trades WHERE symbol = ?", (symbol,))
            else:
                cursor.execute("SELECT COUNT(*) FROM simulated_trades")
            
            return cursor.fetchone()[0]
    
    # ==================== МЕТОДЫ ДЛЯ РЕАЛЬНЫХ СДЕЛОК БОТОВ ====================
    
    def save_bot_trade(self, trade: Dict[str, Any]) -> Optional[int]:
        """Сохраняет или обновляет сделку бота"""
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                # Проверяем, существует ли сделка
                trade_id = trade.get('id') or trade.get('trade_id')
                if trade_id:
                    cursor.execute("SELECT id FROM bot_trades WHERE trade_id = ?", (trade_id,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Извлекаем volatility и volume_ratio из entry_data если есть
                        entry_data = trade.get('entry_data', {})
                        if isinstance(entry_data, str):
                            try:
                                entry_data = json.loads(entry_data)
                            except:
                                entry_data = {}
                        elif not isinstance(entry_data, dict):
                            entry_data = {}
                        
                        entry_volatility = trade.get('entry_volatility') or entry_data.get('volatility')
                        entry_volume_ratio = trade.get('entry_volume_ratio') or entry_data.get('volume_ratio')
                        
                        # Обновляем существующую
                        cursor.execute("""
                            UPDATE bot_trades SET
                                symbol = ?, direction = ?, entry_price = ?, exit_price = ?,
                                pnl = ?, roi = ?, status = ?, exit_rsi = ?, exit_trend = ?,
                                entry_volatility = ?, entry_volume_ratio = ?,
                                close_reason = ?, exit_market_data_json = ?, updated_at = ?
                            WHERE trade_id = ?
                        """, (
                            trade.get('symbol'),
                            trade.get('direction'),
                            trade.get('entry_price'),
                            trade.get('exit_price'),
                            trade.get('pnl'),
                            trade.get('roi'),
                            trade.get('status'),
                            trade.get('exit_rsi'),
                            trade.get('exit_trend'),
                            entry_volatility,
                            entry_volume_ratio,
                            trade.get('close_reason'),
                            json.dumps(trade.get('exit_market_data')) if trade.get('exit_market_data') else None,
                            now,
                            trade_id
                        ))
                        return existing[0]
                
                # Создаем новую
                # Извлекаем volatility и volume_ratio из entry_data если есть
                entry_data = trade.get('entry_data', {})
                if isinstance(entry_data, str):
                    try:
                        entry_data = json.loads(entry_data)
                    except:
                        entry_data = {}
                elif not isinstance(entry_data, dict):
                    entry_data = {}
                
                entry_volatility = trade.get('entry_volatility') or entry_data.get('volatility')
                entry_volume_ratio = trade.get('entry_volume_ratio') or entry_data.get('volume_ratio')
                
                # Извлекаем все параметры конфига из trade или entry_data
                config_params = trade.get('config_params') or trade.get('config') or entry_data.get('config')
                filters_params = trade.get('filters_params') or trade.get('filters') or entry_data.get('filters')
                entry_conditions = trade.get('entry_conditions') or entry_data.get('entry_conditions')
                exit_market_data = trade.get('exit_market_data') or trade.get('market_data', {})
                if isinstance(exit_market_data, str):
                    try:
                        exit_market_data = json.loads(exit_market_data)
                    except:
                        exit_market_data = {}
                elif not isinstance(exit_market_data, dict):
                    exit_market_data = {}
                exit_conditions = trade.get('exit_conditions') or exit_market_data.get('exit_conditions')
                restrictions = trade.get('restrictions') or entry_data.get('restrictions')
                
                cursor.execute("""
                    INSERT OR IGNORE INTO bot_trades (
                        trade_id, bot_id, symbol, direction, entry_price, exit_price,
                        entry_time, exit_time, pnl, roi, status, decision_source,
                        ai_decision_id, ai_confidence, entry_rsi, exit_rsi,
                        entry_trend, exit_trend, entry_volatility, entry_volume_ratio,
                        close_reason,
                        position_size_usdt, position_size_coins,
                        entry_data_json, exit_market_data_json,
                        config_params_json, filters_params_json, entry_conditions_json,
                        exit_conditions_json, restrictions_json,
                        is_simulated,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_id,
                    trade.get('bot_id'),
                    trade.get('symbol'),
                    trade.get('direction'),
                    trade.get('entry_price'),
                    trade.get('exit_price'),
                    trade.get('timestamp') or trade.get('entry_time'),
                    trade.get('close_timestamp') or trade.get('exit_time'),
                    trade.get('pnl'),
                    trade.get('roi'),
                    trade.get('status', 'CLOSED'),
                    trade.get('decision_source', 'SCRIPT'),
                    trade.get('ai_decision_id'),
                    trade.get('ai_confidence'),
                    trade.get('entry_rsi') or entry_data.get('rsi'),
                    trade.get('exit_rsi') or exit_market_data.get('rsi'),
                    trade.get('entry_trend') or entry_data.get('trend'),
                    trade.get('exit_trend') or exit_market_data.get('trend'),
                    entry_volatility,
                    entry_volume_ratio,
                    trade.get('close_reason'),
                    trade.get('position_size_usdt'),
                    trade.get('position_size_coins'),
                    json.dumps(trade.get('entry_data')) if trade.get('entry_data') else None,
                    json.dumps(trade.get('exit_market_data') or trade.get('market_data')) if (trade.get('exit_market_data') or trade.get('market_data')) else None,
                    json.dumps(config_params) if config_params else None,
                    json.dumps(filters_params) if filters_params else None,
                    json.dumps(entry_conditions) if entry_conditions else None,
                    json.dumps(exit_conditions) if exit_conditions else None,
                    json.dumps(restrictions) if restrictions else None,
                    1 if trade.get('is_simulated', False) else 0,
                    now,
                    now
                ))
                
                return cursor.lastrowid
    
    def get_bot_trades(self,
                       symbol: Optional[str] = None,
                       bot_id: Optional[str] = None,
                       status: Optional[str] = None,
                       decision_source: Optional[str] = None,
                       min_pnl: Optional[float] = None,
                       max_pnl: Optional[float] = None,
                       limit: Optional[int] = None,
                       offset: int = 0) -> List[Dict[str, Any]]:
        """Получает сделки ботов с фильтрацией"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM bot_trades WHERE is_simulated = 0"
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            if bot_id:
                query += " AND bot_id = ?"
                params.append(bot_id)
            
            if status:
                query += " AND status = ?"
                params.append(status)
            
            if decision_source:
                query += " AND decision_source = ?"
                params.append(decision_source)
            
            if min_pnl is not None:
                query += " AND pnl >= ?"
                params.append(min_pnl)
            
            if max_pnl is not None:
                query += " AND pnl <= ?"
                params.append(max_pnl)
            
            query += " ORDER BY entry_time DESC"
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            if offset:
                query += " OFFSET ?"
                params.append(offset)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                trade = dict(row)
                # Восстанавливаем JSON поля
                if trade.get('entry_data_json'):
                    trade['entry_data'] = json.loads(trade['entry_data_json'])
                if trade.get('exit_market_data_json'):
                    trade['exit_market_data'] = json.loads(trade['exit_market_data_json'])
                result.append(trade)
            
            return result
    
    # ==================== МЕТОДЫ ДЛЯ ИСТОРИИ БИРЖИ ====================
    
    def save_exchange_trades(self, trades: List[Dict[str, Any]]) -> int:
        """Сохраняет сделки с биржи"""
        if not trades:
            return 0
        
        saved_count = 0
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                for trade in trades:
                    try:
                        trade_id = trade.get('id') or trade.get('orderId') or f"exchange_{trade.get('symbol')}_{trade.get('timestamp')}"
                        cursor.execute("""
                            INSERT OR IGNORE INTO exchange_trades (
                                trade_id, symbol, direction, entry_price, exit_price,
                                entry_time, exit_time, pnl, roi,
                                position_size_usdt, position_size_coins,
                                order_id, source, saved_timestamp, is_real, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            trade_id,
                            trade.get('symbol'),
                            trade.get('direction'),
                            trade.get('entry_price'),
                            trade.get('exit_price'),
                            trade.get('timestamp'),
                            trade.get('close_timestamp'),
                            trade.get('pnl'),
                            trade.get('roi'),
                            trade.get('position_size_usdt'),
                            trade.get('position_size_coins'),
                            trade.get('orderId'),
                            trade.get('source', 'exchange_api'),
                            trade.get('saved_timestamp', now),
                            1,
                            now
                        ))
                        if cursor.rowcount > 0:
                            saved_count += 1
                    except Exception as e:
                        logger.debug(f"⚠️ Ошибка сохранения сделки биржи: {e}")
                        continue
                
                conn.commit()
        
        return saved_count
    
    def count_exchange_trades(self) -> int:
        """Подсчитывает количество сделок биржи"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM exchange_trades")
            return cursor.fetchone()[0]
    
    def count_bot_trades(self, symbol: Optional[str] = None, is_simulated: Optional[bool] = None) -> int:
        """Подсчитывает количество сделок ботов"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT COUNT(*) FROM bot_trades WHERE 1=1"
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            if is_simulated is not None:
                query += " AND is_simulated = ?"
                params.append(1 if is_simulated else 0)
            
            cursor.execute(query, params)
            return cursor.fetchone()[0]
    
    # ==================== МЕТОДЫ ДЛЯ РЕШЕНИЙ AI ====================
    
    def save_ai_decision(self, decision: Dict[str, Any]) -> int:
        """Сохраняет решение AI"""
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO ai_decisions (
                        decision_id, symbol, decision_type, signal, confidence,
                        rsi, trend, price, market_data_json, decision_params_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    decision.get('decision_id'),
                    decision.get('symbol'),
                    decision.get('decision_type', 'SIGNAL'),
                    decision.get('signal'),
                    decision.get('confidence'),
                    decision.get('rsi'),
                    decision.get('trend'),
                    decision.get('price'),
                    json.dumps(decision.get('market_data')) if decision.get('market_data') else None,
                    json.dumps(decision.get('params')) if decision.get('params') else None,
                    now
                ))
                
                return cursor.lastrowid
    
    def update_ai_decision_result(self, decision_id: str, pnl: float, is_successful: bool):
        """Обновляет результат решения AI"""
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                cursor.execute("""
                    UPDATE ai_decisions SET
                        result_pnl = ?, result_successful = ?, executed_at = ?
                    WHERE decision_id = ?
                """, (pnl, 1 if is_successful else 0, now, decision_id))
    
    # ==================== МЕТОДЫ ДЛЯ СЕССИЙ ОБУЧЕНИЯ ====================
    
    def create_training_session(self, session_type: str, training_seed: Optional[int] = None, metadata: Optional[Dict] = None) -> int:
        """Создает новую сессию обучения"""
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                cursor.execute("""
                    INSERT INTO training_sessions (
                        session_type, training_seed, started_at, status, metadata_json
                    ) VALUES (?, ?, ?, 'RUNNING', ?)
                """, (
                    session_type,
                    training_seed,
                    now,
                    json.dumps(metadata) if metadata else None
                ))
                
                return cursor.lastrowid
    
    def update_training_session(self, session_id: int, **kwargs):
        """Обновляет сессию обучения"""
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                updates = []
                params = []
                
                for key, value in kwargs.items():
                    if key == 'metadata' and isinstance(value, dict):
                        updates.append("metadata_json = ?")
                        params.append(json.dumps(value))
                    elif key in ('coins_processed', 'models_saved', 'candles_processed', 
                                'total_trades', 'successful_trades', 'failed_trades',
                                'params_used', 'params_total'):
                        updates.append(f"{key} = ?")
                        params.append(value)
                    elif key in ('win_rate', 'total_pnl', 'accuracy', 'mse'):
                        updates.append(f"{key} = ?")
                        params.append(value)
                    elif key == 'status':
                        updates.append("status = ?")
                        params.append(value)
                        if value in ('COMPLETED', 'FAILED'):
                            updates.append("completed_at = ?")
                            params.append(now)
                
                if updates:
                    params.append(session_id)
                    cursor.execute(f"""
                        UPDATE training_sessions SET {', '.join(updates)}
                        WHERE id = ?
                    """, params)
    
    # ==================== СЛОЖНЫЕ ЗАПРОСЫ И АНАЛИЗ ====================
    
    def compare_simulated_vs_real(self, symbol: Optional[str] = None, limit: int = 1000) -> Dict[str, Any]:
        """
        Сравнивает симулированные и реальные сделки
        
        Returns:
            Статистика сравнения
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Статистика симуляций
            sim_query = "SELECT AVG(pnl) as avg_pnl, COUNT(*) as count, AVG(CASE WHEN is_successful = 1 THEN 1.0 ELSE 0.0 END) as win_rate FROM simulated_trades"
            sim_params = []
            if symbol:
                sim_query += " WHERE symbol = ?"
                sim_params.append(symbol)
            
            cursor.execute(sim_query, sim_params)
            sim_stats = dict(cursor.fetchone())
            
            # Статистика реальных сделок
            real_query = "SELECT AVG(pnl) as avg_pnl, COUNT(*) as count FROM bot_trades WHERE is_simulated = 0 AND status = 'CLOSED' AND pnl IS NOT NULL"
            real_params = []
            if symbol:
                real_query += " AND symbol = ?"
                real_params.append(symbol)
            
            cursor.execute(real_query, real_params)
            real_stats = dict(cursor.fetchone())
            
            return {
                'simulated': sim_stats,
                'real': real_stats,
                'comparison': {
                    'pnl_diff': (sim_stats.get('avg_pnl') or 0) - (real_stats.get('avg_pnl') or 0),
                    'count_ratio': (sim_stats.get('count') or 0) / max(real_stats.get('count') or 1, 1)
                }
            }
    
    def get_trades_for_training(self,
                               include_simulated: bool = True,
                               include_real: bool = True,
                               include_exchange: bool = True,
                               min_trades: int = 10,
                               limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Получает все сделки для обучения ИИ (объединенные из разных источников)
        
        Args:
            include_simulated: Включить симуляции
            include_real: Включить реальные сделки ботов
            include_exchange: Включить сделки с биржи
            min_trades: Минимальное количество сделок для символа
            limit: Лимит на общее количество
        
        Returns:
            Список сделок для обучения
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Объединяем все источники через UNION
            queries = []
            params = []
            
            if include_simulated:
                queries.append("""
                    SELECT 
                        'SIMULATED' as source,
                        symbol, direction, entry_price, exit_price,
                        entry_rsi as rsi, entry_trend as trend,
                        entry_volatility, entry_volume_ratio,
                        pnl, pnl_pct as roi, is_successful,
                        entry_time as timestamp, exit_time as close_timestamp,
                        exit_reason as close_reason,
                        NULL as ai_decision_id, NULL as ai_confidence
                    FROM simulated_trades
                    WHERE exit_price IS NOT NULL
                """)
            
            if include_real:
                queries.append("""
                    SELECT 
                        'BOT' as source,
                        symbol, direction, entry_price, exit_price,
                        entry_rsi as rsi, entry_trend as trend,
                        entry_volatility, entry_volume_ratio,
                        pnl, roi, CASE WHEN pnl > 0 THEN 1 ELSE 0 END as is_successful,
                        entry_time as timestamp, exit_time as close_timestamp,
                        close_reason, ai_decision_id, ai_confidence
                    FROM bot_trades
                    WHERE is_simulated = 0 AND status = 'CLOSED' AND pnl IS NOT NULL
                """)
            
            if include_exchange:
                queries.append("""
                    SELECT 
                        'EXCHANGE' as source,
                        symbol, direction, entry_price, exit_price,
                        NULL as rsi, NULL as trend,
                        NULL as entry_volatility, NULL as entry_volume_ratio,
                        pnl, roi, CASE WHEN pnl > 0 THEN 1 ELSE 0 END as is_successful,
                        entry_time as timestamp, exit_time as close_timestamp,
                        NULL as close_reason, NULL as ai_decision_id, NULL as ai_confidence
                    FROM exchange_trades
                    WHERE pnl IS NOT NULL
                """)
            
            if not queries:
                return []
            
            # Объединяем запросы
            union_query = " UNION ALL ".join(queries)
            
            # Группируем по символам и фильтруем по минимальному количеству
            final_query = f"""
                WITH all_trades AS ({union_query})
                SELECT * FROM all_trades
                WHERE symbol IN (
                    SELECT symbol FROM all_trades
                    GROUP BY symbol
                    HAVING COUNT(*) >= ?
                )
                ORDER BY timestamp DESC
            """
            params.append(min_trades)
            
            if limit:
                final_query += " LIMIT ?"
                params.append(limit)
            
            cursor.execute(final_query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    def analyze_patterns(self, 
                         symbol: Optional[str] = None,
                         rsi_range: Optional[Tuple[float, float]] = None,
                         min_trades: int = 10) -> List[Dict[str, Any]]:
        """
        Анализирует паттерны в сделках
        
        Args:
            symbol: Фильтр по символу
            rsi_range: Диапазон RSI (min, max)
            min_trades: Минимальное количество сделок для паттерна
        
        Returns:
            Список паттернов с метриками
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    symbol,
                    CASE 
                        WHEN entry_rsi <= 25 THEN '<=25'
                        WHEN entry_rsi <= 30 THEN '26-30'
                        WHEN entry_rsi <= 35 THEN '31-35'
                        WHEN entry_rsi >= 70 THEN '>=70'
                        WHEN entry_rsi >= 65 THEN '65-69'
                        ELSE 'OTHER'
                    END as rsi_range,
                    entry_trend as trend,
                    COUNT(*) as trade_count,
                    AVG(pnl) as avg_pnl,
                    SUM(CASE WHEN is_successful = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate,
                    AVG(duration_candles) as avg_duration
                FROM simulated_trades
                WHERE entry_rsi IS NOT NULL
            """
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            if rsi_range:
                query += " AND entry_rsi >= ? AND entry_rsi <= ?"
                params.extend(rsi_range)
            
            query += """
                GROUP BY symbol, rsi_range, trend
                HAVING trade_count >= ?
                ORDER BY win_rate DESC, avg_pnl DESC
            """
            params.append(min_trades)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    def get_ai_decision_performance(self, 
                                    symbol: Optional[str] = None,
                                    min_confidence: Optional[float] = None) -> Dict[str, Any]:
        """
        Анализирует производительность решений AI
        
        Returns:
            Статистика по решениям AI
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    COUNT(*) as total_decisions,
                    AVG(confidence) as avg_confidence,
                    SUM(CASE WHEN result_successful = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate,
                    AVG(result_pnl) as avg_pnl,
                    COUNT(DISTINCT symbol) as symbols_count
                FROM ai_decisions
                WHERE result_pnl IS NOT NULL
            """
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            if min_confidence:
                query += " AND confidence >= ?"
                params.append(min_confidence)
            
            cursor.execute(query, params)
            result = dict(cursor.fetchone())
            
            return result
    
    def get_training_statistics(self, session_type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Получает статистику по сессиям обучения"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM training_sessions WHERE 1=1"
            params = []
            
            if session_type:
                query += " AND session_type = ?"
                params.append(session_type)
            
            query += " ORDER BY started_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                session = dict(row)
                if session.get('metadata_json'):
                    session['metadata'] = json.loads(session['metadata_json'])
                result.append(session)
            
            return result
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Получает общую статистику базы данных"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Подсчеты по таблицам
            tables = ['simulated_trades', 'bot_trades', 'exchange_trades', 'ai_decisions', 'training_sessions']
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[f"{table}_count"] = cursor.fetchone()[0]
            
            # Размер базы данных
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            stats['database_size_mb'] = db_size / 1024 / 1024
            
            # Статистика по символам
            cursor.execute("SELECT COUNT(DISTINCT symbol) FROM simulated_trades")
            stats['unique_symbols_simulated'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT symbol) FROM bot_trades WHERE is_simulated = 0")
            stats['unique_symbols_real'] = cursor.fetchone()[0]
            
            return stats


# Глобальный экземпляр базы данных
_ai_database_instance = None
_ai_database_lock = threading.Lock()


def get_ai_database(db_path: str = None) -> AIDatabase:
    """Получает глобальный экземпляр базы данных AI"""
    global _ai_database_instance
    
    with _ai_database_lock:
        if _ai_database_instance is None:
            _ai_database_instance = AIDatabase(db_path)
        
        return _ai_database_instance

