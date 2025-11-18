class StatisticsManager {
    constructor() {
        Logger.info('STATS', 'Initializing StatisticsManager');
        
        // Подписываемся на изменения состояния
        this.unsubscribers = [
            stateManager.subscribe('app.theme', this.handleThemeChange.bind(this)),
            stateManager.subscribe('positions.data', this.handlePositionsUpdate.bind(this))
        ];

        // Инициализируем состояние для RSI
        const state = stateManager.getState('statistics');
        this.chartData = {
            labels: state?.chartData?.labels || [],
            values: state?.chartData?.values || []
        };
        
        this.chartId = `chart_${Math.random().toString(36).substr(2, 9)}`;
        this.chart = null;
        this.isFirstUpdate = true;
        this.currentSymbol = null;
        this.rsiUpdateInterval = null;

        // Сохраняем начальное состояние
        stateManager.setState('statistics.chartData', this.chartData);
        stateManager.setState('statistics.isLoading', false);

        // Инициализируем график только если мы на странице позиций
        if (document.querySelector('.positions-container')) {
            requestAnimationFrame(() => this.initializeChart());
            // Загружаем RSI при инициализации
            this.loadRSIData();
            // Устанавливаем периодическое обновление RSI (каждые 5 минут)
            this.rsiUpdateInterval = setInterval(() => this.loadRSIData(), 5 * 60 * 1000);
        }
    }

    handlePositionsUpdate(data) {
        if (data?.stats) {
            this.updateStats(data.stats);
            // При обновлении позиций обновляем RSI для первого символа
            this.loadRSIData();
        }
    }

    handleThemeChange(newTheme) {
        Logger.debug('STATS', `Theme changed to: ${newTheme}`);
        this.updateChartTheme(newTheme);
    }

    async loadRSIData() {
        try {
            // Получаем первую позицию для отображения RSI
            const positionsData = stateManager.getState('positions.data');
            let symbol = 'BTC'; // По умолчанию используем BTC
            
            if (positionsData) {
                const allPositions = [
                    ...(positionsData.high_profitable || []),
                    ...(positionsData.profitable || []),
                    ...(positionsData.losing || [])
                ];
                
                if (allPositions.length > 0) {
                    // Берем первую позицию
                    const firstPosition = allPositions[0];
                    symbol = firstPosition.symbol || 'BTC';
                    // Убираем USDT если есть
                    symbol = symbol.replace('USDT', '');
                }
            }
            
            this.currentSymbol = symbol;
            
            // Загружаем RSI данные
            const response = await fetch(`/api/rsi_6h/${symbol}`);
            if (!response.ok) {
                Logger.warn('STATS', `Failed to load RSI data for ${symbol}`);
                return;
            }
            
            const data = await response.json();
            if (data.success && data.rsi_values) {
                this.updateRSIChart(data.rsi_values, data.timestamps || []);
            }
        } catch (error) {
            Logger.error('STATS', 'Error loading RSI data:', error);
        }
    }

    updateStats(stats) {
        try {
            Logger.debug('STATS', 'Updating statistics:', stats);
            stateManager.setState('statistics.isUpdating', true);

            // Обновляем значения статистики
            this.updateStatValues(stats);

            stateManager.setState('statistics.lastUpdate', new Date().toISOString());
            stateManager.setState('statistics.data', stats);

        } catch (error) {
            Logger.error('STATS', 'Error updating statistics:', error);
            stateManager.setState('statistics.error', error.message);
        } finally {
            stateManager.setState('statistics.isUpdating', false);
        }
    }

    updateStatValues(stats) {
        const updates = {
            'total-pnl': { value: stats.total_pnl, useSign: true },
            'total-profit': { value: stats.total_profit },
            'total-loss': { value: stats.total_loss },
            'total-trades': { value: stats.total_trades },
            'total-high-profitable': { value: stats.high_profitable_count },
            'total-all-profitable': { value: stats.profitable_count },
            'total-losing': { value: stats.losing_count }
        };

        Object.entries(updates).forEach(([elementId, { value, useSign }]) => {
            this.updateStatValue(elementId, value, useSign);
        });
    }

    updateStatValue(elementId, value, useSign = false) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const isTradeCount = [
            'total-trades',
            'total-high-profitable',
            'total-all-profitable',
            'total-losing'
        ].includes(elementId);

        element.textContent = isTradeCount ? 
            Math.round(value) : 
            `${formatUtils.formatNumber(value)} USDT`;

        if (useSign) {
            element.className = `stats-value ${value >= 0 ? 'positive' : 'negative'}`;
        }
    }

    updateRSIChart(rsiValues, timestamps) {
        if (!this.chart) {
            Logger.warn('STATS', 'Chart not initialized');
            return;
        }

        try {
            // Форматируем временные метки для отображения
            const labels = timestamps.length > 0 
                ? timestamps.map(ts => {
                    const date = new Date(ts);
                    return formatUtils.formatTime(date);
                })
                : rsiValues.map((_, i) => `Candle ${i + 1}`);
            
            // Обновляем данные графика
            this.chartData.labels = labels.slice(-56); // Последние 56 свечей
            this.chartData.values = rsiValues.slice(-56);
            
            // Обновляем данные графика RSI
            this.chart.data.labels = this.chartData.labels;
            this.chart.data.datasets[0].data = this.chartData.values;
            
            // Обновляем линии границ
            const numPoints = this.chartData.labels.length;
            if (this.chart.data.datasets.length > 1) {
                // Верхняя красная граница (80)
                this.chart.data.datasets[1].data = new Array(numPoints).fill(80);
                // Нижняя зеленая граница (20)
                this.chart.data.datasets[2].data = new Array(numPoints).fill(20);
                // Центральная серая прерывистая (50)
                this.chart.data.datasets[3].data = new Array(numPoints).fill(50);
            }
            
            this.updateChartTheme(stateManager.getState('app.theme'));

            stateManager.setState('statistics.chartData', this.chartData);

            requestAnimationFrame(() => this.chart.update());
        } catch (error) {
            Logger.error('STATS', 'Error updating RSI chart:', error);
        }
    }

    updateChartTheme(theme) {
        if (!this.chart) return;

        try {
            const isDark = theme !== 'light';
            
            // Цвет линии RSI
            this.chart.data.datasets[0].borderColor = isDark ? '#00ff00' : '#1f77b4';
            this.chart.data.datasets[0].backgroundColor = this.hexToRgba(
                isDark ? '#00ff00' : '#1f77b4',
                0.1
            );

            // Обновляем цвет сетки и осей
            const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
            this.chart.options.scales.y.grid.color = gridColor;
            
            // Обновляем цвет линий границ
            if (this.chart.data.datasets.length > 1) {
                // Верхняя красная граница (80)
                this.chart.data.datasets[1].borderColor = '#ff0000';
                // Нижняя зеленая граница (20)
                this.chart.data.datasets[2].borderColor = '#00ff00';
                // Центральная серая прерывистая (50)
                this.chart.data.datasets[3].borderColor = isDark ? '#888888' : '#666666';
            }

            this.chart.update();
        } catch (error) {
            Logger.error('STATS', 'Error updating chart theme:', error);
        }
    }

    destroy() {
        // Отписываемся от всех подписок
        this.unsubscribers.forEach(unsubscribe => unsubscribe());
        
        // Останавливаем периодическое обновление RSI
        if (this.rsiUpdateInterval) {
            clearInterval(this.rsiUpdateInterval);
            this.rsiUpdateInterval = null;
        }
        
        // Уничтожаем график
        this.destroyChart();
        
        // Очищаем данные
        this.chartData = { labels: [], values: [] };
        stateManager.setState('statistics.chartData', this.chartData);
    }

    destroyChart() {
        Logger.info('STATS', 'Destroying chart');
        if (this.chart) {
            try {
                this.chart.destroy();
                this.chart = null;
                
                if (Chart.getChart(this.chartId)) {
                    Chart.getChart(this.chartId).destroy();
                }
            } catch (error) {
                Logger.error('STATS', 'Error destroying chart:', error);
            }
        }
    }

    initializeChart() {
        try {
            Logger.info('STATS', 'Initializing RSI 6h chart');
            this.destroyChart();

            const ctx = document.getElementById('pnlChart');
            if (!ctx) {
                Logger.warn('STATS', 'Chart canvas not found');
                return;
            }

            const theme = stateManager.getState('app.theme') || 'dark';
            const isDark = theme !== 'light';
            const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';

            // Подготавливаем данные для линий границ
            const labels = this.chartData.labels.length > 0 ? this.chartData.labels : ['', '', ''];
            const boundaryValues = labels.map(() => 80); // Верхняя граница 80
            const lowerBoundaryValues = labels.map(() => 20); // Нижняя граница 20
            const centerBoundaryValues = labels.map(() => 50); // Центральная граница 50

            this.chart = new Chart(ctx, {
                id: this.chartId,
                type: 'line',
                data: {
                    labels: this.chartData.labels,
                    datasets: [
                        {
                            label: 'RSI 6h',
                            data: this.chartData.values,
                            borderColor: isDark ? '#00ff00' : '#1f77b4',
                            backgroundColor: this.hexToRgba(isDark ? '#00ff00' : '#1f77b4', 0.1),
                            fill: false,
                            tension: 0.4,
                            pointRadius: 0,
                            pointHoverRadius: 3
                        },
                        {
                            label: 'Верхняя граница (80)',
                            data: boundaryValues,
                            borderColor: '#ff0000',
                            backgroundColor: 'transparent',
                            fill: false,
                            borderWidth: 2,
                            pointRadius: 0,
                            borderDash: [] // Сплошная линия
                        },
                        {
                            label: 'Нижняя граница (20)',
                            data: lowerBoundaryValues,
                            borderColor: '#00ff00',
                            backgroundColor: 'transparent',
                            fill: false,
                            borderWidth: 2,
                            pointRadius: 0,
                            borderDash: [] // Сплошная линия
                        },
                        {
                            label: 'Центральная линия (50)',
                            data: centerBoundaryValues,
                            borderColor: isDark ? '#888888' : '#666666',
                            backgroundColor: 'transparent',
                            fill: false,
                            borderWidth: 1,
                            pointRadius: 0,
                            borderDash: [5, 5] // Прерывистая линия
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: false,
                    scales: {
                        y: {
                            beginAtZero: false,
                            min: 0,
                            max: 100,
                            grid: {
                                color: gridColor
                            },
                            ticks: {
                                stepSize: 20
                            }
                        },
                        x: {
                            grid: {
                                display: false
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            enabled: true,
                            callbacks: {
                                label: function(context) {
                                    if (context.datasetIndex === 0) {
                                        return `RSI: ${context.parsed.y.toFixed(2)}`;
                                    }
                                    return context.dataset.label + ': ' + context.parsed.y;
                                }
                            }
                        }
                    }
                }
            });

            Logger.info('STATS', 'RSI 6h chart initialized successfully');
        } catch (error) {
            Logger.error('STATS', 'Error initializing RSI chart:', error);
            NotificationManager.error('Error initializing RSI chart');
        }
    }

    hexToRgba(hex, alpha) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }
}

// Экспортируем класс
window.StatisticsManager = StatisticsManager; 