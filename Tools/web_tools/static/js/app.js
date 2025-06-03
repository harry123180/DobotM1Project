/**
 * Camera Control Web Application
 * 相机控制Web应用主脚本
 */

class CameraController {
    constructor() {
        // 初始化Socket.IO连接
        this.socket = io();
        
        // 状态变量
        this.devices = [];
        this.currentDeviceIndex = -1;
        this.isConnected = false;
        this.isStreaming = false;
        this.currentMode = 'continuous';
        
        // 初始化事件监听
        this.initSocketEvents();
        this.initUIEvents();
        
        // 初始化UI状态
        this.updateUIState();
        
        console.log('Camera Controller initialized');
    }

    /**
     * 初始化Socket.IO事件监听
     */
    initSocketEvents() {
        // 连接事件
        this.socket.on('connect', () => {
            this.addLogEntry('已连接到服务器', 'success');
            this.hideLoading();
        });

        this.socket.on('disconnect', () => {
            this.addLogEntry('与服务器断开连接', 'error');
            this.showLoading('正在重连...');
        });

        // 状态更新事件
        this.socket.on('status_update', (data) => {
            this.handleStatusUpdate(data);
        });

        // 设备列表更新事件
        this.socket.on('devices_list', (data) => {
            this.handleDevicesListUpdate(data);
        });

        // 参数更新事件
        this.socket.on('parameters_updated', (data) => {
            this.handleParametersUpdate(data);
        });

        // 日志消息事件
        this.socket.on('log_message', (data) => {
            this.addLogEntry(data.message, data.level);
        });
    }

    /**
     * 初始化UI事件监听
     */
    initUIEvents() {
        // 设备控制
        document.getElementById('refresh-devices-btn').addEventListener('click', () => {
            this.refreshDevices();
        });

        document.getElementById('device-select').addEventListener('change', (e) => {
            this.currentDeviceIndex = parseInt(e.target.value);
        });

        // 连接控制
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

        // 参数控制
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

        // 触发控制
        document.getElementById('software-trigger-btn').addEventListener('click', () => {
            this.softwareTrigger();
        });

        document.getElementById('reset-trigger-btn').addEventListener('click', () => {
            this.resetTriggerCount();
        });

        // 图像保存
        document.getElementById('save-image-btn').addEventListener('click', () => {
            this.saveImage();
        });

        // 日志清除
        document.getElementById('clear-log-btn').addEventListener('click', () => {
            this.clearLog();
        });

        // 防止表单提交
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && e.target.tagName === 'INPUT') {
                e.preventDefault();
            }
        });
    }

    /**
     * 处理状态更新
     */
    handleStatusUpdate(data) {
        // 更新连接状态
        this.isConnected = data.is_connected;
        this.isStreaming = data.is_streaming;
        this.currentMode = data.current_mode;

        // 更新UI显示
        this.updateConnectionStatus(data.connection_status);
        this.updateStreamStatus(data.is_streaming);
        this.updateModeStatus(data.current_mode);
        this.updateDeviceInfo(data.device_info);
        this.updateCounts(data.trigger_count, data.save_count);
        
        // 更新UI状态
        this.updateUIState();
    }

    /**
     * 处理设备列表更新
     */
    handleDevicesListUpdate(data) {
        this.devices = data.devices;
        const select = document.getElementById('device-select');
        
        // 清空现有选项
        select.innerHTML = '';
        
        if (this.devices.length === 0) {
            select.innerHTML = '<option value="">未找到设备</option>';
            select.disabled = true;
        } else {
            select.innerHTML = '<option value="">请选择设备</option>';
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
     * 处理参数更新
     */
    handleParametersUpdate(data) {
        document.getElementById('exposure-time').value = data.exposure_time.toFixed(2);
        document.getElementById('gain').value = data.gain.toFixed(2);
        document.getElementById('frame-rate').value = data.frame_rate.toFixed(2);
    }

    /**
     * 刷新设备列表
     */
    refreshDevices() {
        this.showLoading('正在枚举设备...');
        this.socket.emit('refresh_devices');
    }

    /**
     * 连接设备
     */
    connectDevice() {
        if (this.currentDeviceIndex < 0) {
            this.addLogEntry('请先选择一个设备', 'warning');
            return;
        }

        this.showLoading('正在连接设备...');
        this.socket.emit('connect_device', {
            device_index: this.currentDeviceIndex
        });
    }

    /**
     * 断开设备
     */
    disconnectDevice() {
        this.showLoading('正在断开连接...');
        this.socket.emit('disconnect_device');
    }

    /**
     * 重置连接
     */
    resetConnection() {
        this.showLoading('正在重置连接...');
        this.socket.emit('reset_connection', {
            device_index: this.currentDeviceIndex
        });
    }

    /**
     * 优化包大小
     */
    optimizePacketSize() {
        this.socket.emit('optimize_packet_size');
    }

    /**
     * 获取参数
     */
    getParameters() {
        this.socket.emit('get_parameters');
    }

    /**
     * 设置参数
     */
    setParameters() {
        const exposureTime = parseFloat(document.getElementById('exposure-time').value);
        const gain = parseFloat(document.getElementById('gain').value);
        const frameRate = parseFloat(document.getElementById('frame-rate').value);

        if (isNaN(exposureTime) || isNaN(gain) || isNaN(frameRate)) {
            this.addLogEntry('参数格式错误，请输入有效数字', 'error');
            return;
        }

        this.socket.emit('set_parameters', {
            exposure_time: exposureTime,
            gain: gain,
            frame_rate: frameRate
        });
    }

    /**
     * 设置模式
     */
    setMode(mode) {
        this.socket.emit('set_mode', { mode: mode });
    }

    /**
     * 开始串流
     */
    startStreaming() {
        this.showLoading('正在启动串流...');
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
     * 软触发
     */
    softwareTrigger() {
        this.socket.emit('software_trigger');
    }

    /**
     * 重置触发计数
     */
    resetTriggerCount() {
        this.socket.emit('reset_trigger_count');
    }

    /**
     * 保存图像
     */
    saveImage() {
        const format = document.querySelector('input[name="image-format"]:checked').value;
        this.socket.emit('save_image', { format: format });
    }

    /**
     * 清除日志
     */
    clearLog() {
        const logContainer = document.getElementById('log-container');
        logContainer.innerHTML = '';
        this.addLogEntry('日志已清除', 'info');
    }

    /**
     * 更新连接状态显示
     */
    updateConnectionStatus(status) {
        const statusElement = document.getElementById('connection-status');
        statusElement.className = 'status-value';
        
        switch (status) {
            case 'connected':
                statusElement.textContent = '已连接';
                statusElement.classList.add('status-connected');
                break;
            case 'streaming':
                statusElement.textContent = '串流中';
                statusElement.classList.add('status-streaming');
                break;
            case 'disconnected':
                statusElement.textContent = '未连接';
                statusElement.classList.add('status-disconnected');
                break;
            case 'error':
                statusElement.textContent = '错误';
                statusElement.classList.add('status-disconnected');
                break;
            default:
                statusElement.textContent = '未知';
                statusElement.classList.add('status-disconnected');
        }
    }

    /**
     * 更新串流状态显示
     */
    updateStreamStatus(isStreaming) {
        const statusElement = document.getElementById('stream-status');
        statusElement.className = 'status-value';
        
        if (isStreaming) {
            statusElement.textContent = '运行中';
            statusElement.classList.add('status-connected');
        } else {
            statusElement.textContent = '已停止';
            statusElement.classList.add('status-stopped');
        }
    }

    /**
     * 更新模式状态显示
     */
    updateModeStatus(mode) {
        const statusElement = document.getElementById('current-mode');
        const modeText = mode === 'continuous' ? '连续模式' : '触发模式';
        statusElement.textContent = modeText;
        
        // 更新单选按钮状态
        const radioButton = document.querySelector(`input[name="mode"][value="${mode}"]`);
        if (radioButton) {
            radioButton.checked = true;
        }
    }

    /**
     * 更新设备信息显示
     */
    updateDeviceInfo(deviceInfo) {
        if (deviceInfo) {
            document.getElementById('device-name').textContent = deviceInfo.name || '无';
            document.getElementById('device-type').textContent = deviceInfo.type || '无';
            document.getElementById('device-serial').textContent = deviceInfo.serial || '无';
            document.getElementById('device-ip').textContent = deviceInfo.ip || '无';
        } else {
            document.getElementById('device-name').textContent = '无';
            document.getElementById('device-type').textContent = '无';
            document.getElementById('device-serial').textContent = '无';
            document.getElementById('device-ip').textContent = '无';
        }
    }

    /**
     * 更新计数显示
     */
    updateCounts(triggerCount, saveCount) {
        document.getElementById('trigger-count').textContent = triggerCount;
        document.getElementById('save-count').textContent = saveCount;
    }

    /**
     * 更新UI控件状态
     */
    updateUIState() {
        // 连接控制按钮
        document.getElementById('connect-btn').disabled = this.isConnected || this.currentDeviceIndex < 0;
        document.getElementById('disconnect-btn').disabled = !this.isConnected;
        document.getElementById('optimize-packet-btn').disabled = !this.isConnected;

        // 参数控制
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

        // 触发控制
        const isTriggerMode = this.currentMode === 'trigger';
        document.getElementById('software-trigger-btn').disabled = !(this.isStreaming && isTriggerMode);

        // 图像保存
        document.getElementById('save-image-btn').disabled = !this.isStreaming;
    }

    /**
     * 添加日志条目
     */
    addLogEntry(message, level = 'info') {
        const logContainer = document.getElementById('log-container');
        const entry = document.createElement('div');
        entry.className = `log-entry log-${level}`;
        
        const now = new Date();
        const timeStr = now.toLocaleTimeString('zh-CN', { 
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
        
        // 自动滚动到底部
        logContainer.scrollTop = logContainer.scrollHeight;
        
        // 限制日志条目数量
        const entries = logContainer.children;
        if (entries.length > 1000) {
            for (let i = 0; i < 100; i++) {
                logContainer.removeChild(entries[0]);
            }
        }
    }

    /**
     * 显示加载遮罩
     */
    showLoading(text = '处理中...') {
        const overlay = document.getElementById('loading-overlay');
        const loadingText = document.getElementById('loading-text');
        loadingText.textContent = text;
        overlay.style.display = 'flex';
        
        // 自动隐藏（防止卡住）
        setTimeout(() => {
            this.hideLoading();
        }, 10000);
    }

    /**
     * 隐藏加载遮罩
     */
    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        overlay.style.display = 'none';
    }
}

// 页面加载完成后初始化应用
document.addEventListener('DOMContentLoaded', () => {
    window.cameraController = new CameraController();
    
    // 页面加载后自动刷新设备列表
    setTimeout(() => {
        window.cameraController.refreshDevices();
    }, 1000);
});

// 页面卸载时清理
window.addEventListener('beforeunload', () => {
    if (window.cameraController) {
        window.cameraController.socket.disconnect();
    }
});