import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import cv2
import numpy as np

import camera_manager  # 請確認 camera_manager.py 和此檔案在同一層目錄

# 初始化相機們
camera_manager.initialize_all_cameras()

# 建立主視窗
root = tk.Tk()
root.title("多相機圖像查看器")
root.geometry("800x600")

# 相機選單（下拉式）
camera_names = list(camera_manager.CAMERA_CONFIG.keys())
selected_camera = tk.StringVar()
selected_camera.set(camera_names[0])
dropdown = ttk.Combobox(root, textvariable=selected_camera, values=camera_names, state="readonly")
dropdown.pack(pady=10)

# 圖像顯示區塊
image_label = tk.Label(root)
image_label.pack()

# 假設所有相機回傳尺寸相同（如 2592x1944）
IMAGE_WIDTH = 2592
IMAGE_HEIGHT = 1944

def update_image():
    cam_name = selected_camera.get()
    try:
        # 從相機取得 raw image bytes
        raw_data = camera_manager.get_image(cam_name)

        # 將 raw bytes 轉成 numpy，視為 Bayer GR8 單通道影像
        bayer_image = np.frombuffer(raw_data, dtype=np.uint8).reshape((IMAGE_HEIGHT, IMAGE_WIDTH))

        # 轉為 RGB 彩色圖
        rgb_image = cv2.cvtColor(bayer_image, cv2.COLOR_BAYER_GR2RGB)

        # 在中央貼文字
        text = "Hello, world"
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 2
        thickness = 3
        text_size = cv2.getTextSize(text, font, scale, thickness)[0]
        text_x = (rgb_image.shape[1] - text_size[0]) // 2
        text_y = (rgb_image.shape[0] + text_size[1]) // 2
        cv2.putText(rgb_image, text, (text_x, text_y), font, scale, (0, 255, 0), thickness)

        # 調整圖片大小顯示
        display_image = cv2.resize(rgb_image, (800, 600))

        # 顯示到 tkinter
        img_pil = Image.fromarray(display_image)
        img_tk = ImageTk.PhotoImage(img_pil)
        image_label.configure(image=img_tk)
        image_label.image = img_tk

    except Exception as e:
        messagebox.showerror("錯誤", f"取圖失敗: {e}")

# 取圖按鈕
btn = tk.Button(root, text="擷取影像", command=update_image)
btn.pack(pady=10)

# 啟動介面
root.mainloop()
