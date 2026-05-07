import { useState, useRef, ChangeEvent, DragEvent } from "react";
import { UploadCloud, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useUploadBatch, useRebuildFaiss } from "@/api/mutations";

export default function UploadPage() {
  const [dragActive, setDragActive] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const uploadMutation = useUploadBatch();
  const rebuildMutation = useRebuildFaiss();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files.length > 0) {
      handleFiles(Array.from(e.target.files));
    }
  };

  const handleFiles = (newFiles: File[]) => {
    const imageFiles = newFiles.filter((file) => file.type.startsWith("image/"));
    if (imageFiles.length !== newFiles.length) {
      toast.error("部分檔案不是圖片，已被過濾");
    }
    setFiles((prev) => [...prev, ...imageFiles]);
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) return;

    try {
      const result = await uploadMutation.mutateAsync(files);
      
      // 開發者可於 Console 檢視哪些檔案被重複攔截
      console.log("批次上傳詳細結果:", result.results);

      if (result.status === "failed") {
        toast.error(`全部上傳失敗 (${result.failed_count} 張)。查看日誌取得重複檔案清單。`);
        return; // 不清空列表、不重建 FAISS
      } else if (result.status === "partial") {
        toast.warning(`部分成功：上傳 ${result.uploaded_count} 張，攔截 ${result.failed_count} 張 (重複/錯誤)。查看日誌。`);
        setFiles([]);
      } else {
        toast.success(`成功上傳 ${result.uploaded_count} 張圖片！`);
        setFiles([]);
      }

      if (result.uploaded_count > 0) {
        toast.info("正在同步向量大腦...");
        await rebuildMutation.mutateAsync();
        toast.success("FAISS 向量索引同步完成！");
      }
    } catch (error: any) {
      // 現在 API client 會攔截後端 JSON detail，拋出 Error 對象
      toast.error(`上傳失敗: ${error.message || "伺服器無回應，請稍後再試"}`);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight mb-2">圖片上傳</h2>
        <p className="text-muted-foreground">
          支援拖曳上傳與點擊選檔。將自動計算 Hash 去重與建立 AI 索引。
        </p>
      </div>

      <div
        className={`border-2 border-dashed rounded-xl p-12 text-center transition-colors cursor-pointer ${
          dragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 hover:bg-accent/50"
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/*"
          onChange={handleChange}
          className="hidden"
        />
        <UploadCloud className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
        <h3 className="text-lg font-medium mb-1">拖曳圖片到這裡，即刻上傳</h3>
        <p className="text-sm text-muted-foreground">此處支援一次上傳多張圖片 (PNG, JPG, JPEG, WEBP 等)</p>
      </div>

      {files.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium">已選擇 {files.length} 個檔案</h3>
            <Button 
              onClick={(e) => { e.stopPropagation(); handleUpload(); }} 
              disabled={uploadMutation.isPending || rebuildMutation.isPending}
            >
              {(uploadMutation.isPending || rebuildMutation.isPending) && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {uploadMutation.isPending ? "AI 處理中..." : rebuildMutation.isPending ? "重建索引中..." : "開始上傳"}
            </Button>
          </div>
          
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {files.map((file, index) => (
              <div key={index} className="relative group border rounded-lg overflow-hidden bg-muted">
                <img 
                  src={URL.createObjectURL(file)} 
                  alt={file.name}
                  className="w-full h-32 object-cover"
                />
                <button
                  onClick={(e) => { e.stopPropagation(); removeFile(index); }}
                  className="absolute top-2 right-2 p-1 bg-black/50 text-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity hover:bg-black/70"
                >
                  <X className="h-4 w-4" />
                </button>
                <div className="absolute pb-2 bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent pt-6 px-2">
                  <p className="text-xs text-white truncate" title={file.name}>{file.name}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}