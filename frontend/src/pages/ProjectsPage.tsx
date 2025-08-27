import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Star, Download, Upload, Trash2, Play, Edit, Calendar, Server, Layers } from 'lucide-react';
import { ProjectService } from '../services/ProjectService';
import { ProjectSummary } from '../types';
import { formatDistanceToNow } from 'date-fns';

const ProjectsPage: React.FC = () => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [isImporting, setIsImporting] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState<'name' | 'updated' | 'created'>('updated');

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = () => {
    const projectSummaries = ProjectService.getProjectSummaries();
    setProjects(projectSummaries);
  };

  const filteredAndSortedProjects = projects
    .filter(project => 
      project.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      project.description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      project.broker_host.toLowerCase().includes(searchTerm.toLowerCase())
    )
    .sort((a, b) => {
      switch (sortBy) {
        case 'name':
          return a.name.localeCompare(b.name);
        case 'created':
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        case 'updated':
        default:
          return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
      }
    });

  const handleCreateProject = () => {
    navigate('/config');
  };

  const handleOpenProject = async (projectId: string) => {
    const project = ProjectService.getProject(projectId);
    if (project) {
      // Test connection first
      navigate('/monitor', { state: { project } });
    }
  };

  const handleEditProject = (projectId: string) => {
    const project = ProjectService.getProject(projectId);
    if (project) {
      navigate('/editor', { state: { project } });
    }
  };

  const handleDeleteProject = (projectId: string) => {
    if (window.confirm('Are you sure you want to delete this project?')) {
      ProjectService.deleteProject(projectId);
      loadProjects();
    }
  };

  const handleToggleFavorite = (projectId: string) => {
    ProjectService.toggleFavorite(projectId);
    loadProjects();
  };

  const handleExportProject = (projectId: string) => {
    const exportData = ProjectService.exportProject(projectId);
    if (exportData) {
      ProjectService.downloadProjectFile(exportData);
    }
  };

  const handleImportProject = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsImporting(true);
    try {
      const project = await ProjectService.uploadProjectFile(file);
      ProjectService.saveProject(project);
      loadProjects();
    } catch (error) {
      alert('Failed to import project: ' + (error as Error).message);
    } finally {
      setIsImporting(false);
      event.target.value = ''; // Reset file input
    }
  };

  const getEquipmentTypesDisplay = (types: string[]) => {
    return types.slice(0, 3).join(', ') + (types.length > 3 ? '...' : '');
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">MQTT Workflow Projects</h1>
          <p className="text-gray-600">Manage your saved workflow configurations and graphs</p>
        </div>

        {/* Toolbar */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="flex-1">
            <input
              type="text"
              placeholder="Search projects..."
              className="minimal-input"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          
          <div className="flex gap-2">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="minimal-input min-w-0"
            >
              <option value="updated">Last Updated</option>
              <option value="created">Date Created</option>
              <option value="name">Name</option>
            </select>

            <button
              onClick={handleCreateProject}
              className="minimal-button-primary flex items-center whitespace-nowrap"
            >
              <Plus className="w-4 h-4 mr-2" />
              New Project
            </button>

            <label className="minimal-button flex items-center cursor-pointer whitespace-nowrap">
              <Upload className="w-4 h-4 mr-2" />
              {isImporting ? 'Importing...' : 'Import'}
              <input
                type="file"
                accept=".json"
                onChange={handleImportProject}
                className="hidden"
                disabled={isImporting}
              />
            </label>
          </div>
        </div>

        {/* Project Grid */}
        {filteredAndSortedProjects.length === 0 ? (
          <div className="text-center py-16">
            <div className="mb-4">
              <Layers className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No Projects Found</h3>
              <p className="text-gray-600 mb-6">
                {searchTerm ? 'No projects match your search.' : 'Create your first MQTT workflow project to get started.'}
              </p>
            </div>
            {!searchTerm && (
              <button
                onClick={handleCreateProject}
                className="minimal-button-primary"
              >
                <Plus className="w-4 h-4 mr-2" />
                Create First Project
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredAndSortedProjects.map((project) => (
              <div key={project.id} className="minimal-card p-6 hover:shadow-md transition-shadow">
                {/* Project Header */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-gray-900 text-lg truncate">
                      {project.name}
                    </h3>
                    {project.description && (
                      <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                        {project.description}
                      </p>
                    )}
                  </div>
                  <button
                    onClick={() => handleToggleFavorite(project.id)}
                    className="p-1 hover:bg-gray-100 rounded"
                  >
                    <Star 
                      className={`w-4 h-4 ${project.is_favorite ? 'text-yellow-500 fill-current' : 'text-gray-400'}`} 
                    />
                  </button>
                </div>

                {/* Project Stats */}
                <div className="space-y-2 mb-4">
                  <div className="flex items-center text-sm text-gray-600">
                    <Server className="w-4 h-4 mr-2" />
                    <span>{project.broker_host}</span>
                  </div>
                  <div className="flex items-center text-sm text-gray-600">
                    <Layers className="w-4 h-4 mr-2" />
                    <span>{project.node_count} nodes</span>
                    {project.equipment_types.length > 0 && (
                      <span className="ml-2 text-gray-500">
                        ({getEquipmentTypesDisplay(project.equipment_types)})
                      </span>
                    )}
                  </div>
                  <div className="flex items-center text-sm text-gray-600">
                    <Calendar className="w-4 h-4 mr-2" />
                    <span>
                      Updated {formatDistanceToNow(new Date(project.updated_at), { addSuffix: true })}
                    </span>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex gap-2">
                  <button
                    onClick={() => handleOpenProject(project.id)}
                    className="flex-1 minimal-button-primary flex items-center justify-center text-sm"
                  >
                    <Play className="w-4 h-4 mr-1" />
                    Monitor
                  </button>
                  
                  <button
                    onClick={() => handleEditProject(project.id)}
                    className="minimal-button flex items-center justify-center"
                  >
                    <Edit className="w-4 h-4" />
                  </button>
                  
                  <button
                    onClick={() => handleExportProject(project.id)}
                    className="minimal-button flex items-center justify-center"
                  >
                    <Download className="w-4 h-4" />
                  </button>
                  
                  <button
                    onClick={() => handleDeleteProject(project.id)}
                    className="minimal-button text-red-600 hover:bg-red-50 flex items-center justify-center"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Storage Info */}
        {projects.length > 0 && (
          <div className="mt-8 text-center text-sm text-gray-500">
            {projects.length} project{projects.length !== 1 ? 's' : ''} saved locally
          </div>
        )}
      </div>
    </div>
  );
};

export default ProjectsPage; 