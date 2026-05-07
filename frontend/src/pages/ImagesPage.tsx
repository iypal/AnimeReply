import { useState, useEffect } from "react";
import { useImages } from "@/api/queries";
import { useUpdateImage, useDeleteImage, useRebuildFaiss } from "@/api/mutations";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { ImageItem } from "@/types/api";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function ImagesPage() {
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  const [editingImage, setEditingImage] = useState<ImageItem | null>(null);
  const [editForm, setEditForm] = useState({
    subtitle: "",
    vibe_description: "",
    usage_context: "",
    anime_title: "",
    tags: "",
  });

  const { data, isLoading } = useImages(page, 12, debouncedSearch);
  const updateMutation = useUpdateImage();
  const deleteMutation = useDeleteImage();
  const rebuildMutation = useRebuildFaiss();

  // 簡單的防手震 Search
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setPage(1); // Reset page on search
    }, 500);
    return () => clearTimeout(handler);
  }, [searchQuery]);

  const handleEditClick = (img: ImageItem) => {
    setEditingImage(img);
    setEditForm({
      subtitle: img.subtitle || "",
      vibe_description: img.vibe_description || "",
      usage_context: img.usage_context || "",
      anime_title: img.anime_title || "",
      tags: img.tags ? img.tags.join("、") : "",
    });
  };

  const handleSaveEdit = async () => {
    if (!editingImage) return;

    try {
      const updatedData = {
        subtitle: editForm.subtitle,
        vibe_description: editForm.vibe_description,
        usage_context: editForm.usage_context,
        anime_title: editForm.anime_title,
        tags: editForm.tags.split(/[,、]/).map((t) => t.trim()).filter(Boolean),
      };

      await updateMutation.mutateAsync({ id: editingImage.id, data: updatedData });
      toast.success("圖片資訊已更新，正在同步向量大腦...");
    } catch (err: any) {
      toast.error(`更新失敗: ${err.message || "請稍後再試"}`);
      return; // 終止流程，不要去重建索引
    }

    try {
      // 自動觸發重建索引 (Data-Index Consistency)
      await rebuildMutation.mutateAsync();
      toast.success("FAISS 向量索引同步完成！");
      setEditingImage(null);
    } catch (err: any) {
      toast.warning(`更新成功，但 FAISS 重建失敗: ${err.message || "請至設定頁手動重建"}`);
      setEditingImage(null);
    }
  };

  const handleDelete = async (img: ImageItem) => {
    if (!window.confirm("確定要刪除這張圖片嗎？這個操作無法復原。")) return;

    try {
      await deleteMutation.mutateAsync(img.id);
      toast.success("圖片已刪除，正在同步向量大腦...");
    } catch (err: any) {
      toast.error(`刪除失敗: ${err.message || "請稍後再試"}`);
      return;
    }

    try {
      // 自動觸發重建索引
      await rebuildMutation.mutateAsync();
      toast.success("FAISS 向量索引同步完成！");
    } catch (err: any) {
      // Data-Index Consistency: 刪除成功但沒同步，只會跳黃色警告
      toast.warning(`刪除成功，但 FAISS 重建失敗: ${err.message || "請至設定頁手動重建"}`);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold tracking-tight">圖片管理</h2>
        <div className="w-72">
          <Input
            placeholder="搜尋標題、氛圍或標籤..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-10 text-muted-foreground">正在載入圖片...</div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {data?.data.map((img) => (
              <Card key={img.id} className="overflow-hidden flex flex-col">
                <div className="h-48 bg-muted relative">
                  <img
                    src={`${API_URL}${img.image_url}`}
                    alt={img.subtitle || "anime image"}
                    className="w-full h-full object-cover"
                  />
                </div>
                <CardContent className="p-4 flex-1 flex flex-col justify-between">
                  <div className="space-y-2 mb-4">
                    <h3 className="font-semibold truncate" title={img.subtitle || "無字幕"}>
                      {img.subtitle || <span className="text-muted-foreground italic">無字幕</span>}
                    </h3>
                    <p className="text-xs text-muted-foreground line-clamp-2" title={img.vibe_description || ""}>
                      {img.vibe_description || "無氛圍描述"}
                    </p>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {img.tags && img.tags.slice(0, 3).map((tag, idx) => (
                        <span key={idx} className="bg-secondary text-secondary-foreground text-[10px] px-1.5 py-0.5 rounded">
                          {tag}
                        </span>
                      ))}
                      {img.tags && img.tags.length > 3 && (
                        <span className="bg-secondary text-secondary-foreground text-[10px] px-1.5 py-0.5 rounded">
                          +{img.tags.length - 3}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 mt-auto">
                    <Button variant="outline" size="sm" className="flex-1" onClick={() => handleEditClick(img)}>
                      編輯
                    </Button>
                    <Button variant="destructive" size="sm" onClick={() => handleDelete(img)}>
                      刪除
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* 分頁按鈕 */}
          <div className="flex items-center justify-center gap-4 mt-8">
            <Button
              variant="outline"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              上一頁
            </Button>
            <span className="text-sm text-muted-foreground">
              第 {page} 頁 / 共 {data ? Math.ceil(data.total / data.limit) : 1} 頁
            </span>
            <Button
              variant="outline"
              disabled={!data || page >= Math.ceil(data.total / data.limit)}
              onClick={() => setPage((p) => p + 1)}
            >
              下一頁
            </Button>
          </div>
        </>
      )}

      {/* 編輯 Dialog */}
      <Dialog open={!!editingImage} onOpenChange={(open) => !open && setEditingImage(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>編輯圖片資訊</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>字幕 (Subtitle)</Label>
              <Input
                value={editForm.subtitle}
                onChange={(e) => setEditForm({ ...editForm, subtitle: e.target.value })}
                placeholder="例如: 讓我們一起迷失吧"
              />
            </div>
            <div className="space-y-2">
              <Label>氛圍 (Vibe Description)</Label>
              <Input
                value={editForm.vibe_description}
                onChange={(e) => setEditForm({ ...editForm, vibe_description: e.target.value })}
                placeholder="例如: 沮喪、無奈"
              />
            </div>
            <div className="space-y-2">
              <Label>情境 (Usage Context)</Label>
              <Textarea
                value={editForm.usage_context}
                onChange={(e) => setEditForm({ ...editForm, usage_context: e.target.value })}
                placeholder="適合在什麼對話情境使用？"
              />
            </div>
            <div className="space-y-2">
              <Label>標籤 (Tags, 逗號或頓號分隔)</Label>
              <Input
                value={editForm.tags}
                onChange={(e) => setEditForm({ ...editForm, tags: e.target.value })}
                placeholder="例如: MyGO, 祥子, 迷茫"
              />
            </div>
            <div className="space-y-2">
              <Label>動漫出處 (Anime Title)</Label>
              <Input
                value={editForm.anime_title}
                onChange={(e) => setEditForm({ ...editForm, anime_title: e.target.value })}
                placeholder="例如: BanG Dream! It's MyGO!!!!!"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingImage(null)}>
              取消
            </Button>
            <Button onClick={handleSaveEdit}>儲存並重建索引</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
