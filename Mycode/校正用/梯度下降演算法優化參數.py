import cv2
import numpy as np
from scipy.optimize import least_squares

# 固定內參 K
K = np.array([[6.49009830e+00, 0.00000000e+00, 1.68818957e+03],
              [1.00000000e+00, 6.98951077e+00, 3.40924875e+02],
              [0.00000000e+00, 0.00000000e+00, 1.00000000e+00]])

# 初始畸變與外參
D_init = np.array([-0.028, -0.246, 0.004, 0.00004, 0.00000001888])
rvec_init = np.array([ -2.00404296, -2.22470768, -0.1785232])
tvec_init = np.array([323.31947122, 65.62275468, 494.63188712])

# 點對應
image_points = np.array([[1015.33, 1772.74], [1019.41, 1670.46], 
                         [1023.86, 1567.90], [1041.06, 1159.16],
                         [1527.08, 1795.55], [1552.26, 1180.86]])

object_points = np.array([[38.75, -349.44, 0], [28.75, -349.44, 0],
                          [18.75, -349.44, 0], [-23.25, -349.44, 0],
                          [36.75, -300.24, 0], [-23.25, -301.44, 0]])

# 優化變數打包與解包
def pack_params(D, rvec, tvec):
    return np.concatenate([D, rvec, tvec])

def unpack_params(params):
    D = params[0:5]
    rvec = params[5:8]
    tvec = params[8:11]
    return D, rvec, tvec

# 🚩 Z=0 假設下的反投影誤差
def compute_world_error(params):
    D, rvec, tvec = unpack_params(params)
    R, _ = cv2.Rodrigues(rvec)
    errors = []

    for i in range(len(image_points)):
        uv = image_points[i].reshape(1, 1, 2).astype(np.float32)
        undistorted = cv2.undistortPoints(uv, K, D, P=K).reshape(-1)
        uv_hom = np.array([undistorted[0], undistorted[1], 1.0])
        cam_coords = np.linalg.inv(K) @ uv_hom
        s = (0 - tvec[2]) / (R[2] @ cam_coords)
        XYZ_cam = s * cam_coords
        world_point = np.linalg.inv(R) @ (XYZ_cam - tvec)
        error_vec = world_point[:2] - object_points[i, :2]
        errors.extend(error_vec)

    return np.array(errors)

# 優化
initial_params = pack_params(D_init, rvec_init, tvec_init)

bounds = ([
    -1.0, -1.0, -0.1, -0.1, -1.0,   # D 下界
    -np.pi, -np.pi, -np.pi,         # rvec
    -1000, -1000, 100               # tvec
], [
    1.0, 1.0, 0.1, 0.1, 1.0,        # D 上界
    np.pi, np.pi, np.pi,
    1000, 1000, 1000
])

result = least_squares(
    compute_world_error,
    initial_params,
    bounds=bounds,
    loss='soft_l1',
    method='trf',
    max_nfev=1000
)

D_opt, rvec_opt, tvec_opt = unpack_params(result.x)

print("\n✅ 優化完成 (Z=0 假設)")
print("畸變係數 D:", D_opt)
print("旋轉向量 rvec:", rvec_opt)
print("平移向量 tvec:", tvec_opt)

# 顯示誤差統計
errors = compute_world_error(result.x).reshape(-1, 2)
error_norms = np.linalg.norm(errors, axis=1)
print("各點誤差 (mm):", error_norms.round(2))
print("平均 XY 平面誤差 (mm):", np.mean(error_norms).round(2))