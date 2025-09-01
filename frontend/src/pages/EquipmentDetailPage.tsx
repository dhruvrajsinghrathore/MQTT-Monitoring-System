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
  t: number;        // numeric epoch ms (stable x)
  i: number;        // fixed index within window (0..19)
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
  // Track selected features for filtering
  const [selectedFeatures, setSelectedFeatures] = useState<Set<string>>(new Set());
  // Track all available features
  const [availableFeatures, setAvailableFeatures] = useState<string[]>([]);
  
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
      '#E11D48', // rose
      '#6366F1', // indigo
      '#F43F5E', // pink
      '#22D3EE', // sky
      '#A3E635', // light green
      '#FACC15', // amber
      '#D946EF', // fuchsia
      '#64748B', // slate
      '#FDE68A', // light yellow
      '#C026D3', // violet
      '#4ADE80', // emerald
      '#F87171', // light red
      '#0EA5E9', // light blue
      '#FBBF24', // gold
      '#7C3AED', // deep purple
      '#2DD4BF', // teal
      '#F472B6', // light pink
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
            
            if (message.type === 'graph_update' && message.data.nodes) {
              const equipmentNode = message.data.nodes.find((node: any) => 
                node.data.equipment_id === equipmentId
              );
              
              if (equipmentNode && equipmentNode.data.sensors) {
                // ✅ one batch timestamp for all sensors in this update
                const batchIso =
                  message.data?.timestamp ??
                  equipmentNode.data?.timestamp ??
                  new Date().toISOString();

                // Process each sensor separately
                equipmentNode.data.sensors.forEach((sensor: any) => {
                  const timestamp = sensor.timestamp || batchIso;
                  const newDataPoint: SensorDataPoint = {
                    timestamp,
                    value: sensor.value,
                    sensor_type: sensor.sensor_type,
                    equipment_id: equipmentId,
                    unit: sensor.unit,
                    status: sensor.status || 'active'
                  };
                  
                  // Update available features if this is a new sensor type
                  setAvailableFeatures(prev => {
                    if (!prev.includes(sensor.sensor_type)) {
                      return [...prev, sensor.sensor_type].sort();
                    }
                    return prev;
                  });

                  // Append to existing data without removing old points
                  setSensorData(prev => [...prev, newDataPoint]);
                });

                setLastUpdate(new Date().toLocaleTimeString());
              }
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

    // 1) unique sorted timestamps (epoch ms)
    const allTs = Array.from(
      new Set(sensorData.map(p => new Date(p.timestamp).getTime()))
    ).sort((a, b) => a - b);

    // 2) Calculate sliding window (last 30 seconds)
    const windowSize = 30 * 1000; // 30 seconds in milliseconds
    const latestTime = allTs[allTs.length - 1];
    const windowStart = latestTime - windowSize;
    
    // Keep only timestamps within sliding window
    const windowTs = allTs.filter(t => t >= windowStart);

    // 3) Create rows for timestamps in window
    const rows: ChartDataPoint[] = windowTs.map((t, idx) => {
      const row: ChartDataPoint = {
        t,
        i: idx,
        time: new Date(t).toLocaleTimeString(),
      };
      return row;
    });

    const rowByT = new Map<number, ChartDataPoint>(rows.map(r => [r.t, r]));

    // 3) Find all sensor types present in these last 20 timestamps
    const typesInWindow = new Set<string>();
    for (const p of sensorData) {
      const t = new Date(p.timestamp).getTime();
      if (!rowByT.has(t)) continue;
      typesInWindow.add(p.sensor_type);
    }

    // 4) Initialize each row with all sensor keys set to null
    rows.forEach(r => {
      typesInWindow.forEach(st => { if (!(st in r)) r[st] = null; });
    });

    // 5) Fill values for (t, sensor_type)
    for (const p of sensorData) {
      const t = new Date(p.timestamp).getTime();
      const row = rowByT.get(t);
      if (!row) continue;
      row[p.sensor_type] = formatValue(p.value);
    }

    setChartData(rows);
  }, [sensorData]);


  // Get unique sensor types for the chart
  // const sensorTypes = Array.from(new Set(sensorData.map(point => point.sensor_type)));

  const sensorTypes = React.useMemo(() => {
    const set = new Set<string>();
    chartData.forEach(row => {
      Object.keys(row).forEach(k => {
        if (k !== 't' && k !== 'i' && k !== 'time') set.add(k);
      });
    });
    return Array.from(set).sort();
  }, [chartData]);


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
              <div className="space-y-4 mb-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-medium text-gray-900">Sensor Trends</h3>
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <RefreshCw className="w-4 h-4" />
                    <span>{chartData.length} data points</span>
                  </div>
                </div>

                {/* Feature Selection */}
                <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Select Features to Display</h4>
                  <div className="flex flex-wrap gap-2">
                    {availableFeatures.map(feature => (
                      <button
                        key={feature}
                        onClick={() => setSelectedFeatures(prev => {
                          const newSet = new Set(prev);
                          if (newSet.has(feature)) {
                            newSet.delete(feature);
                          } else {
                            newSet.add(feature);
                          }
                          return newSet;
                        })}
                        className={`px-3 py-1 rounded-full text-sm font-medium transition-colors
                          ${selectedFeatures.has(feature)
                            ? 'bg-blue-100 text-blue-800 hover:bg-blue-200'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                          }`}
                      >
                        {feature.replace('_', ' ')}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              
              {chartData.length > 0 ? (
                <div className="h-96">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis
                        dataKey="t"
                        type="number"
                        allowDecimals={false}
                        domain={['dataMin', 'dataMax']}
                        tickFormatter={(t) => new Date(t).toLocaleTimeString()}
                        stroke="#6b7280"
                        fontSize={12}
                        interval="preserveStartEnd"
                        minTickGap={40}
                        padding={{ left: 0, right: 0 }}
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
                      {sensorTypes
                        .filter(type => selectedFeatures.size === 0 || selectedFeatures.has(type))
                        .map((sensorType, index) => (
                          <Line
                            key={sensorType}
                            type="monotone"
                            dataKey={sensorType}
                            stroke={getSensorColor(sensorType, index)}
                            strokeWidth={2}
                            dot={{ r: 3 }}
                            activeDot={{ r: 5 }}
                            name={sensorType.replace('_', ' ')}
                            connectNulls
                            isAnimationActive={false} // Disable animation for real-time updates
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