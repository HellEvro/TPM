"""
Загрузчик премиум ИИ модулей

Этот модуль проверяет наличие и валидность лицензии для использования премиум ИИ функций.
Если лицензия отсутствует или невалидна, ИИ модули не загружаются.

Для активации лицензии:
    python scripts/activate_premium.py
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger('AI_Premium')


class PremiumModuleLoader:
    """Загрузчик премиум ИИ модулей"""
    
    def __init__(self):
        self.premium_available = False
        self.license_valid = False
        self.license_info = None
        self.modules = {}
    
    def check_premium_module(self) -> bool:
        """
        Проверяет наличие премиум модулей
        
        В режиме разработки (текущая папка) - все модули доступны локально.
        В продакшене - проверяет наличие скомпилированного модуля.
        
        Returns:
            True если модули доступны
        """
        try:
            # Режим разработки - проверяем локальные модули
            from bot_engine.ai import anomaly_detector
            
            self.premium_available = True
            logger.info("[AI_Premium] ✅ Premium модули доступны (режим разработки)")
            return True
            
        except ImportError:
            # Пытаемся загрузить скомпилированный модуль
            try:
                import infobot_ai_premium
                self.premium_available = True
                logger.info("[AI_Premium] ✅ Premium модуль обнаружен (скомпилированная версия)")
                return True
            except ImportError:
                logger.info("[AI_Premium] ℹ️ Premium модули не установлены")
                logger.info("[AI_Premium] 💡 Для использования ИИ функций приобретите лицензию")
                self.premium_available = False
                return False
    
    def verify_license(self, license_path: str = 'license.lic') -> bool:
        """
        Проверяет валидность лицензии
        
        Args:
            license_path: Путь к файлу лицензии
        
        Returns:
            True если лицензия валидна
        """
        if not self.premium_available:
            return False
        
        # В режиме разработки - пропускаем проверку лицензии
        if os.getenv('AI_DEV_MODE') == '1':
            logger.info("[AI_Premium] 🔧 Режим разработки - проверка лицензии отключена")
            self.license_valid = True
            self.license_info = {
                'type': 'developer',
                'expires_at': '9999-12-31',
                'features': {
                    'anomaly_detection': True,
                    'lstm_predictor': True,
                    'pattern_recognition': True,
                    'risk_management': True,
                    'max_bots': 999,
                    'debug_mode': True
                }
            }
            return True
        
        # Проверяем наличие файла лицензии
        if not os.path.exists(license_path):
            logger.warning("[AI_Premium] ⚠️ Файл лицензии не найден")
            logger.info("[AI_Premium] 💡 Активируйте лицензию: python scripts/activate_premium.py")
            return False
        
        try:
            # TODO: Реализовать реальную проверку лицензии
            # Пока заглушка для разработки
            
            logger.warning("[AI_Premium] ⚠️ Проверка лицензии не реализована (в разработке)")
            logger.info("[AI_Premium] 💡 Для разработки установите AI_DEV_MODE=1")
            
            self.license_valid = False
            return False
            
        except Exception as e:
            logger.error(f"[AI_Premium] ❌ Ошибка проверки лицензии: {e}")
            return False
    
    def get_ai_module(self, module_name: str):
        """
        Получает ИИ модуль по имени
        
        Args:
            module_name: Имя модуля (anomaly_detector, lstm_predictor, и т.д.)
        
        Returns:
            Модуль или None если недоступен
        
        Raises:
            RuntimeError: Если модуль недоступен по лицензии
        """
        if not self.premium_available:
            raise RuntimeError(
                "Premium AI module not available. "
                "Please install and activate your license."
            )
        
        if not self.license_valid:
            raise RuntimeError(
                "License is invalid or expired. "
                "Please activate your license: python scripts/activate_premium.py"
            )
        
        # Проверяем права доступа к модулю
        features = self.license_info.get('features', {})
        
        module_feature_map = {
            'anomaly_detector': 'anomaly_detection',
            'lstm_predictor': 'lstm_predictor',
            'pattern_detector': 'pattern_recognition',
            'risk_manager': 'risk_management'
        }
        
        feature_key = module_feature_map.get(module_name)
        if feature_key and not features.get(feature_key, False):
            raise RuntimeError(
                f"Module '{module_name}' is not available in your license. "
                f"Please upgrade your license."
            )
        
        # Кэшируем модули
        if module_name in self.modules:
            return self.modules[module_name]
        
        # Импортируем модуль
        try:
            # Режим разработки - локальные модули
            module = __import__(
                f'bot_engine.ai.{module_name}',
                fromlist=[module_name]
            )
            self.modules[module_name] = module
            return module
            
        except ImportError:
            # Скомпилированная версия
            try:
                import infobot_ai_premium
                module = getattr(infobot_ai_premium, module_name)
                self.modules[module_name] = module
                return module
            except (ImportError, AttributeError) as e:
                raise RuntimeError(f"Failed to load module '{module_name}': {e}")
    
    def get_license_info(self) -> Dict[str, Any]:
        """
        Возвращает информацию о лицензии
        
        Returns:
            Словарь с информацией о лицензии
        """
        if self.license_valid and self.license_info:
            return self.license_info
        
        # Бесплатная версия
        return {
            'type': 'free',
            'expires_at': None,
            'features': {
                'anomaly_detection': False,
                'lstm_predictor': False,
                'pattern_recognition': False,
                'risk_management': False,
                'max_bots': 0,
                'debug_mode': False
            }
        }
    
    def is_feature_available(self, feature_name: str) -> bool:
        """
        Проверяет доступность конкретной функции
        
        Args:
            feature_name: Название функции
        
        Returns:
            True если функция доступна
        """
        if not self.license_valid:
            return False
        
        features = self.license_info.get('features', {})
        return features.get(feature_name, False)


# Глобальный экземпляр загрузчика
_loader: Optional[PremiumModuleLoader] = None


def get_premium_loader() -> PremiumModuleLoader:
    """
    Получает глобальный экземпляр загрузчика премиум модулей
    
    Returns:
        Экземпляр PremiumModuleLoader
    """
    global _loader
    
    if _loader is None:
        _loader = PremiumModuleLoader()
        _loader.check_premium_module()
        
        if _loader.premium_available:
            _loader.verify_license()
    
    return _loader


def enable_dev_mode():
    """
    Включает режим разработки (пропускает проверку лицензии)
    
    Использование:
        import os
        os.environ['AI_DEV_MODE'] = '1'
        
        # Или в терминале:
        # export AI_DEV_MODE=1  # Linux/Mac
        # set AI_DEV_MODE=1     # Windows
    """
    os.environ['AI_DEV_MODE'] = '1'
    logger.info("[AI_Premium] 🔧 Режим разработки активирован")
    
    # Сбрасываем загрузчик для переинициализации
    global _loader
    _loader = None

