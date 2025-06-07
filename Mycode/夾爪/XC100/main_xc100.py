# main_xc100.py
from xc100_control import XC100_Controller
import time

def main():
    # 建立XC100控制器物件（請根據你的實際連接參數調整）
    try:
        # 注意：unit_id請根據控制器上CH旋鈕值+1設定
        # 例如CH旋鈕設為1，則unit_id=2 (MODBUS RTU模式)
        controller = XC100_Controller(port='COM5', baudrate=115200, parity='N', stopbits=1, unit_id=2)
        
        print("=" * 60)
        print("🤖 XC100 控制器測試程序啟動")
        print("=" * 60)
        
        # 檢查初始狀態
        print("\n📋 步驟 1: 檢查初始狀態")
        controller.get_servo_status()
        controller.get_action_status()
        controller.get_alarm_status()
        controller.get_current_position()
        
        # 伺服ON
        print("\n📋 步驟 2: 啟動伺服")
        controller.servo_on()
        time.sleep(1)
        controller.get_servo_status()
        
        # 執行原點復歸（歸零）
        print("\n📋 步驟 3: 執行原點復歸（歸零）")
        controller.origin_return()
        print("等待歸零完成...")
        
        # 等待歸零完成
        if controller.wait_for_completion(timeout=30):
            controller.get_current_position()
        else:
            print("❌ 歸零失敗")
            return
        
        # 設定速度
        print("\n📋 步驟 4: 設定運動速度")
        controller.set_speed(30)  # 設定速度為30%
        time.sleep(0.5)
        
        # 定義A點和B點位置（單位：pulse，請根據實際需求調整）
        position_A = 0      # A點位置（原點）
        position_B = 5000   # B點位置（5000 pulse）
        
        print(f"\n📋 步驟 5: A點B點來回測試")
        print(f"A點位置: {position_A}")
        print(f"B點位置: {position_B}")
        
        # 執行來回運動測試（3個循環）
        for cycle in range(3):
            print(f"\n🔄 第 {cycle + 1} 循環")
            
            # 移動到B點
            print(f"   ➤ 移動到B點 ({position_B})")
            controller.absolute_move(position_B)
            
            if controller.wait_for_completion(timeout=20):
                controller.get_current_position()
            else:
                print("❌ 移動到B點失敗")
                break
            
            time.sleep(1)
            
            # 移動到A點
            print(f"   ➤ 移動到A點 ({position_A})")
            controller.absolute_move(position_A)
            
            if controller.wait_for_completion(timeout=20):
                controller.get_current_position()
            else:
                print("❌ 移動到A點失敗")
                break
                
            time.sleep(1)
        
        # 最終狀態檢查
        print("\n📋 步驟 6: 最終狀態檢查")
        controller.get_action_status()
        controller.get_position_status()
        controller.get_current_position()
        controller.get_servo_status()
        controller.get_alarm_status()
        
        # 伺服OFF
        print("\n📋 步驟 7: 關閉伺服")
        controller.servo_off()
        time.sleep(1)
        controller.get_servo_status()
        
        print("\n✅ 測試完成！")
        
    except ConnectionError as e:
        print(f"❌ 連接錯誤: {e}")
        print("請檢查:")
        print("1. 串口號是否正確 (當前設定: COM4)")
        print("2. XC100控制器是否正確連接")
        print("3. 電源是否接通")
        print("4. 波特率是否匹配 (當前設定: 115200)")
        print("5. unit_id是否正確 (控制器CH旋鈕=1，unit_id=2)")
        
    except Exception as e:
        print(f"❌ 執行錯誤: {e}")
        
    finally:
        # 斷開連線
        try:
            controller.disconnect()
        except:
            pass

def simple_test():
    """簡化測試功能"""
    try:
        controller = XC100_Controller(port='COM5', baudrate=115200, unit_id=2)
        print("=" * 60)
        print("🔧 XC100 簡化測試")
        print("=" * 60)
        
        # 伺服ON
        controller.servo_on()
        time.sleep(1)
        
        # 設定速度
        controller.set_speed(50)
        
        # 簡單的絕對位置移動測試
        print("移動到位置 1000")
        controller.absolute_move(1000)
        controller.wait_for_completion()
        
        time.sleep(2)
        
        print("移動到位置 0")
        controller.absolute_move(0)
        controller.wait_for_completion()
        
        # 伺服OFF
        controller.servo_off()
        print("✅ 簡化測試完成！")
        
    except Exception as e:
        print(f"❌ 簡化測試錯誤: {e}")
    finally:
        try:
            controller.disconnect()
        except:
            pass

def manual_control():
    """手動控制模式"""
    try:
        controller = XC100_Controller(port='COM5', baudrate=115200, unit_id=2)
        print("=" * 60)
        print("🎮 XC100 手動控制模式")
        print("=" * 60)
        print("指令列表:")
        print("  on    - 伺服ON")
        print("  off   - 伺服OFF")
        print("  home  - 原點復歸")
        print("  pos   - 查看當前位置")
        print("  move <位置> - 移動到指定位置")
        print("  speed <速度> - 設定速度(1-100)")
        print("  stop  - 緊急停止")
        print("  status - 查看狀態")
        print("  exit  - 退出")
        print("=" * 60)
        
        while True:
            try:
                cmd = input("\n請輸入指令: ").strip().lower()
                
                if cmd == "exit":
                    break
                elif cmd == "on":
                    controller.servo_on()
                elif cmd == "off":
                    controller.servo_off()
                elif cmd == "home":
                    controller.origin_return()
                    controller.wait_for_completion()
                elif cmd == "pos":
                    controller.get_current_position()
                elif cmd.startswith("move"):
                    try:
                        position = int(cmd.split()[1])
                        controller.absolute_move(position)
                        controller.wait_for_completion()
                    except (IndexError, ValueError):
                        print("❌ 請輸入有效位置，例如: move 1000")
                elif cmd.startswith("speed"):
                    try:
                        speed = int(cmd.split()[1])
                        controller.set_speed(speed)
                    except (IndexError, ValueError):
                        print("❌ 請輸入有效速度(1-100)，例如: speed 50")
                elif cmd == "stop":
                    controller.emergency_stop()
                elif cmd == "status":
                    controller.get_servo_status()
                    controller.get_action_status()
                    controller.get_position_status()
                    controller.get_current_position()
                    controller.get_alarm_status()
                else:
                    print("❌ 未知指令")
                    
            except KeyboardInterrupt:
                print("\n🛑 使用者中斷")
                break
                
    except Exception as e:
        print(f"❌ 手動控制錯誤: {e}")
    finally:
        try:
            controller.disconnect()
        except:
            pass

if __name__ == "__main__":
    print("XC100 控制器測試程序")
    print("請確保XC100控制器已正確連接並通電")
    print("請確認控制器上CH旋鈕設定為1（對應unit_id=2，MODBUS RTU模式）")
    
    choice = input("選擇測試模式:\n1. 完整測試\n2. 簡化測試\n3. 手動控制\n請輸入 (1, 2 或 3): ")
    
    if choice == "2":
        simple_test()
    elif choice == "3":
        manual_control()
    else:
        main()