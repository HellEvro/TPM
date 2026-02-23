# -*- coding: utf-8 -*-
"""
FullAI LLM: опциональное использование LLM (GLM-4.7 flash / Zhipu AI) для решений о входе/выходе.

Когда fullai_llm_enabled=True и задан fullai_llm_api_key (или ZHIPU_API_KEY),
решения о входе и при необходимости о выходе принимает LLM вместо голосования LSTM+pattern.

Модель по умолчанию: glm-4-flash (Zhipu). Поддерживается любой OpenAI-совместимый endpoint
при указании fullai_llm_base_url.
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional

logger = logging.getLogger("FullAI.LLM")

# Кеш клиента (ленивая инициализация)
_llm_client = None


def _get_llm_client(api_key: str, base_url: Optional[str] = None):
    """Возвращает клиент для вызова LLM. Предпочтительно ZhipuAI, иначе OpenAI-совместимый."""
    global _llm_client
    if not api_key or not api_key.strip():
        return None
    if _llm_client is not None:
        return _llm_client
    try:
        if base_url:
            try:
                import openai
                _llm_client = openai.OpenAI(api_key=api_key.strip(), base_url=base_url.rstrip("/") + "/")
                logger.info("[FullAI LLM] Используется OpenAI-совместимый endpoint: %s", base_url)
                return _llm_client
            except ImportError:
                logger.warning("[FullAI LLM] openai не установлен, пробуем zhipuai")
        from zhipuai import ZhipuAI
        _llm_client = ZhipuAI(api_key=api_key.strip())
        logger.info("[FullAI LLM] ZhipuAI (GLM) клиент инициализирован")
        return _llm_client
    except ImportError as e:
        logger.warning("[FullAI LLM] zhipuai не установлен: %s. Установите: pip install zhipuai", e)
        return None
    except Exception as e:
        logger.warning("[FullAI LLM] Ошибка инициализации клиента: %s", e)
        return None


def _candles_summary(candles: List[Dict], max_bars: int = 12) -> str:
    """Краткое описание последних свечей для промпта."""
    if not candles:
        return "нет данных"
    recent = candles[-max_bars:] if len(candles) >= max_bars else candles
    lines = []
    for i, c in enumerate(recent):
        o = c.get("open") or 0
        h = c.get("high") or 0
        l = c.get("low") or 0
        cl = c.get("close") or 0
        lines.append(f"  {i+1}. O={o} H={h} L={l} C={cl}")
    return "\n".join(lines)


def get_llm_entry_decision(
    symbol: str,
    direction: str,
    candles: List[Dict],
    current_price: float,
    config: Dict[str, Any],
    rsi: Optional[float] = None,
    trend: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Запрос к LLM: разрешить ли вход в позицию (LONG/SHORT).
    Возвращает {"allowed": bool, "confidence": float 0-1, "reason": str} или None при ошибке.
    """
    api_key = (config.get("fullai_llm_api_key") or "").strip() or os.environ.get("ZHIPU_API_KEY", "").strip()
    if not api_key:
        return None
    if not config.get("fullai_llm_enabled", False):
        return None

    client = _get_llm_client(api_key, config.get("fullai_llm_base_url"))
    if not client:
        return None

    model = config.get("fullai_llm_model") or "glm-4-flash"
    summary = _candles_summary(candles or [])
    rsi_str = f"RSI={rsi:.1f}" if rsi is not None else "RSI=нет"
    trend_str = trend or "нет"

    system_prompt = (
        "Ты торговый советник. Отвечай ТОЛЬКО валидным JSON, без markdown и пояснений. "
        "Формат ответа: {\"allowed\": true или false, \"confidence\": число от 0 до 1, \"reason\": \"краткая причина\"}."
    )
    user_prompt = (
        f"Символ: {symbol}. Предлагаемый вход: {direction}. Текущая цена: {current_price}. {rsi_str}. Тренд: {trend_str}.\n"
        f"Последние свечи (O/H/L/C):\n{summary}\n\n"
        "Разрешить вход? Верни только JSON: allowed, confidence (0-1), reason."
    )

    try:
        if hasattr(client, "chat") and hasattr(client.chat, "completions"):
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=256,
                temperature=0.3,
            )
        else:
            return None

        text = (resp.choices[0].message.content or "").strip()
        # Убрать обёртку markdown если есть
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(l for l in lines if l.strip() and not l.strip().startswith("```"))
        data = json.loads(text)
        allowed = bool(data.get("allowed", False))
        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
        reason = str(data.get("reason", "LLM"))[:200]
        return {"allowed": allowed, "confidence": confidence, "reason": f"GLM: {reason}"}
    except json.JSONDecodeError as e:
        logger.debug("[FullAI LLM] entry: не удалось распарсить JSON: %s", e)
        return None
    except Exception as e:
        logger.warning("[FullAI LLM] entry %s %s: %s", symbol, direction, e)
        return None


def get_llm_exit_decision(
    symbol: str,
    position: Dict[str, Any],
    candles: List[Dict],
    pnl_percent: float,
    config: Dict[str, Any],
    data_context: Optional[Dict] = None,
) -> Optional[Dict[str, Any]]:
    """
    Запрос к LLM: закрывать ли позицию сейчас.
    Возвращает {"close_now": bool, "reason": str, "confidence": float} или None при ошибке.
    """
    api_key = (config.get("fullai_llm_api_key") or "").strip() or os.environ.get("ZHIPU_API_KEY", "").strip()
    if not api_key or not config.get("fullai_llm_enabled", False):
        return None

    client = _get_llm_client(api_key, config.get("fullai_llm_base_url"))
    if not client:
        return None

    model = config.get("fullai_llm_model") or "glm-4-flash"
    pos_side = (position.get("position_side") or position.get("side") or "LONG").upper()
    summary = _candles_summary(candles or [], max_bars=8)
    system_indicators = ""
    if data_context and isinstance(data_context.get("system"), dict):
        sys_ = data_context["system"]
        system_indicators = f" RSI={sys_.get('rsi')}, тренд={sys_.get('trend')}, сигнал={sys_.get('signal')}."

    system_prompt = (
        "Ты торговый советник. Отвечай ТОЛЬКО валидным JSON: "
        "{\"close_now\": true или false, \"reason\": \"краткая причина\", \"confidence\": число 0-1}. Без markdown."
    )
    user_prompt = (
        f"Символ: {symbol}. Позиция: {pos_side}. PnL: {pnl_percent:.2f}%.{system_indicators}\n"
        f"Последние свечи:\n{summary}\n\n"
        "Закрывать позицию сейчас? Только JSON: close_now, reason, confidence."
    )

    try:
        if hasattr(client, "chat") and hasattr(client.chat, "completions"):
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=256,
                temperature=0.2,
            )
        else:
            return None

        text = (resp.choices[0].message.content or "").strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(l for l in lines if l.strip() and not l.strip().startswith("```"))
        data = json.loads(text)
        close_now = bool(data.get("close_now", False))
        reason = str(data.get("reason", "LLM"))[:200]
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
        return {"close_now": close_now, "reason": f"GLM: {reason}", "confidence": confidence}
    except (json.JSONDecodeError, Exception) as e:
        logger.debug("[FullAI LLM] exit %s: %s", symbol, e)
        return None


def is_llm_available(config: Dict[str, Any]) -> bool:
    """Проверка: включён ли LLM и задан ли API ключ."""
    if not config.get("fullai_llm_enabled", False):
        return False
    key = (config.get("fullai_llm_api_key") or "").strip() or os.environ.get("ZHIPU_API_KEY", "").strip()
    return bool(key)
