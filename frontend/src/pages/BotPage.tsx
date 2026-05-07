import { useState } from "react";
import { Link } from "react-router-dom";
import { useSearchMemes, usePersonas } from "@/api/queries";
import { useUiStore } from "@/store/uiStore";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Send, ThumbsDown, RefreshCw, Sparkles, ShieldAlert } from "lucide-react";
import { SearchResultItem } from "@/types/api";
import { apiClient } from "@/api/client";

// 對於已知的人設標籤，可以給予好讀的中文
const personaLabels: Record<string, string> = {
  "default": "預設",
  "toxic": "毒舌",
  "warm": "溫暖",
  "tsundere": "傲嬌"
};

function ResultCard({ item, onDislike }: { item: SearchResultItem; onDislike: (id: number) => void }) {
  // 自動將相對路徑轉換為包含 API baseURL 的絕對路徑
  const imageUrl = item.image_url.startsWith("http") 
    ? item.image_url 
    : `${apiClient.defaults.baseURL}${item.image_url}`;

  return (
    <Card className="overflow-hidden flex flex-col shadow-md hover:shadow-lg transition-shadow duration-300">
      <div className="relative aspect-video bg-muted/30 flex items-center justify-center border-b">
        <img 
          src={imageUrl} 
          alt={item.subtitle || "Meme"} 
          className="w-full h-full object-contain"
          onError={(e) => {
            (e.target as HTMLImageElement).src = 'https://placehold.co/600x400/png?text=Image+Not+Found';
          }}
        />
        <div className="absolute top-2 right-2 flex gap-2">
          <Badge variant="secondary" className="bg-background/80 backdrop-blur-sm shadow-sm">
            相符度: {(item.similarity_score * 100).toFixed(0)}%
          </Badge>
        </div>
      </div>
      <CardContent className="p-5 flex-1 flex flex-col gap-3">
        <div className="flex-1">
          {item.subtitle ? (
            <p className="font-bold text-xl mb-2 text-foreground">「{item.subtitle}」</p>
          ) : (
            <p className="font-bold text-xl mb-2 text-muted-foreground italic">無字幕</p>
          )}
          
          {item.usage_context && (
            <div className="text-sm text-muted-foreground mb-3">
              <span className="font-semibold text-foreground/80">情境：</span>
              <p className="line-clamp-2 mt-1" title={item.usage_context}>
                {item.usage_context}
              </p>
            </div>
          )}
          
          <div className="flex flex-wrap gap-1.5 mt-auto pt-2">
            {item.tags?.map((tag, i) => (
              <Badge key={i} variant="outline" className="text-xs bg-muted/50">{tag}</Badge>
            ))}
          </div>
        </div>
        <Button 
          variant="secondary" 
          className="w-full mt-4 hover:bg-destructive hover:text-destructive-foreground transition-colors group"
          onClick={() => onDislike(item.id)}
        >
          <ThumbsDown className="w-4 h-4 mr-2 text-muted-foreground group-hover:text-destructive-foreground transition-colors" />
          這張不適合，換一張
        </Button>
      </CardContent>
    </Card>
  );
}

export default function BotPage() {
  const [draftQuery, setDraftQuery] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [topK, setTopK] = useState(3);
  const [selectedPersona, setSelectedPersona] = useState<string>("random");

  const { excludeImageIds, addExcludedId, clearExcludedIds } = useUiStore();
  const { data: personas } = usePersonas();

  const { data: results, isLoading, isError, error, isFetching } = useSearchMemes(
    searchQuery,
    topK,
    excludeImageIds,
    !!searchQuery,
    selectedPersona === "random" ? undefined : selectedPersona
  );
  const memeList = results?.data ?? [];

  const handleSearch = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!draftQuery.trim()) return;
    clearExcludedIds(); // 新搜尋時清空黑名單
    setSearchQuery(draftQuery);
  };

  const handleRefresh = () => {
    clearExcludedIds();
  };

  return (
    <div className="max-w-6xl mx-auto p-4 md:p-8 flex flex-col min-h-screen gap-8 relative">
      {/* Admin Portal Entry */}
      <div className="absolute top-4 right-4 md:top-8 md:right-8 z-50">
        <Button variant="ghost" className="text-muted-foreground hover:text-foreground shadow-sm bg-background/50 backdrop-blur-sm" asChild>
          <Link to="/admin/images">
            <ShieldAlert className="w-4 h-4 mr-2" />
            <span className="font-medium text-sm">前往管理後台</span>
          </Link>
        </Button>
      </div>

      {/* Header Area */}
      <div className="flex flex-col items-center justify-center text-center space-y-4 py-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
        <div className="bg-primary/10 p-4 rounded-2xl mb-2">
          <Sparkles className="w-10 h-10 text-primary" />
        </div>
        <h1 className="text-4xl font-extrabold tracking-tight text-foreground">AnimeReply 梗圖大師</h1>
        <p className="text-lg text-muted-foreground max-w-xl">
          輸入你現在的心情、抱怨或對話，AI 將讀懂你的意圖，並為你挑選最完美的動漫梗圖來回覆。
        </p>
      </div>

      {/* Input Area */}
      <Card className="p-2 shadow-lg border-primary/20 bg-card/50 backdrop-blur-sm z-10 sticky top-4">
        <form onSubmit={handleSearch} className="flex flex-col md:flex-row gap-2 items-center">
          
          {/* Persona Dropdown */}
          <div className="md:w-32 flex-shrink-0 relative my-2 mx-2">
            <select
              value={selectedPersona}
              onChange={(e) => setSelectedPersona(e.target.value)}
              className="flex h-12 w-full appearance-none items-center justify-between rounded-xl border border-input bg-background/50 px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 pr-8 shadow-sm transition-all"
            >
              <option value="random">隨機人設</option>
              {personas && personas.map(p => (
                <option key={p} value={p}>{personaLabels[p] || p}</option>
              ))}
            </select>
            {/* Custom dropdown arrow */}
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-muted-foreground">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
            </div>
          </div>
          
          <div className="flex-1 w-full relative">
            <Input 
              placeholder="試著輸入：「今天又要加班，好想死...」" 
              value={draftQuery}
              onChange={(e) => setDraftQuery(e.target.value)}
              className="text-lg py-7 px-6 border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0 shadow-none"
            />
          </div>
          <div className="h-10 w-px bg-border hidden md:block mx-2"></div>
          <div className="flex items-center gap-3 w-full md:w-auto px-4 pb-4 md:pb-0 md:px-0 pr-2">
            <div className="flex items-center gap-2 whitespace-nowrap">
              <span className="text-sm font-medium text-muted-foreground">顯示數量</span>
              <Input 
                type="number" 
                min={1} max={10} 
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                className="w-16 text-center"
              />
            </div>
            <Button 
              type="submit" 
              size="lg" 
              className="flex-1 md:flex-none rounded-xl px-8"
              disabled={isFetching || !draftQuery.trim()}
            >
              {isFetching ? <RefreshCw className="w-5 h-5 mr-2 animate-spin" /> : <Send className="w-5 h-5 mr-2" />}
              {isFetching ? "通靈中..." : "發射！"}
            </Button>
          </div>
        </form>
      </Card>

      {/* Results Area */}
      <div className="flex-1 pb-12">
        {isError && (
          <div className="text-center text-destructive p-8 bg-destructive/10 rounded-xl border border-destructive/20 mb-6 shadow-sm">
            <p className="font-semibold text-lg flex items-center justify-center gap-2">
              ⚠️ 搜尋發生錯誤
            </p>
            <p className="mt-2 text-sm opacity-90 font-medium">
              {error?.message || "網路異常，請檢查後再試"}
            </p>
          </div>
        )}

        {/* 顯示目前使用的 Persona */}
        {results?.persona_used && (
           <div className="mb-4 pt-4 flex items-center gap-2 text-muted-foreground animate-in fade-in zoom-in-95 duration-500">
             <span className="text-sm font-medium">當前語氣：</span>
             <Badge variant="outline" className="px-3 py-1 font-bold text-primary border-primary/30">
               {personaLabels[results.persona_used] || results.persona_used}
             </Badge>
           </div>
        )}

        {/* [新增] 顯示後端傳來的 Fallback 警告 (例如 LLM 失效) */}
        {results?.warning && (
          <div className="mb-6 p-4 bg-yellow-500/10 border border-yellow-500/20 text-yellow-600 rounded-xl flex items-center justify-center shadow-sm">
            <p className="text-sm font-medium">💡 系統提示：{results.warning}</p>
          </div>
        )}

        {isLoading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-8">
            {Array.from({ length: topK }).map((_, i) => (
              <Card key={i} className="overflow-hidden border-muted">
                <Skeleton className="aspect-video w-full rounded-none" />
                <CardContent className="p-5 space-y-4 mt-2">
                  <Skeleton className="h-7 w-3/4" />
                  <div className="space-y-2">
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-5/6" />
                  </div>
                  <div className="flex gap-2 pt-2">
                    <Skeleton className="h-5 w-16" />
                    <Skeleton className="h-5 w-20" />
                  </div>
                  <Skeleton className="h-10 w-full mt-4" />
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {!isLoading && results && memeList.length > 0 && (
          <div className="space-y-6 mt-4 animate-in fade-in duration-500">
            <div className="flex justify-between items-end pb-2 border-b">
              <div>
                <h2 className="text-2xl font-bold tracking-tight">為您精選的回覆</h2>
                <p className="text-sm text-muted-foreground mt-1">
                  點擊「換一張」可將該圖片加入本次會話黑名單並重新抽取。
                </p>
              </div>
              {excludeImageIds.length > 0 && (
                <Button variant="ghost" size="sm" onClick={handleRefresh} className="text-muted-foreground">
                  <RefreshCw className="w-4 h-4 mr-2" />
                  清除黑名單 ({excludeImageIds.length})
                </Button>
              )}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {memeList.map((item) => (
                <ResultCard 
                  key={item.id} 
                  item={item} 
                  onDislike={addExcludedId} 
                />
              ))}
            </div>
          </div>
        )}

        {!isLoading && results && memeList.length === 0 && searchQuery && (
          <div className="text-center p-16 bg-muted/20 rounded-2xl border border-dashed mt-8">
            <Sparkles className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-foreground mb-2">找不到合適的梗圖</h3>
            <p className="text-muted-foreground">目前圖庫中沒有符合該情境的圖片。請嘗試更換關鍵字，或前往管理後台補充圖庫！</p>
          </div>
        )}
      </div>
    </div>
  );
}
