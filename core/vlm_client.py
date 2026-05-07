import os
import time
import json
import random
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Optional

# ==========================================
# 嚴格定義強制輸出的 JSON 藍圖 (5 欄位架構)
# ==========================================


class AnimeAnalysisResult(BaseModel):
    subtitle: str = Field(
        description="提取畫面中具有『台詞性質』的字幕。請精準辨識，不要加入自己的猜測。如果畫面中沒有任何台詞字幕，請務必填寫『無』。"
    )
    vibe_description: str = Field(
        description="詳細描述圖片的情緒、氛圍與當下的情境狀態（例如：極度震驚且無法理解當下狀況，或是表現出輕蔑與不屑）。"
    )
    usage_context: str = Field(
        description="預測這張梗圖最適合用來回覆什麼樣的日常對話或情境？（例如：當朋友說了很扯的話時用來表達傻眼，或是用來強烈拒絕別人的請求）。"
    )
    # ⚠️ 嚴格限制字數與格式的 Prompt 防禦 (已放寬至 20 字，但強化語法限制)
    character_info: str = Field(
        # 必須精簡在 20 個中文字以內，且絕對禁止寫完整句子，
        description="不需要角色名稱。請詳細描述其外觀特徵。僅使用名詞片語（例如：粉色頭髮小女孩、戴黑框眼鏡的男子）。若無人則填『無』。"
    )
    tags: list[str] = Field(
        description="提取 5 到 8 個最能代表這張圖的精煉關鍵字（包含情緒、動作、物品等。但不要沒有意義的tag，如動漫截圖、動畫梗圖、表情包等），將用於向量搜尋陣列。"
    )

# [新增] LLM 裁判的輸出藍圖


class RerankResult(BaseModel):
    best_image_ids: list[int] = Field(
        description="按照最適合到最不適合的順序，排列出最棒的圖片 ID 陣列")


def analyze_anime_image(
    base64_image_data: str,
    api_key: str,
    base_url: str,
    model_name: str,
    system_prompt: Optional[str] = None
) -> dict:

    if not base64_image_data.startswith("data:image"):
        return {"success": False, "error": "圖片格式錯誤：必須包含 data:image/... 前綴。"}

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)

        default_prompt = (
            "你是一個專業的動畫迷因與梗圖分析專家。你的任務是分析使用者提供的動畫截圖，"
            "並嚴格按照要求的 JSON 格式提取資訊。請特別注意精準 OCR 辨識中文字幕，"
            "並深刻理解圖片的幽默感與適合使用的對話情境，"
            "不需要分析動畫名稱和角色名稱。"
        )
        final_prompt = system_prompt if system_prompt else default_prompt

        response = client.beta.chat.completions.parse(
            model=model_name,
            messages=[
                {"role": "system", "content": final_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "請詳細分析這張動畫截圖並填寫所有要求的欄位。"},
                        {"type": "image_url", "image_url": {
                            "url": base64_image_data}}
                    ]
                }
            ],
            response_format=AnimeAnalysisResult,
            temperature=0.2,
            timeout=30
        )

        return {
            "success": True,
            "data": response.choices[0].message.parsed.model_dump()
        }

    except Exception as e:
        return {"success": False, "error": f"API 解析失敗: {str(e)}"}


def generate_reply_intent(
    user_message: str, 
    api_key: str, 
    base_url: str, 
    model_name: str, 
    persona_name: str, 
    persona_desc: str
) -> tuple[str, Optional[str]]:
    """
    [新增] 意圖轉換器：將使用者的「對話」，轉換為「尋找圖片的描述」
    [更新] 支援由外部控制人設選項，提昇安全與穩定性
    """
    try:
        print(f"🎭 [系統] 本次對話使用人設: {persona_name}")

        client = OpenAI(api_key=api_key, base_url=base_url)
        prompt = (
            f"使用者說了一句話：「{user_message}」。\n"
            f"請你想像你要用一張「梗圖」來回覆他。{persona_desc}，你會尋找一張什麼樣的圖片？\n"
            "請直接給出這張用來回覆的圖片的「畫面描述、情境或氛圍」，絕對不要包含開場白，也不要直接回答使用者的話。\n"
            "字數控制在 50 字以內。"
        )

        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=100
        )
        return response.choices[0].message.content.strip(), None
    except Exception as e:
        print(f"⚠️ 意圖轉換失敗，退回原始字串: {e}")
        return user_message, f"LLM 意圖轉換失效 ({type(e).__name__})，已退回字面比對。"


def llm_reranker(
    user_message: str,
    intent_query: str,
    candidates: list[dict],
    top_k: int,
    api_key: str,
    base_url: str,
    model_name: str
) -> tuple[list[dict], Optional[str]]:
    """
    [新增] LLM 終極重排裁判：讓 AI 直接看圖片的 metadata 來挑選最適合的回覆
    """
    try:
        client = OpenAI(api_key=api_key, base_url=base_url)

        # 將候選清單精簡化，避免 Token 浪費
        candidates_json = [
            {"id": c["id"], "subtitle": c["subtitle"],
                "vibe": c["vibe_description"], "context": c["usage_context"]}
            for c in candidates
        ]

        prompt = (
            f"使用者說了一句話：「{user_message}」\n"
            f"系統期望的回覆氛圍是：「{intent_query}」\n\n"
            f"以下是系統初步篩選出的 {len(candidates)} 張候選梗圖資料：\n{json.dumps(candidates_json, ensure_ascii=False)}\n\n"
            f"請你作為一位幽默、懂梗的裁判，挑選出最完美、最好笑、最適合用來回覆的 {top_k} 張圖片，並按照適合程度由高到低，回傳它們的 ID。\n\n"
            f"【🚨 絕對禁忌】：嚴禁選擇「圖片字幕」與「使用者輸入」高度重複的圖片。\n"
            f"好的回覆必須是『接話』、『吐槽』或『反擊』，而不是重複對方說過的話！"
        )

        response = client.beta.chat.completions.parse(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format=RerankResult,
            temperature=0.3
        )

        best_ids = response.choices[0].message.parsed.best_image_ids
        # 根據 LLM 決定的 ID 順序重新排列 candidates
        return sorted(candidates, key=lambda x: best_ids.index(x["id"]) if x["id"] in best_ids else 999)[:top_k], None
    except Exception as e:
        print(f"⚠️ LLM 裁判重排失敗，退回原始計分排序: {e}")
        return candidates[:top_k], f"LLM 裁判重排失效 ({type(e).__name__})，已退回傳統計分排序。"


# --- 測試區塊 ---
if __name__ == "__main__":
    import sys
    sys.path.append(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    from core.image_utils import encode_image_to_base64
    from dotenv import load_dotenv

    load_dotenv()
    test_image_path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'database', 'images', 'wbIDZmPsG5eEZ.png')

    if os.path.exists(test_image_path):
        base64_img = encode_image_to_base64(test_image_path)
        test_api_key = os.environ.get("GEMINI_API_KEY", "your_api_key_here")
        # "https://generativelanguage.googleapis.com/v1beta/openai/" "http://localhost:11434/v1"
        test_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        test_model = "gemini-3.1-flash-lite-preview"  # "gemini-2.5-flash" "qwen3.5:9b"

        print(f"正在分析圖片 (使用模型: {test_model})...")
        result = analyze_anime_image(
            base64_img, test_api_key, test_base_url, test_model)

        # 啟動計時器
        start_time = time.time()

        result = analyze_anime_image(
            base64_img, test_api_key, test_base_url, test_model)

        # 停止計時器並計算耗時
        end_time = time.time()
        elapsed_time = end_time - start_time

        if result["success"]:
            import json
            print(f"✅ 分析成功！(API 總耗時: {elapsed_time:.2f} 秒)")
            print(json.dumps(result["data"], indent=2, ensure_ascii=False))
        else:
            print(f"❌ 失敗！(API 總耗時: {elapsed_time:.2f} 秒)")
            print(f"錯誤原因: {result['error']}")
