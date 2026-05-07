import os
import base64
from io import BytesIO
from PIL import Image, ImageOps

# 定義 AI 分析的甜點區 (Sweet Spot)
MAX_IMAGE_SIZE = 1024
JPEG_QUALITY = 85

def encode_image_to_base64(image_path: str) -> str:
    """
    將本地圖片讀取、在記憶體中進行甜點區優化 (壓縮/轉正)，
    最後回傳帶有前綴的 Base64 字串，供 OpenAI-Compatible API 使用。
    
    ⚠️ 注意：此過程絕對不會修改或覆蓋硬碟中的原始檔案。
    """
    # 嚴格防禦：檢查檔案是否存在
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"找不到圖片檔案: {image_path}")

    # 使用 with 確保檔案讀取後立刻釋放鎖定，避免佔用硬碟資源
    with Image.open(image_path) as img:
        # 1. EXIF 旋轉校正
        # 很多截圖自帶旋轉屬性，必須先轉正，否則 AI 會看到歪的圖，導致 OCR 失敗
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass # 如果圖片沒有 EXIF 資訊，忽略即可

        # 2. 色彩空間標準化 (RGBA to RGB)
        # 如果是 PNG 且帶有透明背景，強制墊一層白色底，並轉為 RGB
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            background = Image.new('RGB', img.size, (255, 255, 255))
            # 將原圖貼在白色背景上
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[3]) # 使用 alpha 通道作為遮罩
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # 3. 智能等比例縮放 (降維打擊)
        # 只有當圖片最長邊超過 MAX_IMAGE_SIZE 時才縮小，小於則保持原狀
        width, height = img.size
        if width > MAX_IMAGE_SIZE or height > MAX_IMAGE_SIZE:
            # thumbnail 會在原圖比例下，將長邊縮小到指定尺寸，並改變傳入的物件本身
            img.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE), Image.Resampling.LANCZOS)
            
        # 4. 記憶體內轉碼 (In-Memory Encoding)
        # 開闢一塊暫存記憶體
        buffered = BytesIO()
        # 將處理後的圖片以 JPEG 格式存入這塊記憶體，鎖定高辨識率品質
        img.save(buffered, format="JPEG", quality=JPEG_QUALITY)
        
        # 5. Base64 編碼
        # 將記憶體中的二進位資料轉為字串
        base64_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        # 組裝成 OpenAI API 要求的 Data URI 格式
        return f"data:image/jpeg;base64,{base64_str}"

# --- 測試區塊 ---
if __name__ == "__main__":
    print("--- 執行圖片處理工具單元測試 ---")
    
    # 動態產生一個測試用的圖片路徑 (指向上一步我們建立的 images 資料夾)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_image_dir = os.path.join(base_dir, 'database', 'images')
    
    # 確保目錄存在
    if not os.path.exists(test_image_dir):
        os.makedirs(test_image_dir)
        print(f"📁 建立測試資料夾: {test_image_dir}")
        
    test_image_path = os.path.join(test_image_dir, "噗妮露是可愛史萊姆 [5]_06：07_1775217012019.png")
    
    # 如果沒有測試圖片，我們自己畫一張簡單的紅色方塊當作測試圖
    if not os.path.exists(test_image_path):
        print("沒有找到測試圖片，正在生成虛擬的高清紅底測試圖...")
        # 故意做一張很大 (2000x2000) 的圖，測試壓縮功能
        dummy_img = Image.new('RGB', (2000, 2000), color = 'red')
        dummy_img.save(test_image_path)
        print(f"✅ 虛擬圖片已儲存至: {test_image_path} (大小: 2000x2000)")
        
    try:
        print("開始處理圖片...")
        base64_result = encode_image_to_base64(test_image_path)
        
        # 印出前綴和一小段內容來驗證
        print(f"🎉 轉換成功！Base64 字串長度: {len(base64_result)}")
        print(f"字串前 50 個字元: {base64_result[:50]}...")
        
        # 防雷驗證：檢查硬碟裡的原圖有沒有被修改 (長寬應該還是 2000x2000)
        with Image.open(test_image_path) as verify_img:
            print(f"🔍 防雷驗證：硬碟中原檔的尺寸為 {verify_img.size} (如果這還是 2000x2000，代表原檔完美倖存！)")
            
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")