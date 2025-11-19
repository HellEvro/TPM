/**
 * Toast Notification System
 * Красивые всплывающие уведомления справа снизу
 */

class ToastManager {
    constructor() {
        this.container = null;
        this.toasts = new Map();
        this.toastCounter = 0;
        this.init();
    }

    init() {
        // Если контейнер уже существует, не создаем новый
        if (this.container && document.body.contains(this.container)) {
            console.log('[ToastManager] ℹ️ Контейнер уже инициализирован');
            return;
        }
        
        // Создаем контейнер для toast уведомлений
        this.container = document.createElement('div');
        this.container.className = 'toast-container';
        this.container.id = 'toast-container';
        
        // Проверяем, что document.body существует
        if (document.body) {
            document.body.appendChild(this.container);
            console.log('[ToastManager] ✅ Контейнер добавлен в DOM');
        } else {
            // Если body еще не готов, ждем DOMContentLoaded
            console.log('[ToastManager] ⏳ Ожидание DOMContentLoaded...');
            const initContainer = () => {
                if (document.body) {
                    document.body.appendChild(this.container);
                    console.log('[ToastManager] ✅ Контейнер добавлен в DOM (после DOMContentLoaded)');
                } else {
                    console.error('[ToastManager] ❌ document.body все еще не доступен!');
                }
            };
            
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', initContainer);
            } else {
                // DOM уже загружен
                initContainer();
            }
        }
    }

    show(message, type = 'info', duration = 5000) {
        // Проверяем и инициализируем контейнер, если нужно
        if (!this.container) {
            console.warn('[ToastManager] ⚠️ Контейнер не инициализирован, инициализируем...');
            this.init();
        }
        
        // Проверяем, что контейнер в DOM
        if (!document.body.contains(this.container)) {
            console.warn('[ToastManager] ⚠️ Контейнер не в DOM, добавляем...');
            if (document.body) {
                document.body.appendChild(this.container);
            } else {
                console.error('[ToastManager] ❌ document.body не доступен!');
                return null;
            }
        }
        
        const toastId = ++this.toastCounter;
        
        // Создаем элемент toast
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <div class="toast-icon"></div>
            <div class="toast-message">${this.escapeHtml(message)}</div>
            <div class="toast-progress" style="transition-duration: ${duration}ms"></div>
        `;

        // Добавляем toast в контейнер
        this.container.appendChild(toast);
        this.toasts.set(toastId, toast);
        
        // Принудительно устанавливаем стили контейнера
        this.container.style.position = 'fixed';
        this.container.style.top = '20px';
        this.container.style.right = '20px';
        this.container.style.zIndex = '999999';
        this.container.style.display = 'flex';
        this.container.style.visibility = 'visible';

        // Анимация появления - сразу показываем
        requestAnimationFrame(() => {
            toast.classList.add('show');
            // Принудительно устанавливаем стили для видимости
            toast.style.opacity = '1';
            toast.style.transform = 'translateX(0)';
            toast.style.visibility = 'visible';
            toast.style.zIndex = '999999';
        });

        // Запускаем прогресс-бар
        setTimeout(() => {
            const progress = toast.querySelector('.toast-progress');
            if (progress) {
                progress.style.transform = 'scaleX(0)';
            }
        }, 50);

        // Автозакрытие
        if (duration > 0) {
            setTimeout(() => {
                this.hide(toastId);
            }, duration);
        }

        // Клик для закрытия
        toast.addEventListener('click', () => {
            this.hide(toastId);
        });

        return toastId;
    }

    hide(toastId) {
        const toast = this.toasts.get(toastId);
        if (!toast) return;

        toast.classList.remove('show');
        toast.classList.add('hide');

        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
            this.toasts.delete(toastId);
        }, 300);
    }

    // Методы для разных типов уведомлений
    success(message, duration = 4000) {
        return this.show(message, 'success', duration);
    }

    error(message, duration = 6000) {
        return this.show(message, 'error', duration);
    }

    warning(message, duration = 5000) {
        return this.show(message, 'warning', duration);
    }

    info(message, duration = 4000) {
        return this.show(message, 'info', duration);
    }

    // Очистить все уведомления
    clear() {
        this.toasts.forEach((toast, id) => {
            this.hide(id);
        });
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Создаем глобальный экземпляр
window.toastManager = new ToastManager();

// Совместимость с старым API
window.notifications = {
    show: (message, type) => window.toastManager.show(message, type)
};
