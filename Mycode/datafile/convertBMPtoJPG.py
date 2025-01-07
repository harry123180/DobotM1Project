import cv2
import os

# 指定 BMP 檔案的目錄路徑
input_folder = "C:\\Users\\TSIC\\Documents\\GitHub\\DobotM1Project\\Mycode\\datafile"  # 替換成你的 BMP 圖片目錄
output_folder = "C:\\Users\\TSIC\\Documents\\GitHub\\DobotM1Project\\Mycode\\converted_jpgs"  # 儲存 JPG 圖片的目錄

# 確保輸出目錄存在，如果不存在則建立
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# 遍歷目錄中的所有檔案
for file_name in os.listdir(input_folder):
    # 確保檔案是 BMP 格式
    if file_name.lower().endswith(".bmp"):
        # 讀取 BMP 圖片
        bmp_path = os.path.join(input_folder, file_name)
        image = cv2.imread(bmp_path)

        # 構造 JPG 檔案的輸出路徑
        jpg_file_name = os.path.splitext(file_name)[0] + ".jpg"
        jpg_path = os.path.join(output_folder, jpg_file_name)

        # 將 BMP 圖片儲存為 JPG
        cv2.imwrite(jpg_path, image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        print(f"已轉換: {bmp_path} -> {jpg_path}")

print("所有 BMP 圖片已成功轉換為 JPG 格式！")
