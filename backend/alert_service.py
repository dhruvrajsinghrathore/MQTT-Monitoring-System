#!/usr/bin/env python3

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import threading
import time

logger = logging.getLogger(__name__)

class AlertService:
    """Service for evaluating sensor values against alert thresholds and managing alerts"""

    def __init__(self):
        self.active_alerts = {}  # {alert_id: alert_data}
        self.alert_history = []  # List of resolved alerts
        self.lock = threading.RLock()
        self.max_history_size = 1000  # Keep last 1000 alerts in memory

    def set_project_thresholds(self, project_id: str, thresholds: List[Dict[str, Any]]):
        """Update alert thresholds for a project"""
        with self.lock:
            self.thresholds = {t['topic_name']: t for t in thresholds}
            logger.info(f"Updated {len(thresholds)} alert thresholds for project {project_id}")

    def evaluate_sensor_reading(self, equipment_id: str, sensor_type: str, value: float,
                               topic: str, timestamp: str, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Evaluate a sensor reading against alert thresholds
        Returns alert data if threshold is breached, None otherwise
        """
        with self.lock:
            if not hasattr(self, 'thresholds') or not self.thresholds:
                return None

            # Find matching threshold
            threshold = None
            for thresh_topic, thresh_data in self.thresholds.items():
                # Match by exact topic or by sensor type in topic
                if thresh_topic == topic or topic.endswith(f"/{thresh_data['sensor_type']}"):
                    threshold = thresh_data
                    break

            if not threshold or not threshold.get('enabled', True):
                return None

            # Check if value breaches thresholds
            alert_type = None
            threshold_value = None

            if threshold.get('min_value') is not None and value < threshold['min_value']:
                alert_type = 'min'
                threshold_value = threshold['min_value']
            elif threshold.get('max_value') is not None and value > threshold['max_value']:
                alert_type = 'max'
                threshold_value = threshold['max_value']

            if alert_type is None:
                # No threshold breached - check if we need to resolve existing alerts
                self._resolve_alert_if_exists(equipment_id, sensor_type, topic)
                return None

            # Create alert ID
            alert_id = f"{project_id}_{equipment_id}_{sensor_type}_{alert_type}"

            # Check if alert already exists and is active
            if alert_id in self.active_alerts:
                # Update existing alert timestamp
                self.active_alerts[alert_id]['timestamp'] = timestamp
                self.active_alerts[alert_id]['current_value'] = value
                logger.debug(f"Updated existing alert {alert_id}")
                return None  # Don't return duplicate alerts

            # Create new alert
            alert = {
                'id': alert_id,
                'equipment_id': equipment_id,
                'sensor_type': sensor_type,
                'topic': topic,
                'current_value': value,
                'threshold_value': threshold_value,
                'threshold_type': alert_type,
                'severity': self._determine_severity(value, threshold_value, alert_type, threshold),
                'message': self._generate_alert_message(sensor_type, value, threshold_value, alert_type),
                'timestamp': timestamp,
                'resolved': False
            }

            # Add to active alerts
            self.active_alerts[alert_id] = alert
            logger.warning(f"🚨 New alert triggered: {alert['message']}")

            return alert

    def _determine_severity(self, value: float, threshold: float, alert_type: str,
                          threshold_config: Dict[str, Any]) -> str:
        """Determine alert severity based on how far the value is from threshold"""
        deviation = abs(value - threshold)

        # Simple severity logic - can be made more sophisticated
        if alert_type == 'max':
            # For max thresholds, higher values are more severe
            if deviation > threshold * 0.2:  # More than 20% over threshold
                return 'critical'
        else:  # min threshold
            # For min thresholds, lower values are more severe
            if deviation > threshold * 0.2:  # More than 20% under threshold
                return 'critical'

        return 'warning'

    def _generate_alert_message(self, sensor_type: str, value: float,
                              threshold: float, alert_type: str) -> str:
        """Generate human-readable alert message"""
        direction = "above" if alert_type == "max" else "below"
        return f"{sensor_type.replace('_', ' ').title()} is {direction} threshold: {value:.2f} (threshold: {threshold:.2f})"

    def _resolve_alert_if_exists(self, equipment_id: str, sensor_type: str, topic: str):
        """Resolve alerts that are no longer active"""
        with self.lock:
            # Find alerts for this equipment/sensor combination
            alerts_to_resolve = []
            for alert_id, alert in self.active_alerts.items():
                if (alert['equipment_id'] == equipment_id and
                    alert['sensor_type'] == sensor_type and
                    alert['topic'] == topic):
                    alerts_to_resolve.append(alert_id)

            # Resolve found alerts
            for alert_id in alerts_to_resolve:
                alert = self.active_alerts[alert_id]
                alert['resolved'] = True
                alert['resolved_at'] = datetime.now().isoformat()

                # Move to history
                self.alert_history.append(alert)
                del self.active_alerts[alert_id]

                # Keep history size manageable
                if len(self.alert_history) > self.max_history_size:
                    self.alert_history.pop(0)

                logger.info(f"✅ Alert resolved: {alert['message']}")

    def get_active_alerts(self, equipment_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all active alerts, optionally filtered by equipment"""
        with self.lock:
            alerts = list(self.active_alerts.values())
            if equipment_id:
                alerts = [a for a in alerts if a['equipment_id'] == equipment_id]
            return sorted(alerts, key=lambda x: x['timestamp'], reverse=True)

    def get_alert_history(self, limit: int = 50, equipment_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent alert history"""
        with self.lock:
            history = self.alert_history[-limit:] if limit > 0 else self.alert_history
            if equipment_id:
                history = [a for a in history if a['equipment_id'] == equipment_id]
            return sorted(history, key=lambda x: x.get('resolved_at', x['timestamp']), reverse=True)

    def clear_resolved_alerts(self, older_than_hours: int = 24):
        """Clear resolved alerts older than specified hours"""
        with self.lock:
            cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
            self.alert_history = [
                alert for alert in self.alert_history
                if datetime.fromisoformat(alert.get('resolved_at', alert['timestamp'])) > cutoff_time
            ]
            logger.info(f"Cleared old alerts, {len(self.alert_history)} remaining in history")

    def get_alert_stats(self) -> Dict[str, Any]:
        """Get alert statistics"""
        with self.lock:
            active_count = len(self.active_alerts)
            history_count = len(self.alert_history)

            severity_counts = {'warning': 0, 'critical': 0}
            for alert in self.active_alerts.values():
                severity_counts[alert['severity']] = severity_counts.get(alert['severity'], 0) + 1

            return {
                'active_alerts': active_count,
                'historical_alerts': history_count,
                'severity_breakdown': severity_counts,
                'most_recent_alert': max(self.active_alerts.values(), key=lambda x: x['timestamp']) if active_count > 0 else None
            }

# Global alert service instance
alert_service = AlertService()
