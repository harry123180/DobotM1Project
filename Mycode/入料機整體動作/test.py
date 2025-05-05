import cv2
import numpy as np

# === 相機參數 ===
K = np.array([
    [5527.91522, 0.0, 1249.56097],
    [0.0, 5523.37409, 997.41524],
    [0.0, 0.0, 1.0]
])

D = np.array([
    -0.06833483, 0.00056340, 0.00137019, 0.00055740, 4.80949681
])

rvec = np.array([[-0.0002], [0.001], [0.0288]])  # shape (3,1)
tvec = np.array([[-81.91100754], [213.58274176], [539.49932382]])  # shape (3,1)

def pixel_to_world(u, v, K, D, rvec, tvec, Z_plane=0):
    print(f"輸入像素點: u={u}, v={v}")
    
    undistorted = cv2.undistortPoints(np.array([[[u, v]]], dtype=np.float32), K, D, P=K)
    uv_hom = np.array([undistorted[0, 0, 0], undistorted[0, 0, 1], 1.0], dtype=np.float64)

    R, _ = cv2.Rodrigues(rvec)
    cam_coords = np.linalg.inv(K) @ uv_hom

    tz = float(tvec.flatten()[2])
    s = (Z_plane - tz) / (R[2, :] @ cam_coords)
    XYZ_cam = s * cam_coords
    world_coords = np.linalg.inv(R) @ (XYZ_cam - tvec.flatten())

    print("world_coords (原始):", world_coords)
    print("world_coords.shape:", world_coords.shape)
    print("world_coords.dtype:", world_coords.dtype)

    result = tuple(world_coords.flatten().astype(float))
    print("world_coords (轉換後):", result)
    return result

# 測試座標點
Xw, Yw, Zw = pixel_to_world(1608, 1116, K, D, rvec, tvec)

print("\n✅ 最終輸出結果:")
print(f"Xw = {Xw:.2f}, Yw = {Yw:.2f}, Zw = {Zw:.2f}")
