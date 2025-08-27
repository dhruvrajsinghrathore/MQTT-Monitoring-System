import React from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { useNavigate } from 'react-router-dom';
import { useProject } from '../contexts/ProjectContext';
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
      >
        {/* Header */}
        <div className="flex items-center gap-3 mb-3">
          <div className="p-2 bg-white/20 rounded-md">
            {equipmentIcon}
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-white text-sm truncate hover:text-blue-200 transition-colors">
              {data.equipment_id || data.label || 'Unknown Equipment'}
            </h3>
            <p className="text-white/80 text-xs capitalize">
              {data.equipment_type?.replace('_', ' ') || 'Unknown'}
            </p>
          </div>
        </div>
        
        {/* Sensors */}
        <div className="mb-3 space-y-2">
          {data.sensors && data.sensors.length > 0 ? (
            data.sensors.map((sensor, index) => (
              <div key={index} className="text-white text-xs bg-black/20 rounded-md p-2">
                <div className="flex items-center gap-2 mb-1">
                  {getSensorIcon(sensor.sensor_type)}
                  <span className="font-medium capitalize">
                    {sensor.sensor_type?.replace('_', ' ')}
                  </span>
                </div>
                <div className="font-mono text-white/90 ml-5">
                  {formatValue(sensor.value || 0, sensor.unit || '')}
                </div>
              </div>
            ))
          ) : (
            <div className="text-white/60 text-xs text-center py-2">
              No sensor data
            </div>
          )}
        </div>
        
        {/* Status and Workflow */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-white/70">Status:</span>
            <span className="text-xs font-medium text-white bg-white/20 px-2 py-1 rounded-full">
              {data.status || 'unknown'}
            </span>
          </div>
          
          {data.workflow_step && (
            <div className="flex items-center justify-between">
              <span className="text-xs text-white/70">Step:</span>
              <span className="text-xs font-medium text-white bg-white/20 px-2 py-1 rounded-full">
                {data.workflow_step}
              </span>
            </div>
          )}
          
          <div className="flex items-center gap-1 text-xs text-white/60 mt-2">
            <Clock className="w-3 h-3" />
            <span>{timeAgo}</span>
          </div>
        </div>
      </div>
      
      <Handle type="source" position={Position.Bottom} className="opacity-0" />
    </div>
  );
};

export default CustomNode; 