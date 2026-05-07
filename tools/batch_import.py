import os
import sys
import time
import shutil
import uuid
import hashlib
from dotenv import load_dotenv

# ==========================================
# 嚴格的路徑設定與模組匯入防禦
# ==========================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from core.image_utils import encode_image_to_base64
from core.vlm_client import analyze_anime_image
from database.db_handler import insert_image_data, is_hash_exists, init_db
from core.vector_search import VectorSearchEngine

# 資料夾常數
IMPORT_DIR = os.path.join(BASE_DIR, 'database', 'import_queue')
IMAGE_DIR = os.path.join(BASE_DIR, 'database', 'images')
DUPLICATE_DIR = os.path.join(BASE_DIR, 'database', 'duplicates')

# 確保所有必要的資料夾都存在
for d in [IMPORT_DIR, IMAGE_DIR, DUPLICATE_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# ==========================================
# API Key 輪替管理員 (API Key Pool & Rotation)
# ==========================================
class APIKeyManager:
    def __init__(self):
        load_dotenv()
        self.keys = []
        
        # 優先讀取陣列格式的 Keys
        keys_str = os.environ.get("GEMINI_API_KEYS", "")
        if keys_str:
            self.keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        
        # 若無陣列，退回讀取單一 Key
        if not self.keys:
            single_key = os.environ.get("GEMINI_API_KEY", "")
            if single_key:
                self.keys.append(single_key.strip())
                
        if not self.keys:
            print("❌ 錯誤：找不到任何有效的 API Key，請檢查 .env 檔案中的 GEMINI_API_KEYS 或 GEMINI_API_KEY。")
            sys.exit(1)
            
        self.current_index = 0
        print(f"🔑 成功載入 {len(self.keys)} 把 API Key 準備輪替。")

    def get_current_key(self) -> str:
        return self.keys[self.current_index]

    def rotate_key(self) -> bool:
        """切換到下一把 Key，若全部用盡則回傳 False"""
        self.current_index += 1
        if self.current_index >= len(self.keys):
            print("🚨 警告：所有 API Key 的額度都已經耗盡 (429 Error)！")
            return False
        print(f"🔄 觸發 Rate Limit，已自動切換至第 {self.current_index + 1} 把 API Key。")
        return True

def calculate_md5(file_path: str) -> str:
    """計算檔案的 MD5 Hash"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

# ==========================================
# 主程式
# ==========================================
def main():
    print("="*50)
    print("🚀 啟動批次上傳與打標籤工具 (Batch Uploader)")
    print("="*50)

    # 1. 初始化資料庫結構與 Hash 護城河
    init_db()

    # 2. 載入模型設定
    base_url = os.environ.get("BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    model_name = os.environ.get("MODEL_NAME", "gemini-3.1-flash-lite-preview")
    
    # 3. 初始化 Key 管理員
    key_manager = APIKeyManager()

    # 4. 掃描待處理圖片
    valid_extensions = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    files_to_process = [
        f for f in os.listdir(IMPORT_DIR) 
        if os.path.splitext(f)[1].lower() in valid_extensions
    ]

    if not files_to_process:
        print(f"📂 資料夾 {IMPORT_DIR} 中沒有找到待處理的圖片。")
        print("💡 請將想批次上傳的圖片放入該資料夾後再執行本腳本。")
        return

    print(f"📦 發現 {len(files_to_process)} 張待處理圖片，開始執行管線...")
    
    processed_count = 0
    skipped_count = 0
    error_count = 0

    for filename in files_to_process:
        source_path = os.path.join(IMPORT_DIR, filename)
        print(f"\n⏳ 正在處理: {filename}")

        # [中斷恢復機制 1] 計算 MD5
        file_hash = calculate_md5(source_path)
        
        # [中斷恢復機制 2] 檢查是否已存在於資料庫
        if is_hash_exists(file_hash):
            print(f"⏭️  [跳過] Hash 已存在資料庫，自動移至 duplicates 資料夾 ({file_hash[:8]}...)")
            shutil.move(source_path, os.path.join(DUPLICATE_DIR, filename))
            skipped_count += 1
            continue
            
        # 轉換為 base64
        base64_data = encode_image_to_base64(source_path)
        if not base64_data:
            print(f"❌ [錯誤] 圖片轉碼失敗: {filename}")
            error_count += 1
            continue

        # 呼叫 API (具備自動重試與 Key 輪替機制)
        success = False
        while not success:
            current_key = key_manager.get_current_key()
            result = analyze_anime_image(base64_data, current_key, base_url, model_name)
            
            if result["success"]:
                success = True
                ai_data = result["data"]
                break
            else:
                error_msg = result.get("error", "").lower()
                # 偵測是否為 Rate Limit (429) 錯誤
                if "429" in error_msg or "quota" in error_msg or "exhausted" in error_msg:
                    print(f"⚠️ [API 限制] 偵測到 429 錯誤: {result['error']}")
                    if key_manager.rotate_key():
                        print("⏳ 等待 2 秒後使用新 Key 重試...")
                        time.sleep(2)
                        continue # 回到 while 迴圈開頭使用新 Key
                    else:
                        print("🛑 批次任務因 API 額度耗盡而強制作業中斷。")
                        return # 直接結束整個腳本
                else:
                    print(f"❌ [錯誤] AI 解析失敗: {result['error']}")
                    break # 跳出 while，進入下一張圖片
                    
        if not success:
            error_count += 1
            continue

        # 生成新檔名並搬移檔案 (寫入正式圖庫)
        ext = os.path.splitext(filename)[1] or ".png"
        safe_filename = f"img_{uuid.uuid4().hex}{ext}"
        target_path = os.path.join(IMAGE_DIR, safe_filename)
        
        try:
            shutil.move(source_path, target_path)
        except Exception as e:
            print(f"❌ [錯誤] 移動檔案失敗: {e}")
            error_count += 1
            continue

        # 寫入資料庫
        db_id = insert_image_data(safe_filename, ai_data, file_hash)
        if db_id:
            print(f"✅ [成功] 已存入資料庫 ID: {db_id} (標籤: {', '.join(ai_data.get('tags', []))})")
            processed_count += 1
        else:
            print(f"❌ [錯誤] 寫入資料庫失敗，退回檔案...")
            shutil.move(target_path, source_path) # 退回 import_queue
            error_count += 1

        # [嚴格的 RPM 節流閥] 
        # 由於 Gemini Free 限制 15 RPM，我們強制每次請求後休息 4.1 秒 (60 / 15 = 4)
        print("💤 節流閥啟動，冷卻 4.1 秒以保護 API Rate Limit...")
        time.sleep(4.1)

    print("\n" + "="*50)
    print("🎉 批次任務執行完畢！")
    print(f"📊 統計報表: 處理成功 {processed_count} 張 | 跳過重複 {skipped_count} 張 | 發生錯誤 {error_count} 張")
    
    if processed_count > 0:
        print("🧠 偵測到新資料寫入，正在觸發 FAISS 索引重建...")
        engine = VectorSearchEngine()
        engine.build_index()
        print("✅ FAISS 大腦更新完成！")
    print("="*50)

if __name__ == "__main__":
    main()