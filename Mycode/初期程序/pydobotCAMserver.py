import socket
import random

# 設定伺服器參數
HOST = "192.168.1.2"  # 電腦的 IP
PORT = 6001           # 與機械臂設置的目標端口一致

def start_server():
    try:
        # 建立 TCP 伺服器
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((HOST, PORT))
        server.listen(1)
        print(f"伺服器已啟動，等待機械臂連線... (IP: {HOST}, Port: {PORT})")

        # 等待機械臂連線
        conn, addr = server.accept()
        print(f"機械臂已連線：{addr}")

        while True:
            # 接收來自機械臂的訊息
            data = conn.recv(1024).decode("utf-8")
            if not data:
                print("機械臂已中斷連線")
                break
            print(f"接收到訊息：{data}")

            # 根據接收到的訊息執行對應操作
            if data.lower() == "trigger_photo":
                # 生成隨機的 D1, D2, D3 值
                D1 = round(random.uniform(0, 100), 2)
                D2 = round(random.uniform(0, 100), 2)
                D3 = round(random.uniform(0, 100), 2)
                response = f"{D1},{D2},{D3};"
                conn.send(response.encode("utf-8"))
                print(f"回覆：{response}")

            else:
                response = "Unknown Command"
                conn.send(response.encode("utf-8"))
                print(f"回覆：{response}")

        conn.close()
        print("連線已關閉")

    except Exception as e:
        print(f"伺服器發生錯誤：{e}")
    finally:
        server.close()

if __name__ == "__main__":
    start_server()
