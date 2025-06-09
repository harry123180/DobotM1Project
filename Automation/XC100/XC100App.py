"""
XC100App.py - 基於XC100_Manager的Flask Web應用
實現完整的握手機制和Web界面控制
"""
from flask import Flask, render_template, request, jsonify
import logging
import time
import threading
from datetime import datetime
from typing import Dict, Any

# 導入XC100_Manager (假設已存在)
from XC100_Manager import XC100_Manager

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'xc100-app-secret-key'

class XC100WebController:
    """XC100 Web控制器 - 整合XC100_Manager和握手機制"""
    
    def __init__(self):
        # XC100管理器
        self.xc100 = XC100_Manager()
        
        # 外部控制模式
        self.external_control_mode = False
        
        # 握手機制暫存器 (Modbus TCP協議)
        self.handshake_registers = {
            "control_register": 0x500,      # 控制暫存器
            "param_register_low": 0x501,    # 參數暫存器低位
            "param_register_high": 0x502,   # 參數暫存器高位  
            "status_register": 0x503,       # 狀態暫存器
        }
        
        # 握手狀態
        self.handshake_status = {
            "ready": False,          # Bit 0
            "running": False,        # Bit 1
            "alarm": False,          # Bit 2
            "initialized": False     # Bit 3
        }
        
        # 統計資訊
        self.stats = {
            "commands_sent": 0,
            "successful_commands": 0,
            "connection_errors": 0,
            "last_command_time": None,
            "uptime_start": datetime.now()
        }
        
        # 握手監控執行緒
        self.handshake_monitoring = False
        self.handshake_thread = None
        
    def start_handshake_monitoring(self):
        """啟動握手機制監控"""
        self.handshake_monitoring = True
        self.handshake_thread = threading.Thread(target=self._handshake_monitor_loop)
        self.handshake_thread.daemon = True
        self.handshake_thread.start()
        logger.info("握手機制監控已啟動")
    
    def stop_handshake_monitoring(self):
        """停止握手機制監控"""
        self.handshake_monitoring = False
        if self.handshake_thread:
            self.handshake_thread.join(timeout=1)
        logger.info("握手機制監控已停止")
    
    def _handshake_monitor_loop(self):
        """握手機制監控執行緒"""
        while self.handshake_monitoring:
            try:
                self._update_handshake_status()
                self._process_handshake_commands()
                time.sleep(0.1)  # 100ms週期
            except Exception as e:
                logger.error(f"握手監控錯誤: {e}")
                time.sleep(1)
    
    def _update_handshake_status(self):
        """更新握手狀態暫存器"""
        if not self.xc100.is_connected:
            self.handshake_status.update({
                "ready": False,
                "running": False, 
                "alarm": True,
                "initialized": False
            })
            return
        
        # 從XC100_Manager獲取狀態
        device_status = self.xc100.get_status()
        
        # 更新握手狀態
        self.handshake_status.update({
            "ready": device_status.get("ready", False),
            "running": device_status.get("running", False),
            "alarm": device_status.get("alarm_status", 0) != 0,
            "initialized": device_status.get("initialized", False)
        })
        
        # 寫入狀態暫存器 (模擬)
        status_value = (
            (1 if self.handshake_status["ready"] else 0) |
            (2 if self.handshake_status["running"] else 0) |
            (4 if self.handshake_status["alarm"] else 0) |
            (8 if self.handshake_status["initialized"] else 0)
        )
        
        # 在實際應用中，這裡應該寫入到Modbus暫存器
        # self.xc100._write_register(self.handshake_registers["status_register"], status_value)
    
    def _process_handshake_commands(self):
        """處理握手控制命令"""
        if not self.xc100.is_connected or not self.external_control_mode:
            return
        
        try:
            # 讀取控制暫存器 (模擬)
            # 在實際應用中應該從Modbus讀取
            # control_value = self.xc100.client.read_holding_registers(
            #     self.handshake_registers["control_register"], 1, slave=self.xc100.station_id
            # ).registers[0]
            
            # 這裡模擬控制命令處理
            # 實際應用中需要根據讀取到的控制值執行相應動作
            pass
            
        except Exception as e:
            logger.error(f"處理握手命令錯誤: {e}")
    
    def execute_handshake_command(self, command: int, position_mm: float = None) -> Dict[str, Any]:
        """執行握手命令 (外部調用接口)"""
        try:
            self.stats["commands_sent"] += 1
            
            # 檢查Ready狀態
            if not self.handshake_status["ready"]:
                return {
                    "success": False,
                    "message": f"設備未就緒 (Ready={self.handshake_status['ready']}, Alarm={self.handshake_status['alarm']})"
                }
            
            # 執行命令
            result = None
            if command == 0:
                # 清除控制指令
                result = {"success": True, "message": "控制指令已清除"}
                
            elif command == 8:
                # 移動到參數暫存器位置
                if position_mm is not None:
                    result = self.xc100.move_absolute(position_mm, wait_completion=False)
                else:
                    result = {"success": False, "message": "缺少位置參數"}
                    
            elif command == 16:
                # 原點賦歸
                result = self.xc100.home_return(wait_completion=False)
                
            elif command == 32:
                # 重新初始化
                result = self.xc100.initialize_device()
                
            else:
                result = {"success": False, "message": f"未知控制命令: {command}"}
            
            if result and result["success"]:
                self.stats["successful_commands"] += 1
                self.stats["last_command_time"] = datetime.now().isoformat()
            
            return result
            
        except Exception as e:
            logger.error(f"執行握手命令錯誤: {e}")
            return {"success": False, "message": f"命令執行錯誤: {str(e)}"}

# 全域控制器實例
controller = XC100WebController()

@app.route('/')
def index():
    """主頁面"""
    return render_template('index.html')

@app.route('/api/scan_ports')
def scan_ports():
    """掃描COM口"""
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        port_list = []
        
        for port in ports:
            port_list.append({
                "device": port.device,
                "description": port.description,
                "hwid": getattr(port, 'hwid', 'Unknown')
            })
        
        logger.info(f"掃描到 {len(port_list)} 個COM口")
        return jsonify({"ports": port_list})
    except Exception as e:
        logger.error(f"掃描COM口錯誤: {e}")
        return jsonify({"ports": []})

@app.route('/api/connect', methods=['POST'])
def connect():
    """連接設備"""
    data = request.get_json()
    port = data.get('port')
    baudrate = int(data.get('baudrate', 115200))
    station_id = int(data.get('station_id', 2))
    
    try:
        result = controller.xc100.connect(port, baudrate, station_id)
        
        if result["success"]:
            # 啟動握手機制監控
            controller.start_handshake_monitoring()
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"連接錯誤: {e}")
        return jsonify({"success": False, "message": f"連接錯誤: {str(e)}"})

@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    """斷開連線"""
    try:
        controller.stop_handshake_monitoring()
        controller.xc100.disconnect()
        return jsonify({"success": True, "message": "已斷開連線"})
    except Exception as e:
        logger.error(f"斷線錯誤: {e}")
        return jsonify({"success": False, "message": f"斷線錯誤: {str(e)}"})

@app.route('/api/status')
def get_status():
    """獲取設備狀態"""
    try:
        device_status = controller.xc100.get_status()
        
        # 計算運行時間
        uptime = datetime.now() - controller.stats["uptime_start"]
        
        return jsonify({
            "connected": controller.xc100.is_connected,
            "external_control": controller.external_control_mode,
            "device_status": device_status,
            "handshake_status": controller.handshake_status,
            "stats": {
                **controller.stats,
                "uptime_seconds": int(uptime.total_seconds()),
                "uptime_formatted": str(uptime).split('.')[0]
            },
            "registers": controller.handshake_registers
        })
    except Exception as e:
        logger.error(f"獲取狀態錯誤: {e}")
        return jsonify({
            "connected": False,
            "external_control": False,
            "device_status": {},
            "handshake_status": {"ready": False, "running": False, "alarm": True, "initialized": False},
            "stats": controller.stats,
            "registers": controller.handshake_registers
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

# === 外部控制API (握手機制) ===

@app.route('/api/handshake/move', methods=['POST'])
def handshake_move():
    """握手機制：移動到指定位置"""
    data = request.get_json()
    position_mm = float(data.get('position', 0))
    
    result = controller.execute_handshake_command(8, position_mm)
    return jsonify(result)

@app.route('/api/handshake/home', methods=['POST'])
def handshake_home():
    """握手機制：原點賦歸"""
    result = controller.execute_handshake_command(16)
    return jsonify(result)

@app.route('/api/handshake/clear', methods=['POST'])
def handshake_clear():
    """握手機制：清除控制"""
    result = controller.execute_handshake_command(0)
    return jsonify(result)

@app.route('/api/handshake/initialize', methods=['POST'])
def handshake_initialize():
    """握手機制：重新初始化"""
    result = controller.execute_handshake_command(32)
    return jsonify(result)

@app.route('/api/handshake/write_register', methods=['POST'])
def write_handshake_register():
    """握手機制：寫入控制暫存器"""
    data = request.get_json()
    command = int(data.get('command', 0))
    position_mm = data.get('position', None)
    
    if position_mm is not None:
        position_mm = float(position_mm)
    
    result = controller.execute_handshake_command(command, position_mm)
    return jsonify(result)

# === 手動控制API ===

@app.route('/api/manual/move', methods=['POST'])
def manual_move():
    """手動控制移動"""
    if controller.external_control_mode:
        return jsonify({"success": False, "message": "外部控制情況下無法手動控制"})
    
    data = request.get_json()
    move_type = data.get('type')
    value = float(data.get('value', 0))
    
    try:
        if move_type == "relative":
            result = controller.xc100.move_relative(value)
        elif move_type == "absolute":
            result = controller.xc100.move_absolute(value)
        else:
            result = {"success": False, "message": "未知移動類型"}
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": f"移動錯誤: {str(e)}"})

@app.route('/api/manual/home', methods=['POST'])
def manual_home():
    """手動控制原點賦歸"""
    if controller.external_control_mode:
        return jsonify({"success": False, "message": "外部控制情況下無法手動控制"})
    
    try:
        result = controller.xc100.home_return()
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": f"原點賦歸錯誤: {str(e)}"})

@app.route('/api/manual/clear', methods=['POST'])
def manual_clear():
    """手動清除控制"""
    if controller.external_control_mode:
        return jsonify({"success": False, "message": "外部控制情況下無法手動控制"})
    
    try:
        # 手動模式下的清除操作
        result = controller.xc100.clear_alarm()
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": f"清除錯誤: {str(e)}"})

@app.route('/api/servo', methods=['POST'])
def servo_control():
    """伺服控制"""
    data = request.get_json()
    state = data.get('state')
    
    try:
        if state == "on":
            result = controller.xc100.servo_on()
        elif state == "off":
            result = controller.xc100.servo_off()
        else:
            result = {"success": False, "message": "未知伺服狀態"}
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": f"伺服控制錯誤: {str(e)}"})

@app.route('/api/emergency_stop', methods=['POST'])
def emergency_stop():
    """緊急停止"""
    try:
        result = controller.xc100.emergency_stop()
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": f"緊急停止錯誤: {str(e)}"})

@app.route('/api/initialize', methods=['POST'])
def initialize_device():
    """初始化設備"""
    try:
        result = controller.xc100.initialize_device()
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": f"初始化錯誤: {str(e)}"})

# === 高級功能API ===

@app.route('/api/move_sequence', methods=['POST'])
def move_sequence():
    """執行移動序列"""
    data = request.get_json()
    positions = data.get('positions', [])
    wait_each = data.get('wait_each', True)
    
    try:
        result = controller.xc100.move_to_positions(positions, wait_each)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": f"移動序列錯誤: {str(e)}"})

@app.route('/api/get_error_info/<int:error_code>')
def get_error_info(error_code):
    """獲取錯誤代碼資訊"""
    try:
        description = controller.xc100.get_error_description(error_code)
        return jsonify({"error_code": error_code, "description": description})
    except Exception as e:
        return jsonify({"error": f"獲取錯誤資訊失敗: {str(e)}"})

@app.route('/api/get_alarm_info/<int:alarm_code>')
def get_alarm_info(alarm_code):
    """獲取警報代碼資訊"""
    try:
        description = controller.xc100.get_alarm_description(alarm_code)
        return jsonify({"alarm_code": alarm_code, "description": description})
    except Exception as e:
        return jsonify({"error": f"獲取警報資訊失敗: {str(e)}"})

# === 系統資訊API ===

@app.route('/api/system_info')
def system_info():
    """獲取系統資訊"""
    try:
        import platform
        import psutil
        
        return jsonify({
            "system": {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent
            },
            "application": {
                "name": "XC100 Web Controller",
                "version": "1.0.0",
                "port": 5007
            }
        })
    except Exception as e:
        return jsonify({"error": f"獲取系統資訊失敗: {str(e)}"})

if __name__ == '__main__':
    print("🎛️ XC100 Web Controller 正在啟動...")
    print("📡 訪問地址: http://localhost:5007")
    print("🤝 支援握手機制的Modbus TCP控制協議")
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5007, use_reloader=False)
    except KeyboardInterrupt:
        print("\n🛑 正在關閉伺服器...")
        controller.stop_handshake_monitoring()
        controller.xc100.disconnect()
        print("✅ 伺服器已安全關閉")