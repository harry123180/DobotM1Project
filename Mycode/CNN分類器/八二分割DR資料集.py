import shutil
import random
from pathlib import Path

# 路徑設定
root_dir = Path("D:/AWORKSPACE/Github/DobotM1Project")
input_dir = root_dir / "output_circles_all"
output_base = root_dir / "circle_split_dataset"

# 輸出資料夾結構
output_dirs = {
    "A_train": output_base / "A_train",
    "A_test": output_base / "A_test",
    "B_train": output_base / "B_train",
    "B_test": output_base / "B_test"
}

# 建立資料夾
for path in output_dirs.values():
    path.mkdir(parents=True, exist_ok=True)

# 依照 prefix 分類圖片
images = list(input_dir.glob("*.bmp"))
group_A = [img for img in images if "front" in img.name.lower()]
group_B = [img for img in images if "back" in img.name.lower()]

# 分割函式
def split_and_copy(images, train_dir, test_dir, ratio=0.8):
    random.shuffle(images)
    split_idx = int(len(images) * ratio)
    for i, img_path in enumerate(images):
        dest = train_dir if i < split_idx else test_dir
        new_name = f"{img_path.stem}.bmp"
        shutil.copy(img_path, dest / new_name)

# 分別分割 A/B 類
split_and_copy(group_A, output_dirs["A_train"], output_dirs["A_test"])
split_and_copy(group_B, output_dirs["B_train"], output_dirs["B_test"])

import os
result = {
    "A_train": len(os.listdir(output_dirs["A_train"])),
    "A_test": len(os.listdir(output_dirs["A_test"])),
    "B_train": len(os.listdir(output_dirs["B_train"])),
    "B_test": len(os.listdir(output_dirs["B_test"]))
}
result
