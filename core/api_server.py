import os
import sys

# ==========================================
# 嚴格的路徑設定與模組匯入防禦
# ==========================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from database.db_handler import (
    insert_image_data, init_db, is_hash_exists,
    get_all_images, get_image_by_id, update_image_metadata, delete_image_by_id
)
from core.vector_search import VectorSearchEngine
from core.vlm_client import analyze_anime_image, generate_reply_intent, llm_reranker
from core.image_utils import encode_image_to_base64
import uuid
import hashlib  # [新增] 用於計算檔案 MD5
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# [修改] 匯入新增的 is_hash_exists 城門守衛

load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
BASE_URL = os.environ.get(
    "BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
# "gemini-3.1-flash-lite-preview" "gemini-2.5-flash"
MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-3.1-flash-lite-preview")

IMAGE_DIR = os.path.join(BASE_DIR, 'database', 'images')
if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

# ==========================================
# 生命週期管理
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [系統啟動] 正在初始化資料庫與 Hash 護城河...")
    init_db()

    print("🚀 [系統啟動] 正在掛載 AI 向量檢索引擎...")
    app.state.vector_engine = VectorSearchEngine()

    yield

    print("🛑 [系統關閉] 正在釋放記憶體資源...")
    app.state.vector_engine = None

# ==========================================
# FastAPI 實例與中介軟體設定
# ==========================================
app = FastAPI(
    title="梗圖機器人 API 中樞",
    description="提供影像語意分析、向量檢索與 Hash 去重的無頭服務",
    version="1.1.0",  # 升級版號
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")

class SearchResultItem(BaseModel):
    id: int
    filename: str
    subtitle: str
    vibe_description: str
    usage_context: str
    similarity_score: float
    image_url: str
    tags: list[str]  # [新增] 讓前端能顯示標籤藥丸
    total_score: float = 0.0      # [新增] 綜合總分
    debug_scores: dict = Field(default_factory=dict)  # [新增] 各項得分細節

class SearchResponse(BaseModel):
    success: bool
    data: list[SearchResultItem]
    error: Optional[str] = None
    warning: Optional[str] = None
    persona_used: Optional[str] = None  # [新增] 本次選用的人設 Key

# ==========================================
# 核心端點
# ==========================================

@app.get("/")
async def health_check():
    return {"status": "ok", "message": "API 伺服器運行中", "engine_loaded": hasattr(app.state, "vector_engine")}

import json
import random

def load_personas() -> dict:
    """從外部設定檔讀取人設清單"""
    personas_path = os.path.join(BASE_DIR, "personas.json")
    personas = {"default": "為了達到幽默吐槽、溫暖安慰、或是產生共鳴的效果"}
    if os.path.exists(personas_path):
        try:
            with open(personas_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if loaded:
                    personas = loaded
        except Exception:
            pass
    return personas

@app.get("/api/personas")
async def get_personas():
    """取得系統所有可用的人設 Key"""
    personas = load_personas()
    return {"success": True, "data": list(personas.keys())}
    
@app.get("/api/search", response_model=SearchResponse)
async def search_memes(
    query: str = Query(..., description="使用者的日常對話或抱怨"),
    top_k: int = Query(3, description="回傳的圖片數量", ge=1, le=10),
    exclude_img_ids: list[int] = Query(default=[], description="要排除的圖片 ID 列表"),
    persona: Optional[str] = Query(None, description="指定使用的人設 (留空或 random 則隨機)")
):
    if not query.strip():
        raise HTTPException(status_code=400, detail="搜尋字串不能為空")

    warning_messages: list[str] = []

    try:
        # 處理人設選擇，防呆白名單確保安全
        all_personas = load_personas()
        if not persona or persona == "random" or persona not in all_personas:
            persona_name, persona_desc = random.choice(list(all_personas.items()))
        else:
            persona_name = persona
            persona_desc = all_personas[persona]

        # [修改] 1. 讓 LLM 進行意圖轉換 (Query Transformation)，並傳遞人設
        intent_query, intent_warning = await run_in_threadpool(
            generate_reply_intent, query, GEMINI_API_KEY, BASE_URL, MODEL_NAME, persona_name, persona_desc
        )
        print(f"\n🧠 [AI 意圖轉換]\n💬 使用者說: {query}\n🎯 尋找目標: {intent_query}\n")
        if intent_warning:
            warning_messages.append(intent_warning)

        engine: VectorSearchEngine = app.state.vector_engine
        # [修改] 2. 第一、第二階段：多抓取 3 倍的候選名單 (e.g., 要 3 張圖，就先海選 9 張)
        candidate_count = max(top_k * 3, 10)
        result = await run_in_threadpool(engine.search, query, intent_query, candidate_count)

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])

        # [新增] 黑名單過濾機制
        if exclude_img_ids and result["data"]:
            filtered_data = [item for item in result["data"]
                             if item["id"] not in exclude_img_ids]
            if not filtered_data:
                print("⚠️ [黑名單過濾] 警告：所有候選圖片都在黑名單中，忽略黑名單條件。")
            else:
                result["data"] = filtered_data

        # [新增] 3. 第三階段：LLM 裁判重排 (Rerank)
        if result["data"]:
            print(
                f"⚖️ [LLM 裁判] 正在從 {len(result['data'])} 張候選圖中挑選最棒的 {top_k} 張...")
            final_candidates, reranker_warning = await run_in_threadpool(
                llm_reranker, query, intent_query, result["data"], top_k, GEMINI_API_KEY, BASE_URL, MODEL_NAME
            )
            if reranker_warning:
                warning_messages.append(reranker_warning)
        else:
            final_candidates = []

        for item in final_candidates:
            item["image_url"] = f"/images/{item['filename']}"

        final_warning = " | ".join(warning_messages) if warning_messages else None
        return {
            "success": True, 
            "data": final_candidates, 
            "warning": final_warning,
            "persona_used": persona_name
        }
    except HTTPException:
        # Pydantic/FastAPI will natively handle HTTPException, re-raise explicitly
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"搜尋發生未預期錯誤: {type(e).__name__} - {str(e)}")

@app.post("/api/upload")
async def upload_and_analyze(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="僅允許上傳圖片格式")

    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="未設定 GEMINI_API_KEY")

    # ==========================================
    # [新增] 階段 1：記憶體讀取與 Hash 計算
    # ==========================================
    try:
        # 將整張圖片讀入記憶體 (注意：若檔案過大會有 OOM 風險)
        contents = await file.read()
        file_hash = hashlib.md5(contents).hexdigest()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"讀取檔案失敗: {str(e)}")

    # ==========================================
    # [新增] 階段 2：呼叫守衛，攔截重複檔案
    # ==========================================
    # 這裡會去資料庫極速比對，如果是 True 直接拋出 409 錯誤終止！
    is_duplicate = await run_in_threadpool(is_hash_exists, file_hash)
    if is_duplicate:
        print(f"🛡️ [閘道攔截] 拒絕上傳，發現重複圖片，Hash: {file_hash}")
        raise HTTPException(
            status_code=409,
            detail=f"圖片已存在系統中 (Hash: {file_hash})"
        )

    # 階段 3：生成 UUID 檔名並存檔
    ext = os.path.splitext(file.filename)[1] or ".png"
    safe_filename = f"img_{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(IMAGE_DIR, safe_filename)

    try:
        # [修改] 因為資料已經在記憶體裡了，直接用寫入 (write) 模式存檔，放棄 copyfileobj
        with open(file_path, "wb") as buffer:
            buffer.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"圖片儲存至硬碟失敗: {str(e)}")

    # 階段 4：進入核心分析與寫入管線
    try:
        # 轉換 base64 (因為圖片已存檔，讓底層去讀取)
        base64_data = await run_in_threadpool(encode_image_to_base64, file_path)

        print(f"🧠 正在分析全新圖片: {safe_filename}...")
        vlm_result = await run_in_threadpool(
            analyze_anime_image,
            base64_data, GEMINI_API_KEY, BASE_URL, MODEL_NAME
        )

        if not vlm_result["success"]:
            raise Exception(f"AI 分析失敗: {vlm_result['error']}")

        ai_data = vlm_result["data"]

        # [修改] 階段 5：寫入資料庫時，一併傳入 file_hash
        db_id = await run_in_threadpool(insert_image_data, safe_filename, ai_data, file_hash)
        if not db_id:
            raise Exception("寫入 SQLite 資料庫失敗 (可能被底層 UNIQUE 攔截)")

        # 更新 FAISS 記憶體
        engine: VectorSearchEngine = app.state.vector_engine
        await run_in_threadpool(engine.build_index)

        return {
            "success": True,
            "message": "上傳與分析成功",
            "image_id": db_id,
            "filename": safe_filename,
            "hash": file_hash,
            "ai_analysis": ai_data
        }

    except Exception as e:
        # Rollback: 發生錯誤時刪除剛存好的孤兒圖片
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑️ [Rollback] 已刪除因流程中斷而產生的孤兒圖片: {safe_filename}")
        raise HTTPException(status_code=500, detail=str(e))

class ImageMetadataUpdate(BaseModel):
    subtitle: Optional[str] = None
    vibe_description: Optional[str] = None
    usage_context: Optional[str] = None
    tags: Optional[list[str]] = None
    anime_title: Optional[str] = None

@app.get("/api/images")
async def api_get_images(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query("")
):
    try:
        result = await run_in_threadpool(get_all_images, page, limit, search)
        for item in result["data"]:
            item["image_url"] = f"/images/{item['filename']}"
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/images/{image_id}")
async def api_get_image(image_id: int):
    try:
        item = await run_in_threadpool(get_image_by_id, image_id)
        if not item:
            raise HTTPException(status_code=404, detail="找不到該圖片")
        item["image_url"] = f"/images/{item['filename']}"
        return {"success": True, "data": item}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/images/{image_id}")
async def api_update_image(image_id: int, data: ImageMetadataUpdate):
    try:
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        success = await run_in_threadpool(update_image_metadata, image_id, update_data)
        if not success:
            raise HTTPException(status_code=404, detail="找不到該圖片或更新失敗")
        return {"success": True, "message": "更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/images/{image_id}")
async def api_delete_image(image_id: int):
    try:
        filename = await run_in_threadpool(delete_image_by_id, image_id)
        if not filename:
            raise HTTPException(status_code=404, detail="找不到該圖片或刪除失敗")
        
        file_path = os.path.join(IMAGE_DIR, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            
        # 注意：刪除後可能也需要 rebuild FAISS，但在這裡不強制自動執行，可以讓前端打 rebuild API
        return {"success": True, "message": "刪除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/rebuild-faiss")
async def api_rebuild_faiss():
    try:
        engine: VectorSearchEngine = app.state.vector_engine
        success = await run_in_threadpool(engine.build_index)
        if success:
            return {"success": True, "message": "FAISS 索引重建成功"}
        else:
            raise HTTPException(status_code=500, detail="FAISS 索引重建失敗")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload-batch")
async def api_upload_batch(files: list[UploadFile] = File(...)):
    # 簡單的 MVP 實作，針對每個檔案依序處理，可根據後續需求調整
    results = []
    engine: VectorSearchEngine = app.state.vector_engine
    
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="未設定 GEMINI_API_KEY")

    uploaded_count = 0
    failed_count = 0

    for file in files:
        current_file_path = None
        committed = False

        try:
            if not file.content_type.startswith("image/"):
                results.append({"filename": file.filename, "success": False, "error": "僅允許上傳圖片格式"})
                failed_count += 1
                continue

            contents = await file.read()
            file_hash = hashlib.md5(contents).hexdigest()
            
            is_duplicate = await run_in_threadpool(is_hash_exists, file_hash)
            if is_duplicate:
                results.append({"filename": file.filename, "success": False, "error": "圖片已存在系統中"})
                failed_count += 1
                continue

            ext = os.path.splitext(file.filename)[1] or ".png"
            safe_filename = f"img_{uuid.uuid4().hex}{ext}"
            current_file_path = os.path.join(IMAGE_DIR, safe_filename)

            with open(current_file_path, "wb") as buffer:
                buffer.write(contents)

            base64_data = await run_in_threadpool(encode_image_to_base64, current_file_path)
            vlm_result = await run_in_threadpool(
                analyze_anime_image,
                base64_data, GEMINI_API_KEY, BASE_URL, MODEL_NAME
            )

            if not vlm_result["success"]:
                raise RuntimeError(f"AI 分析失敗: {vlm_result['error']}")

            ai_data = vlm_result["data"]
            db_id = await run_in_threadpool(insert_image_data, safe_filename, ai_data, file_hash)
            
            if not db_id:
                raise RuntimeError("寫入資料庫失敗")

            committed = True

            results.append({"filename": file.filename, "success": True, "image_id": db_id})
            uploaded_count += 1
            
        except Exception as e:
            if current_file_path and (not committed) and os.path.exists(current_file_path):
                os.remove(current_file_path)
            results.append({"filename": file.filename, "success": False, "error": str(e)})
            failed_count += 1

    # 決定整體狀態
    if failed_count == 0 and uploaded_count > 0:
        status = "all_success"
    elif uploaded_count == 0:
        status = "failed"
    else:
        status = "partial"

    print(f"\n📊 [批次上傳總結] 狀態: {status}, 共 {len(files)} 件，成功: {uploaded_count}，失敗: {failed_count}\n")

    # 判斷是否需要重建索引
    if uploaded_count > 0:
        await run_in_threadpool(engine.build_index)
        
    return {
        "success": True if status != "failed" else False,
        "status": status,
        "uploaded_count": uploaded_count,
        "failed_count": failed_count,
        "results": results
    }

if __name__ == "__main__":
    import uvicorn
    print("="*50)
    print("啟動 API 中樞伺服器 (FastAPI) - 具備 Hash 攔截系統")
    print("請在瀏覽器開啟 API 文件: http://localhost:8000/docs")
    print("="*50)
    uvicorn.run("core.api_server:app", host="0.0.0.0", port=8000, reload=True)
