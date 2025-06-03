/**
 * Camera Control Web Application
 * 相機控制Web應用程式主腳本
 */

class CameraController {
    constructor() {
        // 初始化Socket.IO連接
        this.socket = io();
        
        // 狀態變數
        this.devices = [];
        this.currentDeviceIndex = -1;
        this.isConnected = false;
        this.isStreaming = false;
        this.currentMode = 'continuous';
        
        // 初始化事件監聽
        this.initSocketEvents();
        this.initUIEvents();
        
        // 初始化UI狀態
        this.updateUIState();
        
        console.log('Camera Controller initialized');
    }

    /**
     * 初始化Socket.IO事件監聽
     */
    initSocketEvents() {
        // 連接事件
        this.socket.on('connect', () => {
            this.addLogEntry('已連接到伺服器', 'success');
            this.hideLoading();
        });

        this.socket.on('disconnect', () => {
            this.addLogEntry('與伺服器斷開連接', 'error');
            this.showLoading('正在重連...');
        });

        // 狀態更新事件
        this.socket.on('status_update', (data) => {
            this.handleStatusUpdate(data);
        });

        // 設備列表更新事件
        this.socket.on('devices_list', (data) => {
            this.handleDevicesListUpdate(data);
        });

        // 參數更新事件
        this.socket.on('parameters_updated', (data) => {
            this.handleParametersUpdate(data);
        });

        // 日誌訊息事件
        this.socket.on('log_message', (data) => {
            this.addLogEntry(data.message, data.level);
        });

        // 圖像保存結果事件
        this.socket.on('image_saved', (data) => {
            this.handleImageSaveResult(data);
        });
    }

    /**
     * 初始化UI事件監聽
     */
    initUIEvents() {
        // 設備控制
        document.getElementById('refresh-devices-btn').addEventListener('click', () => {
            this.refreshDevices();
        });

        document.getElementById('device-select').addEventListener('change', (e) => {
            this.currentDeviceIndex = parseInt(e.target.value);
        });

        // 連接控制
        document.getElementById('connect-btn').addEventListener('click', () => {
            this.connectDevice();
        });

        document.getElementById('disconnect-btn').addEventListener('click', () => {
            this.disconnectDevice();
        });

        document.getElementById('reset-connection-btn').addEventListener('click', () => {
            this.resetConnection();
        });

        document.getElementById('optimize-packet-btn').addEventListener('click', () => {
            this.optimizePacketSize();
        });

        // 參數控制
        document.getElementById('get-params-btn').addEventListener('click', () => {
            this.getParameters();
        });

        document.getElementById('set-params-btn').addEventListener('click', () => {
            this.setParameters();
        });

        // 模式控制
        document.querySelectorAll('input[name="mode"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                if (e.target.checked) {
                    this.setMode(e.target.value);
                }
            });
        });

        // 串流控制
        document.getElementById('start-stream-btn').addEventListener('click', () => {
            this.startStreaming();
        });

        document.getElementById('stop-stream-btn').addEventListener('click', () => {
            this.stopStreaming();
        });

        // 觸發控制
        document.getElementById('software-trigger-btn').addEventListener('click', () => {
            this.softwareTrigger();
        });

        document.getElementById('reset-trigger-btn').addEventListener('click', () => {
            this.resetTriggerCount();
        });

        // 圖像保存
        document.getElementById('save-image-btn').addEventListener('click', () => {
            this.saveImage();
        });

        // 日誌清除
        document.getElementById('clear-log-btn').addEventListener('click', () => {
            this.clearLog();
        });

        // 防止表單提交
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && e.target.tagName === 'INPUT') {
                e.preventDefault();
            }
        });
    }

    /**
     * 處理狀態更新
     */
    handleStatusUpdate(data) {
        // 更新連接狀態
        this.isConnected = data.is_connected;
        this.isStreaming = data.is_streaming;
        this.currentMode = data.current_mode;

        // 更新UI顯示
        this.updateConnectionStatus(data.connection_status);
        this.updateStreamStatus(data.is_streaming);
        this.updateModeStatus(data.current_mode);
        this.updateDeviceInfo(data.device_info);
        this.updateCounts(data.trigger_count, data.save_count);
        
        // 更新UI狀態
        this.updateUIState();
    }

    /**
     * 處理設備列表更新
     */
    handleDevicesListUpdate(data) {
        this.devices = data.devices;
        const select = document.getElementById('device-select');
        
        // 清空現有選項
        select.innerHTML = '';
        
        if (this.devices.length === 0) {
            select.innerHTML = '<option value="">未找到設備</option>';
            select.disabled = true;
        } else {
            select.innerHTML = '<option value="">請選擇設備</option>';
            this.devices.forEach(device => {
                const option = document.createElement('option');
                option.value = device.index;
                option.textContent = device.display_name;
                select.appendChild(option);
            });
            select.disabled = false;
        }
        
        this.hideLoading();
    }

    /**
     * 處理圖像保存結果
     */
    handleImageSaveResult(data) {
        const saveStatus = document.getElementById('save-status');
        const saveMessage = saveStatus.querySelector('.save-message');
        const savePath = saveStatus.querySelector('.save-path');
        
        if (data.success) {
            saveStatus.className = 'save-status success';
            saveMessage.textContent = `圖像保存成功 (${data.format}) - 第 ${data.count} 張`;
            savePath.textContent = `保存路徑: ${data.path}`;
            saveStatus.style.display = 'block';
            
            // 3秒後自動隱藏成功訊息
            setTimeout(() => {
                saveStatus.style.display = 'none';
            }, 3000);
        } else {
            saveStatus.className = 'save-status error';
            saveMessage.textContent = '圖像保存失敗';
            savePath.textContent = `錯誤: ${data.error}`;
            saveStatus.style.display = 'block';
            
            // 5秒後自動隱藏錯誤訊息
            setTimeout(() => {
                saveStatus.style.display = 'none';
            }, 5000);
        }
    }

    /**
     * 處理參數更新
     */
    handleParametersUpdate(data) {
        document.getElementById('exposure-time').value = data.exposure_time.toFixed(2);
        document.getElementById('gain').value = data.gain.toFixed(2);
        document.getElementById('frame-rate').value = data.frame_rate.toFixed(2);
    }

    /**
     * 刷新設備列表
     */
    refreshDevices() {
        this.showLoading('正在枚舉設備...');
        this.socket.emit('refresh_devices');
    }

    /**
     * 連接設備
     */
    connectDevice() {
        if (this.currentDeviceIndex < 0) {
            this.addLogEntry('請先選擇一個設備', 'warning');
            return;
        }

        this.showLoading('正在連接設備...');
        this.socket.emit('connect_device', {
            device_index: this.currentDeviceIndex
        });
    }

    /**
     * 斷開設備
     */
    disconnectDevice() {
        this.showLoading('正在斷開連接...');
        this.socket.emit('disconnect_device');
    }

    /**
     * 重置連接
     */
    resetConnection() {
        this.showLoading('正在重置連接...');
        this.socket.emit('reset_connection', {
            device_index: this.currentDeviceIndex
        });
    }

    /**
     * 優化包大小
     */
    optimizePacketSize() {
        this.socket.emit('optimize_packet_size');
    }

    /**
     * 獲取參數
     */
    getParameters() {
        this.socket.emit('get_parameters');
    }

    /**
     * 設置參數
     */
    setParameters() {
        const exposureTime = parseFloat(document.getElementById('exposure-time').value);
        const gain = parseFloat(document.getElementById('gain').value);
        const frameRate = parseFloat(document.getElementById('frame-rate').value);

        if (isNaN(exposureTime) || isNaN(gain) || isNaN(frameRate)) {
            this.addLogEntry('參數格式錯誤，請輸入有效數字', 'error');
            return;
        }

        this.socket.emit('set_parameters', {
            exposure_time: exposureTime,
            gain: gain,
            frame_rate: frameRate
        });
    }

    /**
     * 設置模式
     */
    setMode(mode) {
        this.socket.emit('set_mode', { mode: mode });
    }

    /**
     * 開始串流
     */
    startStreaming() {
        this.showLoading('正在啟動串流...');
        this.socket.emit('start_streaming');
    }

    /**
     * 停止串流
     */
    stopStreaming() {
        this.showLoading('正在停止串流...');
        this.socket.emit('stop_streaming');
    }

    /**
     * 軟觸發
     */
    softwareTrigger() {
        this.socket.emit('software_trigger');
    }

    /**
     * 重置觸發計數
     */
    resetTriggerCount() {
        this.socket.emit('reset_trigger_count');
    }

    /**
     * 保存圖像
     */
    saveImage() {
        const format = document.querySelector('input[name="image-format"]:checked').value;
        
        // 顯示保存中狀態
        const saveBtn = document.getElementById('save-image-btn');
        const originalText = saveBtn.innerHTML;
        saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 保存中...';
        saveBtn.disabled = true;
        
        // 發送保存請求
        this.socket.emit('save_image', { format: format });
        
        // 3秒後恢復按鈕狀態（防止卡住）
        setTimeout(() => {
            saveBtn.innerHTML = originalText;
            saveBtn.disabled = !this.isStreaming;
        }, 3000);
    }

    /**
     * 清除日誌
     */
    clearLog() {
        const logContainer = document.getElementById('log-container');
        logContainer.innerHTML = '';
        this.addLogEntry('日誌已清除', 'info');
    }

    /**
     * 更新連接狀態顯示
     */
    updateConnectionStatus(status) {
        const statusElement = document.getElementById('connection-status');
        statusElement.className = 'status-value';
        
        switch (status) {
            case 'connected':
                statusElement.textContent = '已連接';
                statusElement.classList.add('status-connected');
                break;
            case 'streaming':
                statusElement.textContent = '串流中';
                statusElement.classList.add('status-streaming');
                break;
            case 'disconnected':
                statusElement.textContent = '未連接';
                statusElement.classList.add('status-disconnected');
                break;
            case 'error':
                statusElement.textContent = '錯誤';
                statusElement.classList.add('status-disconnected');
                break;
            default:
                statusElement.textContent = '未知';
                statusElement.classList.add('status-disconnected');
        }
    }

    /**
     * 更新串流狀態顯示
     */
    updateStreamStatus(isStreaming) {
        const statusElement = document.getElementById('stream-status');
        statusElement.className = 'status-value';
        
        if (isStreaming) {
            statusElement.textContent = '運行中';
            statusElement.classList.add('status-connected');
        } else {
            statusElement.textContent = '已停止';
            statusElement.classList.add('status-stopped');
        }
    }

    /**
     * 更新模式狀態顯示
     */
    updateModeStatus(mode) {
        const statusElement = document.getElementById('current-mode');
        const modeText = mode === 'continuous' ? '連續模式' : '觸發模式';
        statusElement.textContent = modeText;
        
        // 更新單選按鈕狀態
        const radioButton = document.querySelector(`input[name="mode"][value="${mode}"]`);
        if (radioButton) {
            radioButton.checked = true;
        }
    }

    /**
     * 更新設備資訊顯示
     */
    updateDeviceInfo(deviceInfo) {
        if (deviceInfo) {
            document.getElementById('device-name').textContent = deviceInfo.name || '無';
            document.getElementById('device-type').textContent = deviceInfo.type || '無';
            document.getElementById('device-serial').textContent = deviceInfo.serial || '無';
            document.getElementById('device-ip').textContent = deviceInfo.ip || '無';
        } else {
            document.getElementById('device-name').textContent = '無';
            document.getElementById('device-type').textContent = '無';
            document.getElementById('device-serial').textContent = '無';
            document.getElementById('device-ip').textContent = '無';
        }
    }

    /**
     * 更新計數顯示
     */
    updateCounts(triggerCount, saveCount) {
        document.getElementById('trigger-count').textContent = triggerCount;
        document.getElementById('save-count').textContent = saveCount;
    }

    /**
     * 更新UI控件狀態
     */
    updateUIState() {
        // 連接控制按鈕
        document.getElementById('connect-btn').disabled = this.isConnected || this.currentDeviceIndex < 0;
        document.getElementById('disconnect-btn').disabled = !this.isConnected;
        document.getElementById('optimize-packet-btn').disabled = !this.isConnected;

        // 參數控制
        const paramInputs = ['exposure-time', 'gain', 'frame-rate'];
        paramInputs.forEach(id => {
            document.getElementById(id).disabled = !this.isConnected;
        });
        document.getElementById('get-params-btn').disabled = !this.isConnected;
        document.getElementById('set-params-btn').disabled = !this.isConnected;

        // 模式控制
        document.querySelectorAll('input[name="mode"]').forEach(radio => {
            radio.disabled = !this.isConnected;
        });

        // 串流控制
        document.getElementById('start-stream-btn').disabled = !this.isConnected || this.isStreaming;
        document.getElementById('stop-stream-btn').disabled = !this.isStreaming;

        // 觸發控制
        const isTriggerMode = this.currentMode === 'trigger';
        document.getElementById('software-trigger-btn').disabled = !(this.isStreaming && isTriggerMode);

        // 圖像保存
        document.getElementById('save-image-btn').disabled = !this.isStreaming;
    }

    /**
     * 添加日誌條目
     */
    addLogEntry(message, level = 'info') {
        const logContainer = document.getElementById('log-container');
        const entry = document.createElement('div');
        entry.className = `log-entry log-${level}`;
        
        const now = new Date();
        const timeStr = now.toLocaleTimeString('zh-TW', { 
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        
        entry.innerHTML = `
            <span class="log-time">[${timeStr}]</span>
            <span class="log-message">${message}</span>
        `;
        
        logContainer.appendChild(entry);
        
        // 自動滾動到底部
        logContainer.scrollTop = logContainer.scrollHeight;
        
        // 限制日誌條目數量
        const entries = logContainer.children;
        if (entries.length > 1000) {
            for (let i = 0; i < 100; i++) {
                logContainer.removeChild(entries[0]);
            }
        }
    }

    /**
     * 顯示載入遮罩
     */
    showLoading(text = '處理中...') {
        const overlay = document.getElementById('loading-overlay');
        const loadingText = document.getElementById('loading-text');
        loadingText.textContent = text;
        overlay.style.display = 'flex';
        
        // 自動隱藏（防止卡住）
        setTimeout(() => {
            this.hideLoading();
        }, 10000);
    }

    /**
     * 隱藏載入遮罩
     */
    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        overlay.style.display = 'none';
    }
}

// 頁面載入完成後初始化應用程式
document.addEventListener('DOMContentLoaded', () => {
    window.cameraController = new CameraController();
    
    // 頁面載入後自動刷新設備列表
    setTimeout(() => {
        window.cameraController.refreshDevices();
    }, 1000);
});

// 頁面卸載時清理
window.addEventListener('beforeunload', () => {
    if (window.cameraController) {
        window.cameraController.socket.disconnect();
    }
});