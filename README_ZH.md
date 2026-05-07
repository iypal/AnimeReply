# AnimeReply

[English](./README.md)

AnimeReply 是一個 AI 動漫梗圖回覆系統。輸入你現在的心情、抱怨或對話內容，AI 會讀懂你的意圖，並替你挑選最適合拿來回話的動漫梗圖。

## 功能概覽

- 上傳動漫梗圖並交給 AI 自動分析
- 將圖片整理成可搜尋的 metadata
- 讓系統根據使用者意圖挑選合適的動漫梗圖回覆
- 使用 SQLite 管理圖像資料
- 使用 FAISS 建立本地向量索引
- 提供前台回覆頁與後台管理頁
- 支援批次匯入圖片

## 使用流程

1. 收集動漫截圖、台詞圖與梗圖素材
2. 上傳到系統
3. 由 AI 產生 `subtitle`、`usage_context`、`tags` 等欄位
4. 建立 embedding 與 FAISS index
5. 在前端輸入你的心情、抱怨或對話內容
6. 取得最適合拿來回話的動漫梗圖

## 技術棧

- Backend: `FastAPI`
- Frontend: `React + Vite + TypeScript`
- Database: `SQLite`
- Vector Search: `FAISS`
- Embedding: `Sentence-Transformers`
- Vision / LLM: `Gemini`

目前 API 模型支援以 `Gemini` 為主。  
未來希望擴充成多模型架構，支援：

- `ChatGPT`
- 本地 `LLM`
- 其他 OpenAI-compatible provider
- 自架模型服務

## 回覆流程

目前邏輯不是單純做關鍵字比對，而是大致分成以下幾步：

1. 使用者輸入心情、抱怨或對話內容
2. LLM 將輸入改寫成更適合搜尋的 intent
3. 用向量搜尋找出候選梗圖
4. 依照 tags / context / lexical penalty 做額外分數調整
5. 最後再用 LLM 對候選結果 rerank

這樣做的目標是讓結果更接近「真的拿來回話會想用的梗圖」，而不是只做表面文字重疊。

## 介面結構

### `/bot`

前台頁面，主要給使用者輸入內容並取得推薦的動漫梗圖回覆。

### `/admin/images`

後台圖庫管理頁，可以：

- 瀏覽圖片
- 搜尋圖片
- 編輯 metadata
- 刪除圖片

### `/admin/upload`

支援單次多張上傳，做批次匯入與 AI 分析。

### `/admin/settings`

目前是簡化版本，之後會再擴充。

## 專案結構

```text
AnimeReply/
├─ core/                  # FastAPI、VLM client、向量搜尋、圖片處理
├─ database/
│  ├─ data/               # 本地 SQLite / FAISS 資料（不建議公開）
│  └─ images/             # 本地圖片資料庫（不建議公開）
├─ frontend/              # React + Vite 前端
├─ tools/                 # 批次匯入工具
├─ personas.json          # 搜尋 persona 設定
├─ requirements.txt       # Python 依賴
├─ README.md              # English README
└─ README_ZH.md           # 中文說明
```

## 本地開發

### 後端依賴

```bash
pip install -r requirements.txt
```

### 前端依賴

```bash
cd frontend
npm install
```

## 環境變數

根目錄 `.env` 至少需要：

```env
GEMINI_API_KEY=your_api_key
BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
MODEL_NAME=gemini-3.1-flash-lite-preview
```

如果要使用批次工具的多 key 輪替，也可以設定：

```env
GEMINI_API_KEYS=key1,key2,key3
```

## 啟動方式

### 啟動後端

```bash
python core/api_server.py
```

預設位置：

- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`

### 啟動前端

```bash
cd frontend
npm run dev
```

預設位置：

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`

如果要修改前端 API 位址：

```env
VITE_API_URL=http://localhost:8000
```

## 批次匯入工具

專案提供 `tools/batch_import.py` 做批次圖片處理。

大致流程：

1. 把圖片放進 `database/import_queue/`
2. 執行：

```bash
python tools/batch_import.py
```

工具會：

- 檢查副檔名
- 計算 hash
- 跳過重複圖片
- 呼叫 AI 分析
- 寫入本地資料庫
- 最後重建 FAISS index

## 後續方向

- 多模型 provider 抽象層
- 支援 ChatGPT / local LLM / 其他 provider
- 更完整的 settings 頁
- 更好的 metadata 編輯流程
- 更穩定的 index 更新策略
- 搜尋分數與 rerank 可視化

## 備註

這個 repo 主要公開程式碼與專案實作本身。  
本地資料庫、向量索引、圖片素材與內部 AI 協作文件不一定適合一起公開，因此已在 `.gitignore` 中排除。
