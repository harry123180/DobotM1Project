import socket
import random
import time

# 機械臂的伺服器參數
ROBOT_IP = "192.168.1.6"  # 機械臂的 IP
ROBOT_PORT = 6001         # 與機械臂配置的端口號一致

def start_client():
    try:
        # 建立 TCP 客戶端
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(10)  # 設定超時時間
        print(f"嘗試連接到機械臂伺服器：{ROBOT_IP}:{ROBOT_PORT}")
        
        # 連接到機械臂伺服器
        client.connect((ROBOT_IP, ROBOT_PORT))
        print("成功連接到機械臂伺服器")

        while True:
            # 接收來自機械臂的訊息
            data = client.recv(1024).decode("utf-8")
            if data :
                print(f"接收到訊息：{data}")

                # 根據接收到的訊息執行對應操作
                if data.lower() == "abcc":
                    # 生成隨機的 D1, D2, D3 值
                    D1 = round(random.uniform(0, 100), 2)
                    D2 = round(random.uniform(0, 100), 2)
                    D3 = round(random.uniform(0, 100), 2)
                    response = f"{D1},{D2},{D3};"
                    #client.send(response.encode("utf-8"))
                    print(f"回覆：{response}")
                
                else:
                    print(f"未知的指令：{data}")

    except socket.timeout:
        print("連線超時，無法連接到機械臂伺服器")
    except Exception as e:
        print(f"客戶端發生錯誤：{e}")
    finally:
        client.close()
        print("連線已關閉")

if __name__ == "__main__":
    start_client()
