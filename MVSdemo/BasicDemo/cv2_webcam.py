import cv2

# 開啟默認攝影機 (設備索引為 0)
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("無法開啟攝影機")
    exit()

while True:
    # 從攝影機獲取一幀
    ret, frame = cap.read()
    if not ret:
        print("無法讀取畫面")
        break

    # 顯示畫面
    cv2.imshow('WebCam', frame)

    # 按下 'q' 鍵退出
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 釋放攝影機資源並關閉視窗
cap.release()
cv2.destroyAllWindows()
