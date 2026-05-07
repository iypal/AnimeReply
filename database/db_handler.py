import sqlite3
import json
import os

# ==========================================
# 嚴格的路徑防禦機制
# ==========================================
# 自動推導當前檔案的絕對路徑，確保 SQLite 不會因為執行目錄不同而找不到檔案
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'metadata.db')

def _get_connection():
    """內部函數：確保資料夾存在並回傳連線"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    return sqlite3.connect(DB_PATH)

def init_db():
    """
    初始化資料庫。
    ⚠️ 差異點：新增 file_hash 欄位，並加上 UNIQUE 終極護城河。
    """
    conn = _get_connection()
    cursor = conn.cursor()
    
    # 創建動畫圖片詮釋資料表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS anime_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_hash TEXT NOT NULL UNIQUE,  -- [新增] 檔案 DNA，保證系統不存重複圖
            subtitle TEXT,
            vibe_description TEXT,
            usage_context TEXT,
            character_info TEXT,
            tags TEXT,
            anime_title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # [新增] 為了讓 is_hash_exists 查詢速度達到毫秒級，必須為 Hash 欄位建立索引
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_file_hash ON anime_images(file_hash)
    ''')
    
    conn.commit()
    conn.close()
    print(f"✅ 資料庫初始化完成，已建立 Hash 護城河！路徑: {DB_PATH}")

def is_hash_exists(file_hash: str) -> bool:
    """
    [新增] 城門守衛函數。
    API 伺服器在收到圖片瞬間，會呼叫此函數查詢該 Hash 是否已存在。
    """
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT 1 FROM anime_images WHERE file_hash = ?', (file_hash,))
    # fetchone 只要有抓到一筆就是 tuple，沒抓到就是 None
    result = cursor.fetchone() 
    
    conn.close()
    return result is not None

def insert_image_data(filename: str, ai_data: dict, file_hash: str) -> int:
    """
    將 AI 解析出來的 JSON 寫入資料庫，並綁定實體檔名與 Hash。
    ⚠️ 差異點：必須傳入 file_hash 參數。
    
    回傳值：
        插入成功後產生的 Primary Key (id)
    """
    conn = _get_connection()
    cursor = conn.cursor()
    
    # 安全的陣列轉字串：將 ['標籤1', '標籤2'] 轉成 JSON 字串陣列存入
    tags_json = json.dumps(ai_data.get("tags", []), ensure_ascii=False)
    
    try:
        # ⚠️ 差異點：寫入語法新增 file_hash
        cursor.execute('''
            INSERT INTO anime_images (
                filename, file_hash, subtitle, vibe_description, usage_context, character_info, tags, anime_title
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            filename,
            file_hash, # [新增]
            ai_data.get("subtitle", ""),
            ai_data.get("vibe_description", ""),
            ai_data.get("usage_context", ""),
            ai_data.get("character_info", ""),
            tags_json,
            ai_data.get("anime_title", "未分類")
        ))
        
        db_id = cursor.lastrowid
        conn.commit()
        print(f"💾 圖片資料已寫入資料庫，獲得專屬 ID: {db_id} (Hash: {file_hash[:8]}...)")
        return db_id
        
    except sqlite3.IntegrityError:
        # 防禦機制啟動：就算上一層判斷失誤，這裡也會被 UNIQUE 擋下
        print(f"❌ [底層防禦] 資料庫拒絕寫入，發現重複的檔案 Hash: {file_hash}")
        return None
    except Exception as e:
        print(f"❌ [底層防禦] 寫入資料庫發生未預期錯誤: {e}")
        return None
    finally:
        conn.close()

def get_all_images(page: int = 1, limit: int = 20, search: str = "") -> dict:
    """取得圖片列表，支援分頁與搜尋"""
    conn = _get_connection()
    # 讓查詢結果回傳 dict 而非 tuple
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    offset = (page - 1) * limit
    
    query = '''
        SELECT * FROM anime_images 
        WHERE subtitle LIKE ? OR vibe_description LIKE ? OR usage_context LIKE ? OR tags LIKE ? OR anime_title LIKE ?
        ORDER BY id DESC
        LIMIT ? OFFSET ?
    '''
    search_term = f"%{search}%"
    params = (search_term, search_term, search_term, search_term, search_term, limit, offset)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    # 計算總數
    count_query = '''
        SELECT COUNT(*) as total FROM anime_images 
        WHERE subtitle LIKE ? OR vibe_description LIKE ? OR usage_context LIKE ? OR tags LIKE ? OR anime_title LIKE ?
    '''
    cursor.execute(count_query, (search_term, search_term, search_term, search_term, search_term))
    total_count = cursor.fetchone()['total']
    
    conn.close()
    
    # 處理 JSON 欄位
    data = []
    for row in rows:
        item = dict(row)
        try:
            item['tags'] = json.loads(item['tags']) if item['tags'] else []
        except:
            item['tags'] = []
        data.append(item)
        
    return {
        "data": data,
        "total": total_count,
        "page": page,
        "limit": limit
    }

def get_image_by_id(image_id: int) -> dict:
    """取得單筆圖片詳情"""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM anime_images WHERE id = ?', (image_id,))
    row = cursor.fetchone()
    
    conn.close()
    
    if row:
        item = dict(row)
        try:
            item['tags'] = json.loads(item['tags']) if item['tags'] else []
        except:
            item['tags'] = []
        return item
    return None

def update_image_metadata(image_id: int, data: dict) -> bool:
    """更新圖片 Metadata"""
    conn = _get_connection()
    cursor = conn.cursor()
    
    tags_json = json.dumps(data.get("tags", []), ensure_ascii=False) if "tags" in data else None
    
    update_fields = []
    params = []
    
    if "subtitle" in data:
        update_fields.append("subtitle = ?")
        params.append(data["subtitle"])
    if "vibe_description" in data:
        update_fields.append("vibe_description = ?")
        params.append(data["vibe_description"])
    if "usage_context" in data:
        update_fields.append("usage_context = ?")
        params.append(data["usage_context"])
    if tags_json is not None:
        update_fields.append("tags = ?")
        params.append(tags_json)
    if "anime_title" in data:
        update_fields.append("anime_title = ?")
        params.append(data["anime_title"])
        
    if not update_fields:
        conn.close()
        return True # 沒有需要更新的欄位
        
    query = f"UPDATE anime_images SET {', '.join(update_fields)} WHERE id = ?"
    params.append(image_id)
    
    try:
        cursor.execute(query, tuple(params))
        conn.commit()
        success = cursor.rowcount > 0
    except Exception as e:
        print(f"❌ 更新資料庫錯誤: {e}")
        success = False
    finally:
        conn.close()
        
    return success

def delete_image_by_id(image_id: int) -> str:
    """
    從資料庫刪除圖片記錄，並回傳 filename 以便刪除實體檔案。
    回傳值：
        filename: 若刪除成功
        None: 若找不到該筆資料或發生錯誤
    """
    conn = _get_connection()
    cursor = conn.cursor()
    
    # 先取得 filename
    cursor.execute('SELECT filename FROM anime_images WHERE id = ?', (image_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
        
    filename = row[0]
    
    try:
        cursor.execute('DELETE FROM anime_images WHERE id = ?', (image_id,))
        conn.commit()
        success = cursor.rowcount > 0
    except Exception as e:
        print(f"❌ 刪除資料庫紀錄錯誤: {e}")
        success = False
    finally:
        conn.close()
        
    return filename if success else None

# ==========================================
# 本地端模組測試 (防禦性執行)
# ==========================================
if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 啟動資料庫模組自我檢測 (含 Hash 防禦)")
    print("="*50)
    
    # 1. 測試建立結構
    init_db()
    
    # 2. 準備假資料與假 Hash
    test_filename = "fake_db_test_002.png"
    test_hash = "fake_md5_d41d20427e"
    test_ai_data = {
        "subtitle": "欸！？",
        "vibe_description": "極度震驚且無法理解當下狀況的表情。",
        "usage_context": "當聽到非常荒謬、不合邏輯的言論時，用來表達強烈的不解與傻眼。",
        "character_info": "粉色頭髮小女孩",
        "tags": ["驚訝", "傻眼", "安妮亞", "下巴掉下來"]
        # 沒有提供 anime_title
    }
    
    # 3. 測試：寫入新資料
    print("\n[測試 1] 寫入全新 Hash 資料...")
    inserted_id = insert_image_data(test_filename, test_ai_data, test_hash)
    if inserted_id:
        print(f"   => 成功！ID 為 {inserted_id}")
    else:
        print("   => 失敗！寫入異常。")
        
    # 4. 測試：查詢 Hash 存在與否
    print("\n[測試 2] 驗證城門守衛 (is_hash_exists)...")
    exists = is_hash_exists(test_hash)
    print(f"   => 剛剛寫入的 Hash 是否存在？ {'是' if exists else '否'} (應為 是)")
    
    # 5. 測試：觸發終極護城河 (重複寫入)
    print("\n[測試 3] 惡意寫入相同 Hash 的資料 (預期會被擋下)...")
    duplicate_id = insert_image_data("another_file.png", test_ai_data, test_hash)
    if duplicate_id is None:
        print("   => 成功！資料庫的 UNIQUE 護城河發揮作用，成功攔截重複資料。")
    else:
        print("   => 致命錯誤！系統被重複 Hash 滲透了！")