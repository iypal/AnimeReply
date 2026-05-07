import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import {
  BasicResponse,
  ImageMetadataUpdate,
  UploadBatchResponse,
} from "@/types/api";

export const useUpdateImage = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: number; data: ImageMetadataUpdate }) => {
      const response = await apiClient.put<BasicResponse>(`/api/images/${id}`, data);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["images"] });
      queryClient.invalidateQueries({ queryKey: ["image", variables.id] });
    },
  });
};

export const useDeleteImage = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number) => {
      const response = await apiClient.delete<BasicResponse>(`/api/images/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["images"] });
    },
  });
};

export const useRebuildFaiss = () => {
  return useMutation({
    mutationFn: async () => {
      const response = await apiClient.post<BasicResponse>("/api/rebuild-faiss");
      return response.data;
    },
  });
};

export const useUploadBatch = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (files: File[]) => {
      const formData = new FormData();
      files.forEach((file) => formData.append("files", file));

      const response = await apiClient.post<UploadBatchResponse>(
        "/api/upload-batch",
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        }
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["images"] });
    },
  });
};
