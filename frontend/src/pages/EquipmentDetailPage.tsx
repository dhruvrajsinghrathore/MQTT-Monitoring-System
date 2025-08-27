import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft, Activity, Thermometer, Gauge, Zap, Navigation, Beaker, RefreshCw, Database } from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';
import { WEBSOCKET_URL } from '../config/api';
import { DatabaseService } from '../services/DatabaseService';

interface SensorDataPoint {
  timestamp: string;
  value: number | string | object;
  sensor_type: string;
  equipment_id: string;
  unit?: string;
  status?: string;
}

interface ChartDataPoint {
  time: string;
  [key: string]: any; // Dynamic sensor values
}

const EquipmentDetailPage: React.FC = () => {
  const { equipmentId } = useParams<{ equipmentId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  
  const [sensorData, setSensorData] = useState<SensorDataPoint[]>([]);
  const [chartData, setChartData] = useState<ChartDataPoint[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<string>('');
  const [historicalDataLoaded, setHistoricalDataLoaded] = useState(false);
  const [availableSessions, setAvailableSessions] = useState<string[]>([]);
  
  const equipment = (location.state as any)?.equipment;
  const project = (location.state as any)?.project;

  // Load historical data from database
  const loadHistoricalData = async () => {
    if (!equipmentId) return;

    console.log(`📚 Loading historical data for equipment: ${equipmentId}`);
    
    try {
      // Get project ID from the passed project context
      const projectId = project?.id || 'default_project';
      console.log(`🔍 Using project ID: ${projectId} for equipment: ${equipmentId}`);
      
      const messages = await DatabaseService.getMessagesForEquipment(projectId, equipmentId, 100);
      
      if (messages.length === 0) {
        console.log(`📭 No historical data found for equipment: ${equipmentId} in project: ${projectId}`);
        console.log('💡 Historical data will appear after you start monitoring and recording sessions');
        setHistoricalDataLoaded(true);
        return;
      }

      // Convert to our format
      const historicalMessages: SensorDataPoint[] = messages.map(msg => ({
        timestamp: msg.timestamp,
        value: msg.value,
        sensor_type: msg.sensor_type,
        equipment_id: msg.equipment_id,
        unit: msg.unit,
        status: msg.status
      }));

      // Sort by timestamp (should already be sorted, but just in case)
      historicalMessages.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
      
      console.log(`📊 Loaded ${historicalMessages.length} historical data points`);
      
      // Set historical data as initial sensor data
      setSensorData(historicalMessages);
      setAvailableSessions([`Found ${messages.length} historical messages`]);
    } catch (error) {
      console.error('Error loading historical data:', error);
    }
    
    setHistoricalDataLoaded(true);
  };

  const getSensorIcon = (sensorType: string) => {
    const icons = {
      temperature: <Thermometer className="w-4 h-4" />,
      pressure: <Gauge className="w-4 h-4" />,
      force: <Zap className="w-4 h-4" />,
      position: <Navigation className="w-4 h-4" />,
      speed: <Activity className="w-4 h-4" />,
      flow_rate: <Activity className="w-4 h-4" />,
      composition: <Beaker className="w-4 h-4" />,
      flow: <Activity className="w-4 h-4" />,
      level: <Gauge className="w-4 h-4" />,
      vibration: <Activity className="w-4 h-4" />
    };
    return icons[sensorType as keyof typeof icons] || <Activity className="w-4 h-4" />;
  };

  const getSensorColor = (_sensorType: string, index: number) => {
    const colors = [
      '#3B82F6', // blue
      '#EF4444', // red
      '#10B981', // green
      '#F59E0B', // yellow
      '#8B5CF6', // purple
      '#06B6D4', // cyan
      '#F97316', // orange
      '#84CC16', // lime
    ];
    return colors[index % colors.length];
  };

  const formatValue = (value: number | string | object): number => {
    if (typeof value === 'number') {
      return value;
    }
    if (typeof value === 'string') {
      const parsed = parseFloat(value);
      return isNaN(parsed) ? 0 : parsed;
    }
    if (typeof value === 'object' && value !== null) {
      // For composition objects, return the average or first numeric value
      const values = Object.values(value);
      const numericValues = values.filter(v => typeof v === 'number') as number[];
      return numericValues.length > 0 ? numericValues[0] : 0;
    }
    return 0;
  };

  // Load historical data on mount
  useEffect(() => {
    loadHistoricalData();
  }, [equipmentId]); // Only depend on equipmentId

  // Connect to WebSocket for real-time data
  useEffect(() => {
    if (!equipmentId) return;

    let websocket: WebSocket | null = null;

    const connectWebSocket = () => {
      try {
        const wsUrl = WEBSOCKET_URL.replace('http', 'ws') + '/ws';
        websocket = new WebSocket(wsUrl);

        websocket.onopen = () => {
          console.log('Equipment detail WebSocket connected');
          setIsConnected(true);
        };

        websocket.onclose = () => {
          console.log('Equipment detail WebSocket disconnected');
          setIsConnected(false);
        };

        websocket.onerror = (error) => {
          console.error('Equipment detail WebSocket error:', error);
          setIsConnected(false);
        };

        websocket.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            
            if (message.type === 'mqtt_data' && message.data.equipment_id === equipmentId) {
              const newDataPoint: SensorDataPoint = {
                timestamp: message.data.timestamp,
                value: message.data.value,
                sensor_type: message.data.sensor_type,
                equipment_id: message.data.equipment_id,
                unit: message.data.unit,
                status: message.data.status
              };
              
              // Append new data to existing historical + live data, keep last 100 points
              setSensorData(prev => [...prev.slice(-99), newDataPoint]);
              setLastUpdate(new Date().toLocaleTimeString());
            }
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };

      } catch (error) {
        console.error('Failed to connect to WebSocket:', error);
        setIsConnected(false);
      }
    };

    connectWebSocket();

    return () => {
      if (websocket) {
        websocket.close();
      }
    };
  }, [equipmentId]);

  // Convert sensor data to chart format
  useEffect(() => {
    if (sensorData.length === 0) return;

    // Group data by timestamp
    const timeGroups = sensorData.reduce((acc, point) => {
      const time = new Date(point.timestamp).toLocaleTimeString();
      if (!acc[time]) {
        acc[time] = { time };
      }
      
      const value = formatValue(point.value);
      acc[time][point.sensor_type] = value;
      
      return acc;
    }, {} as { [key: string]: ChartDataPoint });

    const newChartData = Object.values(timeGroups).slice(-20); // Last 20 time points
    setChartData(newChartData);
  }, [sensorData]);

  // Get unique sensor types for the chart
  const sensorTypes = Array.from(new Set(sensorData.map(point => point.sensor_type)));

  const formatValueForDisplay = (value: number | string | object, unit?: string): string => {
    if (typeof value === 'object' && value !== null) {
      return Object.entries(value).map(([key, val]) => `${key}: ${val}%`).join(', ');
    }
    
    if (typeof value === 'number') {
      return `${value.toFixed(1)} ${unit || ''}`;
    }
    
    return `${value} ${unit || ''}`;
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => navigate(-1)} // Go back to previous page (monitoring)
              className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-xl font-medium text-gray-900">
                {equipment?.equipment_id || equipmentId} Details
              </h1>
              <p className="text-sm text-gray-600">
                {equipment?.equipment_type || 'Equipment'} • Real-time sensor data
              </p>
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            {/* Connection Status */}
            {/* Historical Data Status */}
            {historicalDataLoaded && availableSessions.length > 0 && (
              <div className="flex items-center space-x-2 px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
                <Database className="w-4 h-4" />
                <span>Historical data loaded ({sensorData.length} points)</span>
              </div>
            )}

            {/* Connection Status */}
            <div className={`flex items-center space-x-2 px-3 py-1 rounded-full text-sm font-medium ${
              isConnected 
                ? 'bg-green-100 text-green-800' 
                : 'bg-red-100 text-red-800'
            }`}>
              <Activity className="w-4 h-4" />
              <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
            </div>
            
            {lastUpdate && (
              <div className="text-sm text-gray-600">
                Last update: {lastUpdate}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="p-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Current Values */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow border border-gray-200 p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Current Values</h3>
              
              <div className="space-y-4">
                {equipment?.sensors?.map((sensor: any, index: number) => (
                  <div key={index} className="p-4 rounded-lg bg-gray-50 border border-gray-100">
                    <div className="flex items-center gap-3 mb-2">
                      {getSensorIcon(sensor.sensor_type)}
                      <span className="font-medium text-gray-900 capitalize">
                        {sensor.sensor_type?.replace('_', ' ')}
                      </span>
                    </div>
                    <div className="text-2xl font-bold text-gray-900 mb-1">
                      {formatValueForDisplay(sensor.value, sensor.unit)}
                    </div>
                    <div className="text-xs text-gray-500">
                      {new Date(sensor.timestamp).toLocaleString()}
                    </div>
                  </div>
                )) || (
                  <div className="text-center text-gray-500 py-8">
                    <Activity className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>No sensor data available</p>
                    <p className="text-sm">Start monitoring to see live data</p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Line Chart */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow border border-gray-200 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-gray-900">Sensor Trends</h3>
                <div className="flex items-center space-x-2 text-sm text-gray-600">
                  <RefreshCw className="w-4 h-4" />
                  <span>{chartData.length} data points</span>
                </div>
              </div>
              
              {chartData.length > 0 ? (
                <div className="h-96">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis 
                        dataKey="time" 
                        stroke="#6b7280"
                        fontSize={12}
                      />
                      <YAxis 
                        stroke="#6b7280"
                        fontSize={12}
                      />
                      <Tooltip 
                        contentStyle={{
                          backgroundColor: 'white',
                          border: '1px solid #e5e7eb',
                          borderRadius: '8px',
                          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                        }}
                      />
                      <Legend />
                      {sensorTypes.map((sensorType, index) => (
                        <Line
                          key={sensorType}
                          type="monotone"
                          dataKey={sensorType}
                          stroke={getSensorColor(sensorType, index)}
                          strokeWidth={2}
                          dot={{ r: 3 }}
                          activeDot={{ r: 5 }}
                          name={sensorType.replace('_', ' ')}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="h-96 flex items-center justify-center text-gray-500">
                  <div className="text-center">
                    <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <h4 className="text-lg font-medium mb-2">No Chart Data Yet</h4>
                    <p className="text-sm">
                      {isConnected 
                        ? 'Waiting for sensor data to populate the chart...' 
                        : 'Connect to start receiving data'
                      }
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EquipmentDetailPage; 