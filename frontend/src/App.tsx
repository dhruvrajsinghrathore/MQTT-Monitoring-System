import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ProjectProvider } from './contexts/ProjectContext';
import ProjectsPage from './pages/ProjectsPage';
import CreateProjectPage from './pages/CreateProjectPage';
import GraphEditorPage from './pages/GraphEditorPage';
import MonitoringPage from './pages/MonitoringPage';
import EquipmentDetailPage from './pages/EquipmentDetailPage';

function App() {
  return (
    <ProjectProvider>
      <Router>
        <div className="min-h-screen bg-gray-50">
          <Routes>
            <Route path="/" element={<ProjectsPage />} />
            <Route path="/config" element={<CreateProjectPage />} />
            <Route path="/editor" element={<GraphEditorPage />} />
            <Route path="/monitor" element={<MonitoringPage />} />
            <Route path="/equipment/:equipmentId" element={<EquipmentDetailPage />} />
          </Routes>
        </div>
      </Router>
    </ProjectProvider>
  );
}

export default App; 