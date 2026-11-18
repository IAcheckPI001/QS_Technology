

import "./i18n";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";

import SupportWorkspace from './pages/SupportWorkspace.jsx';
import WorkspaceApp from './workspace/WorkspaceApp.jsx';
import ScrollToTop from "./hooks/scrollToTop.jsx";

// QS AI Workspace mới ở `/` (FRONTEND_REQUIREMENTS.md mục 18); bản Workspace cũ tạm ở `/legacy`,
// xoá ở giai đoạn 6.
function App(){
  return (
    <Router>
      <ScrollToTop />
      <Routes>
        <Route path="/legacy/*" element={<SupportWorkspace />} />
        <Route path="/*" element={<WorkspaceApp />} />
      </Routes>
    </Router>
  )

}

export default App
