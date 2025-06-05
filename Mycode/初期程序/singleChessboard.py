import cv2
import numpy as np

# 棋盤格的行列數 (內部角點數，非棋盤格數)
CHECKERBOARD = (17, 12)

# 圖片檔案路徑
image_path = r'C:\\Users\\TSIC\\Documents\\GitHub\\DobotM1Project\\Mycode\\converted_jpgs\\1717.jpg'

# 讀取圖片
img = cv2.imread(image_path)

# 判斷圖片是否讀取成功
if img is None:
    print(f"無法讀取圖片: {image_path}")
else:
    # 列印圖片大小
    print(f"原始圖片大小 (高度, 寬度, 通道數): {img.shape}")

    # 調整圖片大小到 1920x1080
    resized_img = cv2.resize(img, (1920, 1080))
    print(f"調整後圖片大小 (高度, 寬度, 通道數): {resized_img.shape}")

    # 將調整後的圖片轉為灰階
    gray = cv2.cvtColor(resized_img, cv2.COLOR_BGR2GRAY)

    # 檢測棋盤格角點
    ret, corners = cv2.findChessboardCorners(
        gray, CHECKERBOARD, cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK + cv2.CALIB_CB_NORMALIZE_IMAGE
    )

    # 如果檢測到角點
    if ret:
        print(f"檢測到棋盤格角點: {image_path}")
        # 繪製角點
        img_with_corners = cv2.drawChessboardCorners(resized_img, CHECKERBOARD, corners, ret)
        
        # 顯示結果圖片
        cv2.imshow('Chessboard Corners', img_with_corners)
        cv2.waitKey(0)  # 等待按鍵以關閉視窗
        cv2.destroyAllWindows()
    else:
        print(f"未檢測到棋盤格角點: {image_path}")
