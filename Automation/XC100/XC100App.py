"""
Enhanced XC100 Web Controller Application
支援完整的Modbus TCP協議和握手機制
"""
from flask import Flask, render_template, request, jsonify
from pymodbus.client import ModbusSerialClient
from pymodbus import ModbusException
import threading
import time
import json
import serial.tools.list_ports
from typing import Optional, Dict, Any
import logging
from datetime import datetime

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'xc100-controller-secret-key'

class EnhancedModbusProtocol:
    """增強的Modbus協議處理類"""
    
    def __init__(self, client: ModbusSerialClient, station_id: int):
        self.client = client
        self.station_id = station_id
        
        # 自定義暫存器地址
        self.CONTROL_REGISTER = 0x500
        self.PARAM_REGISTER_LOW = 0x501
        self.PARAM_REGISTER_HIGH = 0x502
        self.STATUS_REGISTER = 0x503
        
        # 狀態機
        self.state_lock = threading.Lock()
        self.last_command_time = 0
        
    def read_status_register(self) -> Optional[int]:
        """讀取狀態暫存器"""
        try:
            result = self.client.read_holding_registers(
                address=self.STATUS_REGISTER,
                count=1,
                slave=self.station_id
            )
            if not result.isError():
                return result.registers[0]
            return None
        except Exception as e:
            logger.error(f"讀取狀態暫存器失敗: {e}")
            return None
    
    def write_control_register(self, value: int) -> bool:
        """寫入控制暫存器"""
        try:
            result = self.client.write_register(
                address=self.CONTROL_REGISTER,
                value=value,
                slave=self.station_id
            )
            success = not result.isError()
            if success:
                self.last_command_time = time.time()
                logger.info(f"控制暫存器寫入: {value}")
            return success
        except Exception as e:
            logger.error(f"寫入控制暫存器失敗: {e}")
            return False
    
    def write_param_registers(self, position_mm: float) -> bool:
        """寫入參數暫存器（32位元位置）"""
        try:
            # 轉換為數值 (1數值 = 0.01mm)
            position_value = int(position_mm * 100)
            
            # 處理負數
            if position_value < 0:
                position_value = position_value + 0x100000000
            
            # 分解為兩個16位元
            high_word = (position_value >> 16) & 0xFFFF
            low_word = position_value & 0xFFFF
            
            result = self.client.write_registers(
                address=self.PARAM_REGISTER_LOW,
                values=[high_word, low_word],
                slave=self.station_id
            )
            success = not result.isError()
            if success:
                logger.info(f"參數暫存器寫入: {position_mm}mm ({position_value})")
            return success
        except Exception as e:
            logger.error(f"寫入參數暫存器失敗: {e}")
            return False
    
    def get_device_status(self) -> Dict[str, Any]:
        """獲取設備狀態"""
        status_value = self.read_status_register()
        if status_value is None:
            return {
                "ready": False,
                "running": False,
                "alarm": True,
                "initialized": False,
                "raw_value": 0
            }
        
        return {
            "ready": bool(status_value & 0x01),
            "running": bool(status_value & 0x02),
            "alarm": bool(status_value & 0x04),
            "initialized": bool(status_value & 0x08),
            "raw_value": status_value
        }
    
    def wait_for_ready(self, timeout: float = 10.0) -> bool:
        """等待設備Ready狀態"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_device_status()
            if status["ready"] and not status["alarm"]:
                return True
            time.sleep(0.1)
        
        logger.warning(f"等待Ready狀態超時 ({timeout}秒)")
        return False
    
    def execute_command_with_handshake(self, command: int, position_mm: float = None) -> Dict[str, Any]:
        """使用握手機制執行命令"""
        with self.state_lock:
            try:
                logger.info(f"執行命令: {command}, 位置: {position_mm}")
                
                # 1. 檢查Ready狀態
                status = self.get_device_status()
                if not status["ready"]:
                    return {
                        "success": False,
                        "message": f"設備未就緒 (Ready={status['ready']}, Alarm={status['alarm']})"
                    }
                
                if status["alarm"]:
                    return {
                        "success": False,
                        "message": "設備有警報狀態，無法執行命令"
                    }
                
                # 2. 如果需要，寫入參數
                if position_mm is not None and command == 8:
                    if not self.write_param_registers(position_mm):
                        return {
                            "success": False,
                            "message": "參數設定失敗"
                        }
                    # 等待參數寫入完成
                    time.sleep(0.05)
                
                # 3. 寫入控制命令
                if not self.write_control_register(command):
                    return {
                        "success": False,
                        "message": "控制命令發送失敗"
                    }
                
                # 4. 驗證命令被接受
                time.sleep(0.1)
                new_status = self.get_device_status()
                
                if command != 0:  # 非清除命令時檢查Ready變化
                    if new_status["ready"]:
                        logger.warning("命令發送後Ready狀態未變化，可能未被接受")
                
                command_names = {0: "清除命令", 8: "移動命令", 16: "原點賦歸"}
                command_name = command_names.get(command, f"命令{command}")
                
                return {
                    "success": True,
                    "message": f"{command_name}已成功發送",
                    "status_before": status,
                    "status_after": new_status
                }
                
            except Exception as e:
                logger.error(f"執行命令時發生錯誤: {e}")
                return {
                    "success": False,
                    "message": f"執行命令時發生錯誤: {str(e)}"
                }

class XC100WebController:
    def __init__(self):
        # Modbus客戶端
        self.client: Optional[ModbusSerialClient] = None
        self.protocol: Optional[EnhancedModbusProtocol] = None
        self.is_connected = False
        self.station_id = 3
        
        # 外部控制模式
        self.external_control_mode = False
        
        # 狀態變數
        self.device_status = {
            "action_status": "未連線",
            "alarm_status": "未連線",
            "servo_status": "未連線",
            "current_position": 0.0,
            "ready": False,
            "running": False,
            "alarm": False,
            "initialized": False,
            "last_update": None
        }
        
        # 監控執行緒
        self.monitoring = False
        self.monitor_thread = None
        
        # 連線設定
        self.connection_config = {
            "port": "",
            "baudrate": 115200,
            "station_id": 3
        }
        
        # 統計資訊
        self.stats = {
            "commands_sent": 0,
            "successful_commands": 0,
            "connection_errors": 0,
            "last_command_time": None
        }
    
    def scan_com_ports(self):
        """掃描可用的COM口"""
        try:
            ports = serial.tools.list_ports.comports()
            port_list = []
            
            for port in ports:
                port_list.append({
                    "device": port.device,
                    "description": port.description,
                    "hwid": getattr(port, 'hwid', 'Unknown')
                })
            
            logger.info(f"掃描到 {len(port_list)} 個COM口")
            return port_list
        except Exception as e:
            logger.error(f"掃描COM口錯誤: {e}")
            return []
    
    def connect_device(self, port, baudrate, station_id):
        """連接設備"""
        try:
            if self.is_connected:
                self.disconnect_device()
            
            self.station_id = station_id
            
            # 建立Modbus客戶端
            self.client = ModbusSerialClient(
                port=port,
                baudrate=baudrate,
                timeout=3,
                parity='N',
                stopbits=1,
                bytesize=8
            )
            
            if self.client.connect():
                self.is_connected = True
                self.protocol = EnhancedModbusProtocol(self.client, station_id)
                
                self.connection_config = {
                    "port": port,
                    "baudrate": baudrate,
                    "station_id": station_id
                }
                
                # 初始化控制暫存器
                self.protocol.write_control_register(0)
                
                # 測試連線
                if self.test_connection():
                    self.start_monitoring()
                    logger.info(f"成功連線到 {port}")
                    return {"success": True, "message": f"已連線到 {port}"}
                else:
                    logger.warning("連線成功但無法與XC100通訊")
                    self.start_monitoring()  # 仍然啟動監控
                    return {"success": True, "message": "連線成功但無法讀取XC100狀態，請檢查站號設定"}
            else:
                logger.error(f"無法連線到 {port}")
                return {"success": False, "message": "連線失敗"}
                
        except Exception as e:
            logger.error(f"連線錯誤: {e}")
            return {"success": False, "message": f"連線錯誤: {str(e)}"}
    
    def disconnect_device(self):
        """斷開設備連線"""
        logger.info("正在斷開設備連線")
        self.stop_monitoring()
        
        if self.client:
            self.client.close()
            self.client = None
            self.protocol = None
            
        self.is_connected = False
        self.device_status = {
            "action_status": "未連線",
            "alarm_status": "未連線",
            "servo_status": "未連線",
            "current_position": 0.0,
            "ready": False,
            "running": False,
            "alarm": True,
            "initialized": False,
            "last_update": None
        }
    
    def test_connection(self):
        """測試連線功能"""
        if not self.client or not self.is_connected:
            return False
            
        try:
            # 嘗試讀取控制器型號來測試連線
            result = self.client.read_holding_registers(
                address=0x10E0, count=1, slave=self.station_id
            )
            return not result.isError()
        except (ModbusException, Exception) as e:
            logger.warning(f"測試連線失敗: {e}")
            return False
    
    def start_monitoring(self):
        """啟動狀態監控"""
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self.monitor_status)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        logger.info("狀態監控已啟動")
    
    def stop_monitoring(self):
        """停止狀態監控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        logger.info("狀態監控已停止")
    
    def monitor_status(self):
        """狀態監控執行緒"""
        consecutive_errors = 0
        max_errors = 5
        
        while self.monitoring and self.is_connected:
            try:
                self.read_all_status()
                consecutive_errors = 0
                time.sleep(1.0)
            except Exception as e:
                consecutive_errors += 1
                self.stats["connection_errors"] += 1
                logger.error(f"監控錯誤 ({consecutive_errors}/{max_errors}): {e}")
                
                if consecutive_errors >= max_errors:
                    logger.error("連續錯誤過多，停止監控")
                    self.device_status["alarm"] = True
                    self.device_status["initialized"] = False
                    break
                    
                time.sleep(2)
    
    def read_all_status(self):
        """讀取所有狀態"""
        if not self.client or not self.is_connected:
            return
            
        try:
            # 讀取原始設備狀態
            self.read_device_status()
            
            # 讀取自定義狀態暫存器
            if self.protocol:
                custom_status = self.protocol.get_device_status()
                self.device_status.update(custom_status)
            
            self.device_status["last_update"] = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"讀取狀態錯誤: {e}")
            self.device_status["alarm"] = True
    
    def read_device_status(self):
        """讀取設備原始狀態"""
        try:
            # 讀取動作狀態 (1000H)
            result = self.client.read_holding_registers(
                address=0x1000, count=1, slave=self.station_id
            )
            if not result.isError():
                action_code = result.registers[0]
                action_texts = {0: "停止", 1: "動作中", 2: "異常停止"}
                self.device_status["action_status"] = action_texts.get(action_code, f"未知({action_code})")
            
            # 讀取警報狀態 (1005H)
            result = self.client.read_holding_registers(
                address=0x1005, count=1, slave=self.station_id
            )
            if not result.isError():
                alarm_code = result.registers[0]
                alarm_texts = {
                    0: "無警報", 1: "迴路錯誤", 2: "計數滿", 3: "過速度",
                    4: "增益值調整不良", 5: "過電壓", 6: "初期化異常", 7: "EEPROM異常",
                    8: "主迴路電源電壓不足", 9: "過電流", 10: "回生異常", 11: "緊急停止",
                    12: "馬達斷線", 13: "編碼器斷線", 14: "保護電流值", 15: "電源再投入", 17: "動作逾時"
                }
                self.device_status["alarm_status"] = alarm_texts.get(alarm_code, f"未知警報({alarm_code})")
            
            # 讀取伺服狀態 (100CH)
            result = self.client.read_holding_registers(
                address=0x100C, count=1, slave=self.station_id
            )
            if not result.isError():
                servo_code = result.registers[0]
                servo_texts = {0: "伺服OFF", 1: "伺服ON"}
                self.device_status["servo_status"] = servo_texts.get(servo_code, f"未知({servo_code})")
            
            # 讀取目前位置 (1008H-1009H)
            result = self.client.read_holding_registers(
                address=0x1008, count=2, slave=self.station_id
            )
            if not result.isError():
                position = (result.registers[0] << 16) | result.registers[1]
                if position > 0x7FFFFFFF:
                    position -= 0x100000000
                self.device_status["current_position"] = position * 0.01
                
        except Exception as e:
            logger.error(f"讀取設備狀態錯誤: {e}")
    
    def external_control_move_to_position(self, position_mm):
        """外部控制：移動到指定位置"""
        if not self.is_connected or not self.protocol:
            return {"success": False, "message": "設備未連線"}
        
        self.stats["commands_sent"] += 1
        result = self.protocol.execute_command_with_handshake(8, position_mm)
        
        if result["success"]:
            self.stats["successful_commands"] += 1
            self.stats["last_command_time"] = datetime.now().isoformat()
        
        return result
    
    def external_control_home(self):
        """外部控制：原點賦歸"""
        if not self.is_connected or not self.protocol:
            return {"success": False, "message": "設備未連線"}
        
        self.stats["commands_sent"] += 1
        result = self.protocol.execute_command_with_handshake(16)
        
        if result["success"]:
            self.stats["successful_commands"] += 1
            self.stats["last_command_time"] = datetime.now().isoformat()
        
        return result
    
    def manual_control_move(self, move_type, value):
        """手動控制移動"""
        if self.external_control_mode:
            return {"success": False, "message": "外部控制情況下無法手動控制"}
        
        if not self.is_connected:
            return {"success": False, "message": "設備未連線"}
        
        try:
            pulse_value = int(value * 100)
            high_word = (pulse_value >> 16) & 0xFFFF
            low_word = pulse_value & 0xFFFF
            
            if move_type == "relative":
                if self.write_registers(0x2000, [high_word, low_word]):
                    if self.write_register(0x201E, 0):
                        return {"success": True, "message": f"相對移動指令已發送: {value} mm"}
                    else:
                        return {"success": False, "message": "移動類型設定失敗"}
                else:
                    return {"success": False, "message": "移動量設定失敗"}
                    
            elif move_type == "absolute":
                if self.write_registers(0x2002, [high_word, low_word]):
                    if self.write_register(0x201E, 1):
                        return {"success": True, "message": f"絕對移動指令已發送: {value} mm"}
                    else:
                        return {"success": False, "message": "移動類型設定失敗"}
                else:
                    return {"success": False, "message": "目標位置設定失敗"}
                    
        except Exception as e:
            return {"success": False, "message": f"移動錯誤: {str(e)}"}
    
    def write_register(self, address, value):
        """寫入暫存器"""
        if not self.client or not self.is_connected:
            return False
            
        try:
            result = self.client.write_register(
                address=address, value=value, slave=self.station_id
            )
            return not result.isError()
        except Exception as e:
            logger.error(f"寫入暫存器錯誤: {e}")
            return False
    
    def write_registers(self, address, values):
        """寫入多個暫存器"""
        if not self.client or not self.is_connected:
            return False
            
        try:
            result = self.client.write_registers(
                address=address, values=values, slave=self.station_id
            )
            return not result.isError()
        except Exception as e:
            logger.error(f"寫入多個暫存器錯誤: {e}")
            return False

# 全域控制器實例
controller = XC100WebController()

# Flask路由
@app.route('/')
def index():
    """主頁面"""
    return render_template('index.html')

@app.route('/api/scan_ports')
def scan_ports():
    """掃描COM口"""
    ports = controller.scan_com_ports()
    return jsonify({"ports": ports})

@app.route('/api/connect', methods=['POST'])
def connect():
    """連接設備"""
    data = request.get_json()
    port = data.get('port')
    baudrate = int(data.get('baudrate', 115200))
    station_id = int(data.get('station_id', 3))
    
    result = controller.connect_device(port, baudrate, station_id)
    return jsonify(result)

@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    """斷開連線"""
    controller.disconnect_device()
    return jsonify({"success": True, "message": "已斷開連線"})

@app.route('/api/status')
def get_status():
    """獲取設備狀態"""
    return jsonify({
        "connected": controller.is_connected,
        "external_control": controller.external_control_mode,
        "device_status": controller.device_status,
        "connection_config": controller.connection_config,
        "stats": controller.stats
    })

@app.route('/api/external_control', methods=['POST'])
def toggle_external_control():
    """切換外部控制模式"""
    data = request.get_json()
    controller.external_control_mode = data.get('enabled', False)
    logger.info(f"外部控制模式: {'開啟' if controller.external_control_mode else '關閉'}")
    
    return jsonify({
        "success": True,
        "external_control": controller.external_control_mode,
        "message": f"外部控制模式已{'開啟' if controller.external_control_mode else '關閉'}"
    })

@app.route('/api/external/move', methods=['POST'])
def external_move():
    """外部控制移動"""
    data = request.get_json()
    position_mm = float(data.get('position', 0))
    result = controller.external_control_move_to_position(position_mm)
    return jsonify(result)

@app.route('/api/external/home', methods=['POST'])
def external_home():
    """外部控制原點賦歸"""
    result = controller.external_control_home()
    return jsonify(result)

@app.route('/api/manual/move', methods=['POST'])
def manual_move():
    """手動控制移動"""
    data = request.get_json()
    move_type = data.get('type')
    value = float(data.get('value', 0))
    result = controller.manual_control_move(move_type, value)
    return jsonify(result)

@app.route('/api/emergency_stop', methods=['POST'])
def emergency_stop():
    """緊急停止"""
    try:
        if controller.write_register(0x201E, 9):
            return jsonify({"success": True, "message": "緊急停止指令已發送"})
        else:
            return jsonify({"success": False, "message": "緊急停止指令發送失敗"})
    except Exception as e:
        return jsonify({"success": False, "message": f"緊急停止錯誤: {str(e)}"})

if __name__ == '__main__':
    print("🎛️ XC100 Web Controller 正在啟動...")
    print("📡 訪問地址: http://localhost:5007")
    app.run(debug=True, host='0.0.0.0', port=5007, use_reloader=False)