import os
import json
import sqlite3
import threading
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

# ==========================================
# 嚴格的環境與路徑設定
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 動態回推至 database/data/ 目錄
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), 'database', 'data')
SQLITE_DB_PATH = os.path.join(DATA_DIR, 'metadata.db')
FAISS_INDEX_PATH = os.path.join(DATA_DIR, 'anime_vectors.faiss')

# 選擇對繁簡中文語意理解極佳的模型
EMBEDDING_MODEL_NAME = "shibing624/text2vec-base-chinese"

class VectorSearchEngine:
    def __init__(self):
        """初始化檢索引擎：載入模型與 FAISS 索引"""
        print(f"⏳ 正在載入 Embedding 模型 ({EMBEDDING_MODEL_NAME})...")
        # 警告：這一步在第一次執行時會花比較久時間下載模型 (約 400MB)
        self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        self.dimension = self.model.get_sentence_embedding_dimension()
        self._index_lock = threading.RLock()
        
        # 載入或建立 FAISS 索引
        # 使用 IndexFlatIP (內積) 搭配後續的 L2 正規化，來達成完美的 Cosine Similarity (餘弦相似度)
        # IndexIDMap 確保 FAISS 的向量 ID 能與 SQLite 的 Primary Key 1:1 綁定
        if os.path.exists(FAISS_INDEX_PATH):
            print(f"📂 找到現有 FAISS 索引，正在載入...")
            self.index = faiss.read_index(FAISS_INDEX_PATH)
        else:
            print(f"✨ 建立全新的 FAISS 索引空間...")
            self.index = faiss.IndexIDMap(faiss.IndexFlatIP(self.dimension))

    def _get_db_connection(self):
        """取得 SQLite 連線的內部防禦函數"""
        if not os.path.exists(SQLITE_DB_PATH):
            raise FileNotFoundError(f"找不到資料庫檔案: {SQLITE_DB_PATH}，請先執行資料庫初始化。")
        return sqlite3.connect(SQLITE_DB_PATH)

    def build_index(self):
        """從 SQLite 撈取所有圖片資料，組合字串後轉換為向量，並寫入 FAISS"""
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        # 嚴格撈取我們約定好的 5 大語意欄位，刻意排除 anime_title 避免污染語意
        cursor.execute('''
            SELECT id, subtitle, vibe_description, usage_context, character_info, tags 
            FROM anime_images
        ''')
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            print("⚠️ 資料庫中目前沒有任何圖片資料，取消建立索引。")
            return False

        texts_to_embed = []
        ids = []

        print(f"🧠 準備將 {len(rows)} 筆資料轉換為高維度向量...")
        for row in rows:
            db_id, subtitle, vibe, context, character, tags_json = row
            
            # 安全還原 tags 陣列為字串
            try:
                tags_list = json.loads(tags_json)
                tags_str = "、".join(tags_list)
            except:
                tags_str = ""

            # 💡 核心魔法：使用前綴 (Prefix) 組合文字，引導模型注意力 (Attention)
            combined_text = (
                f"[字幕]: {subtitle} "
                f"[氛圍]: {vibe} "
                f"[情境]: {context} "
                f"[特徵]: {character} "
                f"[標籤]: {tags_str}"
            )
            texts_to_embed.append(combined_text)
            ids.append(db_id)

        # 轉換為 Embedding 向量
        print("⚡ 正在進行向量運算 (Encoding)...")
        embeddings = self.model.encode(texts_to_embed, show_progress_bar=True)
        
        # ⚠️ 致命防線：FAISS 對資料型別要求極度嚴格
        embeddings = np.array(embeddings).astype('float32')
        ids_array = np.array(ids).astype('int64')

        # L2 正規化是使用 Inner Product 計算 Cosine Similarity 的絕對前提
        faiss.normalize_L2(embeddings)

        # 先建 shadow index，最後再以鎖保護方式 swap，避免與 search 競態
        new_index = faiss.IndexIDMap(faiss.IndexFlatIP(self.dimension))
        new_index.add_with_ids(embeddings, ids_array)
        
        with self._index_lock:
            self.index = new_index
            # 實體化存檔
            if not os.path.exists(DATA_DIR):
                os.makedirs(DATA_DIR)
            faiss.write_index(self.index, FAISS_INDEX_PATH)
        print(f"✅ 成功將 {len(ids)} 筆向量索引寫入硬碟 ({FAISS_INDEX_PATH})！")
        return True

    def _calculate_score(self, original_query: str, intent_query: str, row: tuple, vector_score: float) -> dict:
        """計算多維度綜合權重分數 (防範字面過擬合版)"""
        db_id, filename, subtitle, vibe, context, tags_json = row
        
        # 1. 標籤命中分數 (加入平滑化，防止小樣本放大)
        tag_score = 0.0
        try:
            tags_list = json.loads(tags_json) if tags_json else []
            combined_text = f"{original_query} {intent_query}"
            matched_tags = [tag for tag in tags_list if tag in combined_text]
            if tags_list and matched_tags:
                # 使用平滑化公式 (Smoothing)：分母加上常數 2，避免 1/1 就拿滿分
                tag_score = min(1.0, (len(matched_tags) / (len(tags_list) + 2)) * 2.5)
        except:
            tags_list = []
            
        # 2. 【核心重構 3】柔性化鸚鵡學舌懲罰 (Smart Echo Penalty)
        # 避免使用者發送「蛤？」等短句時，系統因死板扣分而錯失最貼切的短句梗圖。
        # 透過字元重疊率動態計算，只有在「長句高度抄襲」時才給予比例懲罰。
        echo_penalty = 0.0
        if subtitle and subtitle != "無":
            # 移除常見標點與無意義停用詞
            stop_chars = set("的了是你我他這那就在也！？，。、；：()[]（） \t\n~～")
            clean_sub = set(c for c in subtitle if c not in stop_chars)
            clean_query = set(c for c in original_query if c not in stop_chars)
            
            # 短句豁免機制：若字幕有效字元小於 3 個，視為短句語氣，不予懲罰
            if len(clean_sub) >= 3 and len(clean_query) >= 3:
                # 計算交集：字幕中有多少獨立字元出現在使用者的查詢中
                overlap_chars = clean_sub.intersection(clean_query)
                
                # 計算覆蓋率：字幕內容有多少比例是「抄襲」使用者的 (0.0 ~ 1.0)
                overlap_ratio = len(overlap_chars) / len(clean_sub)
                
                # 柔性懲罰：覆蓋率超過 50% 時開始計算懲罰，最高扣 0.2
                if overlap_ratio > 0.5:
                    # 比例映射：重疊率 0.5 -> 扣 0.0; 重疊率 1.0 -> 扣 -0.2
                    echo_penalty = round(-0.2 * ((overlap_ratio - 0.5) / 0.5), 3)
                
        # 3. 情境文字命中分數 (Context Match) - 改為比例計分，防範單一 2-gram 爆發
        context_score = 0.0
        if context and context != "無":
            clean_query = "".join(c for c in original_query if c not in "的了是你我他這那就在也")
            if len(clean_query) >= 2:
                # 計算 query 中的 2-gram 集合
                query_ngrams = set(clean_query[i:i+2] for i in range(len(clean_query)-1))
                if query_ngrams:
                    # 計算有多少個不重複的 2-gram 命中 context
                    matched_ngrams = sum(1 for ngram in query_ngrams if ngram in context)
                    # 依比例給分
                    context_score = min(1.0, matched_ngrams / len(query_ngrams))
                
        # 4. 【核心重構】防範字面過擬合的計分模型 (Base + Bonus)
        # 邏輯死角修復：捨棄固定的百分比權重(e.g., 65/20/15)。
        # 若採固定權重，一個語意極差(0.4)但字面全中(1.0)的結果，
        # 其總分(0.4*0.65 + 0.35 = 0.61)會贏過語意完美(0.9)但字面沒中(0.0)的結果(0.9*0.65 = 0.585)。
        # 新邏輯：以 vector_score 為絕對基底。只有在語意及格時，才給予字面加分 (Bonus)。
        base_score = vector_score
        
        # 動態閥值：語意越好，字面加分的上限才越高
        lexical_bonus = 0.0
        if vector_score >= 0.55:
            # 語意優良：允許最大 +0.15 的字面加分
            lexical_bonus = (tag_score * 0.10) + (context_score * 0.05)
        elif vector_score >= 0.45:
            # 語意及格邊緣：字面加分減半 (最大 +0.075)
            lexical_bonus = (tag_score * 0.05) + (context_score * 0.025)
            
        total_score = base_score + lexical_bonus + echo_penalty
        
        return {
            "total_score": total_score,
            "vector_score": vector_score,
            "subtitle_score": echo_penalty,
            "tag_score": tag_score,
            "tags_list": tags_list,
            "context_score": context_score,
            "lexical_bonus": lexical_bonus
        }

    def search(self, original_query: str, intent_query: str = None, top_k: int = 3) -> dict:
        """
        接收日常對話，透過 FAISS 找出語意最接近的 Top-K 圖片，並回傳完整資料。
        """
        # [核心重構 2] 統一 Embedding Prompt 結構 (提升 FAISS 召回率)
        # 原理：讓 Query (搜尋字串) 的 Prefix 與 Document (資料庫索引) 的 Prefix 完全對齊。
        # 由於 build_index 使用了 [情境]: 與 [氛圍]:，在搜尋時使用相同的 Prompt 結構，
        # 能大幅引導 Sentence-Transformer 在同一個 Latent Space (潛在空間) 進行 Cosine 比對。
        if not intent_query:
            # 若無意圖，為了對齊模型前綴注意力，仍保持基本結構
            search_query = f"[氛圍]: {original_query} [情境]: {original_query}"
        else:
            # 嚴格對齊 build_index 的順序：[氛圍] 在前，[情境] 在後
            search_query = f"[氛圍]: {intent_query} [情境]: {original_query}"

        # 1. 查詢字串向量化與正規化 (💡使用合併後的 search_query 去搜尋)
        query_embedding = self.model.encode([search_query])
        query_embedding = np.array(query_embedding).astype('float32')
        faiss.normalize_L2(query_embedding)

        # 2. FAISS 空間搜索 (進一步擴大海選池，確保好圖片不會在第一階段就被漏掉)
        with self._index_lock:
            if self.index.ntotal == 0:
                return {"success": False, "error": "FAISS 索引目前為空，請先執行 build_index。"}
            candidate_k = max(top_k * 10, 30)
            distances, indices = self.index.search(query_embedding, candidate_k)
        
        # 防禦機制：處理無結果狀態
        matched_ids = indices[0].tolist()
        if not matched_ids or matched_ids[0] == -1:
            return {"success": True, "data": []}

        # 3. 回 SQLite 撈出完整的圖片詮釋資料 (Metadata)
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        placeholders = ','.join(['?'] * len(matched_ids))
        # [修改] SQL 語法新增 tags 欄位
        cursor.execute(f'''
            SELECT id, filename, subtitle, vibe_description, usage_context, tags 
            FROM anime_images 
            WHERE id IN ({placeholders})
        ''', matched_ids)
        
        results = cursor.fetchall()
        conn.close()

        # 4. 依照 FAISS 給的距離分數 (相似度) 重新排序 SQL 結果
        result_dict = {row[0]: row for row in results}
        
        final_results = []
        for i, db_id in enumerate(matched_ids):
            if db_id in result_dict:
                row = result_dict[db_id]
                vector_score = float(distances[0][i])
                
                # 進入多維度評分系統打分
                score_data = self._calculate_score(original_query, intent_query, row, vector_score)

                final_results.append({
                    "id": row[0],
                    "filename": row[1],
                    "subtitle": row[2],
                    "vibe_description": row[3],
                    "usage_context": row[4],
                    "tags": score_data["tags_list"],
                    "similarity_score": vector_score,       # 原始向量分數
                    "total_score": score_data["total_score"], # 綜合總分
                    "debug_scores": score_data              # 除錯用細項
                })
                
        # 5. 根據我們的 Deterministic Score (綜合總分) 進行重排 (Rerank)
        final_results.sort(key=lambda x: x["total_score"], reverse=True)

        # 6. 只回傳使用者要求的前 K 筆
        return {"success": True, "data": final_results[:top_k]}

# ==========================================
# 整合測試區塊 (Integration Test)
# ==========================================
if __name__ == "__main__":
    import sys
    sys.path.append(os.path.dirname(BASE_DIR))
    from database.db_handler import insert_image_data, init_db
    
    print("\n" + "="*50)
    print("🚀 啟動 Vector Search 整合演習")
    print("="*50)
    
    # 確保資料庫結構存在
    init_db()
    
    print("\n[測試步驟 1] 植入極端測試資料至 SQLite...")
    
    dummy_data_1 = {
        "subtitle": "我要殺了你！",
        "vibe_description": "極度憤怒、失去理智、想要破壞一切。",
        "usage_context": "當被老闆陰了、或是玩遊戲遇到豬隊友時。",
        "character_info": "紅眼黑髮男子",
        "tags": ["生氣", "憤怒", "殺意", "翻桌"],
        "anime_title": "未分類"
    }
    
    dummy_data_2 = {
        "subtitle": "為什麼會變成這樣...",
        "vibe_description": "極度悲傷、絕望、失去生存動力的大哭。",
        "usage_context": "當抽卡全部保底、或是薪水不見的時候。",
        "character_info": "藍髮流淚少女",
        "tags": ["悲傷", "大哭", "絕望", "保底"],
        "anime_title": "未分類"
    }
    
    dummy_data_3 = {
        "subtitle": "蛤！？",
        "vibe_description": "無法理解當下狀況的極度傻眼。",
        "usage_context": "聽到荒謬言論時表達震驚。",
        "character_info": "粉色頭髮小女孩",
        "tags": ["傻眼", "驚訝"],
        "anime_title": "未分類"
    }
    
    # [修改] 使用假檔名強制寫入，並補上假 Hash 參數以符合新版資料庫合約
    insert_image_data("test_angry_123.png", dummy_data_1, "fake_hash_angry_001")
    insert_image_data("test_sad_456.png", dummy_data_2, "fake_hash_sad_002")
    insert_image_data("test_shock_789.png", dummy_data_3, "fake_hash_shock_003")
    
    print("\n[測試步驟 2] 啟動檢索引擎並建立大腦索引...")
    engine = VectorSearchEngine()
    engine.build_index()
    
    # 進行高難度讀心測試
    test_query = "天啊，我剛買的便當掉在地上，好想死"
    print(f"\n[測試步驟 3] 模擬使用者發送日常訊息：")
    print(f"💬 使用者：「{test_query}」")
    
    print("\n🔍 正在進行高維度語意搜索...")
    search_result = engine.search(test_query, top_k=2)
    
    if search_result["success"]:
        print(f"\n🎯 系統判斷最符合的梗圖是：")
        for idx, item in enumerate(search_result["data"]):
            print(f"\n   第 {idx+1} 名 (相似度: {item['similarity_score']:.4f})")
            print(f"   - 檔名: {item['filename']}")
            print(f"   - 圖片字幕: {item['subtitle']}")
            print(f"   - 匹配情境: {item['usage_context']}")
    else:
        print(f"❌ 搜尋失敗: {search_result['error']}")
