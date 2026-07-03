import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import Sidebar from "./components/layout/Sidebar.jsx";
import MainContent from "./components/layout/MainContent.jsx";
import NewAnalysisPage from "./pages/NewAnalysisPage.jsx";
import AnalysisPage from "./pages/AnalysisPage.jsx";
import DraftPage from "./pages/DraftPage.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";

export default function App() {
  return (
    <BrowserRouter>
      <Toaster position="top-right" />
      <div className="flex h-screen bg-bgPrimary text-textPrimary">
        <Sidebar />
        <MainContent>
          <Routes>
            <Route path="/" element={<NewAnalysisPage />} />
            <Route path="/analysis/:id" element={<AnalysisPage />} />
            <Route path="/analysis/:id/draft" element={<DraftPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </MainContent>
      </div>
    </BrowserRouter>
  );
}
