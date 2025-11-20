"""
TDengine Tool for CrewAI
Tool for executing SQL queries against TDengine database
"""
import sys
import os

# Add parent directory to path to import tdengine_service
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crewai.tools import tool
from tdengine_service import tdengine_service
import json
import logging

logger = logging.getLogger(__name__)

@tool("Execute TDengine SQL Query")
def execute_tdengine_query(sql_query: str) -> str:
    """
    Execute a SQL query against TDengine database and return results.
    
    This tool allows agents to query TDengine time-series database to retrieve
    sensor data, perform aggregations, correlations, and other analyses.
    
    Args:
        sql_query: Valid TDengine SQL query string
        
    Returns:
        JSON string containing query results or error information
        
    Example:
        execute_tdengine_query("SELECT * FROM cell_1 WHERE subtopic = 'glucose_mM' ORDER BY ts DESC LIMIT 5")
        execute_tdengine_query("SELECT AVG(reading) as avg_value FROM cell_1 WHERE subtopic = 'pH' AND ts >= '2024-01-01 00:00:00'")
    """
    try:
        logger.info(f"Executing TDengine query: {sql_query[:100]}...")
        result = tdengine_service.execute_query(sql_query)
        
        # Format result for agent consumption
        if result.get("code") == 0:
            data = result.get("data", [])
            columns = result.get("columns", [])
            
            # Format response with column names if available
            formatted_data = []
            for row in data:
                if columns:
                    row_dict = {columns[i]: row[i] for i in range(min(len(columns), len(row)))}
                    formatted_data.append(row_dict)
                else:
                    formatted_data.append(row)
            
            return json.dumps({
                "status": "success",
                "data": formatted_data,
                "row_count": len(data),
                "columns": columns if columns else []
            }, indent=2)
        else:
            error_msg = result.get("desc", "Unknown error")
            error_code = result.get("code", -1)
            logger.error(f"TDengine query error: {error_code} - {error_msg}")
            return json.dumps({
                "status": "error",
                "error": error_msg,
                "code": error_code
            }, indent=2)
    except Exception as e:
        logger.error(f"Exception executing TDengine query: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e)
        }, indent=2)

@tool("Get TDengine Schema Information")
def get_tdengine_schema(cell_ids: str) -> str:
    """
    Get TDengine database schema information for specific cell tables.
    This tool fetches table structure, columns, sensors, and metadata needed to generate SQL queries.
    
    Args:
        cell_ids: Comma-separated list of cell IDs (e.g., "cell_1,cell_4" or "cell_1, cell_4")
                 Can also accept formats like "cell 1,cell4" which will be normalized
    
    Returns:
        JSON string containing complete schema information including:
        - Database name
        - Table structures (CREATE TABLE statements)
        - Column details (name, type, length)
        - Available sensors per table
        - Sensor name mappings (@ references)
        - SQL query examples
    
    Example:
        get_tdengine_schema("cell_1,cell_4")
        get_tdengine_schema("cell 1, cell4")  # Will be normalized to cell_1,cell_4
    """
    try:
        import re
        
        # Normalize cell IDs
        cell_list = [c.strip() for c in cell_ids.split(',')]
        normalized_cells = []
        
        for cell_id in cell_list:
            # Handle formats: "cell 1" -> "cell_1", "cell4" -> "cell_4", "cell_1" -> "cell_1"
            if ' ' in cell_id:
                cell_id = cell_id.replace(' ', '_')
            if not cell_id.startswith('cell_'):
                match = re.search(r'\d+', cell_id)
                if match:
                    cell_id = f"cell_{match.group()}"
            normalized_cells.append(cell_id)
        
        logger.info(f"Fetching schema for cells: {normalized_cells}")
        
        schema_info = {
            "database": "rag",
            "tables": [],
            "sensor_mappings": tdengine_service.feature_mapping
        }
        
        for cell_id in normalized_cells:
            # Get CREATE TABLE statement
            create_result = tdengine_service.execute_query(f"SHOW CREATE TABLE {cell_id}")
            create_data = create_result.get("data", []) if create_result.get("code") == 0 else []
            
            # Get column details
            describe_result = tdengine_service.execute_query(f"DESCRIBE {cell_id}")
            describe_data = describe_result.get("data", []) if describe_result.get("code") == 0 else []
            
            # Get sensors
            sensors_result = tdengine_service.execute_query(
                f"SELECT DISTINCT subtopic, field_name, unit, sensor_type FROM {cell_id}"
            )
            sensors_data = sensors_result.get("data", []) if sensors_result.get("code") == 0 else []
            
            table_info = {
                "table_name": cell_id,
                "create_statement": create_data[0][1] if create_data and len(create_data[0]) > 1 else None,
                "columns": [
                    {
                        "name": row[0],
                        "type": row[1],
                        "length": row[2] if len(row) > 2 else None,
                        "note": row[3] if len(row) > 3 else None
                    }
                    for row in describe_data
                ],
                "sensors": [
                    {
                        "subtopic": row[0],
                        "field_name": row[1],
                        "unit": row[2],
                        "sensor_type": row[3]
                    }
                    for row in sensors_data
                ]
            }
            
            schema_info["tables"].append(table_info)
        
        # Format as context string for LLM
        context = f"""# TDengine Database Schema Information

## Database: {schema_info['database']}

## Available Tables (Cells):
{', '.join([t['table_name'] for t in schema_info['tables']])}

"""
        
        for table in schema_info["tables"]:
            context += f"""## Table: {table['table_name']}

### Table Structure:
```sql
{table['create_statement'] if table['create_statement'] else 'N/A'}
```

### Columns:
"""
            for col in table['columns']:
                col_info = f"- **{col['name']}**: {col['type']}"
                if col['length']:
                    col_info += f"({col['length']})"
                if col['note']:
                    col_info += f" - {col['note']}"
                context += col_info + "\n"
            
            context += f"\n### Available Sensors ({len(table['sensors'])} total):\n"
            for sensor in table['sensors']:
                context += f"- **{sensor['subtopic']}** ({sensor['field_name']}) - Unit: {sensor['unit']}, Type: {sensor['sensor_type']}\n"
            context += "\n"
        
        context += f"""## Sensor Name Mapping (@ references):
"""
        for key, value in schema_info['sensor_mappings'].items():
            context += f"- \"{key}\" → \"{value}\"\n"
        
        context += f"""
## SQL Query Principles:

### Database Structure:
- Primary timestamp column: `ts` (TIMESTAMP)
- Sensor identifier column: `subtopic` (VARCHAR)
- Value column: `reading` (DOUBLE)
- Table naming: cell_N format (e.g., cell_1, cell_2)

### Time Syntax:
- Relative periods: NOW() - 24h, NOW() - 7d, NOW() - 1w, NOW() - 30d (NOT INTERVAL syntax)
- Absolute dates: 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DDTHH:MM:SS.000Z'
- Always include time filtering in WHERE clause

### Query Optimization Principles (CRITICAL - Apply to ALL time periods):

1. **ALL Time Periods (including 24 hours):**
   - ALWAYS use SQL aggregation functions (AVG, STDDEV, MIN, MAX, PERCENTILE, COUNT) to calculate statistics directly
   - NEVER fetch raw data points - they can cause context overflow even for short periods with many data points
   - For trends: ALWAYS use INTERVAL grouping for time-based sampling (e.g., INTERVAL(10m) for 24h trends, INTERVAL(1h) for weekly trends, INTERVAL(1d) for monthly trends)
   - For statistical queries: Calculate statistics in SQL, return aggregated values only
   - For comparison queries: Use statistical aggregation per cell for comparison
   - For correlation queries: Use time-bucketing, return only correlation coefficient and statistics

3. **Multi-Cell Queries:**
   - For all-cell searches: FIRST execute "SHOW TABLES" to discover ALL available cell tables (don't assume cell_1 through cell_5)
   - Use UNION ALL to query ALL discovered cells in single query
   - Include cell_id in SELECT to identify source cell
   - Apply same filtering conditions uniformly across all cells
   - For "right now" or "current" queries: Use ORDER BY ts DESC LIMIT 1 per cell, and consider adding time filter (ts >= NOW() - 1h) to ensure readings are recent

4. **Correlation Queries (CRITICAL - ALL time periods):**
   - Sensors may have different timestamps - use time-bucketing with INTERVAL to align them
   - Use INTERVAL grouping to create time windows, then calculate correlation from aligned data
   - Filter out NULL values after bucketing
   - ALWAYS return ONLY correlation coefficient, covariance, and data_point_count - NEVER return raw or bucketed data points
   - This prevents context overflow even for short periods (24 hours) that may have thousands of data points

5. **Statistical Functions:**
   - Available: AVG, STDDEV, VAR, MIN, MAX, COUNT, SUM, PERCENTILE, FIRST, LAST
   - Correlation: Manual formula (AVG(x*y) - AVG(x)*AVG(y)) / (STDDEV(x) * STDDEV(y))

### Query Patterns:

- **Current Value:** ORDER BY ts DESC LIMIT 1
- **Historical Data:** Include time filtering, ORDER BY ts ASC
- **Aggregation:** Use AVG, STDDEV, MIN, MAX, PERCENTILE, COUNT for statistics
- **Time Sampling:** Use INTERVAL grouping for trend analysis over long periods
- **Multi-Cell:** Use UNION ALL with cell_id in SELECT
- **Filtering:** Apply WHERE conditions for sensor names, value thresholds, time ranges

"""
        
        return context
        
    except Exception as e:
        logger.error(f"Exception fetching TDengine schema: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e)
        }, indent=2)

