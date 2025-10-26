"""
Типы и возможности лицензий для InfoBot AI Premium
"""


class LicenseType:
    """Типы лицензий"""
    
    TRIAL = 'trial'           # Пробная версия (7 дней)
    MONTHLY = 'monthly'       # Месячная подписка
    YEARLY = 'yearly'         # Годовая подписка
    LIFETIME = 'lifetime'     # Пожизненная лицензия
    DEVELOPER = 'developer'   # Для разработчиков (без ограничений)


class LicenseFeatures:
    """Возможности разных типов лицензий"""
    
    FEATURES = {
        'trial': {
            # Функции
            'anomaly_detection': True,      # Обнаружение аномалий
            'lstm_predictor': False,        # LSTM предсказания (недоступно)
            'pattern_recognition': False,   # Распознавание паттернов (недоступно)
            'risk_management': False,       # Динамический риск (недоступно)
            
            # Ограничения
            'max_bots': 3,                  # Максимум 3 бота
            'duration_days': 7,             # 7 дней
            'auto_training': False,         # Автообучение недоступно
            
            # Цена
            'price_usd': 0,                 # Бесплатно
        },
        
        'monthly': {
            # Функции
            'anomaly_detection': True,
            'lstm_predictor': True,
            'pattern_recognition': True,
            'risk_management': True,
            
            # Ограничения
            'max_bots': 20,
            'duration_days': 30,
            'auto_training': True,
            
            # Цена
            'price_usd': 29.99,
        },
        
        'yearly': {
            # Функции
            'anomaly_detection': True,
            'lstm_predictor': True,
            'pattern_recognition': True,
            'risk_management': True,
            
            # Ограничения
            'max_bots': 50,
            'duration_days': 365,
            'auto_training': True,
            
            # Цена
            'price_usd': 299.00,  # Скидка 16% (12 * 29.99 = 359.88)
        },
        
        'lifetime': {
            # Функции
            'anomaly_detection': True,
            'lstm_predictor': True,
            'pattern_recognition': True,
            'risk_management': True,
            
            # Ограничения
            'max_bots': 999,               # Без ограничений
            'duration_days': 99999,        # Пожизненно
            'auto_training': True,
            
            # Бонусы
            'priority_support': True,      # Приоритетная поддержка
            'early_access': True,          # Ранний доступ к новым функциям
            
            # Цена
            'price_usd': 999.00,
        },
        
        'developer': {
            # Функции
            'anomaly_detection': True,
            'lstm_predictor': True,
            'pattern_recognition': True,
            'risk_management': True,
            
            # Ограничения
            'max_bots': 999,
            'duration_days': 99999,
            'auto_training': True,
            
            # Специальные возможности
            'debug_mode': True,            # Отладочный режим
            'no_hardware_binding': True,   # Без привязки к железу
            'unlimited_activations': True, # Неограниченные активации
            
            # Цена
            'price_usd': 0,  # Для разработчиков бесплатно
        }
    }
    
    @classmethod
    def get_features(cls, license_type: str) -> dict:
        """
        Получает возможности для типа лицензии
        
        Args:
            license_type: Тип лицензии
        
        Returns:
            Словарь с возможностями
        """
        return cls.FEATURES.get(license_type, cls.FEATURES['trial'])
    
    @classmethod
    def get_price(cls, license_type: str) -> float:
        """
        Получает цену для типа лицензии
        
        Args:
            license_type: Тип лицензии
        
        Returns:
            Цена в USD
        """
        features = cls.get_features(license_type)
        return features.get('price_usd', 0)
    
    @classmethod
    def is_feature_available(cls, license_type: str, feature_name: str) -> bool:
        """
        Проверяет доступность функции
        
        Args:
            license_type: Тип лицензии
            feature_name: Название функции
        
        Returns:
            True если доступна
        """
        features = cls.get_features(license_type)
        return features.get(feature_name, False)

