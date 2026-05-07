import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Info } from "lucide-react";

export default function SettingsPage() {
  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold tracking-tight mb-2">系統設定</h2>      
        <p className="text-muted-foreground">管理 API Keys 與模型偏好設定。</p>
      </div>
      
      <Card className="border-primary/20 bg-primary/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-primary">
            <Info className="h-5 w-5" />
            Phase 1 MVP 簡化版
          </CardTitle>
          <CardDescription className="text-base mt-2">
            目前系統正在使用 <code className="bg-background px-1.5 py-0.5 rounded border">.env</code> 檔案中的 <code className="bg-background px-1.5 py-0.5 rounded border">GEMINI_API_KEY</code> 與基礎模型設定。
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            若要擴充支援多組設定或更換不同的 LLM 供應商 (Model Profiles)，這部分的功能將於 Phase 2 正式開放。
            現階段為確保系統穩定性並避免過度工程化 (Over-engineering)，請透過環境變數直接進行管理。
          </p>
        </CardContent>
      </Card>
    </div>
  );
}