from pathlib import Path
import os

# 指定路徑
target_dir = Path(__file__).resolve().parents[2] / "parameter" / "DR" / "BD-00009260-DR"


# 檢查路徑是否正確
print(f"🔍 目前 target_dir = {target_dir}")
print(f"📁 資料夾存在嗎？ {target_dir.exists()}")

print("📃 該資料夾下檔案如下：")
for f in target_dir.iterdir():
    print(f" - {f.name}")

# 找出 bmp 檔案
bmp_files = sorted(target_dir.glob("*.bmp"))

if not bmp_files:
    print("⚠️ 沒有找到任何 .bmp 檔案，請確認路徑與副檔名大小寫。")
else:
    for idx, file in enumerate(bmp_files, start=1):
        new_name = f"{idx}.bmp"
        new_path = target_dir / new_name
        print(f"📝 重新命名：{file.name} ➜ {new_name}")
        os.rename(file, new_path)

    print("✅ 所有檔案已重新命名完成！")
