# main_pge.py
from pge_gripper_control import PGE_Gripper
import time

def main():
    # 建立夾爪控制物件（根據你的實際連接參數調整）
    # 根據說明書，PGE系列默認配置：波特率115200，ID為1
    try:
        gripper = PGE_Gripper(port='COM3', baudrate=115200, parity='N', stopbits=1, unit_id=1)
        print("=" * 50)
        print("🤖 PGE 夾爪測試程序啟動")
        print("=" * 50)
        
        # 檢查初始化狀態
        print("\n📋 步驟 1: 檢查初始化狀態")
        gripper.get_initialization_status()
        
        # 初始化（歸零）
        print("\n📋 步驟 2: 初始化夾爪")
        gripper.initialize(0x01)  # 回零位初始化
        time.sleep(3)  # 等待初始化完成
        
        # 檢查初始化完成狀態
        print("\n📋 步驟 3: 確認初始化完成")
        gripper.get_initialization_status()
        gripper.get_current_settings()
        
        # 設定力道與速度
        print("\n📋 步驟 4: 設定力道與速度")
        gripper.set_force(50)    # 設定力道為50%
        gripper.set_speed(40)    # 設定速度為40%
        
        # 開合測試
        print("\n📋 步驟 5: 夾爪動作測試")
        
        # 移動到400位置
        print("   ➤ 移動到位置 400")
        gripper.set_position(400)
        time.sleep(3)
        gripper.get_position_feedback()
        gripper.get_grip_status()
        
        # 移動到500位置
        print("   ➤ 移動到位置 500")
        gripper.set_position(500)
        time.sleep(3)
        gripper.get_position_feedback()
        gripper.get_grip_status()
        
        # 完全閉合（位置0）
        print("   ➤ 完全閉合")
        gripper.close()
        time.sleep(3)
        gripper.get_position_feedback()
        gripper.get_grip_status()
        
        # 完全張開（位置1000）
        print("   ➤ 完全張開")
        gripper.open()
        time.sleep(3)
        gripper.get_position_feedback()
        gripper.get_grip_status()
        
        # 停止當前動作
        print("\n📋 步驟 6: 停止動作")
        gripper.stop()
        
        # 最終狀態檢查
        print("\n📋 步驟 7: 最終狀態檢查")
        gripper.get_current_settings()
        gripper.get_position_feedback()
        gripper.get_grip_status()
        
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

if __name__ == "__main__":
    print("PGE 夾爪測試程序")
    print("請確保夾爪已正確連接並通電")
    input("按 Enter 鍵開始測試...")
    main()