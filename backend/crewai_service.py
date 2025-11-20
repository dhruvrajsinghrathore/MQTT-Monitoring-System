"""
CrewAI Service Wrapper
Wrapper for integrating CrewAI with FastAPI endpoint
"""
import logging
from typing import Optional, List
from crew import get_chatbot_crew

logger = logging.getLogger(__name__)

class CrewAIService:
    """Service wrapper for CrewAI crew"""
    
    def __init__(self):
        self.crew = None
        logger.info("CrewAI Service initialized")
    
    def _get_crew(self):
        """Lazy load crew instance"""
        if self.crew is None:
            try:
                self.crew = get_chatbot_crew()
                logger.info("CrewAI crew loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load CrewAI crew: {e}")
                raise
        return self.crew
    
    async def process_query(
        self,
        user_query: str,
        page_type: str = "monitor",
        cell_id: Optional[str] = None,
        references: Optional[List[str]] = None
    ) -> str:
        """
        Process user query using CrewAI
        
        Args:
            user_query: User's natural language query
            page_type: 'monitor' or 'equipment'
            cell_id: Optional cell_id if on equipment page
            references: List of @references from frontend
        
        Returns:
            Natural language response string
        """
        try:
            crew = self._get_crew()
            response = crew.process_query(
                user_query=user_query,
                page_type=page_type,
                cell_id=cell_id,
                references=references or []
            )
            return response
        except Exception as e:
            logger.error(f"Error in CrewAI workflow: {e}")
            raise

# Global instance
crewai_service = CrewAIService()

