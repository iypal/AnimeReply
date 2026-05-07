# AnimeReply

[中文版 README](./README_ZH.md)

AnimeReply is a local AI-powered anime reaction image search system that turns anime screenshots, quote images, and reaction images into a searchable library.

When a user enters a scenario such as “I want a shocked anime reply image for an absurd message,” the system tries to return the most suitable result.

## Overview

- Upload anime images and analyze them with AI
- Turn images into searchable metadata
- Search reaction images with natural language
- Manage image records with SQLite
- Build a local FAISS vector index
- Provide both a user-facing search page and an admin panel
- Support batch import workflows

## Workflow

1. Collect anime screenshots or reaction images
2. Upload them into the system
3. Let AI generate fields such as `subtitle`, `usage_context`, and `tags`
4. Build embeddings and a FAISS index
5. Enter a natural-language scenario in the frontend
6. Get the most relevant image results

## Tech Stack

- Backend: `FastAPI`
- Frontend: `React + Vite + TypeScript`
- Database: `SQLite`
- Vector Search: `FAISS`
- Embedding: `Sentence-Transformers`
- Vision / LLM: `Gemini`

The current API model support is focused on `Gemini`.  
In the future, the architecture is intended to support multiple AI providers, such as:

- `ChatGPT`
- local `LLM`s
- other OpenAI-compatible providers
- self-hosted model services

## Search Pipeline

The current search logic is more than plain keyword matching. At a high level, it works like this:

1. The user enters a natural-language scenario
2. An LLM rewrites it into a better search intent
3. Vector search retrieves candidate images
4. Extra scoring adjusts the candidates using tags, context, and lexical penalties
5. An LLM reranks the final candidates

The goal is to return images that feel actually usable as reaction replies, not just images with overlapping words.

## Interface Structure

### `/bot`

The main user-facing search page for entering a scenario and getting recommended images.

### `/admin/images`

The image management page, where you can:

- browse images
- search images
- edit metadata
- delete records

### `/admin/upload`

Supports multi-file upload for batch importing and AI analysis.

### `/admin/settings`

Currently a simplified version and will be expanded later.

## Project Structure

```text
AnimeReply/
├─ core/                  # FastAPI, VLM client, vector search, image processing
├─ database/
│  ├─ data/               # local SQLite / FAISS data (not intended for publishing)
│  └─ images/             # local image library (not intended for publishing)
├─ frontend/              # React + Vite frontend
├─ tools/                 # batch import utilities
├─ personas.json          # search persona configuration
├─ requirements.txt       # Python dependencies
├─ README.md              # English README
└─ README_ZH.md           # Chinese README
```

## Local Development

### Backend dependencies

```bash
pip install -r requirements.txt
```

### Frontend dependencies

```bash
cd frontend
npm install
```

## Environment Variables

At minimum, the root `.env` needs:

```env
GEMINI_API_KEY=your_api_key
BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
MODEL_NAME=gemini-3.1-flash-lite-preview
```

If you want key rotation for the batch tool, you can also use:

```env
GEMINI_API_KEYS=key1,key2,key3
```

## Running the Project

### Start the backend

```bash
python core/api_server.py
```

Default URLs:

- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`

### Start the frontend

```bash
cd frontend
npm run dev
```

Default URLs:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`

To change the frontend API target:

```env
VITE_API_URL=http://localhost:8000
```

## Batch Import Tool

The project includes `tools/batch_import.py` for batch image processing.

Typical flow:

1. Put images into `database/import_queue/`
2. Run:

```bash
python tools/batch_import.py
```

The tool will:

- validate file extensions
- calculate hashes
- skip duplicates
- call AI analysis
- write records into the local database
- rebuild the FAISS index at the end

## Future Directions

- multi-provider model abstraction
- support for ChatGPT / local LLM / other providers
- a more complete settings page
- better metadata editing workflows
- more stable index update strategies
- score and rerank visualization

## Notes

This repository mainly publishes the code and project implementation itself.  
Local databases, vector indexes, image assets, and internal AI collaboration files are excluded through `.gitignore`.
