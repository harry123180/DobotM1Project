// WebSocket連接和實時數據更新
class ControlRoomWebSocket {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000;
        
        this.init();
    }
    
    init() {
        try {
            // 連接到Flask-SocketIO服務器
            this.socket = io('http://localhost:5000');
            this.setupEventListeners();
        } catch (error) {
            console.error('WebSocket連接失敗:', error);
            this.scheduleReconnect();
        }
    }
    
    setupEventListeners() {
        // 連接成功
        this.socket.on('connect', () => {
            console.log('✅ WebSocket連接成功');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this.updateConnectionStatus(true);
            this.addLogEntry('WebSocket連接成功', 'info');
        });
        
        // 連接斷開
        this.socket.on('disconnect', () => {
            console.log('❌ WebSocket連接斷開');
            this.isConnected = false;
            this.updateConnectionStatus(false);
            this.addLogEntry('WebSocket連接斷開', 'warning');
            this.scheduleReconnect();
        });
        
        // 接收數據更新
        this.socket.on('data_update', (data) => {
            this.updateAxisData(data.axes);
            this.updateSystemStats(data.stats);
            this.updatePLCStatus(data.plc);
        });
        
        // 接收新日誌
        this.socket.on('new_log', (logEntry) => {
            this.addLogEntry(logEntry.message, logEntry.level);
        });
        
        // 緊急停止事件
        this.socket.on('emergency_stop', (data) => {
            this.handleEmergencyStop(data.status);
        });
        
        // 緊急停止重置事件
        this.socket.on('emergency_reset', (data) => {
            this.handleEmergencyStop(false);
        });
        
        // 相機切換事件
        this.socket.on('camera_switched', (data) => {
            this.updateCameraDisplay(data.camera_id);
        });
        
        // 軸移動事件
        this.socket.on('axis_moving', (data) => {
            this.showAxisMovement(data.axis, data.position, data.speed);
        });
        
        // PLC更新事件
        this.socket.on('plc_updated', (data) => {
            this.addLogEntry(`PLC ${data.register} 更新為 ${data.value}`, 'info');
        });
        
        // 連接確認
        this.socket.on('connected', (data) => {
            console.log('服務器確認:', data.data);
        });
    }
    
    updateAxisData(axesData) {
        // 更新X軸數據
        if (axesData.x_axis) {
            const xAxis = axesData.x_axis;
            document.getElementById('xCommandPos').textContent = xAxis.command_pos;
            document.getElementById('xFeedbackPos').textContent = xAxis.feedback_pos;
            document.getElementById('xSpeed').textContent = xAxis.speed;
            this.updateAxisStatus('x_axis', xAxis.status);
        }
        
        // 更新Y軸數據
        if (axesData.y_axis) {
            const yAxis = axesData.y_axis;
            document.getElementById('yCommandPos').textContent = yAxis.command_pos;
            document.getElementById('yFeedbackPos').textContent = yAxis.feedback_pos;
            document.getElementById('ySpeed').textContent = yAxis.speed;
            this.updateAxisStatus('y_axis', yAxis.status);
        }
        
        // 更新Z軸數據
        if (axesData.z_axis) {
            const zAxis = axesData.z_axis;
            document.getElementById('zCommandPos').textContent = zAxis.command_pos;
            document.getElementById('zFeedbackPos').textContent = zAxis.feedback_pos;
            document.getElementById('zSpeed').textContent = zAxis.speed;
            this.updateAxisStatus('z_axis', zAxis.status);
        }
    }
    
    updateSystemStats(stats) {
        if (stats.total_operations) {
            document.getElementById('totalOperations').textContent = stats.total_operations.toLocaleString();
        }
        if (stats.success_rate) {
            document.getElementById('successRate').textContent = stats.success_rate + '%';
        }
        if (stats.avg_cycle_time) {
            document.getElementById('avgCycleTime').textContent = stats.avg_cycle_time + 's';
        }
        if (stats.temperature) {
            document.getElementById('temperature').textContent = stats.temperature + '°C';
        }
        if (stats.pressure) {
            document.getElementById('pressure').textContent = stats.pressure + 'bar';
        }
        if (stats.cpu_usage) {
            document.getElementById('cpuUsage').textContent = stats.cpu_usage + '%';
        }
    }
    
    updatePLCStatus(plcData) {
        if (plcData.z_son !== undefined) {
            document.getElementById('zSon').textContent = plcData.z_son ? 'ON' : 'OFF';
        }
        if (plcData.z_emg !== undefined) {
            document.getElementById('zEmg').textContent = plcData.z_emg ? 'ON' : 'OFF';
        }
        if (plcData.z_dog !== undefined) {
            document.getElementById('zDog').textContent = plcData.z_dog ? 'ON' : 'OFF';
        }
        if (plcData.z_done !== undefined) {
            document.getElementById('zDone').textContent = plcData.z_done ? 'TRUE' : 'FALSE';
        }
    }
    
    updateAxisStatus(axisName, status) {
        const statusMap = {
            'ready': 'status-ready',
            'moving': 'status-moving',
            'error': 'status-error',
            'emergency_stop': 'status-error',
            'idle': 'status-idle'
        };
        
        // 找到對應的狀態指示器並更新
        const axisCard = document.querySelector(`[data-axis="${axisName}"]`);
        if (axisCard) {
            const indicator = axisCard.querySelector('.status-indicator');
            if (indicator) {
                // 移除所有狀態類別
                Object.values(statusMap).forEach(cls => indicator.classList.remove(cls));
                // 添加新的狀態類別
                indicator.classList.add(statusMap[status] || 'status-idle');
            }
        }
    }
    
    updateConnectionStatus(connected) {
        const connectionDot = document.querySelector('.connection-dot');
        const statusText = document.querySelector('.network-status span');
        
        if (connected) {
            connectionDot.style.backgroundColor = '#10b981';
            statusText.textContent = 'EtherCAT: 連線正常';
        } else {
            connectionDot.style.backgroundColor = '#ef4444';
            statusText.textContent = 'EtherCAT: 連線中斷';
        }
    }
    
    addLogEntry(message, level = 'info') {
        const logContainer = document.getElementById('systemLog');
        const time = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry log-${level}`;
        logEntry.innerHTML = `<span class="log-time">[${time}]</span> ${message}`;
        
        logContainer.insertBefore(logEntry, logContainer.firstChild);
        
        // 保持最多50條記錄
        if (logContainer.children.length > 50) {
            logContainer.removeChild(logContainer.lastChild);
        }
    }
    
    handleEmergencyStop(isActive) {
        const emergencyBtn = document.querySelector('.emergency-stop');
        if (isActive) {
            emergencyBtn.style.background = 'linear-gradient(135deg, #7f1d1d 0%, #991b1b 100%)';
            emergencyBtn.textContent = '🔴 緊急停止已啟動';
            emergencyBtn.onclick = () => this.resetEmergencyStop();
            this.addLogEntry('緊急停止已啟動！', 'error');
        } else {
            emergencyBtn.style.background = 'linear-gradient(135deg, #dc2626 0%, #ef4444 100%)';
            emergencyBtn.textContent = '🛑 緊急停止';
            emergencyBtn.onclick = () => window.emergencyStop();
            this.addLogEntry('緊急停止已解除', 'info');
        }
    }
    
    updateCameraDisplay(cameraId) {
        this.addLogEntry(`切換到相機 ${cameraId}`, 'info');
        
        // 更新相機按鈕狀態
        document.querySelectorAll('.control-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        // 高亮當前選中的相機按鈕
        const currentBtn = document.querySelector(`[onclick="switchCamera(${cameraId})"]`);
        if (currentBtn) {
            currentBtn.classList.add('active');
        }
    }
    
    showAxisMovement(axis, position, speed) {
        this.addLogEntry(`${axis.toUpperCase()}軸移動到位置 ${position}，速度 ${speed}`, 'info');
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`嘗試重新連接 (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            this.addLogEntry(`嘗試重新連接 (${this.reconnectAttempts}/${this.maxReconnectAttempts})`, 'warning');
            
            setTimeout(() => {
                this.init();
            }, this.reconnectDelay);
        } else {
            console.error('超過最大重連次數，請檢查網路連接');
            this.addLogEntry('WebSocket連接失敗，請檢查網路', 'error');
        }
    }
    
    // API調用方法
    async callAPI(endpoint, method = 'GET', data = null) {
        try {
            const options = {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                }
            };
            
            if (data) {
                options.body = JSON.stringify(data);
            }
            
            const response = await fetch(`http://localhost:5000/api${endpoint}`, options);
            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.message || `HTTP ${response.status}`);
            }
            
            return result;
        } catch (error) {
            console.error('API調用失敗:', error);
            this.addLogEntry(`API調用失敗: ${endpoint} - ${error.message}`, 'error');
            return null;
        }
    }
    
    // 軸移動控制
    async moveAxis(axisName, position, speed = 100) {
        const result = await this.callAPI(`/axis/${axisName}/move`, 'POST', {
            position: position,
            speed: speed
        });
        
        if (result && result.status === 'success') {
            this.addLogEntry(result.message, 'info');
        }
        return result;
    }
    
    // 緊急停止
    async triggerEmergencyStop() {
        const result = await this.callAPI('/emergency_stop', 'POST');
        if (result && result.status === 'success') {
            this.addLogEntry(result.message, 'error');
        }
        return result;
    }
    
    // 重置緊急停止
    async resetEmergencyStop() {
        if (confirm('確定要重置緊急停止嗎？')) {
            const result = await this.callAPI('/reset_emergency', 'POST');
            if (result && result.status === 'success') {
                this.addLogEntry(result.message, 'info');
            }
            return result;
        }
    }
    
    // 切換相機
    async switchCamera(cameraId) {
        const result = await this.callAPI(`/camera/switch/${cameraId}`, 'POST');
        if (result && result.status === 'success') {
            this.addLogEntry(`相機切換到 ${cameraId}`, 'info');
        }
        return result;
    }
    
    // PLC寫入
    async writePLC(register, value) {
        const result = await this.callAPI('/plc/write', 'POST', {
            register: register,
            value: value
        });
        
        if (result && result.status === 'success') {
            this.addLogEntry(result.message, 'info');
        }
        return result;
    }
    
    // 獲取系統狀態
    async getSystemStatus() {
        const result = await this.callAPI('/status');
        return result;
    }
    
    // 心跳檢測
    startHeartbeat() {
        setInterval(() => {
            if (this.isConnected) {
                this.socket.emit('heartbeat', { timestamp: Date.now() });
            }
        }, 30000); // 每30秒發送一次心跳
    }
}

// 全局變數
let wsClient;

// 頁面載入完成後初始化
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 初始化戰情室系統...');
    
    // 初始化WebSocket客戶端
    wsClient = new ControlRoomWebSocket();
    
    // 啟動心跳檢測
    wsClient.startHeartbeat();
    
    // 將WebSocket客戶端設為全局變數
    window.wsClient = wsClient;
    
    // 重新定義全局函數以使用WebSocket客戶端
    window.switchCamera = function(cameraId) {
        if (wsClient && wsClient.isConnected) {
            wsClient.switchCamera(cameraId);
        } else {
            console.log('WebSocket未連接，使用本地處理');
            // 本地處理相機切換
            document.querySelectorAll('.control-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');
            addLogEntry(`切換到相機 ${cameraId}`, 'info');
        }
    };
    
    window.emergencyStop = function() {
        if (confirm('確定要執行緊急停止嗎？')) {
            if (wsClient && wsClient.isConnected) {
                wsClient.triggerEmergencyStop();
            } else {
                console.log('WebSocket未連接，使用本地處理');
                addLogEntry('緊急停止已啟動！', 'error');
            }
        }
    };
    
    // 添加鍵盤快捷鍵
    document.addEventListener('keydown', function(event) {
        // ESC鍵 - 緊急停止
        if (event.key === 'Escape') {
            event.preventDefault();
            window.emergencyStop();
        }
        
        // F1-F4 - 相機切換
        if (event.key >= 'F1' && event.key <= 'F4') {
            event.preventDefault();
            const cameraId = parseInt(event.key.replace('F', ''));
            window.switchCamera(cameraId);
        }
        
        // Ctrl+R - 重置緊急停止
        if (event.ctrlKey && event.key === 'r') {
            event.preventDefault();
            if (wsClient) {
                wsClient.resetEmergencyStop();
            }
        }
    });
    
    console.log('✅ 系統初始化完成');
    console.log('📋 快捷鍵說明:');
    console.log('   ESC - 緊急停止');
    console.log('   F1-F4 - 相機切換');
    console.log('   Ctrl+R - 重置緊急停止');
});

// 手動軸移動函數（可在控制台中使用）
window.moveAxisManual = function(axis, position, speed = 100) {
    if (wsClient && wsClient.isConnected) {
        return wsClient.moveAxis(axis, position, speed);
    } else {
        console.log('WebSocket未連接');
        return null;
    }
};

// 獲取系統狀態
window.getSystemStatus = async function() {
    if (wsClient && wsClient.isConnected) {
        const status = await wsClient.getSystemStatus();
        console.log('系統狀態:', status);
        return status;
    } else {
        console.log('WebSocket未連接');
        return null;
    }
};

// PLC控制函數
window.writePLC = function(register, value) {
    if (wsClient && wsClient.isConnected) {
        return wsClient.writePLC(register, value);
    } else {
        console.log('WebSocket未連接');
        return null;
    }
};

// 重置緊急停止
window.resetEmergency = function() {
    if (wsClient && wsClient.isConnected) {
        return wsClient.resetEmergencyStop();
    } else {
        console.log('WebSocket未連接');
        return null;
    }
};

// 錯誤處理
window.addEventListener('error', function(event) {
    console.error('JavaScript錯誤:', event.error);
    if (wsClient) {
        wsClient.addLogEntry(`JavaScript錯誤: ${event.error.message}`, 'error');
    }
});

// 連線狀態檢查
window.addEventListener('online', function() {
    console.log('網路連線恢復');
    if (wsClient) {
        wsClient.addLogEntry('網路連線恢復', 'info');
    }
});

window.addEventListener('offline', function() {
    console.log('網路連線中斷');
    if (wsClient) {
        wsClient.addLogEntry('網路連線中斷', 'warning');
    }
});