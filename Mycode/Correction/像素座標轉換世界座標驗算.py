import cv2
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors

# 使用優化後的參數
K = np.array([
    [5527.91522,    0.0,       1249.56097],
    [0.0,        5523.37409,    997.41524],
    [0.0,           0.0,          1.0]
])

D = np.array([
    -0.06833483, 0.00056340, 0.00137019, 0.00055740, 4.80949681
])


tvec = np.array([
    326.756219, 60.44263545, 495.3279892
])



rvec = np.array([
    -2.00076509, -2.12007437, -0.14057056
])



print("\u2699\ufe0f 使用優化後參數")
print("K =\n", K)
print("D =", D)
print("rvec =", rvec)
print("tvec =", tvec)

# 目標點數據
image_coords = np.array([
    [1015.33, 1772.74],
    [1019.41, 1670.46],
    [1023.86, 1567.90],
    [1041.06, 1159.16],
    [1527.08, 1795.55],
    [1552.26, 1180.86]
])

world_coords = np.array([
    [38.75, -349.44, 0],
    [28.75, -349.44, 0],
    [18.75, -349.44, 0],
    [-23.25, -349.44, 0],
    [36.75, -300.24, 0],
    [-23.25, -301.44, 0]
])

R, _ = cv2.Rodrigues(rvec)

# Z=0 反推世界座標
transformed_points = []
for uv in image_coords:
    undistorted_uv = cv2.undistortPoints(
        uv.reshape(1, 1, 2).astype(np.float32), K, D, P=K).reshape(-1)
    uv_hom = np.array([undistorted_uv[0], undistorted_uv[1], 1.0])
    cam_coords = np.linalg.inv(K) @ uv_hom
    s = (0 - tvec[2]) / (R[2] @ cam_coords)
    XYZ_cam = s * cam_coords
    world_point = np.linalg.inv(R) @ (XYZ_cam - tvec)
    transformed_points.append(world_point[:2])

transformed_points = np.array(transformed_points)

# 顏色與視覺化
colormap = cm.get_cmap('viridis')
norm = mcolors.Normalize(vmin=0, vmax=len(image_coords)-1)

plt.figure(figsize=(12, 10))
plt.scatter(image_coords[:, 0], image_coords[:, 1],
            c=[norm(i) for i in range(len(image_coords))], cmap='Greens',
            label='Pixel Coordinates', s=100, edgecolor='black')
plt.scatter(world_coords[:, 0], world_coords[:, 1],
            c=[norm(i) for i in range(len(world_coords))], cmap='Blues',
            label='Real World Coordinates', s=100, marker='s', edgecolor='black')
plt.scatter(transformed_points[:, 0], transformed_points[:, 1],
            c=[norm(i) for i in range(len(transformed_points))], cmap='Oranges',
            label='Transformed World Coordinates (Z=0)', s=100, marker='^', edgecolor='black')

for i in range(len(image_coords)):
    plt.plot([world_coords[i, 0], transformed_points[i, 0]],
             [world_coords[i, 1], transformed_points[i, 1]], 'r-', alpha=0.5)
    plt.text(image_coords[i, 0]+20, image_coords[i, 1], f'P{i}', fontsize=8)
    plt.text(world_coords[i, 0]+5, world_coords[i, 1], f'P{i}', fontsize=8)
    plt.text(transformed_points[i, 0]+5, transformed_points[i, 1], f'P{i}', fontsize=8)

plt.title('Z=0 Back-Projection to World Coordinates')
plt.xlabel('X')
plt.ylabel('Y')
plt.legend()
plt.grid(True)
plt.show()

print("\n座標轉換對比:")
print(f"{'點位':<5} | {'真實世界座標':<25} | {'轉換後世界座標':<25} | {'誤差(XY)':<15}")
print("-"*80)
for i in range(len(image_coords)):
    error = np.linalg.norm(world_coords[i, :2] - transformed_points[i])
    print(f"{i:<5} | {str(world_coords[i, :2]):<25} | {str(transformed_points[i].round(2)):<25} | {error:.2f} mm")
