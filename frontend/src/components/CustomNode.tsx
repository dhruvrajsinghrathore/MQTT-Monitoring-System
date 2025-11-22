import React, { useState } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { useNavigate } from 'react-router-dom';
import { useProject } from '../contexts/ProjectContext';
import SensorDetailModal from './SensorDetailModal';
import { API_BASE_URL } from '../config/api';
import { 
  Thermometer, 
  Gauge, 
  Zap, 
  Navigation, 
  Activity,
  Beaker,
  Clock,
  Cpu,
  Settings,
  Box,
  Package,
  Cog,
  Server
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

interface CustomNodeData {
  label: string;
  equipment_id: string;
  equipment_type: string;
  image_url?: string;
  sensors?: Array<{
    sensor_type: string;
    value: number | string | object;
    unit: string;
    timestamp: string;
    status?: string;
  }>;
  status?: string;
  last_updated?: string;
  workflow_step?: string;
}

const getStatusColor = (status: string) => {
  const colors = {
    idle: 'from-gray-500 to-gray-600',
    normal: 'from-blue-500 to-blue-600', 
    active: 'from-green-500 to-green-600',
    warning: 'from-yellow-500 to-yellow-600',
    error: 'from-red-500 to-red-600',
    analysis_complete: 'from-purple-500 to-purple-600',
  };
  return colors[status as keyof typeof colors] || colors.normal;
};

const getSensorIcon = (sensorType: string) => {
  const icons = {
    temperature: <Thermometer className="w-3 h-3" />,
    pressure: <Gauge className="w-3 h-3" />,
    force: <Zap className="w-3 h-3" />,
    position: <Navigation className="w-3 h-3" />,
    speed: <Activity className="w-3 h-3" />,
    flow_rate: <Activity className="w-3 h-3" />,
    composition: <Beaker className="w-3 h-3" />,
    flow: <Activity className="w-3 h-3" />,
    level: <Gauge className="w-3 h-3" />,
    vibration: <Activity className="w-3 h-3" />
  };
  return icons[sensorType as keyof typeof icons] || <Activity className="w-3 h-3" />;
};

const getEquipmentIcon = (equipmentType: string) => {
  // Dynamic icon mapping based on equipment type
  const iconMap: { [key: string]: React.ReactNode } = {
    cell: <Activity className="w-5 h-5" />,
    sensor: <Cpu className="w-5 h-5" />,
    pump: <Zap className="w-5 h-5" />,
    valve: <Settings className="w-5 h-5" />,
    monitor: <Activity className="w-5 h-5" />,
    controller: <Cpu className="w-5 h-5" />,
    device: <Box className="w-5 h-5" />,
    equipment: <Package className="w-5 h-5" />,
    machine: <Cog className="w-5 h-5" />,
    system: <Server className="w-5 h-5" />,
  };
  
  // Try exact match first, then fallback to generic icons
  return iconMap[equipmentType.toLowerCase()] || <Package className="w-5 h-5" />;
};

const formatValue = (value: number | string | object, unit: string) => {
  if (typeof value === 'object' && value !== null) {
    return Object.entries(value).map(([key, val]) => `${key}: ${val}%`).join(', ');
  }
  
  if (typeof value === 'number') {
    return `${value.toFixed(1)} ${unit}`;
  }
  
  return `${value} ${unit}`;
};

const CustomNode: React.FC<NodeProps<CustomNodeData>> = ({ data }) => {
  const navigate = useNavigate();
  const { project } = useProject();
  const [showSensorModal, setShowSensorModal] = useState(false);

  // Safety check for undefined data
  if (!data) {
    return (
      <div className="min-w-[220px] p-4 rounded-xl bg-gray-500 text-white">
        <span>Loading...</span>
      </div>
    );
  }

  const gradientColor = getStatusColor(data.status || 'normal');
  const equipmentIcon = getEquipmentIcon(data.equipment_type || 'unknown');

  const timeAgo = data.last_updated
    ? formatDistanceToNow(new Date(data.last_updated), { addSuffix: true })
    : 'Never';

  // Check if node has an image
  const hasImage = !!data.image_url;

  // Handle node click
  const handleNodeClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (hasImage) {
      // If node has image, show sensor modal instead of navigating
      setShowSensorModal(true);
    } else {
      // If no image, navigate to equipment detail page
      navigate(`/equipment/${data.equipment_id}`, {
        state: {
          equipment: data,
          project: project
        }
      });
    }
  };



  return (
    <div className="relative">
      <Handle type="target" position={Position.Top} className="opacity-0" />
      
      {/* Pulse animation for active status */}
      {data.status === 'active' && (
        <div className="absolute -inset-1 bg-gradient-to-r from-green-400 to-green-600 rounded-xl opacity-30 animate-pulse pointer-events-none" />
      )}
      
      <div
        className={`
          min-w-[220px] p-4 rounded-xl shadow-lg border border-white/20
          bg-gradient-to-br ${gradientColor}
          transform transition-all duration-300 hover:scale-105 hover:shadow-xl
          cursor-pointer relative z-10
        `}
        onClick={handleNodeClick}
      >
        {/* Always show image - with fallback to equipment info if no image */}
        <div className="relative">
          {hasImage ? (
            <img
              src={`${API_BASE_URL}${data.image_url}`}
              alt={`${data.equipment_id} equipment`}
              className="w-full h-32 object-cover rounded-lg"
            />
          ) : (
            /* Placeholder when no image is available */
            <div className="w-full h-32 bg-gray-300 rounded-lg flex items-center justify-center">
              <div className="text-center">
                <div className="p-2 bg-white/20 rounded-md mb-2 inline-block">
                  {equipmentIcon}
                </div>
                <p className="text-gray-600 text-xs">No image uploaded</p>
              </div>
            </div>
          )}

          {/* Overlay with equipment info */}
          <div className="absolute bottom-0 left-0 right-0 bg-black/70 text-white p-2 rounded-b-lg">
            <h3 className="font-semibold text-sm truncate">
              {data.equipment_id || data.label || 'Unknown Equipment'}
            </h3>
            <p className="text-white/80 text-xs capitalize">
              {data.equipment_type?.replace('_', ' ') || 'Unknown'}
            </p>
            {/* Status indicator */}
            <div className="flex items-center justify-between mt-1">
              <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${
                data.status === 'active' ? 'bg-green-500 text-white' :
                data.status === 'warning' ? 'bg-yellow-500 text-black' :
                data.status === 'error' ? 'bg-red-500 text-white' :
                'bg-blue-500 text-white'
              }`}>
                {data.status || 'unknown'}
              </span>
              <span className="text-xs text-white/80">{timeAgo}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Sensor Detail Modal */}
      <SensorDetailModal
        isOpen={showSensorModal && hasImage}
        onClose={() => setShowSensorModal(false)}
        equipment={data}
      />
      
      <Handle type="source" position={Position.Bottom} className="opacity-0" />
    </div>
  );
};

export default CustomNode; 