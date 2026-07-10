import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import Sidebar from "./components/layout/Sidebar.jsx";
import MainContent from "./components/layout/MainContent.jsx";
import NewAnalysisPage from "./pages/NewAnalysisPage.jsx";
import AnalysisPage from "./pages/AnalysisPage.jsx";
import DraftPage from "./pages/DraftPage.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";
import ComingSoonPage from "./pages/ComingSoonPage.jsx";

export default function App() {
  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: "#1C2420",
            color: "#FAF8F4",
            border: "1px solid #2B5940",
            borderRadius: "2px",
            fontFamily: "Inter, system-ui, sans-serif",
            fontSize: "13px",
          },
          // Icons in the house palette — forest green / muted burgundy,
          // never the library defaults.
          success: { iconTheme: { primary: "#2B5940", secondary: "#FAF8F4" } },
          error: { iconTheme: { primary: "#7D3040", secondary: "#FAF8F4" } },
        }}
      />
      <div className="flex h-screen bg-bgPrimary text-textPrimary">
        <Sidebar />
        <MainContent>
          <Routes>
            <Route path="/" element={<NewAnalysisPage />} />
            <Route path="/analysis/:id" element={<AnalysisPage />} />
            <Route path="/analysis/:id/draft" element={<DraftPage />} />
            <Route
              path="/search"
              element={
                <ComingSoonPage
                  kicker="Research"
                  title="Prior Art Search"
                  description="Semantic search across indexed patents and MPEP guidance, tuned for claim language."
                  points={[
                    "Search by claim limitation, concept, or plain language; results ranked by relevance.",
                    "Every result links to its source passage with section and paragraph provenance.",
                    "Draws on the same verified corpus the analysis pipeline retrieves from.",
                  ]}
                />
              }
            />
            <Route
              path="/audit"
              element={
                <ComingSoonPage
                  kicker="Provenance"
                  title="Audit Trail"
                  description="A complete record of what was retrieved, generated, verified, and flagged for each analysis."
                  points={[
                    "Every model call recorded with its purpose, token counts, and cost; never the privileged content.",
                    "Retrieval and verification steps in order, so any conclusion can be traced to its evidence.",
                    "Exportable for firm records and professional-responsibility review.",
                  ]}
                />
              }
            />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </MainContent>
      </div>
    </BrowserRouter>
  );
}
