#!/usr/bin/env python3
"""
TDengine Service for MQTT Chatbot
Provides real-time data access from TDengine database
"""

import requests
import logging
from typing import Dict, List, Optional, Any

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
            # Add timeout to prevent hanging (5 seconds connect, 30 seconds total)
            response = requests.post(
                self.base_url, 
                headers=self.headers, 
                data=sql,
                timeout=(5, 30)  # (connect_timeout, read_timeout)
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"TDengine query timed out - server not responding")
            return {"code": -1, "desc": "Connection timeout - TDengine server not accessible"}
        except requests.exceptions.ConnectionError as e:
            logger.error(f"TDengine connection error: {e}")
            return {"code": -1, "desc": f"Connection failed - {str(e)}"}
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

# Global instance
tdengine_service = TDengineService()
