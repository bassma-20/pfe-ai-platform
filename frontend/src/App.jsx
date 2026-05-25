import { Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/Navbarbb';
import Home from './pages/Home';
import AutoMLLayout from './pages/automl/AutoMLLayout';
import AutoMLHome from './pages/automl/AutoMLHome';
import UploadPage from './pages/automl/UploadPage';
import ManualPage from './pages/automl/ManualPage';
import AgentRunPage from './pages/automl/AgentRunPage';
import MigrationHome from './pages/migration/MigrationHome';
import ChatbotPage from './pages/chatbot/ChatbotPage';
import ChatBubble from './components/ChatBubble';
import './index.css';

export default function App() {
  return (

      <div className="app-shell">
        <Navbar />
        <Routes>
          <Route path="/" element={<Home />} />

          {/* AutoML — layout avec sidebar */}
          <Route path="/automl" element={<AutoMLLayout />}>
            <Route index element={<AutoMLHome />} />
            <Route path="upload" element={<UploadPage />} />
            <Route path="agent/:runId" element={<AgentRunPage />} />
            <Route path="manual/:runId" element={<ManualPage />} />
          </Route>

          {/* Migration */}
          <Route path="/migration" element={<MigrationHome />} />

          {/* Chatbot */}
          <Route path="/chatbot" element={<ChatbotPage />} />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>

        {/* Bulle flottante — visible sur toutes les pages */}
        <ChatBubble />
      </div>

  );
}
