# ServerApp.py
# 獨立的Modbus TCP Server應用程式
# 版本：1.1.0 - 支援pymodbus 3.9.2 + 高頻訪問優化

import logging
import threading
import time
import json
import os
import sys
import signal
import traceback
import socket
import queue
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, request
from pymodbus.server import StartTcpServer, ModbusTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from concurrent.futures import ThreadPoolExecutor

# 設定日誌
def setup_logging():
    """設定日誌配置"""
    log_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    
    # 檔案日誌處理器
    file_handler = logging.FileHandler('modbus_server.log', encoding='utf-8')
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.INFO)
    
    # 控制台日誌處理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO)
    
    # 設定根記錄器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # 抑制一些第三方庫的詳細日誌
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('pymodbus').setLevel(logging.WARNING)

class EnhancedSynchronizedDataBlock(ModbusSequentialDataBlock):
    """增強版同步化數據塊，支援高頻訪問和線程安全"""
    
    def __init__(self, address, values, server_app):
        super().__init__(address, values)
        self.server_app = server_app
        self._lock = threading.RLock()  # 可重入鎖
        self._last_update = time.time()
        self._update_queue = queue.Queue(maxsize=1000)  # 更新隊列
        
        # 啟動後台更新線程
        self._update_thread = threading.Thread(target=self._process_updates, daemon=True)
        self._update_thread.start()
    
    def _process_updates(self):
        """後台處理更新隊列"""
        while True:
            try:
                update_data = self._update_queue.get(timeout=1.0)
                if update_data is None:  # 停止信號
                    break
                    
                address, values = update_data
                self._apply_updates(address, values)
                self._update_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"處理更新隊列錯誤: {e}")
    
    def _apply_updates(self, address, values):
        """應用更新到主程式陣列"""
        try:
            if self.server_app:
                for i, value in enumerate(values):
                    reg_addr = address + i
                    if 0 <= reg_addr < len(self.server_app.registers):
                        self.server_app.registers[reg_addr] = value
                        
        except Exception as e:
            logging.error(f"應用更新錯誤: {e}")
    
    def setValues(self, address, values):
        """覆寫setValues方法，使用隊列處理高頻更新"""
        try:
            with self._lock:
                result = super().setValues(address, values)
                
                # 將更新放入隊列而非立即處理
                try:
                    self._update_queue.put_nowait((address, values))
                except queue.Full:
                    logging.warning("更新隊列已滿，跳過此次更新")
                
                return result
                
        except Exception as e:
            logging.error(f"同步數據塊設值錯誤: {e}")
            return False
    
    def getValues(self, address, count=1):
        """線程安全的獲取值"""
        try:
            with self._lock:
                return super().getValues(address, count)
        except Exception as e:
            logging.error(f"獲取值錯誤: {e}")
            return [0] * count
    
    def shutdown(self):
        """關閉更新線程"""
        try:
            self._update_queue.put_nowait(None)  # 停止信號
            self._update_thread.join(timeout=2.0)
        except Exception as e:
            logging.error(f"關閉更新線程錯誤: {e}")

class ModbusTCPServer:
    def __init__(self):
        self.slave_id = 1  # 預設SlaveID
        self.server_host = "0.0.0.0"
        self.server_port = 502
        self.api_port = 8001  # API服務端口
        
        # 初始化暫存器數據 (0-999, 共1000個暫存器)
        self.register_count = 1000
        self.registers = [0] * self.register_count
        self._register_lock = threading.RLock()  # 暫存器訪問鎖
        
        # 暫存器註解
        self.register_comments = {}
        self.load_comments()
        
        # Modbus相關
        self.server = None
        self.context = None
        self.slave_context = None
        self.data_block = None
        self.modbus_thread = None
        
        # API Flask應用（僅提供API接口）
        self.api_app = Flask(__name__)
        self.api_app.config['JSON_AS_ASCII'] = False
        self.setup_api_routes()
        
        # 連接管理
        self.connection_pool = ThreadPoolExecutor(max_workers=20)  # 連接池
        self.request_queue = queue.Queue(maxsize=500)  # 請求隊列
        self.rate_limiter = {}  # 簡單的頻率限制
        
        # 伺服器狀態
        self.server_running = False
        self.start_time = time.time()
        self.shutdown_event = threading.Event()
        self.health_check_interval = 5  # 健康檢查間隔(秒)
        
        # 性能監控
        self.stats = {
            'total_requests': 0,
            'failed_requests': 0,
            'connection_errors': 0,
            'last_error_time': None,
            'avg_response_time': 0
        }
        
        # 註冊信號處理器
        self.setup_signal_handlers()
        
        # 啟動健康檢查線程
        self.health_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self.health_thread.start()
        
        logging.info("Modbus TCP Server 初始化完成 - 已啟用高頻訪問優化")
    
    def _health_check_loop(self):
        """健康檢查循環"""
        while not self.shutdown_event.is_set():
            try:
                if self.server_running:
                    # 檢查Modbus伺服器健康狀態
                    self._check_modbus_health()
                    
                    # 清理過期的頻率限制記錄
                    self._cleanup_rate_limiter()
                    
                time.sleep(self.health_check_interval)
            except Exception as e:
                logging.error(f"健康檢查錯誤: {e}")
    
    def _check_modbus_health(self):
        """檢查Modbus伺服器健康狀態"""
        try:
            if self.slave_context:
                # 嘗試讀取一個暫存器測試連接
                test_result = self.slave_context.getValues(3, 0, 1)
                if test_result is None:
                    logging.warning("Modbus上下文健康檢查失敗")
                    self.stats['connection_errors'] += 1
        except Exception as e:
            logging.warning(f"Modbus健康檢查異常: {e}")
    
    def _cleanup_rate_limiter(self):
        """清理過期的頻率限制記錄"""
        try:
            current_time = time.time()
            expired_keys = [
                key for key, last_time in self.rate_limiter.items() 
                if current_time - last_time > 60  # 1分鐘過期
            ]
            for key in expired_keys:
                del self.rate_limiter[key]
        except Exception as e:
            logging.error(f"清理頻率限制記錄錯誤: {e}")
    
    def _check_rate_limit(self, client_ip, max_requests_per_second=10):
        """檢查頻率限制"""
        try:
            current_time = time.time()
            key = f"{client_ip}_{int(current_time)}"
            
            if key in self.rate_limiter:
                self.rate_limiter[key] += 1
                if self.rate_limiter[key] > max_requests_per_second:
                    return False
            else:
                self.rate_limiter[key] = 1
            
            return True
        except Exception as e:
            logging.error(f"頻率限制檢查錯誤: {e}")
            return True  # 發生錯誤時允許請求
    
    def load_comments(self):
        """載入暫存器註解"""
        try:
            comments_file = 'register_comments.json'
            if os.path.exists(comments_file):
                with open(comments_file, 'r', encoding='utf-8') as f:
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
            logging.debug("暫存器註解已保存")
        except Exception as e:
            logging.error(f"保存註解失敗: {e}")
    
    def setup_signal_handlers(self):
        """設定信號處理器以優雅關閉"""
        def signal_handler(signum, frame):
            logging.info(f"收到信號 {signum}，正在優雅關閉伺服器...")
            self.shutdown()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def create_modbus_context(self):
        """創建Modbus數據上下文 - 增強版"""
        try:
            # 使用增強版同步化數據塊
            self.data_block = EnhancedSynchronizedDataBlock(0, self.registers, self)
            
            # 創建Slave上下文
            self.slave_context = ModbusSlaveContext(
                di=ModbusSequentialDataBlock(0, [0]*100),  # Discrete Inputs
                co=ModbusSequentialDataBlock(0, [0]*100),  # Coils
                hr=self.data_block,                        # Holding Registers (主要使用)
                ir=self.data_block,                        # Input Registers (共用同樣的數據)
            )
            
            # 創建伺服器上下文，包含多個slave
            slaves = {self.slave_id: self.slave_context}
            self.context = ModbusServerContext(slaves=slaves, single=False)
            
            return self.context
        except Exception as e:
            logging.error(f"創建Modbus上下文失敗: {e}")
            return None
    
    def update_slave_id(self, new_slave_id):
        """更新SlaveID"""
        try:
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
        except Exception as e:
            logging.error(f"更新SlaveID失敗: {e}")
            return False
    
    def read_register(self, address):
        """讀取暫存器值 - 線程安全版本"""
        start_time = time.time()
        try:
            if 0 <= address < self.register_count:
                with self._register_lock:
                    # 優先從Modbus上下文讀取最新值
                    if self.slave_context:
                        try:
                            result = self.slave_context.getValues(3, address, 1)
                            if result:
                                value = result[0]
                                self.registers[address] = value  # 同步到內部陣列
                                self._update_stats(start_time, True)
                                return value
                        except Exception as e:
                            logging.debug(f"從Modbus上下文讀取失敗: {e}")
                    
                    # 如果Modbus上下文不可用，返回內部陣列的值
                    value = self.registers[address]
                    self._update_stats(start_time, True)
                    return value
            else:
                logging.error(f"暫存器地址超出範圍: {address}")
                self._update_stats(start_time, False)
                return None
        except Exception as e:
            logging.error(f"讀取暫存器失敗: {e}")
            self._update_stats(start_time, False)
            return None
    
    def write_register(self, address, value):
        """寫入暫存器值 - 線程安全版本"""
        start_time = time.time()
        try:
            if 0 <= address < self.register_count:
                # 確保值在無符號16位範圍內 (0 to 65535)
                if 0 <= value <= 65535:
                    with self._register_lock:
                        old_value = self.registers[address]
                        self.registers[address] = value
                        
                        # 同步更新到Modbus上下文
                        if self.slave_context:
                            try:
                                self.slave_context.setValues(3, address, [value])  # Function Code 3 (Holding Registers)
                                self.slave_context.setValues(4, address, [value])  # Function Code 4 (Input Registers)
                            except Exception as e:
                                logging.warning(f"同步到Modbus上下文失敗: {e}")
                        
                        logging.info(f"寫入暫存器 {address}: {old_value} -> {value}")
                        self._update_stats(start_time, True)
                        return True
                else:
                    logging.error(f"暫存器值超出無符號16位範圍: {value} (需要 0-65535)")
                    self._update_stats(start_time, False)
                    return False
            else:
                logging.error(f"暫存器地址超出範圍: {address}")
                self._update_stats(start_time, False)
                return False
        except Exception as e:
            logging.error(f"寫入暫存器失敗: {e}")
            self._update_stats(start_time, False)
            return False
    
    def _update_stats(self, start_time, success):
        """更新性能統計"""
        try:
            response_time = time.time() - start_time
            self.stats['total_requests'] += 1
            
            if success:
                # 更新平均響應時間（簡單移動平均）
                current_avg = self.stats['avg_response_time']
                self.stats['avg_response_time'] = (current_avg * 0.9) + (response_time * 0.1)
            else:
                self.stats['failed_requests'] += 1
                self.stats['last_error_time'] = time.time()
        except Exception as e:
            logging.error(f"更新統計錯誤: {e}")
    
    def write_multiple_registers(self, start_address, values):
        """批量寫入暫存器"""
        try:
            if start_address + len(values) <= self.register_count:
                success_count = 0
                for i, value in enumerate(values):
                    if self.write_register(start_address + i, value):
                        success_count += 1
                
                if success_count == len(values):
                    return True
                else:
                    logging.warning(f"批量寫入部分成功: {success_count}/{len(values)}")
                    return False
            else:
                logging.error(f"批量寫入超出範圍: start={start_address}, count={len(values)}")
                return False
        except Exception as e:
            logging.error(f"批量寫入失敗: {e}")
            return False
    
    def get_register_status(self):
        """獲取暫存器狀態摘要 - 增強版"""
        try:
            with self._register_lock:
                # 限制同步範圍避免阻塞
                sync_limit = min(50, self.register_count)
                if self.slave_context:
                    try:
                        for addr in range(sync_limit):
                            result = self.slave_context.getValues(3, addr, 1)
                            if result:
                                self.registers[addr] = result[0]
                    except Exception as e:
                        logging.debug(f"同步暫存器值失敗: {e}")
                
                non_zero_registers = {
                    addr: val for addr, val in enumerate(self.registers) 
                    if val != 0
                }
                
                return {
                    'total_registers': self.register_count,
                    'non_zero_count': len(non_zero_registers),
                    'non_zero_registers': non_zero_registers,
                    'slave_id': self.slave_id,
                    'server_running': self.server_running,
                    'version': '1.1.0',
                    'uptime': time.time() - self.start_time,
                    'modbus_port': self.server_port,
                    'api_port': self.api_port,
                    'performance_stats': {
                        'total_requests': self.stats['total_requests'],
                        'failed_requests': self.stats['failed_requests'],
                        'success_rate': (
                            (self.stats['total_requests'] - self.stats['failed_requests']) / 
                            max(self.stats['total_requests'], 1) * 100
                        ),
                        'avg_response_time_ms': self.stats['avg_response_time'] * 1000,
                        'connection_errors': self.stats['connection_errors']
                    }
                }
        except Exception as e:
            logging.error(f"獲取暫存器狀態失敗: {e}")
            return {
                'total_registers': self.register_count,
                'non_zero_count': 0,
                'non_zero_registers': {},
                'slave_id': self.slave_id,
                'server_running': self.server_running,
                'error': str(e),
                'performance_stats': self.stats
            }
    
    def get_register_range(self, start_address, count):
        """獲取指定範圍的暫存器數據"""
        try:
            if start_address < 0 or start_address >= self.register_count:
                return None
            
            end_address = min(start_address + count, self.register_count)
            registers_data = []
            
            for addr in range(start_address, end_address):
                value = self.read_register(addr)  # 使用read_register確保數據同步
                comment = self.register_comments.get(str(addr), '')
                registers_data.append({
                    'address': addr,
                    'value': value if value is not None else 0,
                    'comment': comment
                })
            
            return registers_data
        except Exception as e:
            logging.error(f"獲取暫存器範圍失敗: {e}")
            return None
    
    def update_register_comment(self, address, comment):
        """更新暫存器註解"""
        try:
            if 0 <= address < self.register_count:
                if comment.strip():
                    self.register_comments[str(address)] = comment.strip()
                else:
                    # 如果註解為空，則刪除
                    self.register_comments.pop(str(address), None)
                
                self.save_comments()
                return True
            return False
        except Exception as e:
            logging.error(f"更新註解失敗: {e}")
            return False
    
    def setup_api_routes(self):
        """設定API路由（僅提供API接口，不包含Web頁面）- 增強版"""
        
        @self.api_app.before_request
        def before_request():
            """請求前處理 - 頻率限制"""
            client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
            
            if not self._check_rate_limit(client_ip):
                return jsonify({'error': 'Rate limit exceeded'}), 429
        
        @self.api_app.errorhandler(Exception)
        def handle_exception(e):
            logging.error(f"API錯誤: {e}\n{traceback.format_exc()}")
            self.stats['failed_requests'] += 1
            return jsonify({'error': 'Internal server error'}), 500
        
        @self.api_app.route('/api/health')
        def api_health():
            """健康檢查端點"""
            return jsonify({
                'status': 'healthy' if self.server_running else 'unhealthy',
                'timestamp': time.time(),
                'uptime': time.time() - self.start_time
            })
        
        @self.api_app.route('/api/status')
        def api_status():
            return jsonify(self.get_register_status())
        
        @self.api_app.route('/api/slave_id', methods=['POST'])
        def api_set_slave_id():
            try:
                data = request.get_json()
                new_slave_id = data.get('slave_id')
                if self.update_slave_id(new_slave_id):
                    return jsonify({'success': True, 'slave_id': self.slave_id})
                else:
                    return jsonify({'success': False, 'error': 'Invalid SlaveID'}), 400
            except Exception as e:
                logging.error(f"API設定SlaveID失敗: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.api_app.route('/api/register/<int:address>')
        def api_get_register(address):
            try:
                value = self.read_register(address)
                if value is not None:
                    comment = self.register_comments.get(str(address), '')
                    return jsonify({'address': address, 'value': value, 'comment': comment})
                else:
                    return jsonify({'error': 'Invalid address'}), 400
            except Exception as e:
                logging.error(f"API讀取暫存器失敗: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.api_app.route('/api/register/<int:address>', methods=['POST'])
        def api_set_register(address):
            try:
                data = request.get_json()
                value = data.get('value')
                if self.write_register(address, value):
                    return jsonify({'success': True, 'address': address, 'value': value})
                else:
                    return jsonify({'success': False, 'error': 'Invalid address or value (0-65535)'}), 400
            except Exception as e:
                logging.error(f"API寫入暫存器失敗: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.api_app.route('/api/registers', methods=['POST'])
        def api_set_multiple_registers():
            try:
                data = request.get_json()
                start_address = data.get('start_address', 0)
                values = data.get('values', [])
                if self.write_multiple_registers(start_address, values):
                    return jsonify({'success': True})
                else:
                    return jsonify({'success': False, 'error': 'Invalid range or values'}), 400
            except Exception as e:
                logging.error(f"API批量寫入失敗: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.api_app.route('/api/register_range')
        def api_get_register_range():
            try:
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
            except Exception as e:
                logging.error(f"API獲取暫存器範圍失敗: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.api_app.route('/api/comment/<int:address>', methods=['POST'])
        def api_update_comment(address):
            try:
                data = request.get_json()
                comment = data.get('comment', '')
                if self.update_register_comment(address, comment):
                    return jsonify({'success': True, 'address': address, 'comment': comment})
                else:
                    return jsonify({'success': False, 'error': 'Invalid address'}), 400
            except Exception as e:
                logging.error(f"API更新註解失敗: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
    
    def start_modbus_server(self):
        """啟動Modbus TCP伺服器 - 增強版"""
        try:
            # 創建設備識別
            identity = ModbusDeviceIdentification()
            identity.VendorName = 'Python Modbus Server'
            identity.ProductCode = 'PMS'
            identity.VendorUrl = 'https://github.com/your-repo'
            identity.ProductName = 'Python Modbus TCP Server'
            identity.ModelName = 'Production Server Enhanced'
            identity.MajorMinorRevision = '1.1.0'
            
            # 創建上下文
            context = self.create_modbus_context()
            if context is None:
                raise Exception("無法創建Modbus上下文")
            
            # 啟動伺服器 (這會阻塞當前線程)
            logging.info(f"啟動Modbus TCP Server於 {self.server_host}:{self.server_port}, SlaveID: {self.slave_id}")
            logging.info("已啟用高頻訪問優化和連接池管理")
            self.server_running = True
            
            # 使用更健壯的伺服器配置
            StartTcpServer(
                context=context,
                identity=identity,
                address=(self.server_host, self.server_port),
                custom_functions=[],  # 可以添加自定義功能
                defer_start=False,
                ignore_missing_slaves=True,  # 忽略遺失的slave
            )
            
        except Exception as e:
            logging.error(f"Modbus伺服器啟動失敗: {e}\n{traceback.format_exc()}")
            self.server_running = False
    
    def start_api_server(self):
        """啟動API伺服器 - 增強版"""
        try:
            logging.info(f"啟動API伺服器於 http://127.0.0.1:{self.api_port}")
            logging.info("已啟用頻率限制和連接池管理")
            
            # 使用更健壯的配置
            self.api_app.run(
                host='0.0.0.0',
                port=self.api_port,
                debug=False,
                use_reloader=False,
                threaded=True,
                request_handler=None,  # 使用預設處理器
                passthrough_errors=False,
                ssl_context=None,
                extra_files=None,
                exclude_patterns=None
            )
        except Exception as e:
            logging.error(f"API伺服器啟動失敗: {e}\n{traceback.format_exc()}")
    
    def shutdown(self):
        """優雅關閉伺服器 - 增強版"""
        try:
            logging.info("正在關閉伺服器...")
            self.shutdown_event.set()
            self.server_running = False
            
            # 關閉數據塊更新線程
            if self.data_block:
                self.data_block.shutdown()
            
            # 關閉連接池
            if hasattr(self, 'connection_pool'):
                self.connection_pool.shutdown(wait=True, timeout=5)
            
            # 保存註解
            self.save_comments()
            
            # 等待健康檢查線程結束
            if hasattr(self, 'health_thread') and self.health_thread.is_alive():
                self.health_thread.join(timeout=2)
            
            logging.info("伺服器已安全關閉")
        except Exception as e:
            logging.error(f"關閉伺服器時發生錯誤: {e}")
    
    def run(self):
        """主運行方法 - 增強版"""
        try:
            logging.info("=== Modbus TCP Server 啟動 (高頻優化版本) ===")
            logging.info(f"Python 版本: {sys.version}")
            logging.info(f"版本: 1.1.0 - 高頻訪問優化")
            
            # 檢查端口是否可用
            if not self.check_port_available(self.server_port):
                logging.error(f"Modbus TCP 端口 {self.server_port} 已被佔用")
                return
            
            if not self.check_port_available(self.api_port):
                logging.error(f"API 端口 {self.api_port} 已被佔用")
                return
            
            # 初始化測試數據
            self.initialize_test_data()
            
            # 啟動API伺服器 (在單獨線程中)
            api_thread = threading.Thread(target=self.start_api_server, daemon=True, name="APIServer")
            api_thread.start()
            
            # 等待API伺服器啟動
            time.sleep(2)
            
            # 啟動Modbus伺服器 (主線程，會阻塞)
            self.start_modbus_server()
            
        except KeyboardInterrupt:
            logging.info("收到中斷信號，正在關閉...")
        except Exception as e:
            logging.error(f"伺服器運行錯誤: {e}\n{traceback.format_exc()}")
        finally:
            self.shutdown()

    def initialize_test_data(self):
        """初始化測試數據 - 使用無符號範圍"""
        try:
            # 設定一些測試值 (無符號 0-65535)
            test_data = {
                0: 100,     # 地址0 = 100
                1: 200,     # 地址1 = 200
                10: 1000,   # 地址10 = 1000
                50: 5000,   # 地址50 = 5000
                100: 12345, # 地址100 = 12345
                200: 32768, # 地址200 = 32768 (超過有符號範圍但在無符號範圍內)
                500: 65535, # 地址500 = 65535 (最大無符號值)
                999: 40000  # 地址999 = 40000
            }
            
            for addr, value in test_data.items():
                self.write_register(addr, value)
            
            # 設定一些測試註解
            test_comments = {
                0: "溫度感測器",
                1: "濕度感測器", 
                10: "馬達轉速",
                50: "壓力數值",
                100: "測試數據",
                200: "高數值測試",
                500: "最大值測試",
                999: "邊界測試"
            }
            
            for addr, comment in test_comments.items():
                self.register_comments[str(addr)] = comment
            
            self.save_comments()
            logging.info("測試數據和註解初始化完成 (無符號 0-65535 範圍)")
        except Exception as e:
            logging.error(f"初始化測試數據失敗: {e}")
    
    def check_port_available(self, port):
        """檢查端口是否可用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return True
        except OSError:
            return False

def main():
    """主函數 - 高頻優化版本"""
    try:
        # 設定日誌
        setup_logging()
        
        # 打印啟動資訊
        print("=" * 70)
        print("  Modbus TCP Server - 高頻訪問優化版本")
        print("=" * 70)
        print(f"  版本: 1.1.0")
        print(f"  數值範圍: 0-65535 (無符號 16 位)")
        print(f"  Modbus TCP 埠: 502")
        print(f"  API 服務埠: 8001")
        print(f"  API 網址: http://localhost:8001/api/status")
        print(f"  健康檢查: http://localhost:8001/api/health")
        print("=" * 70)
        print("  🚀 新功能:")
        print("    • 線程安全的暫存器操作")
        print("    • 連接池管理 (最大20個並發)")
        print("    • 頻率限制 (10請求/秒/IP)")
        print("    • 後台更新隊列處理")
        print("    • 自動健康檢查")
        print("    • 性能統計監控")
        print("=" * 70)
        print("  按 Ctrl+C 可安全關閉伺服器")
        print("=" * 70)
        
        # 創建並運行伺服器
        server = ModbusTCPServer()
        server.run()
        
    except Exception as e:
        logging.error(f"應用程式啟動失敗: {e}\n{traceback.format_exc()}")
        print(f"\n❌ 啟動失敗: {e}")
        print("請檢查 modbus_server.log 檔案獲取詳細錯誤資訊")
        input("按 Enter 鍵退出...")
        sys.exit(1)

if __name__ == "__main__":
    main()