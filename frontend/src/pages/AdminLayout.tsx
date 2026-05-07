import { Outlet, Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";

export default function AdminLayout() {
  const location = useLocation();

  const navItems = [
    { name: "圖片管理", path: "/admin/images" },
    { name: "圖片上傳", path: "/admin/upload" },
    { name: "系統設定", path: "/admin/settings" },
  ];

  return (
    <div className="flex min-h-screen bg-muted/40">
      {/* 側邊導覽列 */}
      <aside className="w-64 border-r bg-background px-4 py-6">
        <div className="mb-8">
          <h2 className="text-xl font-bold tracking-tight">AnimeReply 管理面板</h2>
        </div>
        <nav className="space-y-2">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={cn(
                "block rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground",
                location.pathname.startsWith(item.path)
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground"
              )}
            >
              {item.name}
            </Link>
          ))}
          <div className="pt-8">
            <Link
              to="/bot"
              className="text-sm text-primary hover:underline px-3"
            >
              ← 返回 Bot Playground
            </Link>
          </div>
        </nav>
      </aside>

      {/* 內容區塊 */}
      <main className="flex-1 p-8">
        <div className="mx-auto max-w-5xl bg-background rounded-lg border shadow-sm p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}