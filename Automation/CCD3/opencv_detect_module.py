# -*- coding: utf-8 -*-
import cv2
import numpy as np
import math
import random

#[U+5F71][U+50CF][U+524D][U+8655][U+7406]
def get_pre_treatment_image(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh

## [U+89D2][U+5EA6][U+6AA2][U+6E2C]
def get_main_contour(image,min_area_size_rate = 0.05,sequence = False):
    min_area = image.shape[0]*image.shape[1] * min_area_size_rate
    contours, _ = cv2.findContours(image, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    contours = [cnt for cnt in contours if cv2.contourArea(cnt) > min_area]
    if not contours:
        return None
    # [U+627E][U+51FA][U+6700][U+5927][U+5167][U+8F2A][U+5ED3]
    if sequence:#
        contour = contours[-1]
    else:
        contour = contours[0]
    return contour

def get_obj_angle(image,mode=0):
    #mode->0 case ,mode->1 dr
    contour = None
    rst_contour = None

    pt_img = get_pre_treatment_image(image)
    
    if mode == 0:
        contour = get_main_contour(pt_img,sequence=True)
        if contour is None:
            return None
        mask_1 = np.zeros((image.shape[1], image.shape[0]), dtype=np.uint8)
        mask_2 = np.zeros((image.shape[1], image.shape[0]), dtype=np.uint8)
        cv2.drawContours(mask_1, [contour], -1, (255,255,255), -1)
        ellipse = cv2.fitEllipse(contour)

        # [U+53D6][U+5F97][U+4E2D][U+5FC3][U+8207][U+89D2][U+5EA6]
        (x, y), (MA, ma), angle = ellipse
        print(MA)
        center = (int(x), int(y))
        # cv2.line(image,(center[0],int(center[1] - MA//2)),(center[0],int(center[1] + MA//2)),(10,50,134),2)
        # cv2.putText(image, f"MA: {MA:.2f}", (center[0]-200 , center[1] - 10),
        #         cv2.FONT_HERSHEY_SIMPLEX, 0.6, (50, 200, 0), 2)
        # [U+756B][U+6A62][U+5713][U+8207][U+65B9][U+5411]
        cv2.ellipse(mask_1, ellipse, (0,0,0), -1)
        # cv2.ellipse(image, ellipse, (35,150,0), 1)
        # print(ellipse)
        center, radius = cv2.minEnclosingCircle(contour)
        center = (int(center[0]),int(center[-1]))
        
        cv2.circle(mask_2,center,int(radius),(255,255,255),-1)
        kernel = np.ones((11, 11), np.uint8)
        mask_1 = cv2.dilate(mask_1,kernel,iterations = 1)
        mask_1 = cv2.bitwise_not(mask_1)
        rst = cv2.bitwise_and(mask_1,mask_1,mask=mask_2)
        rst_contour = get_main_contour(rst)

    else:
        rst_contour = get_main_contour(pt_img)
        if rst_contour is None:
            return None
    rect = cv2.minAreaRect(rst_contour)
    box = cv2.boxPoints(rect)
    box = np.int_(box)
    angle = rect[2]

    # [U+8996][U+89BA][U+5316]
    cv2.drawContours(image, [box], 0, (0, 255, 0), 2)
    center = tuple(np.int_(rect[0]))
    
    return center,angle



# [U+5F71][U+7247][U+4F86][U+6E90]
video_path = "video/Video_20250605172016964.avi"

# [U+91CD][U+65B0][U+8B80][U+53D6][U+5F71][U+7247]
cap = cv2.VideoCapture(video_path)
# [U+8655][U+7406][U+6BCF][U+5E40]
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    frame2 = cv2.resize(frame,(600,600))
    center,angle = get_obj_angle(frame2,mode=0)
    # frame2 = 
    cv2.putText(frame2, f"Angle: {angle:.2f} deg", (center[0] - 70, center[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
    # cv2.imshow("main",cv2.resize(frame,(1000,1000)))
    cv2.imshow("main2",frame2)
    if cv2.waitKey(0) & 0xff  == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()







# def detect_angle_with_minAreaRect(video_path):
#     cap = cv2.VideoCapture(video_path)

#     while cap.isOpened():
#         ret, frame = cap.read()
#         if not ret:
#             break

#         contour = get_main_contour(frame)
#         if contour is None:
#             continue

#         # [U+4F7F][U+7528] minAreaRect [U+64EC][U+5408][U+5916][U+63A5][U+65CB][U+8F49][U+77E9][U+5F62]
#         rect = cv2.minAreaRect(contour)
#         box = cv2.boxPoints(rect)
#         box = np.int_(box)
#         angle = rect[2]

#         # [U+8996][U+89BA][U+5316]
#         cv2.drawContours(frame, [box], 0, (0, 255, 0), 2)
#         center = tuple(np.int_(rect[0]))
#         cv2.putText(frame, f"Angle: {angle:.2f} deg", (center[0] - 70, center[1] - 10),
#                     cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

#         cv2.imshow("minAreaRect Angle Detection", cv2.resize(frame,(1000,1000)))
#         if cv2.waitKey(0) & 0xFF == ord('q'):
#             break

#     cap.release()
#     cv2.destroyAllWindows()