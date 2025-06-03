# modbus_tcp_server_separated.py
# 支援分離檔案版本 (templates + static)

import logging
import threading
import time
import json
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from pymodbus.server import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('modbus_server.log'),
        logging.StreamHandler()
    ]
)

class SynchronizedDataBlock(ModbusSequentialDataBlock):
    """同步化的數據塊，當外部修改時會更新主程式的暫存器陣列"""
    
    def __init__(self, address, values, server_app):
        super().__init__(address, values)
        self.server_app = server_app
    
    def setValues(self, address, values):
        """覆寫setValues方法，同步更新主程式的陣列"""
        result = super().setValues(address, values)
        
        # 同步更新主程式的暫存器陣列
        if self.server_app:
            for i, value in enumerate(values):
                reg_addr = address + i
                if 0 <= reg_addr < len(self.server_app.registers):
                    self.server_app.registers[reg_addr] = value
                    logging.info(f"外部更新暫存器 {reg_addr}: {value}")
        
        return result

class ModbusTCPServerApp:
    def __init__(self):
        self.slave_id = 1  # 預設SlaveID
        self.server_host = "0.0.0.0"
        self.server_port = 502
        self.web_port = 8000
        
        # 初始化暫存器數據 (0-999, 共1000個暫存器)
        self.register_count = 1000
        self.registers = [0] * self.register_count
        
        # 暫存器註解
        self.register_comments = {}
        self.load_comments()
        
        # 創建templates和static目錄
        self.create_directories()
        
        # Modbus相關
        self.server = None
        self.context = None
        self.slave_context = None
        
        # Web應用 - 設定模板和靜態檔案路徑
        self.flask_app = Flask(__name__, 
                              template_folder='templates',
                              static_folder='static')
        self.setup_web_routes()
        
        # 伺服器狀態
        self.server_running = False
        
        logging.info("Modbus TCP Server 應用程式初始化完成")
    
    def create_directories(self):
        """創建必要的目錄結構"""
        directories = [
            'templates',
            'static'
        ]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    def load_comments(self):
        """載入暫存器註解"""
        try:
            if os.path.exists('register_comments.json'):
                with open('register_comments.json', 'r', encoding='utf-8') as f:
                    self.register_comments = json.load(f)
                logging.info(f"載入了 {len(self.register_comments)} 個暫存器註解")
        except Exception as e:
            logging.error(f"載入註解失敗: {e}")
            self.register_comments = {}
    
    def save_comments(self):
        """保存暫存器註解"""
        try:
            with open('register_comments.json', 'w', encoding='utf-8') as f:
                json.dump(self.register_comments, f, ensure_ascii=False, indent=2)
            logging.info("暫存器註解已保存")
        except Exception as e:
            logging.error(f"保存註解失敗: {e}")
    
    def create_modbus_context(self):
        """創建Modbus數據上下文"""
        # 使用同步化的數據塊
        holding_registers = SynchronizedDataBlock(0, self.registers, self)
        
        # 創建Slave上下文
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
            # 從Modbus上下文讀取最新值
            if self.slave_context:
                try:
                    result = self.slave_context.getValues(3, address, 1)
                    if result:
                        value = result[0]
                        self.registers[address] = value  # 同步到內部陣列
                        return value
                except:
                    pass
            
            # 如果Modbus上下文不可用，返回內部陣列的值
            value = self.registers[address]
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
        # 同步所有暫存器值
        if self.slave_context:
            try:
                for addr in range(min(100, self.register_count)):  # 只同步前100個避免太慢
                    result = self.slave_context.getValues(3, addr, 1)
                    if result:
                        self.registers[addr] = result[0]
            except:
                pass
        
        non_zero_registers = {addr: val for addr, val in enumerate(self.registers) if val != 0}
        return {
            'total_registers': self.register_count,
            'non_zero_count': len(non_zero_registers),
            'non_zero_registers': non_zero_registers,
            'slave_id': self.slave_id,
            'server_running': self.server_running
        }
    
    def get_register_range(self, start_address, count):
        """獲取指定範圍的暫存器數據"""
        if start_address < 0 or start_address >= self.register_count:
            return None
        
        end_address = min(start_address + count, self.register_count)
        registers_data = []
        
        for addr in range(start_address, end_address):
            value = self.read_register(addr)  # 使用read_register確保數據同步
            comment = self.register_comments.get(str(addr), '')
            registers_data.append({
                'address': addr,
                'value': value,
                'comment': comment
            })
        
        return registers_data
    
    def update_register_comment(self, address, comment):
        """更新暫存器註解"""
        if 0 <= address < self.register_count:
            if comment.strip():
                self.register_comments[str(address)] = comment.strip()
            else:
                # 如果註解為空，則刪除
                self.register_comments.pop(str(address), None)
            
            self.save_comments()
            return True
        return False
    
    def setup_web_routes(self):
        """設定Web介面路由"""
        
        @self.flask_app.route('/')
        def index():
            return render_template('index.html')
        
        @self.flask_app.route('/static/<path:filename>')
        def static_files(filename):
            return send_from_directory('static', filename)
        
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
                comment = self.register_comments.get(str(address), '')
                return jsonify({'address': address, 'value': value, 'comment': comment})
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
        
        @self.flask_app.route('/api/register_range')
        def api_get_register_range():
            start_address = int(request.args.get('start', 0))
            count = int(request.args.get('count', 20))
            count = min(count, 100)  # 限制最大數量
            
            registers_data = self.get_register_range(start_address, count)
            if registers_data is not None:
                return jsonify({
                    'success': True,
                    'start_address': start_address,
                    'count': len(registers_data),
                    'registers': registers_data
                })
            else:
                return jsonify({'success': False, 'error': 'Invalid address range'}), 400
        
        @self.flask_app.route('/api/comment/<int:address>', methods=['POST'])
        def api_update_comment(address):
            data = request.get_json()
            comment = data.get('comment', '')
            if self.update_register_comment(address, comment):
                return jsonify({'success': True, 'address': address, 'comment': comment})
            else:
                return jsonify({'success': False, 'error': 'Invalid address'}), 400
    
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
        
        # 設定一些測試註解
        test_comments = {
            0: "溫度感測器",
            1: "濕度感測器", 
            10: "馬達轉速",
            50: "壓力數值",
            100: "測試數據"
        }
        
        for addr, comment in test_comments.items():
            self.register_comments[str(addr)] = comment
        
        self.save_comments()
        logging.info("測試數據和註解初始化完成")
    
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

if __name__ == "__main__":
    app = ModbusTCPServerApp()
    app.run()