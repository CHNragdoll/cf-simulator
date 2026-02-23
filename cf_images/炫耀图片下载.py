import requests
import os

# 保存目录
save_dir = "lotb_images"
os.makedirs(save_dir, exist_ok=True)

# 基础URL
base_url = "https://game.gtimg.cn/images/actdaoju/act/a20260130ryzc/lot/lotb{}.png"

for i in range(1, 12):  # 1 到 11
    url = base_url.format(i)
    filename = os.path.join(save_dir, f"lotb{i}.png")

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open(filename, "wb") as f:
                f.write(response.content)
            print(f"✅ 下载成功: lotb{i}.png")
        else:
            print(f"❌ 文件不存在: lotb{i}.png (状态码 {response.status_code})")
    except Exception as e:
        print(f"⚠️ 下载失败: lotb{i}.png -> {e}")

print("下载完成")