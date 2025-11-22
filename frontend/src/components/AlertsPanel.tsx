import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, X, ChevronDown, ChevronUp, Activity } from 'lucide-react';
import { Alert } from '../types';
import { getApiUrlWithParams, API_ENDPOINTS } from '../config/api';

interface AlertsPanelProps {
  projectId?: string;
  isMinimized?: boolean;
  onToggleMinimize?: () => void;
}

const AlertsPanel: React.FC<AlertsPanelProps> = ({
  projectId,
  isMinimized = false,
  onToggleMinimize
}) => {
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load initial alerts
  useEffect(() => {
    if (projectId) {
      loadAlerts();
    }
  }, [projectId]);

  const loadAlerts = async () => {
    if (!projectId) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(
        getApiUrlWithParams(API_ENDPOINTS.ALERTS_ACTIVE, { project_id: projectId })
      );

      if (!response.ok) {
        throw new Error(`Failed to load alerts: ${response.status}`);
      }

      const data = await response.json();
      setAlerts(data.alerts || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load alerts');
      console.error('Failed to load alerts:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Listen for WebSocket alert updates
  useEffect(() => {
    const handleAlertUpdate = (event: CustomEvent) => {
      const alertData = event.detail;
      if (alertData && alertData.type === 'alert_update') {
        // Add new alert to the list
        setAlerts(prevAlerts => {
          const newAlert = alertData.data;
          // Check if alert already exists (avoid duplicates)
          const existingIndex = prevAlerts.findIndex(a => a.id === newAlert.id);
          if (existingIndex >= 0) {
            // Update existing alert
            const updatedAlerts = [...prevAlerts];
            updatedAlerts[existingIndex] = newAlert;
            return updatedAlerts;
          } else {
            // Add new alert
            return [newAlert, ...prevAlerts];
          }
        });
      }
    };

    // Listen for custom alert events (dispatched by WebSocket handler)
    window.addEventListener('alertUpdate', handleAlertUpdate as EventListener);

    return () => {
      window.removeEventListener('alertUpdate', handleAlertUpdate as EventListener);
    };
  }, []);

  const handleAlertClick = (alert: Alert) => {
    // Navigate to equipment detail page
    navigate(`/equipment/${alert.equipment_id}`);
  };

  const dismissAlert = (alertId: string) => {
    // Remove alert from local state (it will be re-added if still active)
    setAlerts(prevAlerts => prevAlerts.filter(a => a.id !== alertId));
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-100 border-red-300 text-red-800';
      case 'warning':
        return 'bg-yellow-100 border-yellow-300 text-yellow-800';
      default:
        return 'bg-blue-100 border-blue-300 text-blue-800';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <AlertTriangle className="w-4 h-4 text-red-600" />;
      case 'warning':
        return <AlertTriangle className="w-4 h-4 text-yellow-600" />;
      default:
        return <Activity className="w-4 h-4 text-blue-600" />;
    }
  };

  if (isMinimized) {
    return (
      <div className="fixed bottom-4 right-4 z-40">
        <button
          onClick={onToggleMinimize}
          className={`
            flex items-center gap-2 px-3 py-2 rounded-lg shadow-lg border transition-colors
            ${alerts.length > 0
              ? 'bg-red-600 text-white border-red-700 hover:bg-red-700'
              : 'bg-gray-600 text-white border-gray-700 hover:bg-gray-700'
            }
          `}
        >
          <AlertTriangle className="w-4 h-4" />
          <span className="text-sm font-medium">
            {alerts.length > 0 ? `Alerts (${alerts.length})` : 'No Alerts'}
          </span>
          <ChevronUp className="w-4 h-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="fixed bottom-0 right-0 w-96 max-h-96 bg-white border-t border-l border-gray-200 shadow-lg z-40">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-red-600" />
          <h3 className="font-semibold text-gray-900">
            Active Alerts ({alerts.length})
          </h3>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={loadAlerts}
            disabled={isLoading}
            className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
            title="Refresh alerts"
          >
            <Activity className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={onToggleMinimize}
            className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
            title="Minimize panel"
          >
            <ChevronDown className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="max-h-80 overflow-y-auto">
        {error && (
          <div className="p-3 text-sm text-red-600 bg-red-50 border-b border-red-200">
            {error}
          </div>
        )}

        {isLoading && alerts.length === 0 && (
          <div className="p-4 text-center text-gray-500">
            <Activity className="w-6 h-6 animate-spin mx-auto mb-2" />
            Loading alerts...
          </div>
        )}

        {!isLoading && !error && alerts.length === 0 && (
          <div className="p-4 text-center text-gray-500">
            <AlertTriangle className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No active alerts</p>
          </div>
        )}

        {alerts.map((alert) => (
          <div
            key={alert.id}
            className={`
              p-3 border-b border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors
              ${getSeverityColor(alert.severity)}
            `}
            onClick={() => handleAlertClick(alert)}
          >
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-2 flex-1">
                {getSeverityIcon(alert.severity)}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium text-sm">
                      {alert.equipment_id}
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-white/50 font-medium capitalize">
                      {alert.severity}
                    </span>
                  </div>

                  <p className="text-sm mb-1">
                    {alert.sensor_type.replace('_', ' ')}
                  </p>

                  <div className="text-xs space-y-0.5">
                    <div>Current: <span className="font-mono font-medium">{alert.current_value.toFixed(2)}</span></div>
                    <div>Threshold: <span className="font-mono font-medium">{alert.threshold_value.toFixed(2)}</span></div>
                  </div>

                  <div className="text-xs text-gray-600 mt-1">
                    {new Date(alert.timestamp).toLocaleString()}
                  </div>
                </div>
              </div>

              <button
                onClick={(e) => {
                  e.stopPropagation();
                  dismissAlert(alert.id);
                }}
                className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
                title="Dismiss alert"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default AlertsPanel;
