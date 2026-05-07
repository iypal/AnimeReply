import { useQuery } from "@tanstack/react-query";
import { apiClient } from "./client";
import {
  PaginatedImagesResponse,
  SearchResponse,
  SingleImageResponse,
} from "@/types/api";

export const queryKeys = {
  images: (page: number, limit: number, search: string) =>
    ["images", page, limit, search] as const,
  image: (id: number) => ["image", id] as const,
  search: (query: string, topK: number, excludeIds: number[]) =>
    ["search", query, topK, excludeIds] as const,
};

export const useImages = (page: number, limit: number, search: string) => {
  return useQuery({
    queryKey: queryKeys.images(page, limit, search),
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedImagesResponse>("/api/images", {
        params: { page, limit, search },
      });
      return data;
    },
  });
};

export const useImage = (id: number) => {
  return useQuery({
    queryKey: queryKeys.image(id),
    queryFn: async () => {
      const { data } = await apiClient.get<SingleImageResponse>(`/api/images/${id}`);
      return data.data;
    },
    enabled: !!id,
  });
};

export const useSearchMemes = (
  query: string,
  topK: number,
  excludeIds: number[],
    enabled: boolean,
    persona?: string 
  ) => {
    // 把 persona 納入 queryKey，更換 persona 會觸發重新搜尋
    return useQuery({
      queryKey: [...queryKeys.search(query, topK, excludeIds), persona],
      queryFn: async () => {
        // 在 GET 請求中傳遞陣列參數，會被 axios 序列化成 exclude_img_ids[]=1&exclude_img_ids[]=2
        const params = new URLSearchParams();
        params.append("query", query);
        params.append("top_k", topK.toString());
        if (persona) {
          params.append("persona", persona);
        }
        excludeIds.forEach((id) => params.append("exclude_img_ids", id.toString()));

        const { data } = await apiClient.get<SearchResponse>("/api/search", { params });
        // 回傳整包 data，以便 UI層取用 persona_used 與 warning
        return data;
      },
      enabled: enabled && !!query.trim(),
      staleTime: 0, // 搜尋結果不要快取太久，隨時反映黑名單變化
    });
  };

  export const usePersonas = () => {
    return useQuery({
      queryKey: ["personas"],
      queryFn: async () => {
        const { data } = await apiClient.get<{success: boolean, data: string[]}>("/api/personas");
        return data.data;
      },
      staleTime: 1000 * 60 * 60 * 24, // 除非重整，否則長期持有
    });
  };
