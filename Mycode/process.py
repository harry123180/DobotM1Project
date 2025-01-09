import glob

import cv2
import numpy as np
from PIL import Image

# 8行11列棋盘角点
CHECKERBOARD = (17, 12)
criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

# 世界坐标中的3D角点，z恒为0
objpoints = []
# 像素坐标中的2D点
imgpoints = []

# 利用棋盘定义世界坐标系中的角点
objp = np.zeros((1, CHECKERBOARD[0] * CHECKERBOARD[1], 3), np.float32)
objp[0, :, :2] = np.mgrid[0:CHECKERBOARD[0], 0:CHECKERBOARD[1]].T.reshape(-1, 2)

# 从文件夹中读取所有图片
images = glob.glob('C:\\Users\\TSIC\\Documents\\GitHub\\DobotM1Project\\Mycode\\converted_jpgs\\*.jpg')
gray = None
for i in range(len(images)):
    
    fname = images[i]
    img = cv2.imread(fname)
    print(i,fname)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 查找棋盘角点
    ret, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, cv2.CALIB_CB_ADAPTIVE_THRESH +
                                             cv2.CALIB_CB_FAST_CHECK + cv2.CALIB_CB_NORMALIZE_IMAGE)
    print(ret)
    """
    使用cornerSubPix优化探测到的角点
    """
    if ret == True:
        print("det")
        objpoints.append(objp)
        corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        imgpoints.append(corners2)
        # 显示角点
        img = cv2.drawChessboardCorners(img, CHECKERBOARD, corners2, ret)
        new_img = Image.fromarray(img.astype(np.uint8))
        new_img.save('chessboard_{}.png'.format(i))
        # plt.imshow(img)
        # plt.show()
    #cv2.imshow('img', gray)
    #cv2.waitKey(0)

# cv2.destroyAllWindows()
# 标定
ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)
print("重投影误差:\n")
print(ret)
print("内参 : \n")
print(mtx)
print("畸变 : \n")
print(dist)
print("旋转向量 : \n")
print(rvecs)
print("平移向量 : \n")
print(tvecs)

