#!/usr/bin/env python3
"""
TDengine Service for MQTT Chatbot
Provides real-time data access from TDengine database
"""

import requests
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TDengineService:
    """Service for interacting with TDengine database"""
    
    def __init__(self):
        self.base_url = "http://213.218.240.182:6041/rest/sql/rag"
        self.auth_header = "Basic cm9vdDp0YW9zZGF0YQ=="
        self.headers = {
            "Authorization": self.auth_header,
            "Content-Type": "text/plain"
        }
        
        # Feature mapping for @ references
        self.feature_mapping = {
            "glucose mM": "glucose_mM",
            "glucose": "glucose_mM", 
            "pH": "pH",
            "o2 percent": "o2_percent",
            "oxygen": "o2_percent",
            "pressure mbar": "pressure_mbar",
            "pressure": "pressure_mbar",
            "flow uL min": "flow_uL_min",
            "flow": "flow_uL_min",
            "viability percent": "hcs_viability_pct",
            "viability": "hcs_viability_pct",
            "cell count": "qpi_cell_count",
            "confluence": "qpi_confluence_pct",
            "dry mass": "qpi_dry_mass_pg",
            "ROS AU": "hcs_ROS_AU",
            "ROS IU": "hcs_ROS_IU",
            "Ca ratio": "hcs_Ca_ratio",
            "tumor proliferation": "tumor_prolif_index",
            "tumor EMT": "tumor_EMT_index",
            "aptamer IL6": "aptamer_IL6_nM",
            "aptamer TNFa": "aptamer_TNFa_nM",
            "barrier impedance": "barrier_impedance_kOhm"
        }
        
        logger.info("TDengine Service initialized with enhanced features")
    
    def execute_query(self, sql: str) -> Dict[str, Any]:
        """Execute SQL query against TDengine"""
        try:
            response = requests.post(self.base_url, headers=self.headers, data=sql)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"TDengine query failed: {e}")
            return {"code": -1, "desc": str(e)}
    
    def get_available_cells(self) -> List[str]:
        """Get list of available cell tables"""
        try:
            result = self.execute_query("SHOW TABLES")
            if result.get("code") == 0:
                tables = result.get("data", [])
                # Filter for cell tables (cell_1, cell_2, etc.)
                cell_tables = [table[0] for table in tables if table[0].startswith("cell_")]
                return sorted(cell_tables)
            return []
        except Exception as e:
            logger.error(f"Failed to get available cells: {e}")
            return []
    
    def get_cell_sensors(self, cell_id: str) -> List[Dict[str, Any]]:
        """Get available sensors for a specific cell"""
        try:
            sql = f"SELECT DISTINCT subtopic, field_name, unit, sensor_type FROM {cell_id}"
            result = self.execute_query(sql)
            
            if result.get("code") == 0:
                sensors = []
                for row in result.get("data", []):
                    sensors.append({
                        "subtopic": row[0],
                        "field_name": row[1], 
                        "unit": row[2],
                        "sensor_type": row[3]
                    })
                return sensors
            return []
        except Exception as e:
            logger.error(f"Failed to get sensors for {cell_id}: {e}")
            return []
    
    def get_latest_readings(self, cell_id: str) -> Dict[str, Any]:
        """Get latest sensor readings for a cell"""
        try:
            # Get recent data (last 10 records) and group by sensor
            sql = f"""
            SELECT subtopic, field_name, reading, unit, sensor_type, min_val, max_val, ts
            FROM {cell_id}
            ORDER BY ts DESC
            LIMIT 50
            """
            
            result = self.execute_query(sql)
            
            if result.get("code") == 0 and result.get("data"):
                sensors = {}
                # Group by subtopic and take the latest for each
                seen_sensors = set()
                
                for row in result.get("data", []):
                    subtopic = row[0]
                    if subtopic not in seen_sensors:
                        seen_sensors.add(subtopic)
                        sensors[subtopic] = {
                            "value": row[2],
                            "unit": row[3],
                            "sensor_type": row[4],
                            "min_val": row[5],
                            "max_val": row[6],
                            "timestamp": row[7],
                            "status": "active"
                        }
                
                return {
                    "equipment_id": cell_id,
                    "status": "active",
                    "last_updated": datetime.now().isoformat(),
                    "sensors": sensors
                }
            return {}
        except Exception as e:
            logger.error(f"Failed to get latest readings for {cell_id}: {e}")
            return {}
    
    def get_historical_data(self, cell_id: str, sensor_name: str, time_range: str = "24 HOUR") -> List[Dict[str, Any]]:
        """Get historical data for a specific sensor"""
        try:
            sql = f"""
            SELECT ts, reading, unit, sensor_type
            FROM {cell_id}
            WHERE subtopic = '{sensor_name}'
            AND ts >= NOW() - INTERVAL {time_range}
            ORDER BY ts
            """
            
            result = self.execute_query(sql)
            
            if result.get("code") == 0:
                data_points = []
                for row in result.get("data", []):
                    data_points.append({
                        "timestamp": row[0],
                        "value": row[1],
                        "unit": row[2],
                        "sensor_type": row[3]
                    })
                return data_points
            return []
        except Exception as e:
            logger.error(f"Failed to get historical data for {cell_id}.{sensor_name}: {e}")
            return []
    
    def compare_cells(self, cell_ids: List[str], sensor_name: str, time_range: str = "24 HOUR") -> Dict[str, List[Dict[str, Any]]]:
        """Compare sensor data across multiple cells"""
        try:
            comparison_data = {}
            
            for cell_id in cell_ids:
                data = self.get_historical_data(cell_id, sensor_name, time_range)
                comparison_data[cell_id] = data
            
            return comparison_data
        except Exception as e:
            logger.error(f"Failed to compare cells {cell_ids} for {sensor_name}: {e}")
            return {}
    
    def extract_cell_ids_from_query(self, user_query: str) -> List[str]:
        """Extract cell IDs mentioned in user query"""
        # Pattern to match cell_1, cell_2, etc.
        cell_pattern = r'\bcell_(\d+)\b'
        matches = re.findall(cell_pattern, user_query.lower())
        
        # Convert to cell_id format and validate against available cells
        available_cells = self.get_available_cells()
        cell_ids = [f"cell_{match}" for match in matches if f"cell_{match}" in available_cells]
        
        return cell_ids
    
    def extract_time_range_from_query(self, user_query: str) -> str:
        """Extract time range from user query"""
        user_query_lower = user_query.lower()
        
        # Check for specific patterns
        if re.search(r'\blast\s+(\d+)\s+days?\b', user_query_lower):
            match = re.search(r'\blast\s+(\d+)\s+days?\b', user_query_lower)
            return f"{match.group(1)} DAY"
        elif re.search(r'\blast\s+(\d+)\s+hours?\b', user_query_lower):
            match = re.search(r'\blast\s+(\d+)\s+hours?\b', user_query_lower)
            return f"{match.group(1)} HOUR"
        elif re.search(r'\blast\s+(\d+)\s+weeks?\b', user_query_lower):
            match = re.search(r'\blast\s+(\d+)\s+weeks?\b', user_query_lower)
            return f"{match.group(1)} WEEK"
        elif re.search(r'\blast\s+(\d+)\s+months?\b', user_query_lower):
            match = re.search(r'\blast\s+(\d+)\s+months?\b', user_query_lower)
            return f"{match.group(1)} MONTH"
        elif re.search(r'\b(\d+)\s+days?\s+ago\b', user_query_lower):
            match = re.search(r'\b(\d+)\s+days?\s+ago\b', user_query_lower)
            return f"{match.group(1)} DAY"
        elif re.search(r'\b(\d+)\s+hours?\s+ago\b', user_query_lower):
            match = re.search(r'\b(\d+)\s+hours?\s+ago\b', user_query_lower)
            return f"{match.group(1)} HOUR"
        elif re.search(r'\bpast\s+(\d+)\s+days?\b', user_query_lower):
            match = re.search(r'\bpast\s+(\d+)\s+days?\b', user_query_lower)
            return f"{match.group(1)} DAY"
        elif re.search(r'\bpast\s+(\d+)\s+hours?\b', user_query_lower):
            match = re.search(r'\bpast\s+(\d+)\s+hours?\b', user_query_lower)
            return f"{match.group(1)} HOUR"
        elif re.search(r'\bover\s+the\s+past\s+(\d+)\s+months?\b', user_query_lower):
            match = re.search(r'\bover\s+the\s+past\s+(\d+)\s+months?\b', user_query_lower)
            return f"{match.group(1)} MONTH"
        elif re.search(r'\bover\s+the\s+past\s+month\b', user_query_lower):
            return "1 MONTH"
        elif re.search(r'\bover\s+the\s+past\s+(\d+)\s+days?\b', user_query_lower):
            match = re.search(r'\bover\s+the\s+past\s+(\d+)\s+days?\b', user_query_lower)
            return f"{match.group(1)} DAY"
        elif re.search(r'\bover\s+the\s+past\s+(\d+)\s+weeks?\b', user_query_lower):
            match = re.search(r'\bover\s+the\s+past\s+(\d+)\s+weeks?\b', user_query_lower)
            return f"{match.group(1)} WEEK"
        elif 'today' in user_query_lower:
            return '1 DAY'
        elif 'yesterday' in user_query_lower:
            return '2 DAY'
        elif 'this week' in user_query_lower:
            return '7 DAY'
        elif 'this month' in user_query_lower:
            return '30 DAY'
        
        return "24 HOUR"  # Default
    
    def extract_referenced_features(self, user_query: str, references: List[str]) -> List[str]:
        """Extract specific features mentioned with @ symbols"""
        if not references:
            return []
        
        mapped_features = []
        for ref in references:
            ref_lower = ref.lower().strip()
            
            # Direct mapping
            if ref_lower in self.feature_mapping:
                mapped_features.append(self.feature_mapping[ref_lower])
            else:
                # Partial matching
                for key, value in self.feature_mapping.items():
                    if ref_lower in key.lower() or key.lower() in ref_lower:
                        mapped_features.append(value)
                        break
        
        return mapped_features
    
    def extract_sensor_names_from_query(self, user_query: str) -> List[str]:
        """Extract sensor names mentioned in user query"""
        # Common sensor name patterns
        sensor_patterns = [
            r'\bglucose\s+mM\b',
            r'\bpH\b',
            r'\bo2\s+percent\b',
            r'\bpressure\s+mbar\b',
            r'\bflow\s+uL_min\b',
            r'\bhcs\s+ROS_AU\b',
            r'\bhcs\s+ROS_IU\b',
            r'\bhcs\s+viability_pct\b',
            r'\bhcs\s+Ca_ratio\b',
            r'\baptamer\s+IL6_nM\b',
            r'\baptamer\s+TNFa_nM\b',
            r'\bbarrier\s+impedance_kOhm\b',
            r'\bqpi\s+cell_count\b',
            r'\bqpi\s+confluence_pct\b',
            r'\bqpi\s+dry_mass_pg\b',
            r'\btumor\s+EMT_index\b',
            r'\btumor\s+prolif_index\b'
        ]
        
        found_sensors = []
        for pattern in sensor_patterns:
            matches = re.findall(pattern, user_query.lower())
            if matches:
                # Convert to database field names
                sensor_name = pattern.replace(r'\b', '').replace(r'\s+', '_').replace('\\', '')
                found_sensors.append(sensor_name)
        
        return found_sensors
    
    def build_context_from_query(self, user_query: str) -> str:
        """Build context string based on user query"""
        cell_ids = self.extract_cell_ids_from_query(user_query)
        sensor_names = self.extract_sensor_names_from_query(user_query)
        time_range = self.extract_time_range_from_query(user_query)
        
        context = f"# Real-time Data Analysis\n\n"
        
        if cell_ids:
            context += f"## Cells Analyzed: {', '.join(cell_ids)}\n\n"
            
            for cell_id in cell_ids:
                # Get latest readings
                latest_data = self.get_latest_readings(cell_id)
                if latest_data:
                    context += f"### {cell_id.upper()}\n"
                    context += f"- Status: {latest_data.get('status', 'Unknown')}\n"
                    context += f"- Last Updated: {latest_data.get('last_updated', 'Unknown')}\n\n"
                    
                    sensors = latest_data.get('sensors', {})
                    if sensor_names:
                        # Show only requested sensors
                        for sensor_name in sensor_names:
                            if sensor_name in sensors:
                                sensor_data = sensors[sensor_name]
                                context += f"- {sensor_name}: {sensor_data['value']} {sensor_data['unit']} (Range: {sensor_data['min_val']}-{sensor_data['max_val']})\n"
                    else:
                        # Show all sensors
                        for sensor_name, sensor_data in sensors.items():
                            context += f"- {sensor_name}: {sensor_data['value']} {sensor_data['unit']} (Range: {sensor_data['min_val']}-{sensor_data['max_val']})\n"
                    
                    context += "\n"
        
        # Add historical data if time range is specified
        if sensor_names and cell_ids and time_range != "24 HOUR":
            context += f"## Historical Analysis ({time_range})\n\n"
            for cell_id in cell_ids:
                for sensor_name in sensor_names:
                    historical_data = self.get_historical_data(cell_id, sensor_name, time_range)
                    if historical_data:
                        context += f"### {cell_id} - {sensor_name}\n"
                        context += f"- Data Points: {len(historical_data)}\n"
                        if historical_data:
                            latest_value = historical_data[-1]['value']
                            earliest_value = historical_data[0]['value']
                            context += f"- Latest: {latest_value} {historical_data[-1]['unit']}\n"
                            context += f"- Earliest: {earliest_value} {historical_data[0]['unit']}\n"
                            context += f"- Trend: {'Increasing' if latest_value > earliest_value else 'Decreasing' if latest_value < earliest_value else 'Stable'}\n"
                        context += "\n"
        
        return context

    def get_specific_sensor_data(self, cell_ids: List[str], sensor_names: List[str], time_range: str = "24 HOUR") -> Dict[str, Any]:
        """Get specific sensors for specific cells with time filtering"""
        data = {}
        
        # Calculate actual date based on time range
        from datetime import datetime, timedelta
        
        if time_range.endswith('HOUR'):
            hours = int(time_range.split()[0])
            cutoff_date = datetime.now() - timedelta(hours=hours)
        elif time_range.endswith('DAY'):
            days = int(time_range.split()[0])
            cutoff_date = datetime.now() - timedelta(days=days)
        elif time_range.endswith('WEEK'):
            weeks = int(time_range.split()[0])
            cutoff_date = datetime.now() - timedelta(weeks=weeks)
        elif time_range.endswith('MONTH'):
            months = int(time_range.split()[0])
            cutoff_date = datetime.now() - timedelta(days=months*30)  # Approximate
        else:
            cutoff_date = datetime.now() - timedelta(hours=24)  # Default
        
        # Format for TDengine (ISO format)
        cutoff_str = cutoff_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        
        for cell_id in cell_ids:
            for sensor_name in sensor_names:
                sql = f"""
                SELECT reading, unit, sensor_type, min_val, max_val, ts
                FROM {cell_id}
                WHERE subtopic = '{sensor_name}'
                AND ts >= '{cutoff_str}'
                ORDER BY ts DESC
                LIMIT 1
                """
                
                result = self.execute_query(sql)
                if result.get("data"):
                    row = result["data"][0]
                    data[f"{cell_id}_{sensor_name}"] = {
                        "value": row[0],
                        "unit": row[1],
                        "sensor_type": row[2],
                        "min_val": row[3],
                        "max_val": row[4],
                        "timestamp": row[5],
                        "status": "active"
                    }
        
        return data
    
    def get_historical_data(self, cell_ids: List[str], sensor_names: List[str], time_range: str) -> Dict[str, List[Dict[str, Any]]]:
        """Get historical data for trend analysis"""
        historical_data = {}
        
        # Calculate actual date based on time range
        from datetime import datetime, timedelta
        
        if time_range.endswith('HOUR'):
            hours = int(time_range.split()[0])
            cutoff_date = datetime.now() - timedelta(hours=hours)
        elif time_range.endswith('DAY'):
            days = int(time_range.split()[0])
            cutoff_date = datetime.now() - timedelta(days=days)
        elif time_range.endswith('WEEK'):
            weeks = int(time_range.split()[0])
            cutoff_date = datetime.now() - timedelta(weeks=weeks)
        elif time_range.endswith('MONTH'):
            months = int(time_range.split()[0])
            cutoff_date = datetime.now() - timedelta(days=months*30)  # Approximate
        else:
            cutoff_date = datetime.now() - timedelta(hours=24)  # Default
        
        # Format for TDengine (ISO format)
        cutoff_str = cutoff_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        
        for cell_id in cell_ids:
            for sensor_name in sensor_names:
                sql = f"""
                SELECT ts, reading, unit, sensor_type
                FROM {cell_id}
                WHERE subtopic = '{sensor_name}'
                AND ts >= '{cutoff_str}'
                ORDER BY ts
                """
                
                result = self.execute_query(sql)
                if result.get("data"):
                    data_points = []
                    for row in result["data"]:
                        data_points.append({
                            "timestamp": row[0],
                            "value": row[1],
                            "unit": row[2],
                            "sensor_type": row[3]
                        })
                    historical_data[f"{cell_id}_{sensor_name}"] = data_points
        
        return historical_data

    def get_simple_trend_summary(self, cell_id: str, sensor_name: str, time_range: str) -> Dict[str, Any]:
        """Get a simple trend summary for single cell/sensor - much simpler than raw data"""
        try:
            # Calculate cutoff date
            if time_range.endswith('HOUR'):
                hours = int(time_range.split()[0])
                cutoff_date = datetime.now() - timedelta(hours=hours)
            elif time_range.endswith('DAY'):
                days = int(time_range.split()[0])
                cutoff_date = datetime.now() - timedelta(days=days)
            elif time_range.endswith('WEEK'):
                weeks = int(time_range.split()[0])
                cutoff_date = datetime.now() - timedelta(weeks=weeks)
            elif time_range.endswith('MONTH'):
                months = int(time_range.split()[0])
                cutoff_date = datetime.now() - timedelta(days=months*30)
            else:
                cutoff_date = datetime.now() - timedelta(hours=24)
            
            cutoff_str = cutoff_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            
            # Get first and last values for trend calculation
            sql = f"""
            SELECT ts, reading, unit
            FROM {cell_id}
            WHERE subtopic = '{sensor_name}'
            AND ts >= '{cutoff_str}'
            ORDER BY ts
            """
            
            result = self.execute_query(sql)
            if result.get("code") == 0 and result.get("data"):
                data_points = result["data"]
                if len(data_points) >= 2:
                    first_point = data_points[0]
                    last_point = data_points[-1]
                    
                    # Calculate trend
                    first_value = float(first_point[1])
                    last_value = float(last_point[1])
                    
                    # Calculate statistics
                    values = [float(row[1]) for row in data_points]
                    min_value = min(values)
                    max_value = max(values)
                    avg_value = sum(values) / len(values)
                    
                    if last_value > first_value:
                        trend_direction = "INCREASING"
                        change_percent = ((last_value - first_value) / first_value) * 100 if first_value != 0 else 0
                    elif last_value < first_value:
                        trend_direction = "DECREASING"
                        change_percent = ((first_value - last_value) / first_value) * 100 if first_value != 0 else 0
                    else:
                        trend_direction = "STABLE"
                        change_percent = 0
                    
                    return {
                        "cell_id": cell_id,
                        "sensor_name": sensor_name,
                        "time_range": time_range,
                        "data_points": len(data_points),
                        "first_value": first_value,
                        "last_value": last_value,
                        "min_value": round(min_value, 3),
                        "max_value": round(max_value, 3),
                        "avg_value": round(avg_value, 3),
                        "unit": first_point[2],
                        "trend_direction": trend_direction,
                        "change_percent": round(change_percent, 2),
                        "start_time": first_point[0],
                        "end_time": last_point[0],
                        "status": "success"
                    }
                elif len(data_points) == 1:
                    return {
                        "cell_id": cell_id,
                        "sensor_name": sensor_name,
                        "time_range": time_range,
                        "data_points": 1,
                        "first_value": float(data_points[0][1]),
                        "last_value": float(data_points[0][1]),
                        "unit": data_points[0][2],
                        "trend_direction": "INSUFFICIENT_DATA",
                        "change_percent": 0,
                        "start_time": data_points[0][0],
                        "end_time": data_points[0][0],
                        "status": "insufficient_data"
                    }
            
            return {
                "cell_id": cell_id,
                "sensor_name": sensor_name,
                "time_range": time_range,
                "status": "no_data"
            }
            
        except Exception as e:
            logger.error(f"Failed to get trend summary for {cell_id} {sensor_name}: {e}")
            return {
                "cell_id": cell_id,
                "sensor_name": sensor_name,
                "time_range": time_range,
                "status": "error",
                "error": str(e)
            }

# Global instance
tdengine_service = TDengineService()
