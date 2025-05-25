# modbus_tcp_server.py
import asyncio
import logging
import threading
import time
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
from pymodbus.server import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext

import json

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ModbusServer/logs/modbus_server.log'),
        logging.StreamHandler()
    ]
)

class ModbusTCPServerApp:
    def __init__(self):
        self.slave_id = 1  # 預設SlaveID
        self.server_host = "0.0.0.0"
        self.server_port = 502
        self.web_port = 8000
        
        # 初始化暫存器數據 (0-999, 共1000個暫存器)
        self.register_count = 1000
        self.registers = [0] * self.register_count
        
        # Modbus相關
        self.server = None
        self.context = None
        self.slave_context = None
        
        # Web應用
        self.flask_app = Flask(__name__)
        self.setup_web_routes()
        
        # 伺服器狀態
        self.server_running = False
        
        logging.info("Modbus TCP Server 應用程式初始化完成")
    
    def create_modbus_context(self):
        """創建Modbus數據上下文"""
        # 創建數據塊 (Function Code 0x03, 0x04 - Holding Registers)
        # address=0 表示從地址0開始，values是初始值列表
        holding_registers = ModbusSequentialDataBlock(0, self.registers)
        
        # 創建Slave上下文
        # di = Discrete Inputs, co = Coils, hr = Holding Registers, ir = Input Registers
        self.slave_context = ModbusSlaveContext(
            di=ModbusSequentialDataBlock(0, [0]*100),  # Discrete Inputs
            co=ModbusSequentialDataBlock(0, [0]*100),  # Coils
            hr=holding_registers,                       # Holding Registers (主要使用)
            ir=holding_registers,                       # Input Registers (共用同樣的數據)
            
        )
        
        # 創建伺服器上下文，包含多個slave
        slaves = {self.slave_id: self.slave_context}
        self.context = ModbusServerContext(slaves=slaves, single=False)
        
        return self.context
    
    def update_slave_id(self, new_slave_id):
        """更新SlaveID"""
        if 1 <= new_slave_id <= 247:  # Modbus標準SlaveID範圍
            old_slave_id = self.slave_id
            self.slave_id = new_slave_id
            
            # 如果伺服器正在運行，需要重新創建上下文
            if self.server_running and self.context:
                # 移除舊的slave context
                if old_slave_id in self.context:
                    del self.context[old_slave_id]
                
                # 添加新的slave context
                self.context[self.slave_id] = self.slave_context
                
            logging.info(f"SlaveID 已更新: {old_slave_id} -> {new_slave_id}")
            return True
        else:
            logging.error(f"無效的SlaveID: {new_slave_id}, 必須在1-247範圍內")
            return False
    
    def read_register(self, address):
        """讀取暫存器值"""
        if 0 <= address < self.register_count:
            value = self.registers[address]
            logging.info(f"讀取暫存器 {address}: {value}")
            return value
        else:
            logging.error(f"暫存器地址超出範圍: {address}")
            return None
    
    def write_register(self, address, value):
        """寫入暫存器值"""
        if 0 <= address < self.register_count:
            # 確保值在int16範圍內 (-32768 to 32767)
            if -32768 <= value <= 32767:
                old_value = self.registers[address]
                self.registers[address] = value
                
                # 同步更新到Modbus上下文
                if self.slave_context:
                    self.slave_context.setValues(3, address, [value])  # Function Code 3 (Holding Registers)
                    self.slave_context.setValues(4, address, [value])  # Function Code 4 (Input Registers)
                
                logging.info(f"寫入暫存器 {address}: {old_value} -> {value}")
                return True
            else:
                logging.error(f"暫存器值超出int16範圍: {value}")
                return False
        else:
            logging.error(f"暫存器地址超出範圍: {address}")
            return False
    
    def write_multiple_registers(self, start_address, values):
        """批量寫入暫存器"""
        if start_address + len(values) <= self.register_count:
            for i, value in enumerate(values):
                self.write_register(start_address + i, value)
            return True
        else:
            logging.error(f"批量寫入超出範圍: start={start_address}, count={len(values)}")
            return False
    
    def get_register_status(self):
        """獲取暫存器狀態摘要"""
        non_zero_registers = {addr: val for addr, val in enumerate(self.registers) if val != 0}
        return {
            'total_registers': self.register_count,
            'non_zero_count': len(non_zero_registers),
            'non_zero_registers': non_zero_registers,
            'slave_id': self.slave_id,
            'server_running': self.server_running
        }
    
    def setup_web_routes(self):
        """設定Web介面路由"""
        
        @self.flask_app.route('/')
        def index():
            return render_template_string(WEB_INTERFACE_HTML)
        
        @self.flask_app.route('/api/status')
        def api_status():
            return jsonify(self.get_register_status())
        
        @self.flask_app.route('/api/slave_id', methods=['POST'])
        def api_set_slave_id():
            data = request.get_json()
            new_slave_id = data.get('slave_id')
            if self.update_slave_id(new_slave_id):
                return jsonify({'success': True, 'slave_id': self.slave_id})
            else:
                return jsonify({'success': False, 'error': 'Invalid SlaveID'}), 400
        
        @self.flask_app.route('/api/register/<int:address>')
        def api_get_register(address):
            value = self.read_register(address)
            if value is not None:
                return jsonify({'address': address, 'value': value})
            else:
                return jsonify({'error': 'Invalid address'}), 400
        
        @self.flask_app.route('/api/register/<int:address>', methods=['POST'])
        def api_set_register(address):
            data = request.get_json()
            value = data.get('value')
            if self.write_register(address, value):
                return jsonify({'success': True, 'address': address, 'value': value})
            else:
                return jsonify({'success': False, 'error': 'Invalid address or value'}), 400
        
        @self.flask_app.route('/api/registers', methods=['POST'])
        def api_set_multiple_registers():
            data = request.get_json()
            start_address = data.get('start_address', 0)
            values = data.get('values', [])
            if self.write_multiple_registers(start_address, values):
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'Invalid range or values'}), 400
    
    def start_modbus_server(self):
        """啟動Modbus TCP伺服器"""
        try:
            # 創建設備識別
            identity = ModbusDeviceIdentification()
            identity.VendorName = 'Python Modbus Server'
            identity.ProductCode = 'PMS'
            identity.VendorUrl = 'https://github.com/your-repo'
            identity.ProductName = 'Python Modbus TCP Server'
            identity.ModelName = 'Basic Server'
            identity.MajorMinorRevision = '1.0'
            
            # 創建上下文
            context = self.create_modbus_context()
            
            # 啟動伺服器 (這會阻塞當前線程)
            logging.info(f"啟動Modbus TCP Server於 {self.server_host}:{self.server_port}, SlaveID: {self.slave_id}")
            self.server_running = True
            
            StartTcpServer(
                context=context,
                identity=identity,
                address=(self.server_host, self.server_port),
                
            )
            
        except Exception as e:
            logging.error(f"Modbus伺服器啟動失敗: {e}")
            self.server_running = False
    
    def start_web_server(self):
        """啟動Web管理介面"""
        try:
            logging.info(f"啟動Web管理介面於 http://127.0.0.1:{self.web_port}")
            self.flask_app.run(
                host='0.0.0.0',
                port=self.web_port,
                debug=False,
                use_reloader=False
            )
        except Exception as e:
            logging.error(f"Web伺服器啟動失敗: {e}")
    
    def initialize_test_data(self):
        """初始化測試數據"""
        # 設定一些測試值
        test_data = {
            0: 100,    # 地址0 = 100
            1: 200,    # 地址1 = 200
            10: 1000,  # 地址10 = 1000
            50: 5000,  # 地址50 = 5000
            100: 12345 # 地址100 = 12345
        }
        
        for addr, value in test_data.items():
            self.write_register(addr, value)
        
        logging.info("測試數據初始化完成")
    
    def run(self):
        """主運行方法"""
        logging.info("=== Modbus TCP Server 啟動 ===")
        
        # 初始化測試數據
        self.initialize_test_data()
        
        # 啟動Web伺服器 (在單獨線程中)
        web_thread = threading.Thread(target=self.start_web_server, daemon=True)
        web_thread.start()
        
        # 等待一秒確保Web伺服器啟動
        time.sleep(1)
        
        # 啟動Modbus伺服器 (主線程，會阻塞)
        self.start_modbus_server()

# Web介面HTML模板
WEB_INTERFACE_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Modbus TCP Server 管理介面</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; margin-bottom: 20px; }
        .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        .status { background-color: #e7f3ff; }
        .controls { background-color: #f0f8e7; }
        .registers { background-color: #fff7e6; }
        input, button { padding: 8px; margin: 5px; border: 1px solid #ccc; border-radius: 4px; }
        button { background-color: #007bff; color: white; cursor: pointer; }
        button:hover { background-color: #0056b3; }
        .register-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; max-height: 400px; overflow-y: auto; }
        .register-item { padding: 8px; border: 1px solid #ddd; border-radius: 4px; background-color: #f9f9f9; }
        .register-item.non-zero { background-color: #d4edda; border-color: #c3e6cb; }
        .error { color: #d32f2f; }
        .success { color: #388e3c; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔧 Modbus TCP Server 管理介面</h1>
            <p>伺服器地址: 127.0.0.1:502 | Web管理: 127.0.0.1:8000</p>
        </div>
        
        <div class="section status">
            <h2>📊 伺服器狀態</h2>
            <div id="status-info">載入中...</div>
            <button onclick="refreshStatus()">🔄 刷新狀態</button>
        </div>
        
        <div class="section controls">
            <h2>⚙️ 控制面板</h2>
            <div>
                <label>SlaveID (1-247):</label>
                <input type="number" id="slave-id" min="1" max="247" value="1">
                <button onclick="updateSlaveId()">更新 SlaveID</button>
            </div>
            <div style="margin-top: 10px;">
                <label>暫存器地址 (0-999):</label>
                <input type="number" id="reg-address" min="0" max="999" value="0">
                <label>值 (-32768 ~ 32767):</label>
                <input type="number" id="reg-value" min="-32768" max="32767" value="0">
                <button onclick="writeRegister()">寫入暫存器</button>
                <button onclick="readRegister()">讀取暫存器</button>
            </div>
            <div id="result-message"></div>
        </div>
        
        <div class="section registers">
            <h2>📋 暫存器狀態 (僅顯示非零值)</h2>
            <div id="registers-grid" class="register-grid">載入中...</div>
        </div>
        
        <div class="section">
            <h2>📖 使用說明</h2>
            <ul>
                <li><strong>Modbus Poll 連接設定:</strong> 連接到 127.0.0.1:502</li>
                <li><strong>Function Code:</strong> 使用 0x03 (Read Holding Registers) 讀取暫存器</li>
                <li><strong>SlaveID:</strong> 預設為 1，可透過上面的控制面板修改</li>
                <li><strong>暫存器範圍:</strong> 0-999 (共1000個暫存器)</li>
                <li><strong>數據類型:</strong> 16位有符號整數 (-32768 到 32767)</li>
                <li><strong>測試數據:</strong> 地址 0,1,10,50,100 已預設測試值</li>
            </ul>
        </div>
    </div>

    <script>
        // 刷新伺服器狀態
        function refreshStatus() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('status-info').innerHTML = `
                        <p><strong>伺服器狀態:</strong> ${data.server_running ? '🟢 運行中' : '🔴 停止'}</p>
                        <p><strong>當前 SlaveID:</strong> ${data.slave_id}</p>
                        <p><strong>總暫存器數:</strong> ${data.total_registers}</p>
                        <p><strong>非零暫存器數:</strong> ${data.non_zero_count}</p>
                        <p><strong>最後更新:</strong> ${new Date().toLocaleString()}</p>
                    `;
                    
                    // 更新暫存器顯示
                    updateRegistersDisplay(data.non_zero_registers);
                    
                    // 更新SlaveID輸入框
                    document.getElementById('slave-id').value = data.slave_id;
                })
                .catch(error => {
                    document.getElementById('status-info').innerHTML = `<p class="error">❌ 無法獲取狀態: ${error}</p>`;
                });
        }
        
        // 更新暫存器顯示
        function updateRegistersDisplay(registers) {
            const grid = document.getElementById('registers-grid');
            if (Object.keys(registers).length === 0) {
                grid.innerHTML = '<p>所有暫存器都為零</p>';
                return;
            }
            
            let html = '';
            for (let [address, value] of Object.entries(registers)) {
                html += `
                    <div class="register-item non-zero">
                        <strong>地址 ${address}</strong><br>
                        值: ${value}
                    </div>
                `;
            }
            grid.innerHTML = html;
        }
        
        // 更新SlaveID
        function updateSlaveId() {
            const slaveId = parseInt(document.getElementById('slave-id').value);
            fetch('/api/slave_id', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({slave_id: slaveId})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage(`✅ SlaveID 已更新為: ${data.slave_id}`, 'success');
                    refreshStatus();
                } else {
                    showMessage(`❌ 更新失敗: ${data.error}`, 'error');
                }
            })
            .catch(error => showMessage(`❌ 請求失敗: ${error}`, 'error'));
        }
        
        // 寫入暫存器
        function writeRegister() {
            const address = parseInt(document.getElementById('reg-address').value);
            const value = parseInt(document.getElementById('reg-value').value);
            
            fetch(`/api/register/${address}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({value: value})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage(`✅ 暫存器 ${address} 已設為: ${value}`, 'success');
                    refreshStatus();
                } else {
                    showMessage(`❌ 寫入失敗: ${data.error}`, 'error');
                }
            })
            .catch(error => showMessage(`❌ 請求失敗: ${error}`, 'error'));
        }
        
        // 讀取暫存器
        function readRegister() {
            const address = parseInt(document.getElementById('reg-address').value);
            
            fetch(`/api/register/${address}`)
                .then(response => response.json())
                .then(data => {
                    if (data.address !== undefined) {
                        showMessage(`📖 暫存器 ${data.address} 的值: ${data.value}`, 'success');
                        document.getElementById('reg-value').value = data.value;
                    } else {
                        showMessage(`❌ 讀取失敗: ${data.error}`, 'error');
                    }
                })
                .catch(error => showMessage(`❌ 請求失敗: ${error}`, 'error'));
        }
        
        // 顯示訊息
        function showMessage(message, type) {
            const msgDiv = document.getElementById('result-message');
            msgDiv.innerHTML = `<p class="${type}">${message}</p>`;
            setTimeout(() => msgDiv.innerHTML = '', 5000);
        }
        
        // 頁面載入時刷新狀態
        window.onload = function() {
            refreshStatus();
            // 每30秒自動刷新一次
            setInterval(refreshStatus, 30000);
        };
    </script>
</body>
</html>
'''

if __name__ == "__main__":
    app = ModbusTCPServerApp()
    app.run()