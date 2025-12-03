"""
Vector Search Tool for CrewAI

Tool for searching domain knowledge documents using semantic similarity
with hierarchical affiliation-based search.

Search Behavior:
- When NO filters provided: Searches ALL documents using semantic similarity (recommended)
- When filters provided: Uses hierarchical search (sensor → equipment → general)

Results include page numbers and affiliation levels for context.
"""
import sys
import os
import json
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

# Add parent directory to path to import vectorstore_service
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crewai.tools import tool
from vectorstore_service import vector_store
import logging

logger = logging.getLogger(__name__)

# Thread pool for running async code from sync context
_executor = ThreadPoolExecutor(max_workers=2)

# Global project_id set by crew.py before query processing
_current_project_id: Optional[str] = None


def _run_async_search(query: str, project_id: str, equipment_id: Optional[str], 
                      sensor_type: Optional[str], limit: int):
    """Run the async search in a separate thread with its own event loop"""
    import asyncio
    
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            vector_store.search_similar(
                query=query,
                project_id=project_id,
                equipment_id=equipment_id,
                sensor_type=sensor_type,
                limit=limit
            )
        )
        return result
    finally:
        loop.close()


@tool("Search Domain Knowledge Documents")
def search_domain_knowledge(query: str) -> str:
    """
    Search through domain knowledge documents using semantic similarity.
    The project_id is automatically determined from the current context.
    
    Call this tool with ONLY the query text. Include all relevant keywords from the user's question.
    
    Examples:
    - search_domain_knowledge("flowmeter accuracy specifications")
    - search_domain_knowledge("calibration test lines wafer cone")
    - search_domain_knowledge("maintenance procedure compressor")

    Args:
        query: The search query text - include ALL relevant keywords from user's question

    Returns:
        JSON string containing search results with document chunks, similarity scores, and metadata
    """
    global _current_project_id
    
    # Use the project_id from context
    project_id = _current_project_id
    
    # Default values for optional parameters
    equipment_id = None
    sensor_type = None
    limit = 5
    
    if not project_id:
        return json.dumps({
            "status": "error",
            "query": query,
            "error": "No project context available. Please ensure you're in a project.",
            "message": "Failed to search domain knowledge documents."
        }, indent=2)
    
    try:
        logger.info(f"Searching domain knowledge: '{query}' (project: {project_id})")

        # Run async search in a separate thread to avoid event loop conflicts
        future = _executor.submit(_run_async_search, query, project_id, equipment_id, sensor_type, limit)
        results = future.result(timeout=60)  # 60 second timeout

        # Format results for agent consumption
        if not results:
            return json.dumps({
                "status": "success",
                "query": query,
                "project_id": project_id,
                "total_documents": 0,
                "results": [],
                "message": "No relevant documents found. The user may need to upload documentation for this topic."
            }, indent=2)

        # Group results by document for better readability
        documents = {}
        for result in results:
            doc_id = result['metadata']['doc_id']
            filename = result.get('filename') or result['metadata'].get('filename')

            if doc_id not in documents:
                documents[doc_id] = {
                    "filename": filename,
                    "equipment_id": result.get('equipment_id'),
                    "sensor_type": result.get('sensor_type'),
                    "document_type": result.get('document_type'),
                    "affiliation_level": result.get('affiliation_level', 'general'),
                    "chunks": []
                }

            # Include page number and element type in chunk info
            chunk_info = {
                "content": result['content'][:500] + "..." if len(result['content']) > 500 else result['content'],
                "similarity_score": round(result['similarity_score'], 4),
                "chunk_index": result['metadata'].get('chunk_index')
            }
            
            # Add page number if available
            page_number = result.get('page_number') or result['metadata'].get('page_number')
            if page_number is not None:
                chunk_info["page_number"] = page_number
            
            # Add element type if available
            element_type = result.get('element_type') or result['metadata'].get('element_type')
            if element_type:
                chunk_info["element_type"] = element_type

            documents[doc_id]["chunks"].append(chunk_info)

        # Convert to list format and sort by affiliation priority
        affiliation_priority = {'sensor': 0, 'equipment': 1, 'general': 2}
        document_list = []
        
        for doc_id, doc_data in documents.items():
            # Sort chunks by similarity score (highest first)
            doc_data["chunks"].sort(key=lambda x: x["similarity_score"], reverse=True)
            document_list.append(doc_data)
        
        # Sort documents by affiliation level priority
        document_list.sort(key=lambda x: affiliation_priority.get(x.get('affiliation_level', 'general'), 2))

        return json.dumps({
            "status": "success",
            "query": query,
            "project_id": project_id,
            "total_documents": len(document_list),
            "results": document_list,
            "instructions": "Use the most relevant chunks to answer user questions. Higher similarity scores indicate better matches."
        }, indent=2)

    except Exception as e:
        logger.error(f"Error searching domain knowledge: {e}")
        return json.dumps({
            "status": "error",
            "query": query,
            "project_id": project_id,
            "error": str(e),
            "message": "Failed to search domain knowledge documents."
        }, indent=2)
