/**
 * BotsManager - 04_service
 */
(function() {
    if (typeof BotsManager === 'undefined') return;
    Object.assign(BotsManager.prototype, {
            initializeBotControls() {
        console.log('[BotsManager] Инициализация кнопок управления ботом...');
        
        // Кнопки управления ботом
        const createBotBtn = document.getElementById('createBotBtn');
        console.log('[BotsManager] createBotBtn найдена:', !!createBotBtn);
        const startBotBtn = document.getElementById('startBotBtn');
        const stopBotBtn = document.getElementById('stopBotBtn');
        const pauseBotBtn = document.getElementById('pauseBotBtn');
        const resumeBotBtn = document.getElementById('resumeBotBtn');

        if (createBotBtn) {
            createBotBtn.addEventListener('click', () => this.createBot());
        }
        if (startBotBtn) {
            startBotBtn.addEventListener('click', () => this.startBot());
        }
        if (stopBotBtn) {
            stopBotBtn.addEventListener('click', () => this.stopBot());
        }
        if (pauseBotBtn) {
            pauseBotBtn.addEventListener('click', () => this.pauseBot());
        }
        if (resumeBotBtn) {
            resumeBotBtn.addEventListener('click', () => this.resumeBot());
        }

        // Обработчики для кнопок индивидуальных настроек
        this.initializeIndividualSettingsButtons();
        
        // Обработчики для кнопок быстрого запуска
        this.initializeQuickLaunchButtons();
    },
            async checkBotsService(retryCount = 0) {
        const MAX_RETRIES = 2;  // Увеличено для слабого ПК: при пиковой нагрузке (RSI, этапы 3–7) сервис может отвечать медленнее
        console.log('[BotsManager] 🔍 Проверка сервиса ботов...' + (retryCount > 0 ? ` (повтор ${retryCount}/${MAX_RETRIES})` : ''));
        console.log('[BotsManager] 🔗 URL:', `${this.BOTS_SERVICE_URL}/api/status`);
        
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 15000);
            
            const response = await fetch(`${this.BOTS_SERVICE_URL}/api/status`, {
                method: 'GET',
                signal: controller.signal,
                headers: {
                    'Accept': 'application/json'
                }
            });
            
            clearTimeout(timeoutId);
            
            if (response.ok) {
                const data = await response.json();
                this._serviceCheckFailures = 0; // Сброс счётчика при успехе
                console.log('[BotsManager] 📊 Ответ сервиса:', data);
                // bots_available: false — app.py работает, но Bots на 5001 не запущен
                this.serviceOnline = data.status === 'online' && data.bots_available !== false;
                this._service503Until = 0; // Сброс бэкоффа при успешном ответе
                
                if (this.serviceOnline) {
                    console.log('[BotsManager] ✅ Сервис ботов онлайн');
                    this.updateServiceStatus('online', 'Сервис ботов онлайн');
                    await this.loadCoinsRsiData();
                } else {
                    console.warn('[BotsManager] ⚠️ Сервис ботов недоступен (app.py работает, позиции отображаются)');
                    this.updateServiceStatus('offline', window.languageUtils?.translate?.('bot_service_unavailable') || 'Сервис ботов недоступен');
                }
            } else {
                console.error('[BotsManager] ❌ HTTP ошибка:', response.status, response.statusText);
                this._service503Until = response.status === 503 ? Date.now() + 30000 : 0;
                this._serviceCheckFailures = (this._serviceCheckFailures || 0) + 1;
                if (this._serviceCheckFailures >= 2) {
                    this.serviceOnline = false;
                    this.updateServiceStatus('offline', 'Сервис ботов недоступен');
                    this.updateCoinsCounter();
                    this.showServiceUnavailable();
                }
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
        } catch (error) {
            if (retryCount < MAX_RETRIES) {
                console.warn('[BotsManager] ⚠️ Повторная попытка через 2 сек (при пиковой нагрузке сервис может отвечать медленнее)...');
                await new Promise(r => setTimeout(r, 2000));
                return this.checkBotsService(retryCount + 1);
            }
            this._serviceCheckFailures = (this._serviceCheckFailures || 0) + 1;
            if (error.name === 'AbortError') {
                console.error('[BotsManager] ❌ Таймаут при проверке сервиса ботов (15 секунд)');
            } else if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
                console.error('[BotsManager] ❌ Ошибка сети при проверке сервиса ботов. Проверьте:');
                console.error('[BotsManager]   1. Запущен ли bots.py?');
                console.error('[BotsManager]   2. Доступен ли порт 5001?');
                console.error('[BotsManager]   3. Нет ли блокировки CORS?');
                console.error('[BotsManager]   URL:', `${this.BOTS_SERVICE_URL}/api/status`);
            } else {
                console.error('[BotsManager] ❌ Ошибка при проверке сервиса ботов:', error);
            }
            // Показываем «недоступен» и сбрасываем список только после 2 подряд неудач (убираем мигание)
            if (this._serviceCheckFailures >= 2) {
                this.serviceOnline = false;
                this.updateServiceStatus('offline', 'Сервис ботов недоступен');
                this.updateCoinsCounter();
                this.showServiceUnavailable();
            }
        }
    },
        _is503Backoff() {
        return this._service503Until && Date.now() < this._service503Until;
    },
            updateServiceStatus(status, message) {
        if (this._lastServiceStatus.status === status && this._lastServiceStatus.message === message) {
            return;
        }
        this._lastServiceStatus = { status, message };
        
        const statusElement = document.getElementById('botsServiceStatus');
        const statusDot = document.getElementById('rsiStatusDot');
        
        if (statusElement) {
            const indicator = statusElement.querySelector('.status-indicator');
            const text = statusElement.querySelector('.status-text');
            
            if (indicator) {
                indicator.className = `status-indicator ${status}`;
                indicator.textContent = status === 'online' ? '🟢' : '🔴';
            }
            
            if (text) {
                text.textContent = message;
            }
        }
        
        if (statusDot) {
            statusDot.style.color = status === 'online' ? '#4caf50' : '#f44336';
        }
    },
            showServiceUnavailable() {
        const coinsListElement = document.getElementById('coinsRsiList');
        if (coinsListElement) {
            coinsListElement.innerHTML = `
                <div class="service-unavailable">
                    <h3>🚫 ${window.languageUtils.translate('bot_service_unavailable')}</h3>
                    <p>${window.languageUtils.translate('bot_service_launch_instruction')}</p>
                    <code>python bots.py</code>
                    <p>${window.languageUtils.translate('bot_service_port_instruction')}</p>
                </div>
            `;
        }
    },
            async loadCoinsRsiData(forceUpdate = false) {
        if (!this.serviceOnline) {
            console.warn('[BotsManager] ⚠️ Сервис не онлайн, пропускаем загрузку');
            return;
        }

        // Получаем текущий таймфрейм для логирования
        const currentTimeframe = this.currentTimeframe || document.getElementById('systemTimeframe')?.value || '6h';
        this.logDebug(`[BotsManager] 📊 Загрузка данных RSI ${currentTimeframe.toUpperCase()}...`);
        
        // Сохраняем текущее состояние поиска
        const searchInput = document.getElementById('coinSearchInput');
        const currentSearchTerm = searchInput ? searchInput.value : '';
        
        try {
            const response = await fetch(`${this.BOTS_SERVICE_URL}/api/bots/coins-with-rsi`);
            
            if (response.status === 503 || response.status === 504) {
                let retryAfterSec = response.status === 504 ? 8 : 5;
                if (response.status === 503) {
                    try {
                        const body = await response.json();
                        if (body && typeof body.retry_after === 'number') retryAfterSec = Math.max(2, body.retry_after);
                    } catch (_) {}
                }
                const reason = response.status === 504 ? 'таймаут (504)' : 'сервер занят (503)';
                this.logDebug('[BotsManager] ⏳ coins-with-rsi: ' + reason + ', повтор через ' + retryAfterSec + ' сек');
                this.updateServiceStatus('online', (response.status === 504 ? 'Таймаут загрузки. Повтор через ' + retryAfterSec + ' сек…' : ((window.languageUtils && window.languageUtils.translate('rsi_update_wait')) ? window.languageUtils.translate('rsi_update_wait') : 'Обновление RSI… повтор через ' + retryAfterSec + ' сек')));
                if (!this._coinsRetryTimer) {
                    this._coinsRetryTimer = setTimeout(() => {
                        this._coinsRetryTimer = null;
                        this.loadCoinsRsiData(forceUpdate);
                    }, retryAfterSec * 1000);
                }
                return;
            }
            if (response.ok) {
            const data = await response.json();
            if (this._coinsRetryTimer) {
                clearTimeout(this._coinsRetryTimer);
                this._coinsRetryTimer = null;
            }
            if (data.success) {
                    // Всегда обновляем UI по ответу сервера — RSI и цены меняются, пользователь должен видеть актуальные данные
                    const currentDataVersion = data.data_version || 0;
                    this.lastDataVersion = currentDataVersion;
                    
                    // Сохраняем флаг загрузки и статистику для отображения при пустом списке
                    this.lastUpdateInProgress = !!data.update_in_progress;
                    this.lastRsiStats = data.stats || null;
                    
                    // Преобразуем словарь в массив для совместимости с UI; гарантируем symbol у каждой монеты (ключ = symbol)
                    this.logDebug('[BotsManager] 🔍 Данные от API:', data);
                    this.logDebug('[BotsManager] 🔍 Ключи coins:', Object.keys(data.coins));
                    const coinsObj = data.coins || {};
                    this.coinsRsiData = Object.entries(coinsObj).map(([sym, coin]) => ({
                        ...coin,
                        symbol: (coin && coin.symbol) ? coin.symbol : sym
                    }));
                    
                    // Лог уровня info: видно без включения debug (чтобы понимать, что данные пришли)
                    console.log('[BotsManager] ✅ Загружено', this.coinsRsiData.length, 'монет с RSI');
                    
                    // Получаем список ручных позиций
                    const manualPositions = data.manual_positions || [];
                    this.logDebug(`[BotsManager] ✋ Ручные позиции получены:`, manualPositions);
                    this.logDebug(`[BotsManager] ✋ Всего ручных позиций: ${manualPositions.length}`);
                    
                    // Помечаем монеты с ручными позициями
                    let markedCount = 0;
                    this.coinsRsiData.forEach(coin => {
                        coin.manual_position = manualPositions.includes(coin.symbol);
                        if (coin.manual_position) {
                            markedCount++;
                            this.logDebug(`[BotsManager] ✋ Монета ${coin.symbol} помечена как ручная позиция`);
                        }
                    });
                    
                    // Загружаем список зрелых монет и помечаем их
                    await this.loadMatureCoinsAndMark();
                    
                    this.logDebug(`[BotsManager] ✅ Загружено ${this.coinsRsiData.length} монет с RSI`);
                    this.logDebug(`[BotsManager] ✅ Помечено ${markedCount} монет с ручными позициями`);
                    this.logDebug('[BotsManager] 🔍 Первые 3 монеты:', this.coinsRsiData.slice(0, 3));
                    
                    // Обновляем интерфейс
                    this.renderCoinsList();
                    this.updateCoinsCounter();
                    // После успешной загрузки монет подтягиваем активных ботов (правая панель «Нет активных ботов»)
                    if (typeof this.loadActiveBotsData === 'function') {
                        this.loadActiveBotsData().catch(() => {});
                    }
                    // Повторно применяем текущий фильтр к новому списку (чтобы после обновления RSI/фильтров отображалась правильная выборка)
                    if (this.currentRsiFilter && this.currentRsiFilter !== 'all') {
                        this.applyRsiFilter(this.currentRsiFilter);
                    }
                    
                    // Обновляем информацию о выбранной монете
                    if (this.selectedCoin) {
                        const updatedCoin = this.coinsRsiData.find(coin => coin.symbol === this.selectedCoin.symbol);
                        if (updatedCoin) {
                            this.selectedCoin = updatedCoin;
                            this.updateCoinInfo();
                            this.renderTradesInfo(this.selectedCoin.symbol);
                        }
                    }
                    
                    // Восстанавливаем состояние поиска
                    // ✅ ИСПРАВЛЕНИЕ: Не перезаписываем значение поля (пользователь может печатать!)
                    // Берем АКТУАЛЬНОЕ значение из поля, а не сохраненное
                    const actualSearchTerm = searchInput ? searchInput.value : '';
                    if (actualSearchTerm) {
                        // Применяем фильтр к новому списку монет
                        this.filterCoins(actualSearchTerm);
                        this.updateSmartFilterControls(actualSearchTerm);
                        this.updateClearButtonVisibility(actualSearchTerm);
                    }
                    
                    // Обновляем статус: время последней загрузки и интервал из конфига («Синхронизация позиций»)
                    const updatedAt = data.response_time || data.last_update;
                    const intervalSec = Math.round(this.refreshInterval / 1000);
                    const timeStr = updatedAt ? new Date(updatedAt).toLocaleTimeString() : (window.languageUtils.translate('unknown') || '—');
                    this.updateServiceStatus('online', `${window.languageUtils.translate('updated')}: ${timeStr} (каждые ${intervalSec} сек)`);
                } else {
                    const errMsg = data.error || data.message || 'Ошибка загрузки данных';
                    throw new Error(errMsg);
                }
            } else {
                const statusText = response.statusText || '';
                throw new Error(`HTTP ${response.status}${statusText ? ': ' + statusText : ''}`);
            }
            
        } catch (error) {
            const message = (error && error.message) ? error.message : 'Ошибка загрузки данных';
            console.error('[BotsManager] ❌ Ошибка загрузки RSI данных:', error);
            this.updateServiceStatus('offline', message);
        }
    },
            async loadDelistedCoins() {
        if (!this.serviceOnline) {
            console.warn('[BotsManager] ⚠️ Сервис не онлайн, пропускаем загрузку делистинговых монет');
            return;
        }

        this.logDebug('[BotsManager] 🚨 Загрузка списка делистинговых монет...');
        
        try {
            const response = await fetch(`${this.BOTS_SERVICE_URL}/api/bots/delisted-coins`);
            
            if (response.ok) {
                const data = await response.json();
                
                if (data.success) {
                    // Обновляем список делистинговых монет
                    this.delistedCoins = Object.keys(data.delisted_coins || {});
                    
                    this.logDebug(`[BotsManager] ✅ Загружено ${this.delistedCoins.length} делистинговых монет: ${this.delistedCoins.join(', ')}`);
                    
                    // Обновляем время последнего сканирования
                    if (data.last_scan) {
                        console.log(`[BotsManager] 📅 Последнее сканирование делистинга: ${new Date(data.last_scan).toLocaleString()}`);
                    }
                } else {
                    console.warn('[BotsManager] ⚠️ Ошибка загрузки делистинговых монет:', data.error);
                }
            } else {
                console.warn(`[BotsManager] ⚠️ HTTP ${response.status} при загрузке делистинговых монет`);
            }
            
        } catch (error) {
            console.error('[BotsManager] ❌ Ошибка загрузки делистинговых монет:', error);
        }
    },
            async loadMatureCoinsCount() {
        try {
            const response = await fetch(`${this.BOTS_SERVICE_URL}/api/bots/mature-coins-list`);
            const data = await response.json();
            
            if (data.success) {
                const countEl = document.getElementById('matureCoinsCount');
                if (countEl) {
                    countEl.textContent = `(${data.total_count})`;
                }
            }
        } catch (error) {
            console.error('[BotsManager] Ошибка загрузки счётчика зрелых монет:', error);
        }
    }
    
    /**
     * Загружает список зрелых монет и помечает их в данных
     */,
            async loadMatureCoinsAndMark() {
        try {
            const response = await fetch(`${this.BOTS_SERVICE_URL}/api/bots/mature-coins-list`);
            const data = await response.json();
            
            if (data.success) {
                const enableMaturity = (this.cachedAutoBotConfig || this.autoBotConfig || {}).enable_maturity_check !== false;
                let markedCount = 0;
                this.coinsRsiData.forEach(coin => {
                    if (!enableMaturity) {
                        coin.is_mature = true; // Проверка отключена — все зрелые
                    } else if (data.mature_coins) {
                        coin.is_mature = data.mature_coins.includes(coin.symbol);
                    }
                    if (coin.is_mature) markedCount++;
                });
                
                // ✅ ИСПРАВЛЕНИЕ: Обновляем счетчик зрелых монет в UI
                await this.loadMatureCoinsCount();
                
                this.logDebug(`[BotsManager] 💎 Помечено ${markedCount} зрелых монет из ${data.total_count} общих`);
            }
        } catch (error) {
            console.error('[BotsManager] ❌ Ошибка загрузки зрелых монет:', error);
        }
    }
    
    /**
     * Показывает уведомление
     */,
                updateCoinsCounter() {
        // Обновляем счетчики для новых фильтров сигналов
        this.updateSignalCounters();
        
        // Обновляем счетчик ручных позиций
        this.updateManualPositionCounter();
    }
    
    /**
     * Обновляет счетчик ручных позиций
     */
    });
})();
