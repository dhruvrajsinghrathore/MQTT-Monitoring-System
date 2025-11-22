"""
Vector Search Tool for CrewAI
Tool for searching domain knowledge documents using vector similarity
"""
import sys
import os
import re
import json
from typing import Optional

# Add parent directory to path to import vectorstore_service
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crewai.tools import tool
from vectorstore_service import vector_store
import logging

logger = logging.getLogger(__name__)

def _extract_sensor_type_from_query(query: str) -> Optional[str]:
    """
    Extract sensor type from user query.
    Looks for common sensor types mentioned in queries.
    """
    sensor_patterns = {
        r'\btemperature\b': 'temperature',
        r'\btemp\b': 'temperature',
        r'\bthermocouple\b': 'temperature',
        r'\bthermostat\b': 'temperature',
        r'\bthermo\b': 'temperature',
        r'\bheat\b': 'temperature',

        r'\bpH\b': 'pH',
        r'\bacidity\b': 'pH',
        r'\balkalinity\b': 'pH',

        r'\bpressure\b': 'pressure',
        r'\bpsi\b': 'pressure',
        r'\bbar\b': 'pressure',
        r'\bkpa\b': 'pressure',

        r'\bconductivity\b': 'conductivity',
        r'\bconductance\b': 'conductivity',
        r'\bec\b': 'conductivity',

        r'\bdissolved oxygen\b': 'dissolved_oxygen',
        r'\bDO\b': 'dissolved_oxygen',
        r'\boxygen\b': 'dissolved_oxygen',

        r'\bturbidity\b': 'turbidity',
        r'\bntu\b': 'turbidity',

        r'\bflow\b': 'flow',
        r'\bflow rate\b': 'flow_rate',
        r'\bvelocity\b': 'flow',

        r'\blevel\b': 'level',
        r'\bheight\b': 'level',
        r'\bdepth\b': 'level',

        r'\bglucose\b': 'glucose',
        r'\bsugar\b': 'glucose',
        r'\bconcentration\b': 'glucose',

        r'\bvibration\b': 'vibration',
        r'\baccelerometer\b': 'vibration',
        r'\baccel\b': 'vibration'
    }

    query_lower = query.lower()

    # Check for explicit sensor mentions
    for pattern, sensor_type in sensor_patterns.items():
        if re.search(pattern, query_lower):
            return sensor_type

    return None

@tool("Search Domain Knowledge Documents")
def search_domain_knowledge(query: str, project_id: str, equipment_id: Optional[str] = None,
                           sensor_type: Optional[str] = None, limit: int = 5) -> str:
    """
    Search through domain knowledge documents using semantic similarity.
    This tool allows agents to find relevant documentation, manuals, specifications,
    and other knowledge resources related to sensors, equipment, and processes.

    Args:
        query: The search query text (e.g., "temperature sensor calibration", "pH meter maintenance")
        project_id: The project ID to search within
        equipment_id: Optional equipment ID to filter results (e.g., "cell_1", "melter_01")
        sensor_type: Optional sensor type to filter results (e.g., "temperature", "pH", "pressure")
        limit: Maximum number of results to return (default: 5)

    Returns:
        JSON string containing search results with document chunks, similarity scores, and metadata

    Examples:
        search_domain_knowledge("temperature sensor calibration", "project123", "cell_1", "temperature", 3)
        search_domain_knowledge("pH meter maintenance procedure", "project123", None, "pH", 5)
        search_domain_knowledge("flow sensor specifications", "project123", "pump_01", None, 2)
    """
    try:
        logger.info(f"Searching domain knowledge: '{query}' (project: {project_id}, equipment: {equipment_id}, sensor: {sensor_type})")

        # If sensor_type is not explicitly provided, try to extract it from the query
        if not sensor_type:
            extracted_sensor_type = _extract_sensor_type_from_query(query)
            if extracted_sensor_type:
                sensor_type = extracted_sensor_type
                logger.info(f"Extracted sensor type from query: {sensor_type}")

        # Perform the search
        results = vector_store.search_similar(
            query=query,
            project_id=project_id,
            equipment_id=equipment_id,
            sensor_type=sensor_type,
            limit=limit
        )

        # Format results for agent consumption
        if not results:
            return json.dumps({
                "status": "success",
                "query": query,
                "total_results": 0,
                "results": [],
                "message": "No relevant documents found. Consider uploading relevant documentation."
            }, indent=2)

        # Group results by document for better readability
        documents = {}
        for result in results:
            doc_id = result['metadata']['doc_id']
            filename = result['metadata']['filename']

            if doc_id not in documents:
                documents[doc_id] = {
                    "filename": filename,
                    "equipment_id": result['metadata'].get('equipment_id'),
                    "sensor_type": result['metadata'].get('sensor_type'),
                    "document_type": result['metadata'].get('document_type'),
                    "chunks": []
                }

            documents[doc_id]["chunks"].append({
                "content": result['content'][:500] + "..." if len(result['content']) > 500 else result['content'],
                "similarity_score": result['similarity_score'],
                "chunk_index": result['metadata']['chunk_index']
            })

        # Convert to list format
        document_list = []
        for doc_id, doc_data in documents.items():
            # Sort chunks by similarity score (highest first)
            doc_data["chunks"].sort(key=lambda x: x["similarity_score"], reverse=True)
            document_list.append(doc_data)

        return json.dumps({
            "status": "success",
            "query": query,
            "sensor_type_used": sensor_type,
            "equipment_id_used": equipment_id,
            "total_documents": len(document_list),
            "results": document_list,
            "instructions": "Use the most relevant chunks to answer user questions. Higher similarity scores indicate better matches."
        }, indent=2)

    except Exception as e:
        logger.error(f"Error searching domain knowledge: {e}")
        return json.dumps({
            "status": "error",
            "query": query,
            "error": str(e),
            "message": "Failed to search domain knowledge documents."
        }, indent=2)
