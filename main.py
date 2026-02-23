import os
import requests
from urllib.parse import urlparse

images = [
      '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/bg.jpg',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/logos.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/titles.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/btns.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/part1_pop1.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/part1_zcx_img.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/part3_porp_img1.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/part3_porp_img2.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/part3_porp_img3.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/part3_porp_img4.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/part3_porp_img5.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/part3_porp_img6.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/part3_porp_img7.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/part3_porp_img8.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/part3_porp_img9.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/part3_porp_img10.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/part3_porp_img11.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/part3_porp_img12.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/part4_porp_img1.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/part4_porp_img2.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/part4_porp_img3.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/lot/lot1.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/lot/lot2.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/lot/lot3.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/lot/lot4.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/lot/lot5.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/lot/lot6.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/lot/lot7.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/lot/lot8.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/lot/lot9.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/lot/lot10.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/lot/lotb1.png',
  '//game.gtimg.cn/images/actdaoju/act/a20260130ryzc/side_qrcode.png'
]

os.makedirs('cf_images', exist_ok=True)
os.makedirs('cf_images/lot', exist_ok=True)

for url in images:
    full_url = 'https:' + url
    filename = os.path.basename(url)
    if '/lot/' in url:
        filepath = f'cf_images/lot/{filename}'
    else:
        filepath = f'cf_images/{filename}'

    try:
        response = requests.get(full_url, timeout=10)
        if response.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(response.content)
            print(f'下载成功: {filename}')
        else:
            print(f'下载失败: {filename}')
    except Exception as e:
        print(f'下载出错: {filename} - {str(e)}')