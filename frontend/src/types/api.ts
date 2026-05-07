export interface SearchResultItem {
  id: number;
  filename: string;
  subtitle: string;
  vibe_description: string;
  usage_context: string;
  similarity_score: number;
  image_url: string;
  tags: string[];
  total_score: number;
  debug_scores: Record<string, number>;
}

export interface SearchResponse {
  success: boolean;
  data: SearchResultItem[];
  error?: string;
  warning?: string;
  persona_used?: string;
}

export interface ImageItem {
  id: number;
  filename: string;
  subtitle: string | null;
  vibe_description: string | null;
  usage_context: string | null;
  character_info: string | null;
  tags: string[];
  anime_title: string | null;
  created_at: string;
  image_url: string;
}

export interface PaginatedImagesResponse {
  success: boolean;
  data: ImageItem[];
  total: number;
  page: number;
  limit: number;
}

export interface SingleImageResponse {
  success: boolean;
  data: ImageItem;
}

export interface ImageMetadataUpdate {
  subtitle?: string;
  vibe_description?: string;
  usage_context?: string;
  tags?: string[];
  anime_title?: string;
}

export interface BasicResponse {
  success: boolean;
  message?: string;
  error?: string;
}

export interface UploadBatchResult {
  filename: string;
  success: boolean;
  image_id?: number;
  error?: string;
}

export interface UploadBatchResponse {
  success: boolean;
  status: "all_success" | "partial" | "failed";
  uploaded_count: number;
  failed_count: number;
  results: UploadBatchResult[];
}
