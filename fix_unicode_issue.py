#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
簡單的ModbusTCP連接測試腳本
用於快速診斷TCPServer連接問題
"""

import socket
import subprocess
import sys

def check_port_502_simple():
    """簡單檢查端口502是否開放"""
    print("檢查端口502狀態...")
    
    try:
        # 使用netstat檢查端口
        result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        port_502_lines = [line for line in lines if ':502 ' in line]
        
        if port_502_lines:
            print("✅ 端口502正在被使用:")
            for line in port_502_lines:
                print(f"   {line.strip()}")
        else:
            print("❌ 端口502沒有被使用")
            return False
            
    except Exception as e:
        print(f"❌ 檢查端口失敗: {e}")
        return False
    
    # 測試TCP連接
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(('127.0.0.1', 502))
        sock.close()
        
        if result == 0:
            print("✅ 端口502可以建立TCP連接")
            return True
        else:
            print(f"❌ 端口502無法建立TCP連接，錯誤: {result}")
            return False
    except Exception as e:
        print(f"❌ TCP連接測試失敗: {e}")
        return False

def test_modbus_basic():
    """基本ModbusTCP測試"""
    print("\n測試ModbusTCP連接...")
    
    try:
        # 嘗試導入pymodbus
        try:
            from pymodbus.client.sync import ModbusTcpClient
            print("✅ 使用pymodbus.client.sync")
            client_type = "sync"
        except ImportError:
            try:
                from pymodbus.client import ModbusTcpClient
                print("✅ 使用pymodbus.client")
                client_type = "new"
            except ImportError:
                print("❌ 無法導入pymodbus")
                return False
        
        # 建立連接
        client = ModbusTcpClient('127.0.0.1', port=502)
        
        if client.connect():
            print("✅ ModbusTCP客戶端連接成功")
            
            # 測試讀取寄存器0
            try:
                if client_type == "sync":
                    result = client.read_holding_registers(0, 1, unit=1)
                else:
                    result = client.read_holding_registers(0, 1, slave=1)
                
                if hasattr(result, 'isError'):
                    if not result.isError():
                        print(f"✅ 讀取寄存器0成功: {result.registers}")
                    else:
                        print(f"❌ 讀取寄存器0失敗: {result}")
                else:
                    print(f"✅ 讀取寄存器0成功: {result}")
                
            except Exception as e:
                print(f"❌ 讀取寄存器異常: {e}")
            
            # 測試LED基地址
            try:
                if client_type == "sync":
                    result = client.read_holding_registers(600, 5, unit=1)
                else:
                    result = client.read_holding_registers(600, 5, slave=1)
                
                if hasattr(result, 'isError'):
                    if not result.isError():
                        print(f"✅ 讀取LED寄存器600-604成功: {result.registers}")
                    else:
                        print(f"❌ 讀取LED寄存器失敗: {result}")
                else:
                    print(f"✅ 讀取LED寄存器成功: {result}")
                
            except Exception as e:
                print(f"❌ 讀取LED寄存器異常: {e}")
            
            client.close()
            return True
        else:
            print("❌ ModbusTCP客戶端連接失敗")
            return False
            
    except Exception as e:
        print(f"❌ ModbusTCP測試異常: {e}")
        return False

def test_led_specific():
    """測試LED模組特定的連接"""
    print("\n測試LED模組特定連接...")
    
    try:
        # 模擬LED_main.py的連接方式
        from pymodbus.client.sync import ModbusTcpClient
        
        # LED配置參數
        host = "127.0.0.1"
        port = 502
        unit_id = 1
        base_address = 600
        
        print(f"連接參數: {host}:{port}, unit_id={unit_id}")
        print(f"LED基地址: {base_address}")
        
        client = ModbusTcpClient(host, port=port)
        
        if client.connect():
            print("✅ LED模組風格連接成功")
            
            # 讀取LED狀態寄存器 (600-615)
            try:
                result = client.read_holding_registers(base_address, 16, unit=unit_id)
                if not result.isError():
                    registers = result.registers
                    print(f"✅ LED狀態寄存器讀取成功:")
                    print(f"   模組狀態(600): {registers[0]}")
                    print(f"   設備連接(601): {registers[1]}")
                    print(f"   錯誤代碼(603): {registers[3]}")
                else:
                    print(f"❌ LED狀態寄存器讀取失敗: {result}")
            except Exception as e:
                print(f"❌ LED狀態寄存器讀取異常: {e}")
            
            # 測試寫入LED指令寄存器 (620)
            try:
                result = client.write_register(base_address + 20, 0, unit=unit_id)
                if not result.isError():
                    print("✅ LED指令寄存器寫入成功")
                else:
                    print(f"❌ LED指令寄存器寫入失敗: {result}")
            except Exception as e:
                print(f"❌ LED指令寄存器寫入異常: {e}")
            
            client.close()
            return True
        else:
            print("❌ LED模組風格連接失敗")
            return False
            
    except Exception as e:
        print(f"❌ LED模組測試異常: {e}")
        return False

def check_pymodbus_version():
    """檢查pymodbus版本"""
    print("\n檢查pymodbus版本...")
    
    try:
        import pymodbus
        print(f"✅ pymodbus版本: {pymodbus.__version__}")
        
        # 檢查可用的客戶端類型
        clients = []
        try:
            from pymodbus.client.sync import ModbusTcpClient
            clients.append("client.sync.ModbusTcpClient")
        except:
            pass
        
        try:
            from pymodbus.client import ModbusTcpClient
            clients.append("client.ModbusTcpClient")
        except:
            pass
        
        try:
            from pymodbus.client.tcp import ModbusTcpClient
            clients.append("client.tcp.ModbusTcpClient")
        except:
            pass
        
        if clients:
            print(f"✅ 可用的客戶端: {', '.join(clients)}")
        else:
            print("❌ 沒有找到可用的ModbusTCP客戶端")
        
        return True
        
    except Exception as e:
        print(f"❌ 檢查pymodbus版本失敗: {e}")
        return False

def suggest_solutions():
    """提供解決方案建議"""
    print("\n" + "=" * 50)
    print("解決方案建議:")
    print("=" * 50)
    
    print("1. 檢查TCPServer是否正確啟動:")
    print("   - 手動啟動: cd ModbusServer && python TCPServer.py")
    print("   - 檢查啟動輸出是否有錯誤")
    
    print("\n2. 檢查pymodbus版本兼容性:")
    print("   - pip show pymodbus")
    print("   - 可能需要: pip install pymodbus==3.9.2")
    
    print("\n3. 手動測試LED_main.py:")
    print("   - cd Automation/light")
    print("   - python LED_main.py")
    print("   - 查看詳細錯誤信息")
    
    print("\n4. 檢查防火牆設定:")
    print("   - 確保端口502沒有被防火牆阻擋")
    
    print("\n5. 重新啟動所有服務:")
    print("   - 停止啟動工具")
    print("   - 重新啟動啟動工具")
    print("   - 按順序啟動: TCPServer -> LED_main -> LED_app")

def main():
    """主函數"""
    print("=" * 50)
    print("簡單ModbusTCP連接診斷工具")
    print("=" * 50)
    
    # 1. 檢查端口502
    port_ok = check_port_502_simple()
    
    # 2. 檢查pymodbus版本
    version_ok = check_pymodbus_version()
    
    # 3. 測試基本ModbusTCP連接
    modbus_ok = test_modbus_basic()
    
    # 4. 測試LED特定連接
    led_ok = test_led_specific()
    
    # 總結
    print("\n" + "=" * 50)
    print("診斷結果:")
    print("=" * 50)
    print(f"端口502狀態: {'✅' if port_ok else '❌'}")
    print(f"pymodbus版本: {'✅' if version_ok else '❌'}")
    print(f"ModbusTCP連接: {'✅' if modbus_ok else '❌'}")
    print(f"LED模組測試: {'✅' if led_ok else '❌'}")
    
    if all([port_ok, version_ok, modbus_ok, led_ok]):
        print("\n🎉 所有測試通過！")
        print("LED模組應該能正常連接到TCPServer")
        print("如果仍有問題，請檢查LED_main.py的具體錯誤信息")
    else:
        print("\n⚠️  發現問題！")
        suggest_solutions()

if __name__ == "__main__":
    main()