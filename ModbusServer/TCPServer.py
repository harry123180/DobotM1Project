# -*- coding: utf-8 -*-
# modbus_tcp_server_production.py
# [U+751F][U+7522][U+74B0][U+5883][U+7248][U+672C] - [U+652F][U+63F4][U+5206][U+96E2][U+6A94][U+6848][U+7248][U+672C] (templates + static)
# [U+66F4][U+65B0][U+FF1A][U+652F][U+63F4][U+7121][U+7B26][U+865F] 0-65535 [U+7BC4][U+570D][U+FF0C][U+52A0][U+5F37][U+932F][U+8AA4][U+8655][U+7406][U+548C][U+65E5][U+8A8C][U+8A18][U+9304]

import logging
import threading
import time
import json
import os
import sys
import signal
import traceback
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
from pymodbus.server import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext

# [U+7372][U+53D6][U+53EF][U+57F7][U+884C][U+6A94][U+7684][U+57FA][U+790E][U+8DEF][U+5F91]
def get_base_path():
    """[U+7372][U+53D6][U+7A0B][U+5F0F][U+57FA][U+790E][U+8DEF][U+5F91][U+FF0C][U+652F][U+63F4] PyInstaller [U+6253][U+5305]"""
    if getattr(sys, 'frozen', False):
        # PyInstaller [U+6253][U+5305][U+5F8C][U+7684][U+8DEF][U+5F91]
        return sys._MEIPASS
    else:
        # [U+958B][U+767C][U+74B0][U+5883][U+8DEF][U+5F91]
        return os.path.dirname(os.path.abspath(__file__))

# [U+8A2D][U+5B9A][U+65E5][U+8A8C] - [U+751F][U+7522][U+74B0][U+5883][U+914D][U+7F6E]
def setup_logging():
    """[U+8A2D][U+5B9A][U+751F][U+7522][U+74B0][U+5883][U+65E5][U+8A8C][U+914D][U+7F6E]"""
    log_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    
    # [U+6A94][U+6848][U+65E5][U+8A8C][U+8655][U+7406][U+5668]
    file_handler = logging.FileHandler('modbus_server.log', encoding='utf-8')
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.INFO)
    
    # [U+63A7][U+5236][U+53F0][U+65E5][U+8A8C][U+8655][U+7406][U+5668]
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO)
    
    # [U+8A2D][U+5B9A][U+6839][U+8A18][U+9304][U+5668]
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # [U+6291][U+5236][U+4E00][U+4E9B][U+7B2C][U+4E09][U+65B9][U+5EAB][U+7684][U+8A73][U+7D30][U+65E5][U+8A8C]
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('pymodbus').setLevel(logging.WARNING)

class SynchronizedDataBlock(ModbusSequentialDataBlock):
    """[U+540C][U+6B65][U+5316][U+7684][U+6578][U+64DA][U+584A][U+FF0C][U+7576][U+5916][U+90E8][U+4FEE][U+6539][U+6642][U+6703][U+66F4][U+65B0][U+4E3B][U+7A0B][U+5F0F][U+7684][U+66AB][U+5B58][U+5668][U+9663][U+5217]"""
    
    def __init__(self, address, values, server_app):
        super().__init__(address, values)
        self.server_app = server_app
    
    def setValues(self, address, values):
        """[U+8986][U+5BEB]setValues[U+65B9][U+6CD5][U+FF0C][U+540C][U+6B65][U+66F4][U+65B0][U+4E3B][U+7A0B][U+5F0F][U+7684][U+9663][U+5217]"""
        try:
            result = super().setValues(address, values)
            
            # [U+540C][U+6B65][U+66F4][U+65B0][U+4E3B][U+7A0B][U+5F0F][U+7684][U+66AB][U+5B58][U+5668][U+9663][U+5217]
            if self.server_app:
                for i, value in enumerate(values):
                    reg_addr = address + i
                    if 0 <= reg_addr < len(self.server_app.registers):
                        self.server_app.registers[reg_addr] = value
                        logging.info(f"[U+5916][U+90E8][U+66F4][U+65B0][U+66AB][U+5B58][U+5668] {reg_addr}: {value}")
            
            return result
        except Exception as e:
            logging.error(f"[U+540C][U+6B65][U+6578][U+64DA][U+584A][U+8A2D][U+503C][U+932F][U+8AA4]: {e}")
            return False

class ModbusTCPServerApp:
    def __init__(self):
        self.base_path = get_base_path()
        self.slave_id = 1  # [U+9810][U+8A2D]SlaveID
        self.server_host = "0.0.0.0"
        self.server_port = 502
        self.web_port = 8000
        
        # [U+521D][U+59CB][U+5316][U+66AB][U+5B58][U+5668][U+6578][U+64DA] (0-999, [U+5171]1000[U+500B][U+66AB][U+5B58][U+5668])
        self.register_count = 3000
        self.registers = [0] * self.register_count
        
        # [U+66AB][U+5B58][U+5668][U+8A3B][U+89E3]
        self.register_comments = {}
        self.load_comments()
        
        # [U+5275][U+5EFA]templates[U+548C]static[U+76EE][U+9304]
        self.create_directories()
        
        # Modbus[U+76F8][U+95DC]
        self.server = None
        self.context = None
        self.slave_context = None
        self.modbus_thread = None
        
        # Web[U+61C9][U+7528] - [U+8A2D][U+5B9A][U+6A21][U+677F][U+548C][U+975C][U+614B][U+6A94][U+6848][U+8DEF][U+5F91]
        template_folder = os.path.join(self.base_path, 'templates')
        static_folder = os.path.join(self.base_path, 'static')
        
        self.flask_app = Flask(__name__, 
                              template_folder=template_folder,
                              static_folder=static_folder)
        self.setup_web_routes()
        
        # [U+4F3A][U+670D][U+5668][U+72C0][U+614B]
        self.server_running = False
        self.shutdown_event = threading.Event()
        
        # [U+8A3B][U+518A][U+4FE1][U+865F][U+8655][U+7406][U+5668]
        self.setup_signal_handlers()
        
        logging.info("Modbus TCP Server [U+61C9][U+7528][U+7A0B][U+5F0F][U+521D][U+59CB][U+5316][U+5B8C][U+6210]")
    
    def setup_signal_handlers(self):
        """[U+8A2D][U+5B9A][U+4FE1][U+865F][U+8655][U+7406][U+5668][U+4EE5][U+512A][U+96C5][U+95DC][U+9589]"""
        def signal_handler(signum, frame):
            logging.info(f"[U+6536][U+5230][U+4FE1][U+865F] {signum}[U+FF0C][U+6B63][U+5728][U+512A][U+96C5][U+95DC][U+9589][U+4F3A][U+670D][U+5668]...")
            self.shutdown()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def create_directories(self):
        """[U+5275][U+5EFA][U+5FC5][U+8981][U+7684][U+76EE][U+9304][U+7D50][U+69CB]"""
        directories = [
            os.path.join(self.base_path, 'templates'),
            os.path.join(self.base_path, 'static')
        ]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    def load_comments(self):
        """[U+8F09][U+5165][U+66AB][U+5B58][U+5668][U+8A3B][U+89E3]"""
        try:
            comments_file = 'register_comments.json'
            if os.path.exists(comments_file):
                with open(comments_file, 'r', encoding='utf-8') as f:
                    self.register_comments = json.load(f)
                logging.info(f"[U+8F09][U+5165][U+4E86] {len(self.register_comments)} [U+500B][U+66AB][U+5B58][U+5668][U+8A3B][U+89E3]")
        except Exception as e:
            logging.error(f"[U+8F09][U+5165][U+8A3B][U+89E3][U+5931][U+6557]: {e}")
            self.register_comments = {}
    
    def save_comments(self):
        """[U+4FDD][U+5B58][U+66AB][U+5B58][U+5668][U+8A3B][U+89E3]"""
        try:
            with open('register_comments.json', 'w', encoding='utf-8') as f:
                json.dump(self.register_comments, f, ensure_ascii=False, indent=2)
            logging.debug("[U+66AB][U+5B58][U+5668][U+8A3B][U+89E3][U+5DF2][U+4FDD][U+5B58]")
        except Exception as e:
            logging.error(f"[U+4FDD][U+5B58][U+8A3B][U+89E3][U+5931][U+6557]: {e}")
    
    def create_modbus_context(self):
        """[U+5275][U+5EFA]Modbus[U+6578][U+64DA][U+4E0A][U+4E0B][U+6587]"""
        try:
            # [U+4F7F][U+7528][U+540C][U+6B65][U+5316][U+7684][U+6578][U+64DA][U+584A]
            holding_registers = SynchronizedDataBlock(0, self.registers, self)
            
            # [U+5275][U+5EFA]Slave[U+4E0A][U+4E0B][U+6587]
            self.slave_context = ModbusSlaveContext(
                di=ModbusSequentialDataBlock(0, [0]*100),  # Discrete Inputs
                co=ModbusSequentialDataBlock(0, [0]*100),  # Coils
                hr=holding_registers,                       # Holding Registers ([U+4E3B][U+8981][U+4F7F][U+7528])
                ir=holding_registers,                       # Input Registers ([U+5171][U+7528][U+540C][U+6A23][U+7684][U+6578][U+64DA])
            )
            
            # [U+5275][U+5EFA][U+4F3A][U+670D][U+5668][U+4E0A][U+4E0B][U+6587][U+FF0C][U+5305][U+542B][U+591A][U+500B]slave
            slaves = {self.slave_id: self.slave_context}
            self.context = ModbusServerContext(slaves=slaves, single=False)
            
            return self.context
        except Exception as e:
            logging.error(f"[U+5275][U+5EFA]Modbus[U+4E0A][U+4E0B][U+6587][U+5931][U+6557]: {e}")
            return None
    
    def update_slave_id(self, new_slave_id):
        """[U+66F4][U+65B0]SlaveID"""
        try:
            if 1 <= new_slave_id <= 247:  # Modbus[U+6A19][U+6E96]SlaveID[U+7BC4][U+570D]
                old_slave_id = self.slave_id
                self.slave_id = new_slave_id
                
                # [U+5982][U+679C][U+4F3A][U+670D][U+5668][U+6B63][U+5728][U+904B][U+884C][U+FF0C][U+9700][U+8981][U+91CD][U+65B0][U+5275][U+5EFA][U+4E0A][U+4E0B][U+6587]
                if self.server_running and self.context:
                    # [U+79FB][U+9664][U+820A][U+7684]slave context
                    if old_slave_id in self.context:
                        del self.context[old_slave_id]
                    
                    # [U+6DFB][U+52A0][U+65B0][U+7684]slave context
                    self.context[self.slave_id] = self.slave_context
                    
                logging.info(f"SlaveID [U+5DF2][U+66F4][U+65B0]: {old_slave_id} -> {new_slave_id}")
                return True
            else:
                logging.error(f"[U+7121][U+6548][U+7684]SlaveID: {new_slave_id}, [U+5FC5][U+9808][U+5728]1-247[U+7BC4][U+570D][U+5167]")
                return False
        except Exception as e:
            logging.error(f"[U+66F4][U+65B0]SlaveID[U+5931][U+6557]: {e}")
            return False
    
    def read_register(self, address):
        """[U+8B80][U+53D6][U+66AB][U+5B58][U+5668][U+503C]"""
        try:
            if 0 <= address < self.register_count:
                # [U+5F9E]Modbus[U+4E0A][U+4E0B][U+6587][U+8B80][U+53D6][U+6700][U+65B0][U+503C]
                if self.slave_context:
                    try:
                        result = self.slave_context.getValues(3, address, 1)
                        if result:
                            value = result[0]
                            self.registers[address] = value  # [U+540C][U+6B65][U+5230][U+5167][U+90E8][U+9663][U+5217]
                            return value
                    except Exception as e:
                        logging.debug(f"[U+5F9E]Modbus[U+4E0A][U+4E0B][U+6587][U+8B80][U+53D6][U+5931][U+6557]: {e}")
                
                # [U+5982][U+679C]Modbus[U+4E0A][U+4E0B][U+6587][U+4E0D][U+53EF][U+7528][U+FF0C][U+8FD4][U+56DE][U+5167][U+90E8][U+9663][U+5217][U+7684][U+503C]
                value = self.registers[address]
                return value
            else:
                logging.error(f"[U+66AB][U+5B58][U+5668][U+5730][U+5740][U+8D85][U+51FA][U+7BC4][U+570D]: {address}")
                return None
        except Exception as e:
            logging.error(f"[U+8B80][U+53D6][U+66AB][U+5B58][U+5668][U+5931][U+6557]: {e}")
            return None
    
    def write_register(self, address, value):
        """[U+5BEB][U+5165][U+66AB][U+5B58][U+5668][U+503C] - [U+652F][U+63F4][U+7121][U+7B26][U+865F] 0-65535 [U+7BC4][U+570D]"""
        try:
            if 0 <= address < self.register_count:
                # [U+78BA][U+4FDD][U+503C][U+5728][U+7121][U+7B26][U+865F]16[U+4F4D][U+7BC4][U+570D][U+5167] (0 to 65535)
                if 0 <= value <= 65535:
                    old_value = self.registers[address]
                    self.registers[address] = value
                    
                    # [U+540C][U+6B65][U+66F4][U+65B0][U+5230]Modbus[U+4E0A][U+4E0B][U+6587]
                    if self.slave_context:
                        self.slave_context.setValues(3, address, [value])  # Function Code 3 (Holding Registers)
                        self.slave_context.setValues(4, address, [value])  # Function Code 4 (Input Registers)
                    
                    logging.info(f"[U+5BEB][U+5165][U+66AB][U+5B58][U+5668] {address}: {old_value} -> {value}")
                    return True
                else:
                    logging.error(f"[U+66AB][U+5B58][U+5668][U+503C][U+8D85][U+51FA][U+7121][U+7B26][U+865F]16[U+4F4D][U+7BC4][U+570D]: {value} ([U+9700][U+8981] 0-65535)")
                    return False
            else:
                logging.error(f"[U+66AB][U+5B58][U+5668][U+5730][U+5740][U+8D85][U+51FA][U+7BC4][U+570D]: {address}")
                return False
        except Exception as e:
            logging.error(f"[U+5BEB][U+5165][U+66AB][U+5B58][U+5668][U+5931][U+6557]: {e}")
            return False
    
    def write_multiple_registers(self, start_address, values):
        """[U+6279][U+91CF][U+5BEB][U+5165][U+66AB][U+5B58][U+5668]"""
        try:
            if start_address + len(values) <= self.register_count:
                success_count = 0
                for i, value in enumerate(values):
                    if self.write_register(start_address + i, value):
                        success_count += 1
                
                if success_count == len(values):
                    return True
                else:
                    logging.warning(f"[U+6279][U+91CF][U+5BEB][U+5165][U+90E8][U+5206][U+6210][U+529F]: {success_count}/{len(values)}")
                    return False
            else:
                logging.error(f"[U+6279][U+91CF][U+5BEB][U+5165][U+8D85][U+51FA][U+7BC4][U+570D]: start={start_address}, count={len(values)}")
                return False
        except Exception as e:
            logging.error(f"[U+6279][U+91CF][U+5BEB][U+5165][U+5931][U+6557]: {e}")
            return False
    
    def get_register_status(self):
        """[U+7372][U+53D6][U+66AB][U+5B58][U+5668][U+72C0][U+614B][U+6458][U+8981]"""
        try:
            # [U+540C][U+6B65][U+6240][U+6709][U+66AB][U+5B58][U+5668][U+503C]
            if self.slave_context:
                try:
                    for addr in range(min(100, self.register_count)):  # [U+53EA][U+540C][U+6B65][U+524D]100[U+500B][U+907F][U+514D][U+592A][U+6162]
                        result = self.slave_context.getValues(3, addr, 1)
                        if result:
                            self.registers[addr] = result[0]
                except Exception as e:
                    logging.debug(f"[U+540C][U+6B65][U+66AB][U+5B58][U+5668][U+503C][U+5931][U+6557]: {e}")
            
            non_zero_registers = {addr: val for addr, val in enumerate(self.registers) if val != 0}
            return {
                'total_registers': self.register_count,
                'non_zero_count': len(non_zero_registers),
                'non_zero_registers': non_zero_registers,
                'slave_id': self.slave_id,
                'server_running': self.server_running,
                'version': '1.0.0',
                'uptime': time.time() - getattr(self, 'start_time', time.time())
            }
        except Exception as e:
            logging.error(f"[U+7372][U+53D6][U+66AB][U+5B58][U+5668][U+72C0][U+614B][U+5931][U+6557]: {e}")
            return {
                'total_registers': self.register_count,
                'non_zero_count': 0,
                'non_zero_registers': {},
                'slave_id': self.slave_id,
                'server_running': self.server_running,
                'error': str(e)
            }
    
    def get_register_range(self, start_address, count):
        """[U+7372][U+53D6][U+6307][U+5B9A][U+7BC4][U+570D][U+7684][U+66AB][U+5B58][U+5668][U+6578][U+64DA]"""
        try:
            if start_address < 0 or start_address >= self.register_count:
                return None
            
            end_address = min(start_address + count, self.register_count)
            registers_data = []
            
            for addr in range(start_address, end_address):
                value = self.read_register(addr)  # [U+4F7F][U+7528]read_register[U+78BA][U+4FDD][U+6578][U+64DA][U+540C][U+6B65]
                comment = self.register_comments.get(str(addr), '')
                registers_data.append({
                    'address': addr,
                    'value': value if value is not None else 0,
                    'comment': comment
                })
            
            return registers_data
        except Exception as e:
            logging.error(f"[U+7372][U+53D6][U+66AB][U+5B58][U+5668][U+7BC4][U+570D][U+5931][U+6557]: {e}")
            return None
    
    def update_register_comment(self, address, comment):
        """[U+66F4][U+65B0][U+66AB][U+5B58][U+5668][U+8A3B][U+89E3]"""
        try:
            if 0 <= address < self.register_count:
                if comment.strip():
                    self.register_comments[str(address)] = comment.strip()
                else:
                    # [U+5982][U+679C][U+8A3B][U+89E3][U+70BA][U+7A7A][U+FF0C][U+5247][U+522A][U+9664]
                    self.register_comments.pop(str(address), None)
                
                self.save_comments()
                return True
            return False
        except Exception as e:
            logging.error(f"[U+66F4][U+65B0][U+8A3B][U+89E3][U+5931][U+6557]: {e}")
            return False
    
    def setup_web_routes(self):
        """[U+8A2D][U+5B9A]Web[U+4ECB][U+9762][U+8DEF][U+7531]"""
        
        @self.flask_app.errorhandler(Exception)
        def handle_exception(e):
            logging.error(f"Web[U+4ECB][U+9762][U+932F][U+8AA4]: {e}\n{traceback.format_exc()}")
            return jsonify({'error': 'Internal server error'}), 500
        
        @self.flask_app.route('/')
        def index():
            return render_template('index.html')
        
        @self.flask_app.route('/static/<path:filename>')
        def static_files(filename):
            return send_from_directory(self.flask_app.static_folder, filename)
        
        @self.flask_app.route('/api/status')
        def api_status():
            return jsonify(self.get_register_status())
        
        @self.flask_app.route('/api/slave_id', methods=['POST'])
        def api_set_slave_id():
            try:
                data = request.get_json()
                new_slave_id = data.get('slave_id')
                if self.update_slave_id(new_slave_id):
                    return jsonify({'success': True, 'slave_id': self.slave_id})
                else:
                    return jsonify({'success': False, 'error': 'Invalid SlaveID'}), 400
            except Exception as e:
                logging.error(f"API[U+8A2D][U+5B9A]SlaveID[U+5931][U+6557]: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.flask_app.route('/api/register/<int:address>')
        def api_get_register(address):
            try:
                value = self.read_register(address)
                if value is not None:
                    comment = self.register_comments.get(str(address), '')
                    return jsonify({'address': address, 'value': value, 'comment': comment})
                else:
                    return jsonify({'error': 'Invalid address'}), 400
            except Exception as e:
                logging.error(f"API[U+8B80][U+53D6][U+66AB][U+5B58][U+5668][U+5931][U+6557]: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.flask_app.route('/api/register/<int:address>', methods=['POST'])
        def api_set_register(address):
            try:
                data = request.get_json()
                value = data.get('value')
                if self.write_register(address, value):
                    return jsonify({'success': True, 'address': address, 'value': value})
                else:
                    return jsonify({'success': False, 'error': 'Invalid address or value (0-65535)'}), 400
            except Exception as e:
                logging.error(f"API[U+5BEB][U+5165][U+66AB][U+5B58][U+5668][U+5931][U+6557]: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.flask_app.route('/api/registers', methods=['POST'])
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
                logging.error(f"API[U+6279][U+91CF][U+5BEB][U+5165][U+5931][U+6557]: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.flask_app.route('/api/register_range')
        def api_get_register_range():
            try:
                start_address = int(request.args.get('start', 0))
                count = int(request.args.get('count', 20))
                count = min(count, 100)  # [U+9650][U+5236][U+6700][U+5927][U+6578][U+91CF]
                
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
                logging.error(f"API[U+7372][U+53D6][U+66AB][U+5B58][U+5668][U+7BC4][U+570D][U+5931][U+6557]: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.flask_app.route('/api/comment/<int:address>', methods=['POST'])
        def api_update_comment(address):
            try:
                data = request.get_json()
                comment = data.get('comment', '')
                if self.update_register_comment(address, comment):
                    return jsonify({'success': True, 'address': address, 'comment': comment})
                else:
                    return jsonify({'success': False, 'error': 'Invalid address'}), 400
            except Exception as e:
                logging.error(f"API[U+66F4][U+65B0][U+8A3B][U+89E3][U+5931][U+6557]: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
    
    def start_modbus_server(self):
        """[U+555F][U+52D5]Modbus TCP[U+4F3A][U+670D][U+5668]"""
        try:
            # [U+5275][U+5EFA][U+8A2D][U+5099][U+8B58][U+5225]
            identity = ModbusDeviceIdentification()
            identity.VendorName = 'Python Modbus Server'
            identity.ProductCode = 'PMS'
            identity.VendorUrl = 'https://github.com/your-repo'
            identity.ProductName = 'Python Modbus TCP Server'
            identity.ModelName = 'Production Server'
            identity.MajorMinorRevision = '1.0.0'
            
            # [U+5275][U+5EFA][U+4E0A][U+4E0B][U+6587]
            context = self.create_modbus_context()
            if context is None:
                raise Exception("[U+7121][U+6CD5][U+5275][U+5EFA]Modbus[U+4E0A][U+4E0B][U+6587]")
            
            # [U+555F][U+52D5][U+4F3A][U+670D][U+5668] ([U+9019][U+6703][U+963B][U+585E][U+7576][U+524D][U+7DDA][U+7A0B])
            logging.info(f"[U+555F][U+52D5]Modbus TCP Server[U+65BC] {self.server_host}:{self.server_port}, SlaveID: {self.slave_id}")
            self.server_running = True
            self.start_time = time.time()
            
            StartTcpServer(
                context=context,
                identity=identity,
                address=(self.server_host, self.server_port),
            )
            
        except Exception as e:
            logging.error(f"Modbus[U+4F3A][U+670D][U+5668][U+555F][U+52D5][U+5931][U+6557]: {e}\n{traceback.format_exc()}")
            self.server_running = False
    
    def start_web_server(self):
        """[U+555F][U+52D5]Web[U+7BA1][U+7406][U+4ECB][U+9762]"""
        try:
            logging.info(f"[U+555F][U+52D5]Web[U+7BA1][U+7406][U+4ECB][U+9762][U+65BC] http://127.0.0.1:{self.web_port}")
            self.flask_app.run(
                host='0.0.0.0',
                port=self.web_port,
                debug=False,
                use_reloader=False,
                threaded=True
            )
        except Exception as e:
            logging.error(f"Web[U+4F3A][U+670D][U+5668][U+555F][U+52D5][U+5931][U+6557]: {e}\n{traceback.format_exc()}")
    
    def initialize_test_data(self):
        """[U+521D][U+59CB][U+5316][U+6E2C][U+8A66][U+6578][U+64DA] - [U+4F7F][U+7528][U+7121][U+7B26][U+865F][U+7BC4][U+570D]"""
        try:
            # [U+8A2D][U+5B9A][U+4E00][U+4E9B][U+6E2C][U+8A66][U+503C] ([U+7121][U+7B26][U+865F] 0-65535)
            test_data = {
                0: 100,     # [U+5730][U+5740]0 = 100
                1: 200,     # [U+5730][U+5740]1 = 200
                10: 1000,   # [U+5730][U+5740]10 = 1000
                50: 5000,   # [U+5730][U+5740]50 = 5000
                100: 12345, # [U+5730][U+5740]100 = 12345
                200: 32768, # [U+5730][U+5740]200 = 32768 ([U+8D85][U+904E][U+6709][U+7B26][U+865F][U+7BC4][U+570D][U+4F46][U+5728][U+7121][U+7B26][U+865F][U+7BC4][U+570D][U+5167])
                500: 65535, # [U+5730][U+5740]500 = 65535 ([U+6700][U+5927][U+7121][U+7B26][U+865F][U+503C])
                999: 40000  # [U+5730][U+5740]999 = 40000
            }
            
            for addr, value in test_data.items():
                self.write_register(addr, value)
            
            # [U+8A2D][U+5B9A][U+4E00][U+4E9B][U+6E2C][U+8A66][U+8A3B][U+89E3]
            test_comments = {
                0: "[U+6EAB][U+5EA6][U+611F][U+6E2C][U+5668]",
                1: "[U+6FD5][U+5EA6][U+611F][U+6E2C][U+5668]", 
                10: "[U+99AC][U+9054][U+8F49][U+901F]",
                50: "[U+58D3][U+529B][U+6578][U+503C]",
                100: "[U+6E2C][U+8A66][U+6578][U+64DA]",
                200: "[U+9AD8][U+6578][U+503C][U+6E2C][U+8A66]",
                500: "[U+6700][U+5927][U+503C][U+6E2C][U+8A66]",
                999: "[U+908A][U+754C][U+6E2C][U+8A66]"
            }
            
            for addr, comment in test_comments.items():
                self.register_comments[str(addr)] = comment
            
            self.save_comments()
            logging.info("[U+6E2C][U+8A66][U+6578][U+64DA][U+548C][U+8A3B][U+89E3][U+521D][U+59CB][U+5316][U+5B8C][U+6210] ([U+7121][U+7B26][U+865F] 0-65535 [U+7BC4][U+570D])")
        except Exception as e:
            logging.error(f"[U+521D][U+59CB][U+5316][U+6E2C][U+8A66][U+6578][U+64DA][U+5931][U+6557]: {e}")
    
    def shutdown(self):
        """[U+512A][U+96C5][U+95DC][U+9589][U+4F3A][U+670D][U+5668]"""
        try:
            logging.info("[U+6B63][U+5728][U+95DC][U+9589][U+4F3A][U+670D][U+5668]...")
            self.shutdown_event.set()
            self.server_running = False
            
            # [U+4FDD][U+5B58][U+8A3B][U+89E3]
            self.save_comments()
            
            logging.info("[U+4F3A][U+670D][U+5668][U+5DF2][U+95DC][U+9589]")
        except Exception as e:
            logging.error(f"[U+95DC][U+9589][U+4F3A][U+670D][U+5668][U+6642][U+767C][U+751F][U+932F][U+8AA4]: {e}")
    
    def run(self):
        """[U+4E3B][U+904B][U+884C][U+65B9][U+6CD5]"""
        try:
            logging.info("=== Modbus TCP Server [U+555F][U+52D5] ([U+751F][U+7522][U+74B0][U+5883]) ===")
            logging.info(f"Python [U+7248][U+672C]: {sys.version}")
            logging.info(f"[U+57FA][U+790E][U+8DEF][U+5F91]: {self.base_path}")
            
            # [U+521D][U+59CB][U+5316][U+6E2C][U+8A66][U+6578][U+64DA]
            self.initialize_test_data()
            
            # [U+555F][U+52D5]Web[U+4F3A][U+670D][U+5668] ([U+5728][U+55AE][U+7368][U+7DDA][U+7A0B][U+4E2D])
            web_thread = threading.Thread(target=self.start_web_server, daemon=True, name="WebServer")
            web_thread.start()
            
            # [U+7B49][U+5F85][U+4E00][U+79D2][U+78BA][U+4FDD]Web[U+4F3A][U+670D][U+5668][U+555F][U+52D5]
            time.sleep(1)
            
            # [U+555F][U+52D5]Modbus[U+4F3A][U+670D][U+5668] ([U+4E3B][U+7DDA][U+7A0B][U+FF0C][U+6703][U+963B][U+585E])
            self.start_modbus_server()
            
        except KeyboardInterrupt:
            logging.info("[U+6536][U+5230][U+4E2D][U+65B7][U+4FE1][U+865F][U+FF0C][U+6B63][U+5728][U+95DC][U+9589]...")
        except Exception as e:
            logging.error(f"[U+4F3A][U+670D][U+5668][U+904B][U+884C][U+932F][U+8AA4]: {e}\n{traceback.format_exc()}")
        finally:
            self.shutdown()

def main():
    """[U+4E3B][U+51FD][U+6578] - [U+751F][U+7522][U+74B0][U+5883][U+5165][U+53E3][U+9EDE]"""
    try:
        # [U+8A2D][U+5B9A][U+65E5][U+8A8C]
        setup_logging()
        
        # [U+6253][U+5370][U+555F][U+52D5][U+8CC7][U+8A0A]
        print("=" * 60)
        print("  Modbus TCP Server - [U+751F][U+7522][U+74B0][U+5883][U+7248][U+672C]")
        print("=" * 60)
        print(f"  [U+7248][U+672C]: 1.0.0")
        print(f"  [U+6578][U+503C][U+7BC4][U+570D]: 0-65535 ([U+7121][U+7B26][U+865F] 16 [U+4F4D])")
        print(f"  Modbus TCP [U+57E0]: 502")
        print(f"  Web [U+7BA1][U+7406][U+57E0]: 8000")
        print(f"  Web [U+7BA1][U+7406][U+7DB2][U+5740]: http://localhost:8000")
        print("=" * 60)
        print("  [U+6309] Ctrl+C [U+53EF][U+5B89][U+5168][U+95DC][U+9589][U+4F3A][U+670D][U+5668]")
        print("=" * 60)
        
        # [U+5275][U+5EFA][U+4E26][U+904B][U+884C][U+4F3A][U+670D][U+5668]
        app = ModbusTCPServerApp()
        app.run()
        
    except Exception as e:
        logging.error(f"[U+61C9][U+7528][U+7A0B][U+5F0F][U+555F][U+52D5][U+5931][U+6557]: {e}\n{traceback.format_exc()}")
        print(f"\n[FAIL] [U+555F][U+52D5][U+5931][U+6557]: {e}")
        print("[U+8ACB][U+6AA2][U+67E5] modbus_server.log [U+6A94][U+6848][U+7372][U+53D6][U+8A73][U+7D30][U+932F][U+8AA4][U+8CC7][U+8A0A]")
        input("[U+6309] Enter [U+9375][U+9000][U+51FA]...")
        sys.exit(1)

if __name__ == "__main__":
    main()