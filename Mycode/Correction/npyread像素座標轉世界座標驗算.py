import cv2
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import os

# === 相機參數 ===
K = np.array([
    [5527.91522, 0.0, 1249.56097],
    [0.0, 5523.37409, 997.41524],
    [0.0, 0.0, 1.0]
])

D = np.array([
    -0.06833483, 0.00056340, 0.00137019, 0.00055740, 4.80949681
])

# 使用上一步 PnP 計算出的 rvec 與 tvec
rvec = np.array([[-2.17796294], [-2.24565035], [0.02621215]])  # shape (3,1)
tvec = np.array([[330.20053861], [48.63793437], [533.5402696]])  # shape (3,1)
# === 讀取資料 ===
base_dir = os.path.dirname(__file__)
corner_path = os.path.join(base_dir, "26_corner_points.npy")
world_path = os.path.join(base_dir, "world_points.npy")

corner_data = np.load(corner_path)  # [id, x, y]
world_data = np.load(world_path)    # [id, x, y]

# 轉為 dict
corner_dict = {int(row[0]): row[1:] for row in corner_data}
world_dict = {int(row[0]): row[1:] for row in world_data}

# 對齊共同點
common_ids = sorted(set(corner_dict.keys()) & set(world_dict.keys()))
if len(common_ids) < 4:
    raise ValueError("共同點位不足，至少需要4點")

# 轉成 numpy array
image_coords = np.array([corner_dict[i] for i in common_ids], dtype=np.float32)
world_coords = np.array([[*world_dict[i], 0.0] for i in common_ids], dtype=np.float32)

# === 計算 Z=0 的反投影世界座標 ===
R, _ = cv2.Rodrigues(rvec)

transformed_points = []
for uv in image_coords:
    undistorted_uv = cv2.undistortPoints(
        uv.reshape(1, 1, 2), K, D, P=K).reshape(-1)
    uv_hom = np.array([undistorted_uv[0], undistorted_uv[1], 1.0])
    cam_coords = np.linalg.inv(K) @ uv_hom
    s = (0 - tvec[2]) / (R[2] @ cam_coords)
    XYZ_cam = s * cam_coords
    world_point = np.linalg.inv(R) @ (XYZ_cam - tvec.ravel())
    transformed_points.append(world_point[:2])

transformed_points = np.array(transformed_points)

# === 可視化比較 ===
colormap = cm.get_cmap('viridis')
norm = mcolors.Normalize(vmin=0, vmax=len(image_coords) - 1)

plt.figure(figsize=(12, 10))
plt.scatter(image_coords[:, 0], image_coords[:, 1],
            c=[norm(i) for i in range(len(image_coords))], cmap='Greens',
            label='Image Pixel Coordinates', s=100, edgecolor='black')
plt.scatter(world_coords[:, 0], world_coords[:, 1],
            c=[norm(i) for i in range(len(world_coords))], cmap='Blues',
            label='True World Coordinates', s=100, marker='s', edgecolor='black')
plt.scatter(transformed_points[:, 0], transformed_points[:, 1],
            c=[norm(i) for i in range(len(transformed_points))], cmap='Oranges',
            label='Back-Projected World Coordinates (Z=0)', s=100, marker='^', edgecolor='black')

for i in range(len(image_coords)):
    plt.plot([world_coords[i, 0], transformed_points[i, 0]],
             [world_coords[i, 1], transformed_points[i, 1]], 'r--', alpha=0.5)
    plt.text(world_coords[i, 0]+3, world_coords[i, 1], f'P{common_ids[i]}', fontsize=8)
    plt.text(transformed_points[i, 0]+3, transformed_points[i, 1], f'P{common_ids[i]}', fontsize=8)

plt.title('Z=0 Back-Projection to World Coordinates')
plt.xlabel('X (mm)')
plt.ylabel('Y (mm)')
plt.legend()
plt.axis('equal')
plt.grid(True)
plt.show()

# === 誤差列印 ===
print("\n📊 座標轉換對比:")
print(f"{'點位':<5} | {'真實世界座標':<25} | {'轉換後座標':<25} | {'誤差 (XY)':<15}")
print("-" * 80)
for i in range(len(common_ids)):
    error = np.linalg.norm(world_coords[i, :2] - transformed_points[i])
    print(f"{common_ids[i]:<5} | {str(world_coords[i, :2]):<25} | {str(transformed_points[i].round(2)):<25} | {error:.2f} mm")
