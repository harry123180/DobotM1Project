#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify
import requests
import json

app = Flask(__name__)

# RS485 Gateway API基礎URL
GATEWAY_URL = "http://localhost:5005"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/gateway/<path:endpoint>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_to_gateway(endpoint):
    """代理請求到RS485 Gateway"""
    try:
        # 構建完整URL
        url = f"{GATEWAY_URL}/{endpoint}"
        
        # 獲取請求數據
        data = None
        if request.method in ['POST', 'PUT']:
            data = request.get_json()
        
        # 發送請求到Gateway
        if request.method == 'GET':
            response = requests.get(url, timeout=5)
        elif request.method == 'POST':
            response = requests.post(url, json=data, timeout=5)
        elif request.method == 'PUT':
            response = requests.put(url, json=data, timeout=5)
        elif request.method == 'DELETE':
            response = requests.delete(url, timeout=5)
        
        # 返回響應
        return jsonify(response.json()), response.status_code
        
    except requests.exceptions.ConnectionError:
        return jsonify({
            'success': False, 
            'message': 'Gateway連接失敗，請確認RS485Gateway正在運行'
        }), 503
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False, 
            'message': 'Gateway請求超時'
        }), 504
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'代理錯誤: {str(e)}'
        }), 500

if __name__ == '__main__':
    print("🌐 Web UI啟動於 http://localhost:5006")
    app.run(host='0.0.0.0', port=5006, debug=True)