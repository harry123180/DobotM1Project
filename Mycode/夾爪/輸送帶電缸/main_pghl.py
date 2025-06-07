# main_pghl.py
from pghl_gripper_control import PGHL_Gripper
import time

def main():
    # 建立夾爪控制物件（根據你的實際連接參數調整）
    # 根據說明書，PGHL系列默認配置：波特率115200，ID為1
    try:
        gripper = PGHL_Gripper(port='COM4', baudrate=115200, parity='N', stopbits=1, unit_id=5)
        print("=" * 50)
        print("🤖 PGHL 夾爪測試程序啟動")
        print("=" * 50)
        
        # 檢查回零狀態
        print("\n📋 步驟 1: 檢查回零狀態")
        gripper.get_home_status()
        
        # 回零操作
        print("\n📋 步驟 2: 夾爪回零")
        gripper.home()
        time.sleep(3)  # 等待回零完成
        
        # 檢查回零完成狀態
        print("\n📋 步驟 3: 確認回零完成")
        gripper.get_home_status()
        gripper.get_current_settings()
        
        # 設定基本參數
        print("\n📋 步驟 4: 設定基本參數")
        gripper.set_push_force(50)        # 推壓力值50%
        gripper.set_max_speed(70)         # 最大速度70%
        gripper.set_acceleration(50)      # 加速度50%
        gripper.set_push_length_mm(8)     # 推壓段長度8mm
        gripper.set_push_speed(30)        # 推壓速度30%
        gripper.set_push_direction(2)     # 雙向推壓
        
        # 動作測試
        print("\n📋 步驟 5: 夾爪動作測試")
        
        # 移動到4mm位置
        print("   ➤ 移動到位置 4mm")
        gripper.move_to_position_mm(4.0)
        time.sleep(3)
        gripper.get_position_feedback()
        gripper.get_running_status()
        
        # 移動到5mm位置
        print("   ➤ 移動到位置 5mm")
        gripper.move_to_position_mm(5.0)
        time.sleep(3)
        gripper.get_position_feedback()
        gripper.get_running_status()
        
        # 完全閉合（位置0）
        print("   ➤ 完全閉合")
        gripper.close_gripper()
        time.sleep(3)
        gripper.get_position_feedback()
        gripper.get_running_status()
        
        # 張開到10mm
        print("   ➤ 張開到10mm")
        gripper.open_gripper(10)
        time.sleep(3)
        gripper.get_position_feedback()
        gripper.get_running_status()
        
        # 相對移動測試
        print("\n📋 步驟 6: 相對移動測試")
        print("   ➤ 相對移動 -2mm")
        gripper.move_relative_mm(-2.0)
        time.sleep(3)
        gripper.get_position_feedback()
        gripper.get_running_status()
        
        # 點動測試
        print("\n📋 步驟 7: 點動測試")
        print("   ➤ 點動張開 1 秒")
        gripper.jog_control(1)
        time.sleep(1)
        gripper.jog_control(0)  # 停止點動
        gripper.get_position_feedback()
        
        print("   ➤ 點動閉合 1 秒")
        gripper.jog_control(-1)
        time.sleep(1)
        gripper.jog_control(0)  # 停止點動
        gripper.get_position_feedback()
        
        # 停止當前動作
        print("\n📋 步驟 8: 停止動作")
        gripper.stop()
        
        # 最終狀態檢查
        print("\n📋 步驟 9: 最終狀態檢查")
        gripper.get_current_settings()
        gripper.get_position_feedback()
        gripper.get_current_feedback()
        gripper.get_running_status()
        
        print("\n✅ 測試完成！")
        
    except ConnectionError as e:
        print(f"❌ 連接錯誤: {e}")
        print("請檢查:")
        print("1. 串口號是否正確 (當前設定: COM3)")
        print("2. 夾爪是否正確連接")
        print("3. 電源是否接通")
        print("4. 波特率是否匹配 (當前設定: 115200)")
        
    except Exception as e:
        print(f"❌ 執行錯誤: {e}")
        
    finally:
        # 斷開連線
        try:
            gripper.disconnect()
        except:
            pass

def advanced_test():
    """進階測試功能"""
    try:
        gripper = PGHL_Gripper(port='COM3', baudrate=115200, unit_id=1)
        print("=" * 50)
        print("🔧 PGHL 夾爪進階測試")
        print("=" * 50)
        
        # 推壓段功能測試
        print("\n📋 推壓段功能測試")
        gripper.set_push_length_mm(5)     # 推壓段5mm
        gripper.set_push_force(40)        # 推壓力40%
        gripper.set_push_speed(20)        # 推壓速度20%
        
        # 移動並進入推壓段
        gripper.move_to_position_mm(3.0)
        time.sleep(4)
        gripper.get_running_status()
        
        # 測試不同推壓方向
        print("\n📋 推壓方向測試")
        for direction in [0, 1, 2]:
            direction_names = ["張開", "閉合", "雙向"]
            print(f"   ➤ 設定推壓方向: {direction_names[direction]}")
            gripper.set_push_direction(direction)
            time.sleep(1)
        
        print("\n✅ 進階測試完成！")
        
    except Exception as e:
        print(f"❌ 進階測試錯誤: {e}")
    finally:
        try:
            gripper.disconnect()
        except:
            pass

if __name__ == "__main__":
    print("PGHL 夾爪測試程序")
    print("請確保夾爪已正確連接並通電")
    
    choice = input("選擇測試模式:\n1. 基本測試\n2. 進階測試\n請輸入 (1 或 2): ")
    
    if choice == "2":
        advanced_test()
    else:
        main()