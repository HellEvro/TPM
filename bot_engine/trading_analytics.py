#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Аналитический модуль торговли.

Анализирует ВСЕ сделки на бирже и сделки ботов из БД:
- Сверка биржа vs bot_trades_history (потерянные/лишние/расхождения)
- Метрики: Win Rate, PnL, просадка, серии убытков
- Анализ по причинам закрытия (Stop Loss, Take Profit, ошибки)
- Разбивка по символам, ботам, источникам решений
- Отчёт в виде словаря/JSON для использования AI модулем
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Допуск при сверке: разница времени выхода (секунды)
RECONCILE_TIME_TOLERANCE_SEC = 120
# Допуск по PnL (абсолютный USDT) для совпадения
RECONCILE_PNL_TOLERANCE = 0.5


@dataclass
class TradeSummary:
    """Нормализованная краткая сводка по сделке для сверки и аналитики."""
    symbol: str
    exit_timestamp: float  # секунды (Unix)
    pnl: float
    entry_price: float
    exit_price: float
    position_size_usdt: Optional[float]
    direction: str
    source: str  # 'exchange' | 'bot'
    bot_id: Optional[str] = None
    close_reason: Optional[str] = None
    decision_source: Optional[str] = None
    raw_id: Any = None
    raw: Optional[Dict[str, Any]] = None


def _ts_to_seconds(ts: Any) -> Optional[float]:
    """Приводит timestamp к секундам (Unix)."""
    if ts is None:
        return None
    try:
        if isinstance(ts, (int, float)):
            if ts > 1e12:
                return ts / 1000.0
            return float(ts)
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            return dt.timestamp()
    except Exception:
        pass
    return None


def _normalize_symbol(s: Optional[str]) -> str:
    if not s:
        return ""
    return (s or "").replace("USDT", "").strip().upper()


def exchange_trades_to_summaries(
    raw_list: List[Dict[str, Any]],
    exchange_name: str = "exchange",
) -> List[TradeSummary]:
    """Преобразует ответ get_closed_pnl биржи в список TradeSummary."""
    result = []
    for i, t in enumerate(raw_list):
        try:
            symbol = _normalize_symbol(t.get("symbol"))
            close_ts = t.get("close_timestamp") or t.get("closeTime") or 0
            ts_sec = _ts_to_seconds(close_ts)
            if ts_sec is None:
                ts_sec = 0.0
            pnl = float(t.get("closed_pnl") or t.get("closedPnl") or 0)
            entry_price = float(t.get("entry_price") or t.get("avgEntryPrice") or 0)
            exit_price = float(t.get("exit_price") or t.get("avgExitPrice") or 0)
            position_value = t.get("position_value")
            if position_value is None and entry_price and t.get("qty"):
                position_value = abs(float(t.get("qty", 0)) * entry_price)
            if position_value is not None:
                position_value = float(position_value)
            side = (t.get("side") or "").upper()
            direction = "LONG" if side in ("BUY", "LONG") else "SHORT"
            result.append(
                TradeSummary(
                    symbol=symbol,
                    exit_timestamp=ts_sec,
                    pnl=pnl,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    position_size_usdt=position_value,
                    direction=direction,
                    source="exchange",
                    raw_id=i,
                    raw=t,
                )
            )
        except Exception as e:
            logger.debug("Пропуск записи биржи %s: %s", t, e)
    return result


def bot_trades_to_summaries(
    raw_list: List[Dict[str, Any]],
) -> List[TradeSummary]:
    """Преобразует записи bot_trades_history в список TradeSummary."""
    result = []
    for t in raw_list:
        try:
            symbol = _normalize_symbol(t.get("symbol"))
            exit_ts = t.get("exit_timestamp")
            ts_sec = _ts_to_seconds(exit_ts)
            if ts_sec is None and t.get("exit_time"):
                ts_sec = _ts_to_seconds(t.get("exit_time"))
            if ts_sec is None:
                continue
            pnl = float(t.get("pnl") or 0)
            entry_price = float(t.get("entry_price") or 0)
            exit_price = float(t.get("exit_price") or 0)
            position_size = t.get("position_size_usdt")
            if position_size is not None:
                position_size = float(position_size)
            direction = (t.get("direction") or "LONG").upper()
            if direction not in ("LONG", "SHORT"):
                direction = "LONG"
            result.append(
                TradeSummary(
                    symbol=symbol,
                    exit_timestamp=ts_sec,
                    pnl=pnl,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    position_size_usdt=position_size,
                    direction=direction,
                    source="bot",
                    bot_id=t.get("bot_id"),
                    close_reason=t.get("close_reason"),
                    decision_source=t.get("decision_source"),
                    raw_id=t.get("id"),
                    raw=t,
                )
            )
        except Exception as e:
            logger.debug("Пропуск записи бота %s: %s", t.get("id"), e)
    return result


def reconcile_trades(
    exchange_summaries: List[TradeSummary],
    bot_summaries: List[TradeSummary],
    time_tolerance_sec: float = RECONCILE_TIME_TOLERANCE_SEC,
    pnl_tolerance: float = RECONCILE_PNL_TOLERANCE,
) -> Dict[str, Any]:
    """
    Сверка сделок биржи и ботов.
    Возвращает: matched, only_on_exchange, only_in_bots, pnl_mismatches.
    """
    only_on_exchange: List[Dict[str, Any]] = []
    only_in_bots: List[Dict[str, Any]] = []
    matched: List[Dict[str, Any]] = []
    pnl_mismatches: List[Dict[str, Any]] = []

    used_bot = set()

    for ex in exchange_summaries:
        best_bot: Optional[TradeSummary] = None
        best_diff = float("inf")
        for bot in bot_summaries:
            if bot.raw_id in used_bot:
                continue
            if bot.symbol != ex.symbol:
                continue
            time_diff = abs(bot.exit_timestamp - ex.exit_timestamp)
            if time_diff > time_tolerance_sec:
                continue
            pnl_diff = abs(bot.pnl - ex.pnl)
            total_diff = time_diff + pnl_diff * 10
            if total_diff < best_diff:
                best_diff = total_diff
                best_bot = bot

        if best_bot is None:
            only_on_exchange.append({
                "symbol": ex.symbol,
                "exit_timestamp": ex.exit_timestamp,
                "pnl": ex.pnl,
                "entry_price": ex.entry_price,
                "exit_price": ex.exit_price,
            })
            continue

        used_bot.add(best_bot.raw_id)
        pnl_diff = abs(best_bot.pnl - ex.pnl)
        if pnl_diff > pnl_tolerance:
            pnl_mismatches.append({
                "symbol": ex.symbol,
                "exchange_pnl": ex.pnl,
                "bot_pnl": best_bot.pnl,
                "diff": best_bot.pnl - ex.pnl,
                "exit_timestamp": ex.exit_timestamp,
                "bot_id": best_bot.bot_id,
            })
        matched.append({
            "symbol": ex.symbol,
            "exit_timestamp": ex.exit_timestamp,
            "pnl": ex.pnl,
            "bot_id": best_bot.bot_id,
            "close_reason": best_bot.close_reason,
            "decision_source": best_bot.decision_source,
        })

    for bot in bot_summaries:
        if bot.raw_id in used_bot:
            continue
        only_in_bots.append({
            "symbol": bot.symbol,
            "exit_timestamp": bot.exit_timestamp,
            "pnl": bot.pnl,
            "bot_id": bot.bot_id,
            "close_reason": bot.close_reason,
            "decision_source": bot.decision_source,
        })

    return {
        "matched_count": len(matched),
        "only_on_exchange_count": len(only_on_exchange),
        "only_in_bots_count": len(only_in_bots),
        "pnl_mismatch_count": len(pnl_mismatches),
        "matched": matched,
        "only_on_exchange": only_on_exchange,
        "only_in_bots": only_in_bots,
        "pnl_mismatches": pnl_mismatches,
    }


def _compute_series(trades: List[TradeSummary]) -> Dict[str, Any]:
    """Считает серии прибыльных/убыточных сделок."""
    if not trades:
        return {"max_consecutive_wins": 0, "max_consecutive_losses": 0, "current_streak": 0}
    sorted_trades = sorted(trades, key=lambda x: x.exit_timestamp)
    max_wins = 0
    max_losses = 0
    cur_wins = 0
    cur_losses = 0
    for t in sorted_trades:
        if t.pnl > 0:
            cur_wins += 1
            cur_losses = 0
            max_wins = max(max_wins, cur_wins)
        elif t.pnl < 0:
            cur_losses += 1
            cur_wins = 0
            max_losses = max(max_losses, cur_losses)
        else:
            cur_wins = 0
            cur_losses = 0
    last = sorted_trades[-1]
    current_streak = cur_wins if last.pnl > 0 else (-cur_losses if last.pnl < 0 else 0)
    return {
        "max_consecutive_wins": max_wins,
        "max_consecutive_losses": max_losses,
        "current_streak": current_streak,
    }


def _compute_drawdown(trades: List[TradeSummary]) -> Dict[str, Any]:
    """Считает просадку по эквити (кумулятивный PnL)."""
    if not trades:
        return {"max_drawdown_usdt": 0.0, "max_drawdown_pct": 0.0, "equity_curve": []}
    sorted_trades = sorted(trades, key=lambda x: x.exit_timestamp)
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    max_dd_pct = 0.0
    curve = []
    for t in sorted_trades:
        equity += t.pnl
        curve.append({"exit_timestamp": t.exit_timestamp, "equity": equity})
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
        if peak > 0 and peak - equity > 0:
            pct = 100.0 * (peak - equity) / peak
            if pct > max_dd_pct:
                max_dd_pct = pct
    return {
        "max_drawdown_usdt": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "final_equity": round(equity, 2),
        "equity_curve": curve[-500:],  # последние 500 точек для экономии
    }


def analyze_bot_trades(
    bot_summaries: List[TradeSummary],
) -> Dict[str, Any]:
    """Полная аналитика по сделкам ботов (без биржи)."""
    closed = [t for t in bot_summaries if t.raw and (t.raw.get("status") == "CLOSED" or t.pnl != 0 or t.raw.get("exit_timestamp"))]
    if not closed:
        closed = bot_summaries

    total = len(closed)
    total_pnl = sum(t.pnl for t in closed)
    wins = [t for t in closed if t.pnl > 0]
    losses = [t for t in closed if t.pnl < 0]
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / total * 100) if total else 0.0
    avg_win = (sum(t.pnl for t in wins) / win_count) if win_count else 0.0
    avg_loss = (sum(t.pnl for t in losses) / loss_count) if loss_count else 0.0

    by_close_reason: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "pnl": 0.0, "wins": 0, "losses": 0})
    for t in closed:
        reason = t.close_reason or "UNKNOWN"
        by_close_reason[reason]["count"] += 1
        by_close_reason[reason]["pnl"] += t.pnl
        if t.pnl > 0:
            by_close_reason[reason]["wins"] += 1
        else:
            by_close_reason[reason]["losses"] += 1

    by_symbol: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "pnl": 0.0, "wins": 0, "losses": 0})
    for t in closed:
        by_symbol[t.symbol]["count"] += 1
        by_symbol[t.symbol]["pnl"] += t.pnl
        if t.pnl > 0:
            by_symbol[t.symbol]["wins"] += 1
        else:
            by_symbol[t.symbol]["losses"] += 1

    by_decision_source: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "pnl": 0.0, "wins": 0, "losses": 0})
    for t in closed:
        src = t.decision_source or "UNKNOWN"
        by_decision_source[src]["count"] += 1
        by_decision_source[src]["pnl"] += t.pnl
        if t.pnl > 0:
            by_decision_source[src]["wins"] += 1
        else:
            by_decision_source[src]["losses"] += 1

    by_bot: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "pnl": 0.0, "wins": 0, "losses": 0})
    for t in closed:
        bid = t.bot_id or "NO_BOT"
        by_bot[bid]["count"] += 1
        by_bot[bid]["pnl"] += t.pnl
        if t.pnl > 0:
            by_bot[bid]["wins"] += 1
        else:
            by_bot[bid]["losses"] += 1

    series = _compute_series(closed)
    drawdown = _compute_drawdown(closed)

    # Потенциальные ошибки: по close_reason или по признакам
    error_keywords = ("error", "ERROR", "fail", "exception", "timeout", "cancel", "reject")
    possible_errors = []
    for t in closed:
        reason = (t.close_reason or "")
        if any(kw in reason for kw in error_keywords):
            possible_errors.append({
                "symbol": t.symbol,
                "exit_timestamp": t.exit_timestamp,
                "pnl": t.pnl,
                "close_reason": t.close_reason,
                "bot_id": t.bot_id,
            })
        if t.raw:
            extra = t.raw.get("extra_data") or t.raw.get("extra_data_json")
            if isinstance(extra, str):
                try:
                    extra = json.loads(extra)
                except Exception:
                    extra = {}
            if extra and isinstance(extra, dict) and any(kw in str(extra).lower() for kw in ("error", "fail", "exception")):
                possible_errors.append({
                    "symbol": t.symbol,
                    "exit_timestamp": t.exit_timestamp,
                    "pnl": t.pnl,
                    "close_reason": t.close_reason,
                    "bot_id": t.bot_id,
                    "extra": extra,
                })

    return {
        "total_trades": total,
        "total_pnl_usdt": round(total_pnl, 2),
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate_pct": round(win_rate, 2),
        "avg_win_usdt": round(avg_win, 2),
        "avg_loss_usdt": round(avg_loss, 2),
        "by_close_reason": {k: dict(v) for k, v in by_close_reason.items()},
        "by_symbol": {k: dict(v) for k, v in by_symbol.items()},
        "by_decision_source": {k: dict(v) for k, v in by_decision_source.items()},
        "by_bot": {k: dict(v) for k, v in by_bot.items()},
        "consecutive_series": series,
        "drawdown": drawdown,
        "possible_errors_count": len(possible_errors),
        "possible_errors": possible_errors[:100],
    }


def analyze_exchange_trades(
    exchange_summaries: List[TradeSummary],
) -> Dict[str, Any]:
    """Аналитика только по сделкам с биржи (агрегированная)."""
    total = len(exchange_summaries)
    total_pnl = sum(t.pnl for t in exchange_summaries)
    wins = [t for t in exchange_summaries if t.pnl > 0]
    losses = [t for t in exchange_summaries if t.pnl < 0]
    win_rate = (len(wins) / total * 100) if total else 0.0
    by_symbol: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "pnl": 0.0})
    for t in exchange_summaries:
        by_symbol[t.symbol]["count"] += 1
        by_symbol[t.symbol]["pnl"] += t.pnl
    series = _compute_series(exchange_summaries)
    drawdown = _compute_drawdown(exchange_summaries)
    return {
        "total_trades": total,
        "total_pnl_usdt": round(total_pnl, 2),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate_pct": round(win_rate, 2),
        "by_symbol": {k: dict(v) for k, v in by_symbol.items()},
        "consecutive_series": series,
        "drawdown": drawdown,
    }


def run_full_analytics(
    exchange_trades: Optional[List[Dict[str, Any]]] = None,
    bot_trades: Optional[List[Dict[str, Any]]] = None,
    load_bot_trades_from_db: bool = True,
    load_exchange_from_api: bool = False,
    exchange_instance: Any = None,
    exchange_period: str = "all",
    bots_db_limit: Optional[int] = 50000,
) -> Dict[str, Any]:
    """
    Запускает полную аналитику торговли.

    Источники данных:
    - exchange_trades: если передан, используется как сделки с биржи
    - bot_trades: если передан, используется как сделки ботов
    - load_bot_trades_from_db=True: подгружает из bots_data.db (bot_trades_history)
    - load_exchange_from_api=True: требует exchange_instance, вызывает get_closed_pnl(period=exchange_period)

    Returns:
        Словарь с ключами: exchange_analytics, bot_analytics, reconciliation, summary, generated_at.
    """
    generated_at = datetime.now(timezone.utc).isoformat()

    # Загрузка сделок ботов из БД
    if bot_trades is None and load_bot_trades_from_db:
        try:
            from bot_engine.bots_database import get_bots_database
            db = get_bots_database()
            bot_trades = db.get_bot_trades_history(
                status="CLOSED",
                limit=bots_db_limit,
            )
            if not bot_trades:
                bot_trades = []
        except Exception as e:
            logger.warning("Не удалось загрузить сделки ботов из БД: %s", e)
            bot_trades = []

    if bot_trades is None:
        bot_trades = []

    # Загрузка сделок с биржи
    if exchange_trades is None and load_exchange_from_api and exchange_instance is not None:
        try:
            if hasattr(exchange_instance, "get_closed_pnl"):
                exchange_trades = exchange_instance.get_closed_pnl(
                    sort_by="time",
                    period=exchange_period,
                ) or []
            else:
                exchange_trades = []
        except Exception as e:
            logger.warning("Не удалось загрузить сделки с биржи: %s", e)
            exchange_trades = []

    if exchange_trades is None:
        exchange_trades = []

    ex_summaries = exchange_trades_to_summaries(exchange_trades)
    bot_summaries = bot_trades_to_summaries(bot_trades)

    exchange_analytics = analyze_exchange_trades(ex_summaries) if ex_summaries else {}
    bot_analytics = analyze_bot_trades(bot_summaries) if bot_summaries else {}

    reconciliation = {}
    if ex_summaries and bot_summaries:
        reconciliation = reconcile_trades(ex_summaries, bot_summaries)

    summary = {
        "exchange_trades_count": len(ex_summaries),
        "bot_trades_count": len(bot_summaries),
        "reconciliation_matched": reconciliation.get("matched_count", 0),
        "reconciliation_only_exchange": reconciliation.get("only_on_exchange_count", 0),
        "reconciliation_only_bots": reconciliation.get("only_in_bots_count", 0),
        "reconciliation_pnl_mismatches": reconciliation.get("pnl_mismatch_count", 0),
        "bot_win_rate_pct": bot_analytics.get("win_rate_pct"),
        "bot_total_pnl_usdt": bot_analytics.get("total_pnl_usdt"),
        "exchange_total_pnl_usdt": exchange_analytics.get("total_pnl_usdt"),
    }

    return {
        "generated_at": generated_at,
        "exchange_analytics": exchange_analytics,
        "bot_analytics": bot_analytics,
        "reconciliation": reconciliation,
        "summary": summary,
    }


def get_analytics_for_ai(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Извлекает из полного отчёта структурированные данные для AI модуля:
    - проблемы (ошибки, расхождения, серии убытков)
    - метрики по причинам закрытия и символам
    - рекомендации (текстовые тезисы)
    """
    bot = report.get("bot_analytics") or {}
    recon = report.get("reconciliation") or {}
    problems: List[str] = []
    recommendations: List[str] = []

    if bot.get("possible_errors_count", 0) > 0:
        problems.append(
            f"Обнаружено потенциальных ошибок в сделках: {bot['possible_errors_count']}. "
            "Проверьте close_reason и extra_data."
        )
        recommendations.append("Проанализировать записи possible_errors и при необходимости скорректировать логику закрытия.")

    max_losses = (bot.get("consecutive_series") or {}).get("max_consecutive_losses", 0)
    if max_losses >= 3:
        problems.append(f"Серия убыточных сделок подряд: до {max_losses}. Возможен переторг или неблагоприятный режим рынка.")
        recommendations.append("Рассмотреть фильтр по сериям убытков (пауза или уменьшение размера).")

    dd = (bot.get("drawdown") or {}).get("max_drawdown_usdt")
    if dd is not None and dd > 10:
        problems.append(f"Максимальная просадка по эквити: {dd} USDT.")
        recommendations.append("Проверить настройки Stop Loss и макс. просадки.")

    if recon.get("only_on_exchange_count", 0) > 5:
        problems.append(
            f"На бирже {recon['only_on_exchange_count']} сделок без соответствия в истории ботов. "
            "Часть сделок могла быть закрыта вручную или другим клиентом."
        )
        recommendations.append("Синхронизировать историю: rebuild_bot_history_from_exchange или импорт закрытых PnL.")

    if recon.get("pnl_mismatch_count", 0) > 0:
        problems.append(f"Расхождение PnL между биржей и историей ботов: {recon['pnl_mismatch_count']} сделок.")
        recommendations.append("Проверить округление и комиссии при сохранении сделок.")

    by_reason = bot.get("by_close_reason") or {}
    stop_loss_count = by_reason.get("STOP_LOSS", {}).get("count", 0) + by_reason.get("Stop Loss", {}).get("count", 0)
    total_closed = bot.get("total_trades", 0)
    if total_closed and stop_loss_count / total_closed > 0.5:
        recommendations.append("Большая доля закрытий по Stop Loss — рассмотреть ослабление SL или улучшение фильтров входа.")

    return {
        "problems": problems,
        "recommendations": recommendations,
        "metrics": {
            "win_rate_pct": bot.get("win_rate_pct"),
            "total_pnl_usdt": bot.get("total_pnl_usdt"),
            "max_consecutive_losses": (bot.get("consecutive_series") or {}).get("max_consecutive_losses"),
            "max_drawdown_usdt": (bot.get("drawdown") or {}).get("max_drawdown_usdt"),
            "by_close_reason_counts": {k: v.get("count", 0) for k, v in by_reason.items()},
        },
        "generated_at": report.get("generated_at"),
    }
