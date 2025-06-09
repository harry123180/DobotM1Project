from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import asyncio
import json
import websockets
import threading
import logging
from datetime import datetime

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")

class GatewayConnector:
    def __init__(self, gateway_url="ws://localhost:5005"):
        self.gateway_url = gateway_url
        self.websocket = None
        self.connected = False
        self.loop = None
        self.thread = None
        
    def start_connection(self):
        """在背景線程中啟動 WebSocket 連接"""
        if self.thread and self.thread.is_alive():
            return
            
        self.thread = threading.Thread(target=self._run_websocket_client)
        self.thread.daemon = True
        self.thread.start()
    
    def _run_websocket_client(self):
        """在新的事件循環中運行 WebSocket 客戶端"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._websocket_client())
    
    async def _websocket_client(self):
        """WebSocket 客戶端邏輯"""
        while True:
            try:
                logger.info(f"Connecting to gateway at {self.gateway_url}")
                async with websockets.connect(self.gateway_url) as websocket:
                    self.websocket = websocket
                    self.connected = True
                    logger.info("Connected to RS485 Gateway")
                    
                    # 通知前端連接狀態
                    socketio.emit('gateway_status', {'connected': True})
                    
                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            # 轉發消息到前端
                            socketio.emit('gateway_message', data)
                        except json.JSONDecodeError:
                            logger.error(f"Invalid JSON received: {message}")
                            
            except Exception as e:
                logger.error(f"Gateway connection error: {e}")
                self.connected = False
                self.websocket = None
                socketio.emit('gateway_status', {'connected': False, 'error': str(e)})
                
                # 等待5秒後重試
                await asyncio.sleep(5)
    
    async def send_command(self, command, params=None):
        """發送命令到 Gateway"""
        if not self.connected or not self.websocket:
            return {"success": False, "error": "Not connected to gateway"}
        
        try:
            message = {
                "command": command,
                "params": params or {},
                "timestamp": datetime.now().isoformat()
            }
            await self.websocket.send(json.dumps(message))
            return {"success": True, "message": "Command sent"}
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return {"success": False, "error": str(e)}
    
    def send_command_sync(self, command, params=None):
        """同步發送命令（用於 Flask 路由）"""
        if not self.loop:
            return {"success": False, "error": "Gateway not initialized"}
        
        future = asyncio.run_coroutine_threadsafe(
            self.send_command(command, params), 
            self.loop
        )
        try:
            return future.result(timeout=5)
        except Exception as e:
            return {"success": False, "error": str(e)}

# 創建全局 Gateway 連接器
gateway = GatewayConnector()

@app.route('/')
def index():
    """主頁面"""
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """獲取連接狀態"""
    return jsonify({
        "gateway_connected": gateway.connected,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/command', methods=['POST'])
def send_command():
    """發送命令到 Gateway"""
    try:
        data = request.get_json()
        command = data.get('command')
        params = data.get('params', {})
        
        if not command:
            return jsonify({"success": False, "error": "No command specified"}), 400
        
        result = gateway.send_command_sync(command, params)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# WebSocket 事件處理
@socketio.on('connect')
def handle_connect():
    """客戶端連接"""
    logger.info("Client connected to SocketIO")
    emit('status', {'message': 'Connected to Flask server'})

@socketio.on('disconnect')
def handle_disconnect():
    """客戶端斷開連接"""
    logger.info("Client disconnected from SocketIO")

@socketio.on('send_command')
def handle_send_command(data):
    """處理來自前端的命令"""
    try:
        command = data.get('command')
        params = data.get('params', {})
        
        logger.info(f"Received SocketIO command: {command} with params: {params}")
        
        result = gateway.send_command_sync(command, params)
        emit('command_result', {
            'command': command,
            'result': result,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"SocketIO command error: {e}")
        emit('command_result', {
            'command': data.get('command', 'unknown'),
            'result': {"success": False, "error": str(e)},
            'timestamp': datetime.now().isoformat()
        })

# 預定義的命令路由（可選）
@app.route('/api/gripper/initialize', methods=['POST'])
def initialize_gripper():
    """初始化夾爪"""
    data = request.get_json() or {}
    mode = data.get('mode', 0x01)
    result = gateway.send_command_sync('initialize', {'mode': mode})
    return jsonify(result)

@app.route('/api/gripper/stop', methods=['POST'])
def stop_gripper():
    """停止夾爪"""
    result = gateway.send_command_sync('stop')
    return jsonify(result)

@app.route('/api/gripper/open', methods=['POST'])
def open_gripper():
    """張開夾爪"""
    result = gateway.send_command_sync('open')
    return jsonify(result)

@app.route('/api/gripper/close', methods=['POST'])
def close_gripper():
    """閉合夾爪"""
    result = gateway.send_command_sync('close')
    return jsonify(result)

@app.route('/api/gripper/position', methods=['POST'])
def set_position():
    """設定位置"""
    data = request.get_json()
    if not data or 'value' not in data:
        return jsonify({"success": False, "error": "Position value required"}), 400
    
    value = data['value']
    if not isinstance(value, int) or not 0 <= value <= 1000:
        return jsonify({"success": False, "error": "Position must be integer between 0 and 1000"}), 400
    
    result = gateway.send_command_sync('set_position', {'value': value})
    return jsonify(result)

@app.route('/api/gripper/force', methods=['POST'])
def set_force():
    """設定力道"""
    data = request.get_json()
    if not data or 'value' not in data:
        return jsonify({"success": False, "error": "Force value required"}), 400
    
    value = data['value']
    if not isinstance(value, int) or not 20 <= value <= 100:
        return jsonify({"success": False, "error": "Force must be integer between 20 and 100"}), 400
    
    result = gateway.send_command_sync('set_force', {'value': value})
    return jsonify(result)

@app.route('/api/gripper/speed', methods=['POST'])
def set_speed():
    """設定速度"""
    data = request.get_json()
    if not data or 'value' not in data:
        return jsonify({"success": False, "error": "Speed value required"}), 400
    
    value = data['value']
    if not isinstance(value, int) or not 1 <= value <= 100:
        return jsonify({"success": False, "error": "Speed must be integer between 1 and 100"}), 400
    
    result = gateway.send_command_sync('set_speed', {'value': value})
    return jsonify(result)

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Flask Web Interface for RS485 Gateway')
    parser.add_argument('--host', default='127.0.0.1', help='Host address (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5006, help='Flask port (default: 5006)')
    parser.add_argument('--gateway-url', default='ws://localhost:5005', help='Gateway WebSocket URL')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # 設定 Gateway URL
    gateway.gateway_url = args.gateway_url
    
    # 啟動 Gateway 連接
    gateway.start_connection()
    
    logger.info(f"Starting Flask server on {args.host}:{args.port}")
    logger.info(f"Gateway URL: {args.gateway_url}")
    
    # 啟動 Flask 應用
    socketio.run(
        app,
        host=args.host,
        port=args.port,
        debug=args.debug
    )

if __name__ == '__main__':
    main()