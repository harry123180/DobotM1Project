import customtkinter as ctk
import cv2
import numpy as np
import os
import glob
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import json
import threading
from datetime import datetime

class CameraCalibrationTool:
    def __init__(self):
        # 設置 CustomTkinter 主題
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # 主窗口
        self.root = ctk.CTk()
        self.root.title("相機標定工具 - Camera Calibration Tool")
        self.root.geometry("1400x900")
        
        # 棋盤格參數（預設值）
        self.checkerboard_width = ctk.IntVar(value=17)
        self.checkerboard_height = ctk.IntVar(value=12)
        self.square_size = ctk.DoubleVar(value=1.0)  # 公分
        
        # 標定參數
        self.criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        
        # 數據存儲
        self.image_paths = []
        self.processed_images = {}  # {path: {"corners": corners, "success": bool}}
        self.camera_matrix = None
        self.dist_coeffs = None
        self.reprojection_error = None
        
        # 當前顯示的圖像
        self.current_image_index = 0
        self.current_image_display = None
        
        self.setup_ui()
        
    def setup_ui(self):
        # 主框架
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 左側控制面板
        self.setup_control_panel(main_frame)
        
        # 右側顯示區域
        self.setup_display_area(main_frame)
        
    def setup_control_panel(self, parent):
        control_frame = ctk.CTkFrame(parent)
        control_frame.pack(side="left", fill="y", padx=(0, 10))
        
        # 標題
        title_label = ctk.CTkLabel(control_frame, text="相機標定工具", font=ctk.CTkFont(size=20, weight="bold"))
        title_label.pack(pady=10)
        
        # 棋盤格設置
        self.setup_checkerboard_settings(control_frame)
        
        # 圖像管理
        self.setup_image_management(control_frame)
        
        # 標定控制
        self.setup_calibration_controls(control_frame)
        
        # 結果顯示
        self.setup_results_display(control_frame)
        
    def setup_checkerboard_settings(self, parent):
        settings_frame = ctk.CTkFrame(parent)
        settings_frame.pack(fill="x", pady=10, padx=10)
        
        ctk.CTkLabel(settings_frame, text="棋盤格設置", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        # 寬度設置
        width_frame = ctk.CTkFrame(settings_frame)
        width_frame.pack(fill="x", pady=2)
        ctk.CTkLabel(width_frame, text="寬度(格數):").pack(side="left", padx=5)
        width_entry = ctk.CTkEntry(width_frame, textvariable=self.checkerboard_width, width=80)
        width_entry.pack(side="right", padx=5)
        
        # 高度設置
        height_frame = ctk.CTkFrame(settings_frame)
        height_frame.pack(fill="x", pady=2)
        ctk.CTkLabel(height_frame, text="高度(格數):").pack(side="left", padx=5)
        height_entry = ctk.CTkEntry(height_frame, textvariable=self.checkerboard_height, width=80)
        height_entry.pack(side="right", padx=5)
        
        # 格子大小設置
        size_frame = ctk.CTkFrame(settings_frame)
        size_frame.pack(fill="x", pady=2)
        ctk.CTkLabel(size_frame, text="格子大小(cm):").pack(side="left", padx=5)
        size_entry = ctk.CTkEntry(size_frame, textvariable=self.square_size, width=80)
        size_entry.pack(side="right", padx=5)
        
    def setup_image_management(self, parent):
        image_frame = ctk.CTkFrame(parent)
        image_frame.pack(fill="x", pady=10, padx=10)
        
        ctk.CTkLabel(image_frame, text="圖像管理", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        # 導入圖像按鈕
        import_btn = ctk.CTkButton(image_frame, text="導入圖像", command=self.import_images)
        import_btn.pack(fill="x", pady=2)
        
        # 清除圖像按鈕
        clear_btn = ctk.CTkButton(image_frame, text="清除所有圖像", command=self.clear_images)
        clear_btn.pack(fill="x", pady=2)
        
        # 圖像列表
        self.image_listbox = ctk.CTkScrollableFrame(image_frame, height=150)
        self.image_listbox.pack(fill="both", expand=True, pady=5)
        
        # 圖像導航
        nav_frame = ctk.CTkFrame(image_frame)
        nav_frame.pack(fill="x", pady=5)
        
        self.prev_btn = ctk.CTkButton(nav_frame, text="上一張", command=self.prev_image, width=70)
        self.prev_btn.pack(side="left", padx=2)
        
        self.next_btn = ctk.CTkButton(nav_frame, text="下一張", command=self.next_image, width=70)
        self.next_btn.pack(side="right", padx=2)
        
        self.image_info_label = ctk.CTkLabel(nav_frame, text="0/0")
        self.image_info_label.pack()
        
    def setup_calibration_controls(self, parent):
        calib_frame = ctk.CTkFrame(parent)
        calib_frame.pack(fill="x", pady=10, padx=10)
        
        ctk.CTkLabel(calib_frame, text="標定控制", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        # 檢測角點按鈕
        detect_btn = ctk.CTkButton(calib_frame, text="檢測所有角點", command=self.detect_all_corners)
        detect_btn.pack(fill="x", pady=2)
        
        # 執行標定按鈕
        calibrate_btn = ctk.CTkButton(calib_frame, text="執行相機標定", command=self.calibrate_camera)
        calibrate_btn.pack(fill="x", pady=2)
        
        # 導出結果按鈕
        export_btn = ctk.CTkButton(calib_frame, text="導出標定結果", command=self.export_calibration)
        export_btn.pack(fill="x", pady=2)
        
        # 進度條
        self.progress_label = ctk.CTkLabel(calib_frame, text="就緒")
        self.progress_label.pack(pady=5)
        
    def setup_results_display(self, parent):
        results_frame = ctk.CTkFrame(parent)
        results_frame.pack(fill="both", expand=True, pady=10, padx=10)
        
        ctk.CTkLabel(results_frame, text="標定結果", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        # 結果文本框
        self.results_text = ctk.CTkTextbox(results_frame, height=200)
        self.results_text.pack(fill="both", expand=True, pady=5)
        
        # 可視化按鈕
        viz_btn = ctk.CTkButton(results_frame, text="可視化精度", command=self.visualize_accuracy)
        viz_btn.pack(fill="x", pady=2)
        
    def setup_display_area(self, parent):
        display_frame = ctk.CTkFrame(parent)
        display_frame.pack(side="right", fill="both", expand=True)
        
        # 顯示標籤
        self.display_label = ctk.CTkLabel(display_frame, text="圖像顯示區域")
        self.display_label.pack(fill="both", expand=True)
        
        # 點位信息框
        info_frame = ctk.CTkFrame(display_frame)
        info_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(info_frame, text="點位信息", font=ctk.CTkFont(size=14, weight="bold")).pack()
        
        self.points_text = ctk.CTkTextbox(info_frame, height=100)
        self.points_text.pack(fill="x", pady=5)
        
    def import_images(self):
        filetypes = [
            ("圖像文件", "*.jpg *.jpeg *.png *.bmp"),
            ("JPEG文件", "*.jpg *.jpeg"),
            ("PNG文件", "*.png"),
            ("BMP文件", "*.bmp"),
            ("所有文件", "*.*")
        ]
        
        files = filedialog.askopenfilenames(
            title="選擇標定圖像",
            filetypes=filetypes
        )
        
        if files:
            self.image_paths.extend(files)
            self.update_image_list()
            self.update_navigation()
            
    def clear_images(self):
        self.image_paths.clear()
        self.processed_images.clear()
        self.current_image_index = 0
        self.update_image_list()
        self.update_navigation()
        self.display_label.configure(image=None, text="圖像顯示區域")
        self.points_text.delete("1.0", "end")
        
    def update_image_list(self):
        # 清除現有列表
        for widget in self.image_listbox.winfo_children():
            widget.destroy()
            
        # 添加圖像項目
        for i, path in enumerate(self.image_paths):
            filename = os.path.basename(path)
            status = "✓" if path in self.processed_images and self.processed_images[path]["success"] else "○"
            
            item_frame = ctk.CTkFrame(self.image_listbox)
            item_frame.pack(fill="x", pady=1)
            
            label = ctk.CTkLabel(item_frame, text=f"{status} {filename}")
            label.pack(side="left", padx=5)
            
            view_btn = ctk.CTkButton(item_frame, text="查看", width=50, 
                                   command=lambda idx=i: self.view_image(idx))
            view_btn.pack(side="right", padx=5)
            
    def update_navigation(self):
        total = len(self.image_paths)
        current = self.current_image_index + 1 if total > 0 else 0
        self.image_info_label.configure(text=f"{current}/{total}")
        
        self.prev_btn.configure(state="normal" if self.current_image_index > 0 else "disabled")
        self.next_btn.configure(state="normal" if self.current_image_index < total - 1 else "disabled")
        
    def prev_image(self):
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.view_current_image()
            self.update_navigation()
            
    def next_image(self):
        if self.current_image_index < len(self.image_paths) - 1:
            self.current_image_index += 1
            self.view_current_image()
            self.update_navigation()
            
    def view_image(self, index):
        self.current_image_index = index
        self.view_current_image()
        self.update_navigation()
        
    def view_current_image(self):
        if not self.image_paths:
            return
            
        path = self.image_paths[self.current_image_index]
        
        try:
            # 讀取圖像
            img = cv2.imread(path)
            if img is None:
                messagebox.showerror("錯誤", f"無法讀取圖像: {path}")
                return
                
            # 檢查是否已處理
            if path in self.processed_images:
                corners = self.processed_images[path]["corners"]
                success = self.processed_images[path]["success"]
                
                if success and corners is not None:
                    # 繪製角點
                    checkerboard = (self.checkerboard_width.get(), self.checkerboard_height.get())
                    img_with_corners = cv2.drawChessboardCorners(img.copy(), checkerboard, corners, success)
                    
                    # 添加編號
                    for idx, corner in enumerate(corners):
                        corner_pos = tuple(corner.ravel().astype(int))
                        cv2.putText(img_with_corners, str(idx), corner_pos, 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
                    
                    img = img_with_corners
                    self.display_points_info(corners)
                else:
                    self.points_text.delete("1.0", "end")
                    self.points_text.insert("1.0", "未檢測到角點")
            else:
                self.points_text.delete("1.0", "end")
                self.points_text.insert("1.0", "尚未處理")
                
            # 顯示圖像
            self.display_image(img)
            
        except Exception as e:
            messagebox.showerror("錯誤", f"顯示圖像時發生錯誤: {str(e)}")
            
    def display_image(self, cv_img):
        # 轉換為RGB
        rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        
        # 調整大小以適應顯示區域
        height, width = rgb_img.shape[:2]
        max_width, max_height = 800, 600
        
        if width > max_width or height > max_height:
            scale = min(max_width/width, max_height/height)
            new_width = int(width * scale)
            new_height = int(height * scale)
            rgb_img = cv2.resize(rgb_img, (new_width, new_height))
            
        # 轉換為PIL圖像
        pil_img = Image.fromarray(rgb_img)
        photo = ImageTk.PhotoImage(pil_img)
        
        # 顯示圖像
        self.display_label.configure(image=photo, text="")
        self.display_label.image = photo  # 保持引用
        
    def display_points_info(self, corners):
        self.points_text.delete("1.0", "end")
        
        info_text = "檢測到的角點座標:\n"
        info_text += f"總計: {len(corners)} 個點\n\n"
        
        for idx, corner in enumerate(corners):
            x, y = corner.ravel()
            info_text += f"點 {idx}: ({x:.2f}, {y:.2f})\n"
            
        self.points_text.insert("1.0", info_text)
        
    def detect_all_corners(self):
        if not self.image_paths:
            messagebox.showwarning("警告", "請先導入圖像")
            return
            
        def detect_corners():
            checkerboard = (self.checkerboard_width.get(), self.checkerboard_height.get())
            total = len(self.image_paths)
            success_count = 0
            
            for i, path in enumerate(self.image_paths):
                # 更新進度
                self.progress_label.configure(text=f"處理中... {i+1}/{total}")
                self.root.update()
                
                try:
                    img = cv2.imread(path)
                    if img is None:
                        continue
                        
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    
                    # 檢測角點
                    ret, corners = cv2.findChessboardCorners(gray, checkerboard, None)
                    
                    if ret and corners.shape[0] == checkerboard[0] * checkerboard[1]:
                        # 精細化角點
                        corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), self.criteria)
                        self.processed_images[path] = {"corners": corners2, "success": True}
                        success_count += 1
                    else:
                        self.processed_images[path] = {"corners": None, "success": False}
                        
                except Exception as e:
                    self.processed_images[path] = {"corners": None, "success": False}
                    
            self.progress_label.configure(text=f"完成! 成功: {success_count}/{total}")
            self.update_image_list()
            
        # 在新線程中執行
        threading.Thread(target=detect_corners, daemon=True).start()
        
    def calibrate_camera(self):
        if not self.processed_images:
            messagebox.showwarning("警告", "請先檢測角點")
            return
            
        # 收集成功的角點數據
        objpoints = []
        imgpoints = []
        
        checkerboard = (self.checkerboard_width.get(), self.checkerboard_height.get())
        square_size_mm = self.square_size.get() * 10  # 轉換為毫米
        
        # 創建世界坐標
        objp = np.zeros((checkerboard[0] * checkerboard[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0:checkerboard[0], 0:checkerboard[1]].T.reshape(-1, 2)
        objp *= square_size_mm
        
        for path, data in self.processed_images.items():
            if data["success"] and data["corners"] is not None:
                objpoints.append(objp)
                imgpoints.append(data["corners"])
                
        if len(objpoints) < 3:
            messagebox.showwarning("警告", "至少需要3張成功檢測角點的圖像進行標定")
            return
            
        self.progress_label.configure(text="執行標定中...")
        
        def calibrate():
            try:
                # 獲取圖像尺寸
                first_image = cv2.imread(self.image_paths[0])
                gray = cv2.cvtColor(first_image, cv2.COLOR_BGR2GRAY)
                image_size = gray.shape[::-1]
                
                # 執行標定
                ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
                    objpoints, imgpoints, image_size, None, None
                )
                
                self.camera_matrix = mtx
                self.dist_coeffs = dist
                self.reprojection_error = ret
                
                # 顯示結果
                self.display_calibration_results(ret, mtx, dist, len(objpoints))
                self.progress_label.configure(text="標定完成!")
                
            except Exception as e:
                messagebox.showerror("錯誤", f"標定失敗: {str(e)}")
                self.progress_label.configure(text="標定失敗")
                
        threading.Thread(target=calibrate, daemon=True).start()
        
    def display_calibration_results(self, reprojection_error, camera_matrix, dist_coeffs, num_images):
        result_text = f"=== 相機標定結果 ===\n\n"
        result_text += f"使用圖像數量: {num_images}\n"
        result_text += f"重投影誤差: {reprojection_error:.4f} 像素\n\n"
        
        result_text += f"相機內參矩陣 (K):\n"
        for row in camera_matrix:
            result_text += f"  [{row[0]:10.2f} {row[1]:10.2f} {row[2]:10.2f}]\n"
            
        result_text += f"\n畸變係數 (D):\n"
        result_text += f"  {dist_coeffs.ravel()}\n\n"
        
        # 提取相機參數
        fx, fy = camera_matrix[0, 0], camera_matrix[1, 1]
        cx, cy = camera_matrix[0, 2], camera_matrix[1, 2]
        
        result_text += f"焦距:\n"
        result_text += f"  fx = {fx:.2f} 像素\n"
        result_text += f"  fy = {fy:.2f} 像素\n"
        result_text += f"主點:\n"
        result_text += f"  cx = {cx:.2f} 像素\n"
        result_text += f"  cy = {cy:.2f} 像素\n"
        
        self.results_text.delete("1.0", "end")
        self.results_text.insert("1.0", result_text)
        
    def export_calibration(self):
        if self.camera_matrix is None:
            messagebox.showwarning("警告", "請先執行相機標定")
            return
            
        save_dir = filedialog.askdirectory(title="選擇保存目錄")
        if not save_dir:
            return
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 保存numpy格式
            np.save(os.path.join(save_dir, f"camera_matrix_{timestamp}.npy"), self.camera_matrix)
            np.save(os.path.join(save_dir, f"dist_coeffs_{timestamp}.npy"), self.dist_coeffs)
            
            # 保存JSON格式
            calib_data = {
                "camera_matrix": self.camera_matrix.tolist(),
                "distortion_coefficients": self.dist_coeffs.tolist(),
                "reprojection_error": float(self.reprojection_error),
                "checkerboard_size": [self.checkerboard_width.get(), self.checkerboard_height.get()],
                "square_size_cm": self.square_size.get(),
                "timestamp": timestamp,
                "num_images": len([d for d in self.processed_images.values() if d["success"]])
            }
            
            with open(os.path.join(save_dir, f"calibration_data_{timestamp}.json"), 'w') as f:
                json.dump(calib_data, f, indent=2)
                
            messagebox.showinfo("成功", f"標定結果已保存到:\n{save_dir}")
            
        except Exception as e:
            messagebox.showerror("錯誤", f"保存失敗: {str(e)}")
            
    def visualize_accuracy(self):
        if not self.processed_images or self.camera_matrix is None:
            messagebox.showwarning("警告", "請先完成標定")
            return
            
        # 創建新窗口顯示精度可視化
        viz_window = ctk.CTkToplevel(self.root)
        viz_window.title("標定精度可視化")
        viz_window.geometry("800x600")
        
        # 計算重投影誤差
        objpoints = []
        imgpoints = []
        
        checkerboard = (self.checkerboard_width.get(), self.checkerboard_height.get())
        square_size_mm = self.square_size.get() * 10
        
        objp = np.zeros((checkerboard[0] * checkerboard[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0:checkerboard[0], 0:checkerboard[1]].T.reshape(-1, 2)
        objp *= square_size_mm
        
        errors = []
        
        for path, data in self.processed_images.items():
            if data["success"] and data["corners"] is not None:
                objpoints.append(objp)
                imgpoints.append(data["corners"])
                
        # 計算每張圖像的重投影誤差
        for i in range(len(objpoints)):
            # 求解位姿
            _, rvec, tvec = cv2.solvePnP(objpoints[i], imgpoints[i], 
                                        self.camera_matrix, self.dist_coeffs)
            
            # 重投影
            projected_points, _ = cv2.projectPoints(objpoints[i], rvec, tvec, 
                                                   self.camera_matrix, self.dist_coeffs)
            
            # 計算誤差
            error = np.linalg.norm(imgpoints[i].reshape(-1, 2) - 
                                 projected_points.reshape(-1, 2), axis=1)
            errors.append(np.mean(error))
            
        # 創建圖表
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        # 誤差分布直方圖
        ax1.hist(errors, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
        ax1.set_xlabel('重投影誤差 (像素)')
        ax1.set_ylabel('圖像數量')
        ax1.set_title('重投影誤差分布')
        ax1.grid(True, alpha=0.3)
        
        # 每張圖像的誤差
        ax2.bar(range(len(errors)), errors, color='lightcoral', alpha=0.7)
        ax2.axhline(y=np.mean(errors), color='red', linestyle='--', 
                   label=f'平均誤差: {np.mean(errors):.3f}')
        ax2.set_xlabel('圖像索引')
        ax2.set_ylabel('平均重投影誤差 (像素)')
        ax2.set_title('各圖像重投影誤差')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # 將圖表嵌入到tkinter窗口
        canvas = FigureCanvasTkAgg(fig, viz_window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = CameraCalibrationTool()
    app.run()