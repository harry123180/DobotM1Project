#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NPY格式診斷工具
用於分析和診斷NPY檔案的格式結構
"""

import numpy as np
import os
import sys
from pathlib import Path

class NPYFormatReader:
    def __init__(self):
        self.supported_formats = {
            'camera_matrix': self.analyze_camera_matrix,
            'dist_coeffs': self.analyze_distortion_coeffs, 
            'extrinsic': self.analyze_extrinsic,
            'corner_points': self.analyze_corner_points,
            'world_points': self.analyze_world_points,
            'generic': self.analyze_generic
        }
    
    def analyze_file(self, file_path):
        """分析NPY檔案"""
        if not os.path.exists(file_path):
            print(f"錯誤: 檔案不存在 - {file_path}")
            return False
        
        try:
            print(f"\n{'='*60}")
            print(f"分析檔案: {file_path}")
            print(f"{'='*60}")
            
            # 載入數據
            data = np.load(file_path, allow_pickle=True)
            
            # 基本資訊
            print(f"數據類型: {type(data)}")
            print(f"numpy dtype: {data.dtype}")
            print(f"數組形狀: {data.shape}")
            print(f"數組大小: {data.size}")
            print(f"記憶體佔用: {data.nbytes} bytes")
            
            # 根據檔案名推測格式類型
            file_name = Path(file_path).stem.lower()
            format_type = self.detect_format_type(file_name, data)
            
            print(f"推測格式: {format_type}")
            print(f"{'-'*40}")
            
            # 執行特定分析
            if format_type in self.supported_formats:
                self.supported_formats[format_type](data, file_path)
            else:
                self.analyze_generic(data, file_path)
                
            return True
            
        except Exception as e:
            print(f"錯誤: 無法讀取檔案 - {str(e)}")
            return False
    
    def detect_format_type(self, file_name, data):
        """根據檔案名和數據特徵推測格式類型"""
        if 'camera_matrix' in file_name or 'intrinsic' in file_name:
            return 'camera_matrix'
        elif 'dist' in file_name or 'distortion' in file_name:
            return 'dist_coeffs'
        elif 'extrinsic' in file_name or 'external' in file_name:
            return 'extrinsic'
        elif 'corner' in file_name or 'image' in file_name:
            return 'corner_points'
        elif 'world' in file_name or 'real' in file_name:
            return 'world_points'
        else:
            # 根據數據特徵推測
            if data.shape == (3, 3):
                return 'camera_matrix'
            elif data.size == 5:
                return 'dist_coeffs'
            elif data.dtype == object:
                return 'extrinsic'
            elif len(data.shape) == 2 and data.shape[1] == 3:
                return 'corner_points'
            else:
                return 'generic'
    
    def analyze_camera_matrix(self, data, file_path):
        """分析相機內參矩陣"""
        print("📷 相機內參矩陣分析")
        print(f"{'-'*30}")
        
        if data.shape != (3, 3):
            print(f"⚠️  警告: 形狀不正確，應為(3,3)，實際為{data.shape}")
            return
        
        print("內參矩陣:")
        print(data)
        print()
        
        # 提取參數
        fx = data[0, 0]
        fy = data[1, 1] 
        cx = data[0, 2]
        cy = data[1, 2]
        skew = data[0, 1]
        
        print(f"焦距 fx: {fx:.2f}")
        print(f"焦距 fy: {fy:.2f}")
        print(f"主點 cx: {cx:.2f}")
        print(f"主點 cy: {cy:.2f}")
        print(f"偏斜 skew: {skew:.6f}")
        
        # 檢查合理性
        if fx <= 0 or fy <= 0:
            print("❌ 錯誤: 焦距應為正值")
        if abs(fx - fy) / max(fx, fy) > 0.1:
            print("⚠️  警告: fx和fy差異較大，可能不正常")
        if abs(skew) > 1:
            print("⚠️  警告: 偏斜值較大，通常應接近0")
        
        print(f"✅ 格式: 標準3x3相機內參矩陣")
    
    def analyze_distortion_coeffs(self, data, file_path):
        """分析畸變係數"""
        print("🔧 畸變係數分析")
        print(f"{'-'*30}")
        
        # 檢查並調整形狀
        original_shape = data.shape
        if data.shape == (1, 5):
            data = data.ravel()
        elif data.shape == (5, 1):
            data = data.ravel()
        elif data.shape != (5,):
            print(f"❌ 錯誤: 形狀不正確，應為(5,)、(1,5)或(5,1)，實際為{original_shape}")
            return
        
        print(f"原始形狀: {original_shape}")
        print(f"調整後形狀: {data.shape}")
        print()
        
        print("畸變係數:")
        print(data)
        print()
        
        # 標記參數
        k1, k2, p1, p2, k3 = data
        print(f"k1 (徑向畸變1): {k1:.8f}")
        print(f"k2 (徑向畸變2): {k2:.8f}")
        print(f"p1 (切向畸變1): {p1:.8f}")
        print(f"p2 (切向畸變2): {p2:.8f}")
        print(f"k3 (徑向畸變3): {k3:.8f}")
        
        # 檢查合理性
        if abs(k1) > 1:
            print("⚠️  警告: k1值較大，可能異常")
        if abs(k2) > 1:
            print("⚠️  警告: k2值較大，可能異常")
        if abs(p1) > 0.1 or abs(p2) > 0.1:
            print("⚠️  警告: 切向畸變值較大")
        
        print(f"✅ 格式: 標準5參數畸變係數")
    
    def analyze_extrinsic(self, data, file_path):
        """分析外參數據"""
        print("🎯 外參數據分析")
        print(f"{'-'*30}")
        
        if data.dtype != object:
            print(f"❌ 錯誤: 應為object類型，實際為{data.dtype}")
            return
        
        # 嘗試提取字典
        try:
            if data.shape == ():
                # 標量object，通常是字典
                extrinsic_dict = data.item()
            else:
                extrinsic_dict = data
            
            print(f"數據類型: {type(extrinsic_dict)}")
            
            if isinstance(extrinsic_dict, dict):
                print("包含的鍵值:")
                for key in extrinsic_dict.keys():
                    print(f"  - {key}: {type(extrinsic_dict[key])}")
                print()
                
                # 檢查必要的鍵
                required_keys = ['rvec', 'tvec']
                missing_keys = [key for key in required_keys if key not in extrinsic_dict]
                
                if missing_keys:
                    print(f"❌ 錯誤: 缺少必要鍵值: {missing_keys}")
                    return
                
                # 分析旋轉向量
                rvec = extrinsic_dict['rvec']
                print(f"旋轉向量 rvec:")
                print(f"  形狀: {rvec.shape}")
                print(f"  數值:")
                print(f"    rx: {rvec[0, 0]:.6f}")
                print(f"    ry: {rvec[1, 0]:.6f}")
                print(f"    rz: {rvec[2, 0]:.6f}")
                
                # 分析平移向量
                tvec = extrinsic_dict['tvec']
                print(f"平移向量 tvec:")
                print(f"  形狀: {tvec.shape}")
                print(f"  數值:")
                print(f"    tx: {tvec[0, 0]:.6f}")
                print(f"    ty: {tvec[1, 0]:.6f}")
                print(f"    tz: {tvec[2, 0]:.6f}")
                
                # 檢查其他可選鍵
                optional_keys = ['algorithm', 'timestamp', 'error']
                for key in optional_keys:
                    if key in extrinsic_dict:
                        print(f"{key}: {extrinsic_dict[key]}")
                
                print(f"✅ 格式: 標準外參字典格式")
            else:
                print(f"❌ 錯誤: 期望字典類型，實際為{type(extrinsic_dict)}")
                
        except Exception as e:
            print(f"❌ 錯誤: 無法解析外參數據 - {str(e)}")
    
    def analyze_corner_points(self, data, file_path):
        """分析角點數據"""
        print("📍 角點數據分析")
        print(f"{'-'*30}")
        
        if len(data.shape) != 2:
            print(f"❌ 錯誤: 應為2D數組，實際為{len(data.shape)}D")
            return
        
        if data.shape[1] != 3:
            print(f"❌ 錯誤: 第二維應為3 [id, x, y]，實際為{data.shape[1]}")
            return
        
        print(f"點位數量: {data.shape[0]}")
        print(f"數據格式: [id, image_x, image_y]")
        print()
        
        # 顯示前幾個點
        display_count = min(5, data.shape[0])
        print(f"前{display_count}個點位:")
        print("ID\t圖像X\t圖像Y")
        print("-" * 30)
        for i in range(display_count):
            print(f"{data[i, 0]:.0f}\t{data[i, 1]:.1f}\t{data[i, 2]:.1f}")
        
        if data.shape[0] > display_count:
            print(f"... (還有{data.shape[0] - display_count}個點位)")
        
        # 統計資訊
        ids = data[:, 0]
        x_coords = data[:, 1]
        y_coords = data[:, 2]
        
        print(f"\n統計資訊:")
        print(f"ID範圍: {ids.min():.0f} ~ {ids.max():.0f}")
        print(f"X座標範圍: {x_coords.min():.1f} ~ {x_coords.max():.1f}")
        print(f"Y座標範圍: {y_coords.min():.1f} ~ {y_coords.max():.1f}")
        
        # 檢查ID唯一性
        unique_ids = np.unique(ids)
        if len(unique_ids) != len(ids):
            print(f"⚠️  警告: ID有重複，唯一ID數量: {len(unique_ids)}")
        
        print(f"✅ 格式: 標準角點數據格式")
    
    def analyze_world_points(self, data, file_path):
        """分析世界座標數據"""
        print("🌍 世界座標數據分析")
        print(f"{'-'*30}")
        
        if len(data.shape) != 2:
            print(f"❌ 錯誤: 應為2D數組，實際為{len(data.shape)}D")
            return
        
        if data.shape[1] != 3:
            print(f"❌ 錯誤: 第二維應為3 [id, x, y]，實際為{data.shape[1]}")
            return
        
        print(f"點位數量: {data.shape[0]}")
        print(f"數據格式: [id, world_x, world_y]")
        print()
        
        # 顯示前幾個點
        display_count = min(5, data.shape[0])
        print(f"前{display_count}個點位:")
        print("ID\t世界X\t世界Y")
        print("-" * 30)
        for i in range(display_count):
            print(f"{data[i, 0]:.0f}\t{data[i, 1]:.1f}\t{data[i, 2]:.1f}")
        
        if data.shape[0] > display_count:
            print(f"... (還有{data.shape[0] - display_count}個點位)")
        
        # 統計資訊
        ids = data[:, 0]
        x_coords = data[:, 1]
        y_coords = data[:, 2]
        
        print(f"\n統計資訊:")
        print(f"ID範圍: {ids.min():.0f} ~ {ids.max():.0f}")
        print(f"X座標範圍: {x_coords.min():.1f} ~ {x_coords.max():.1f}")
        print(f"Y座標範圍: {y_coords.min():.1f} ~ {y_coords.max():.1f}")
        
        # 檢查ID唯一性
        unique_ids = np.unique(ids)
        if len(unique_ids) != len(ids):
            print(f"⚠️  警告: ID有重複，唯一ID數量: {len(unique_ids)}")
        
        print(f"✅ 格式: 標準世界座標數據格式")
    
    def analyze_generic(self, data, file_path):
        """通用數據分析"""
        print("🔍 通用數據分析")
        print(f"{'-'*30}")
        
        print(f"這是一個未識別的數據格式")
        print()
        
        # 顯示數據內容（有限制）
        if data.size <= 50:
            print("完整數據內容:")
            print(data)
        else:
            print("數據內容預覽:")
            if len(data.shape) == 1:
                print(f"前10個元素: {data[:10]}")
            elif len(data.shape) == 2:
                print(f"前5行:")
                print(data[:5])
            else:
                print("數據結構複雜，建議手動檢查")
        
        # 數值統計（如果是數值型）
        if np.issubdtype(data.dtype, np.number):
            print(f"\n數值統計:")
            print(f"最小值: {np.min(data)}")
            print(f"最大值: {np.max(data)}")
            print(f"平均值: {np.mean(data):.6f}")
            print(f"標準差: {np.std(data):.6f}")
    
    def analyze_directory(self, dir_path):
        """分析目錄中的所有NPY檔案"""
        if not os.path.isdir(dir_path):
            print(f"錯誤: 目錄不存在 - {dir_path}")
            return
        
        npy_files = list(Path(dir_path).glob("*.npy"))
        
        if not npy_files:
            print(f"目錄中沒有找到NPY檔案: {dir_path}")
            return
        
        print(f"找到 {len(npy_files)} 個NPY檔案")
        print("="*60)
        
        for npy_file in sorted(npy_files):
            self.analyze_file(str(npy_file))
            print("\n")

def main():
    """主函數"""
    reader = NPYFormatReader()
    
    if len(sys.argv) < 2:
        print("NPY格式診斷工具")
        print("="*40)
        print("使用方法:")
        print("  python npy_format_read.py <檔案路徑>")
        print("  python npy_format_read.py <目錄路徑>")
        print()
        print("範例:")
        print("  python npy_format_read.py camera_matrix.npy")
        print("  python npy_format_read.py ./calibration_data/")
        return
    
    target_path = sys.argv[1]
    
    if os.path.isfile(target_path):
        reader.analyze_file(target_path)
    elif os.path.isdir(target_path):
        reader.analyze_directory(target_path)
    else:
        print(f"錯誤: 路徑不存在 - {target_path}")

if __name__ == "__main__":
    main()