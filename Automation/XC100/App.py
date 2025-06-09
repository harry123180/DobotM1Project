#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XC100 可視化控制應用 - 分離版本
基於Flask的Web界面，通過Modbus TCP與XCModule通訊
適配XC100硬體補償模式
"""

import json
import time
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from pymodbus.client import ModbusTcpClient
import logging

# 禁用Flask的日誌輸出
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

class XCApp:
    """XC100 Web應用 - 分離版本"""
    
    def __init__(self, config_file="xc_app_config.json"):
        self.config_file = config_file
        self.config = self.load_config()
        
        # Modbus TCP客戶端
        self.modbus_client = None
        self.connected = False
        self.connection_retry_count = 0
        self.max_retry_count = 5
        
        # 設備狀態
        self.device_status = {
            "state": "未知",
            "servo_status": False,
            "error_code": 0,
            "current_position": 0,
            "target_position": 0,
            "command_executing": False,
            "position_A": 400,
            "position_B": 2682,
            "module_connected": False,
            "communication_health": 100,  # 通訊健康度
            "last_update": datetime.now().strftime("%H:%M:%S")
        }
        
        # 應用狀態
        self.app_stats = {
            "total_commands": 0,
            "successful_commands": 0,
            "failed_commands": 0,
            "uptime_start": datetime.now(),
            "communication_errors": 0
        }
        
        # Flask應用
        self.app = Flask(__name__)
        self.app.secret_key = 'xc100_app_secret_key_v2'
        self.setup_routes()
        
        # 監控線程
        self.monitor_thread = None
        self.monitor_running = False
        
        print("🚀 XC100 Web應用初始化完成（分離版本）")
    
    def load_config(self):
        """載入配置"""
        default_config = {
            "modbus_tcp": {
                "host": "localhost",
                "port": 502,
                "unit_id": 1,
                "timeout": 5,  # 增加超時時間適配慢速模式
                "retry_on_failure": True,
                "max_retries": 3
            },
            "web_server": {
                "host": "0.0.0.0",
                "port": 5007,
                "debug": False
            },
            "update_interval": 2.0,  # 配合XCModule的慢速模式
            "ui_settings": {
                "auto_refresh": True,
                "show_debug_info": True,
                "command_confirmation": False
            }
        }
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                # 深度合併配置
                for key, value in default_config.items():
                    if key not in loaded_config:
                        loaded_config[key] = value
                    elif isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            if sub_key not in loaded_config[key]:
                                loaded_config[key][sub_key] = sub_value
                return loaded_config
        except FileNotFoundError:
            self.save_config(default_config)
        except Exception as e:
            print(f"載入配置失敗: {e}")
            
        return default_config
    
    def save_config(self, config=None):
        """保存配置"""
        try:
            config_to_save = config or self.config
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置失敗: {e}")
    
    def connect_modbus(self):
        """連線到XCModule with retry logic"""
        try:
            modbus_config = self.config["modbus_tcp"]
            
            if self.modbus_client:
                try:
                    self.modbus_client.close()
                except:
                    pass
            
            self.modbus_client = ModbusTcpClient(
                host=modbus_config["host"],
                port=modbus_config["port"],
                timeout=modbus_config["timeout"]
            )
            
            if self.modbus_client.connect():
                self.connected = True
                self.connection_retry_count = 0
                print(f"✅ 已連線到XCModule: {modbus_config['host']}:{modbus_config['port']}")
                return True
            else:
                self.connected = False
                self.connection_retry_count += 1
                print(f"❌ 連線XCModule失敗 (重試 {self.connection_retry_count}/{self.max_retry_count})")
                return False
                
        except Exception as e:
            self.connected = False
            self.connection_retry_count += 1
            print(f"❌ 連線XCModule異常 (重試 {self.connection_retry_count}/{self.max_retry_count}): {e}")
            return False
    
    def disconnect_modbus(self):
        """斷開Modbus連線"""
        try:
            if self.modbus_client and self.connected:
                self.modbus_client.close()
                self.connected = False
                print("🔌 已斷開XCModule連線")
        except Exception as e:
            print(f"斷開連線異常: {e}")
    
    def read_device_status(self):
        """讀取設備狀態 with error handling"""
        if not self.connected:
            return False
        
        try:
            unit_id = self.config["modbus_tcp"]["unit_id"]
            
            # 讀取狀態寄存器 (地址0-15)
            result = self.modbus_client.read_holding_registers(address=0, count=16, slave=unit_id)
            
            if not result.isError():
                registers = result.registers
                
                # 狀態映射
                state_map = {
                    0: "閒置", 1: "移動中", 2: "原點復歸中", 
                    3: "錯誤", 4: "Servo關閉", 5: "緊急停止"
                }
                
                # 錯誤代碼描述
                error_map = {
                    0: "正常",
                    1: "在動作中接收動作指令",
                    2: "上下限錯誤", 
                    3: "位置錯誤",
                    4: "格式錯誤",
                    5: "控制模式錯誤",
                    6: "斷電重開",
                    7: "初始化未完成",
                    8: "Servo ON/OFF 錯誤",
                    9: "LOCK",
                    10: "軟體極限",
                    11: "參數寫入權限不足",
                    12: "原點復歸未完成",
                    13: "剎車已解除",
                    999: "通訊異常"
                }
                
                self.device_status.update({
                    "state": state_map.get(registers[0], f"未知({registers[0]})"),
                    "error_code": registers[1],
                    "error_description": error_map.get(registers[1], f"未知錯誤({registers[1]})"),
                    "servo_status": registers[2] == 1,
                    "current_position": (registers[4] << 16) | registers[3],
                    "target_position": (registers[6] << 16) | registers[5],
                    "command_executing": registers[10] == 1,
                    "position_A": (registers[12] << 16) | registers[11],
                    "position_B": (registers[14] << 16) | registers[13],
                    "module_connected": registers[15] == 1,
                    "last_update": datetime.now().strftime("%H:%M:%S")
                })
                
                # 計算通訊健康度
                if self.app_stats["communication_errors"] == 0:
                    self.device_status["communication_health"] = 100
                else:
                    health = max(0, 100 - (self.app_stats["communication_errors"] * 10))
                    self.device_status["communication_health"] = health
                
                return True
                
        except Exception as e:
            self.app_stats["communication_errors"] += 1
            print(f"讀取設備狀態異常: {e}")
            self.device_status["module_connected"] = False
            return False
    
    def send_command(self, command, param1=0, param2=0):
        """發送指令到XCModule with enhanced error handling"""
        if not self.connected:
            self.app_stats["failed_commands"] += 1
            return False
        
        try:
            self.app_stats["total_commands"] += 1
            unit_id = self.config["modbus_tcp"]["unit_id"]
            
            # 先檢查是否有指令正在執行
            status_result = self.modbus_client.read_holding_registers(address=10, count=1, slave=unit_id)
            if not status_result.isError() and status_result.registers[0] == 1:
                print("⚠️ 有指令正在執行中，請稍候")
                self.app_stats["failed_commands"] += 1
                return False
            
            # 寫入指令寄存器 (地址7-9)
            values = [command, param1, param2]
            result = self.modbus_client.write_registers(address=7, values=values, slave=unit_id)
            
            if not result.isError():
                command_names = {
                    1: 'Servo ON', 2: 'Servo OFF', 3: '原點復歸',
                    4: '絕對移動', 6: '緊急停止', 7: '錯誤重置'
                }
                print(f"✅ 指令發送成功: {command_names.get(command, f'指令{command}')}")
                self.app_stats["successful_commands"] += 1
                return True
            else:
                print(f"❌ 指令發送失敗: {result}")
                self.app_stats["failed_commands"] += 1
                return False
                
        except Exception as e:
            print(f"發送指令異常: {e}")
            self.app_stats["failed_commands"] += 1
            self.app_stats["communication_errors"] += 1
            return False
    
    def update_position(self, pos_type, position):
        """更新位置設定 with validation"""
        if not self.connected:
            return False
        
        try:
            # 位置範圍檢查
            if not (-999999 <= position <= 999999):
                print(f"❌ 位置超出範圍: {position}")
                return False
            
            unit_id = self.config["modbus_tcp"]["unit_id"]
            
            pos_low = position & 0xFFFF
            pos_high = (position >> 16) & 0xFFFF
            
            if pos_type == 'A':
                # 更新A點位置 (地址11-12)
                result = self.modbus_client.write_registers(address=11, values=[pos_low, pos_high], slave=unit_id)
            elif pos_type == 'B':
                # 更新B點位置 (地址13-14)
                result = self.modbus_client.write_registers(address=13, values=[pos_low, pos_high], slave=unit_id)
            else:
                return False
            
            if not result.isError():
                print(f"✅ {pos_type}點位置已更新為: {position}")
                return True
            else:
                print(f"❌ 位置更新失敗: {result}")
                return False
            
        except Exception as e:
            print(f"更新位置異常: {e}")
            return False
    
    def monitor_loop(self):
        """監控循環 with auto-reconnect"""
        print("🔄 開始設備狀態監控")
        
        while self.monitor_running:
            try:
                if self.connected:
                    if not self.read_device_status():
                        # 讀取失敗，可能需要重連
                        self.connected = False
                else:
                    # 嘗試重新連線
                    if self.connection_retry_count < self.max_retry_count:
                        print(f"🔄 嘗試重新連線... ({self.connection_retry_count + 1}/{self.max_retry_count})")
                        self.connect_modbus()
                    elif self.connection_retry_count >= self.max_retry_count:
                        print("⚠️ 達到最大重試次數，停止重連嘗試")
                        time.sleep(10)  # 等待10秒後重置重試計數
                        self.connection_retry_count = 0
                
                time.sleep(self.config["update_interval"])
                
            except Exception as e:
                print(f"監控循環異常: {e}")
                time.sleep(5)
        
        print("🛑 設備狀態監控停止")
    
    def start_monitoring(self):
        """開始監控"""
        if not self.monitor_running:
            self.monitor_running = True
            self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.monitor_thread.start()
    
    def stop_monitoring(self):
        """停止監控"""
        self.monitor_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=3)
    
    def get_app_statistics(self):
        """獲取應用統計"""
        uptime = datetime.now() - self.app_stats["uptime_start"]
        success_rate = 0
        if self.app_stats["total_commands"] > 0:
            success_rate = (self.app_stats["successful_commands"] / self.app_stats["total_commands"]) * 100
        
        return {
            "uptime": str(uptime).split('.')[0],  # 移除微秒
            "total_commands": self.app_stats["total_commands"],
            "successful_commands": self.app_stats["successful_commands"],
            "failed_commands": self.app_stats["failed_commands"],
            "success_rate": f"{success_rate:.1f}%",
            "communication_errors": self.app_stats["communication_errors"]
        }
    
    def setup_routes(self):
        """設置Flask路由 with enhanced features"""
        
        @self.app.route('/')
        def index():
            """主頁"""
            return render_template('index.html')
        
        @self.app.route('/api/status')
        def get_status():
            """獲取設備狀態API with statistics"""
            return jsonify({
                "success": True,
                "connected": self.connected,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data": self.device_status,
                "statistics": self.get_app_statistics()
            })
        
        @self.app.route('/api/command', methods=['POST'])
        def send_command_api():
            """發送指令API with validation"""
            try:
                data = request.get_json()
                command = data.get('command', 0)
                param1 = data.get('param1', 0)
                param2 = data.get('param2', 0)
                
                # 指令驗證
                valid_commands = [1, 2, 3, 4, 6, 7]
                if command not in valid_commands:
                    return jsonify({"success": False, "message": f"無效的指令代碼: {command}"})
                
                if self.send_command(command, param1, param2):
                    return jsonify({"success": True, "message": "指令發送成功"})
                else:
                    return jsonify({"success": False, "message": "指令發送失敗"})
                    
            except Exception as e:
                return jsonify({"success": False, "message": f"發送指令異常: {e}"})
        
        @self.app.route('/api/position', methods=['POST'])
        def update_position_api():
            """更新位置API with validation"""
            try:
                data = request.get_json()
                pos_type = data.get('type')  # 'A' or 'B'
                position = int(data.get('position', 0))
                
                if pos_type not in ['A', 'B']:
                    return jsonify({"success": False, "message": "無效的位置類型"})
                
                if self.update_position(pos_type, position):
                    return jsonify({"success": True, "message": f"{pos_type}點位置更新成功"})
                else:
                    return jsonify({"success": False, "message": "位置更新失敗"})
                    
            except ValueError:
                return jsonify({"success": False, "message": "位置必須是數字"})
            except Exception as e:
                return jsonify({"success": False, "message": f"更新位置異常: {e}"})
        
        @self.app.route('/api/connect', methods=['POST'])
        def connect_api():
            """連線API with retry reset"""
            self.connection_retry_count = 0  # 重置重試計數
            if self.connect_modbus():
                return jsonify({"success": True, "message": "連線成功"})
            else:
                return jsonify({"success": False, "message": "連線失敗"})
        
        @self.app.route('/api/disconnect', methods=['POST'])
        def disconnect_api():
            """斷開連線API"""
            self.disconnect_modbus()
            return jsonify({"success": True, "message": "已斷開連線"})
        
        @self.app.route('/api/statistics')
        def get_statistics_api():
            """獲取統計信息API"""
            return jsonify({
                "success": True,
                "statistics": self.get_app_statistics(),
                "config": {
                    "update_interval": self.config["update_interval"],
                    "modbus_timeout": self.config["modbus_tcp"]["timeout"],
                    "auto_retry": self.config["modbus_tcp"]["retry_on_failure"]
                }
            })
        
        @self.app.route('/api/reset_stats', methods=['POST'])
        def reset_statistics():
            """重置統計信息"""
            self.app_stats = {
                "total_commands": 0,
                "successful_commands": 0,
                "failed_commands": 0,
                "uptime_start": datetime.now(),
                "communication_errors": 0
            }
            return jsonify({"success": True, "message": "統計信息已重置"})
    
    def run(self):
        """運行Web應用 with enhanced error handling"""
        # 檢查XCModule是否在運行
        if not self.connect_modbus():
            print("❌ 無法連線到XCModule！")
            print("請確保XCModule.py正在運行，然後重試。")
            print("\n🔧 故障排除步驟：")
            print("1. 確認XCModule.py已啟動並顯示'模組啟動成功'")
            print("2. 檢查Modbus TCP Server是否在localhost:5020運行")
            print("3. 確認防火牆沒有阻擋端口5020")
            print("4. 檢查XC100設備是否正確連接")
            
            # 仍然啟動Web服務器，但顯示離線狀態
            print("\n⚠️ 將以離線模式啟動Web界面...")
        
        # 檢查templates目錄是否存在
        import os
        if not os.path.exists('templates'):
            print("❌ 找不到templates目錄！")
            print("請確保templates/index.html文件存在")
            return
        
        if not os.path.exists('templates/index.html'):
            print("❌ 找不到templates/index.html文件！")
            print("請將index.html放置在templates目錄中")
            return
        
        # 開始監控（即使離線也啟動，會自動重連）
        self.start_monitoring()
        
        try:
            web_config = self.config["web_server"]
            print(f"\n🚀 XC100 Web應用啟動（分離版本）")
            print(f"📱 Web界面: http://{web_config['host']}:{web_config['port']}")
            print(f"🔧 配置文件: {self.config_file}")
            print(f"⏱️ 更新間隔: {self.config['update_interval']}秒")
            print(f"🛡️ 硬體補償模式: 已啟用")
            print(f"📁 模板文件: templates/index.html")
            print("\n📊 新功能:")
            print("  • 自動重連機制")
            print("  • 通訊健康度監控")
            print("  • 增強的錯誤處理")
            print("  • 詳細的統計信息")
            print("  • 優化的慢速通訊模式")
            print("  • 分離式架構設計")
            print("\n按 Ctrl+C 停止應用")
            
            # 啟動Flask應用
            self.app.run(
                host=web_config["host"],
                port=web_config["port"],
                debug=web_config["debug"],
                threaded=True  # 啟用多線程支援
            )
            
        except KeyboardInterrupt:
            print("\n\n🛑 正在停止應用...")
        except Exception as e:
            print(f"\n❌ Web應用運行異常: {e}")
        finally:
            self.stop_monitoring()
            self.disconnect_modbus()
            print("✅ Web應用已停止")

def main():
    """主函數 with command line arguments"""
    import argparse
    
    # 命令行參數解析
    parser = argparse.ArgumentParser(description='XC100 Web控制應用')
    parser.add_argument('--config', type=str, default="xc_app_config.json", help='配置文件路徑')
    parser.add_argument('--port', type=int, help='Web服務器端口 (默認: 5000)')
    parser.add_argument('--host', type=str, help='Web服務器主機 (默認: 127.0.0.1)')
    parser.add_argument('--modbus-host', type=str, help='XCModule主機地址 (默認: localhost)')
    parser.add_argument('--modbus-port', type=int, help='XCModule端口 (默認: 5020)')
    parser.add_argument('--debug', action='store_true', help='啟用調試模式')
    args = parser.parse_args()
    
    print("🎮 XC100 Web控制應用 - 分離版本 v2.0")
    print("=" * 50)
    
    # 創建應用實例
    app = XCApp(args.config)
    
    # 覆蓋命令行參數
    if args.port:
        app.config["web_server"]["port"] = args.port
    if args.host:
        app.config["web_server"]["host"] = args.host
    if args.modbus_host:
        app.config["modbus_tcp"]["host"] = args.modbus_host
    if args.modbus_port:
        app.config["modbus_tcp"]["port"] = args.modbus_port
    if args.debug:
        app.config["web_server"]["debug"] = True
    
    # 保存更新後的配置
    app.save_config()
    
    # 運行應用
    app.run()

if __name__ == "__main__":
    main()