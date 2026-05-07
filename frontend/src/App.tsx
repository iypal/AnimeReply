import { Routes, Route, Navigate } from "react-router-dom";
import BotPage from "@/pages/BotPage";
import AdminLayout from "@/pages/AdminLayout";
import ImagesPage from "@/pages/ImagesPage";
import UploadPage from "@/pages/UploadPage";
import SettingsPage from "@/pages/SettingsPage";
import { Toaster } from "@/components/ui/sonner";

function App() {
  return (
    <>
      <Routes>
        {/* 根目錄重定向到 /bot */}
        <Route path="/" element={<Navigate to="/bot" replace />} />
        
        {/* 主功能區 */}
        <Route path="/bot" element={<BotPage />} />

        {/* 管理面板 */}
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<Navigate to="/admin/images" replace />} />
          <Route path="images" element={<ImagesPage />} />
          <Route path="upload" element={<UploadPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
        
        {/* 404 Not Found */}
        <Route path="*" element={<Navigate to="/bot" replace />} />
      </Routes>

      {/* 全域吐司提示組件 */}
      <Toaster position="top-center" richColors />
    </>
  );
}

export default App;