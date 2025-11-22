import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useProject } from '../contexts/ProjectContext';
import { formatDistanceToNow } from 'date-fns';
import { API_BASE_URL } from '../config/api';

interface SensorData {
  sensor_type: string;
  value: number | string | object;
  unit: string;
  timestamp: string;
  status?: string;
}

interface EquipmentData {
  equipment_id: string;
  label?: string;
  equipment_type: string;
  image_url?: string;
  sensors?: SensorData[];
  status?: string;
  last_updated?: string;
}

interface SensorDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  equipment: EquipmentData;
}

const getSensorIcon = (sensorType: string) => {
  // Import icons here or use a similar function
  const icons = {
    temperature: '🌡️',
    pressure: '🔵',
    force: '💪',
    position: '📍',
    speed: '⚡',
    flow_rate: '🌊',
    composition: '🧪',
    flow: '🌊',
    level: '📏',
    vibration: '📳'
  };
  return icons[sensorType as keyof typeof icons] || '📊';
};

const formatValue = (value: any, unit: string) => {
  if (value === null || value === undefined) return 'N/A';

  if (typeof value === 'object') {
    // Handle complex objects (like arrays or nested objects)
    return JSON.stringify(value);
  }

  // Format numbers with appropriate precision
  if (typeof value === 'number') {
    if (value % 1 === 0) {
      return `${value} ${unit}`.trim();
    } else {
      return `${value.toFixed(2)} ${unit}`.trim();
    }
  }

  return `${value} ${unit}`.trim();
};

const SensorDetailModal: React.FC<SensorDetailModalProps> = ({ isOpen, onClose, equipment }) => {
  const navigate = useNavigate();
  const { project } = useProject();

  if (!isOpen) return null;

  const timeAgo = equipment.last_updated
    ? formatDistanceToNow(new Date(equipment.last_updated), { addSuffix: true })
    : 'Never';

  const handleViewDetails = () => {
    onClose();
    navigate(`/equipment/${equipment.equipment_id}`, {
      state: {
        equipment: equipment,
        project: project
      }
    });
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4 max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">
            {equipment.equipment_id} - Sensor Data
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            ✕
          </button>
        </div>

        {/* Equipment Image */}
        {equipment.image_url && (
          <img
            src={`${API_BASE_URL}${equipment.image_url}`}
            alt={`${equipment.equipment_id} equipment`}
            className="w-full h-32 object-cover rounded-lg mb-4"
          />
        )}

        {/* Equipment Info */}
        <div className="mb-4">
          <h3 className="font-semibold text-gray-900">
            {equipment.equipment_id || equipment.label || 'Unknown Equipment'}
          </h3>
          <p className="text-gray-600 text-sm capitalize">
            {equipment.equipment_type?.replace('_', ' ') || 'Unknown'}
          </p>
        </div>

        {/* Sensors */}
        <div className="space-y-3">
          <h4 className="font-medium text-gray-900">Sensor Readings</h4>
          {equipment.sensors && equipment.sensors.length > 0 ? (
            equipment.sensors.map((sensor, index) => (
              <div key={index} className="bg-gray-50 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-lg">{getSensorIcon(sensor.sensor_type)}</span>
                  <span className="font-medium text-gray-900 capitalize">
                    {sensor.sensor_type?.replace('_', ' ')}
                  </span>
                </div>
                <div className="font-mono text-lg text-gray-700">
                  {formatValue(sensor.value || 0, sensor.unit || '')}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  Updated {formatDistanceToNow(new Date(sensor.timestamp), { addSuffix: true })}
                </div>
              </div>
            ))
          ) : (
            <div className="text-gray-500 text-center py-4">
              No sensor data available
            </div>
          )}
        </div>

        {/* Status */}
        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-600">Status:</span>
            <span className={`px-2 py-1 rounded-full text-xs font-medium capitalize
              ${equipment.status === 'active' ? 'bg-green-100 text-green-800' :
                equipment.status === 'warning' ? 'bg-yellow-100 text-yellow-800' :
                equipment.status === 'error' ? 'bg-red-100 text-red-800' :
                'bg-blue-100 text-blue-800'}`}>
              {equipment.status || 'normal'}
            </span>
          </div>
          <div className="text-xs text-gray-500 mt-2">
            Last updated: {timeAgo}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="mt-6 flex gap-3">
          <button
            onClick={handleViewDetails}
            className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors"
          >
            View Details
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default SensorDetailModal;
