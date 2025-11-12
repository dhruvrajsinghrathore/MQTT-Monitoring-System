"""
CrewAI Crew for MQTT Chatbot
Orchestrates multi-agent workflow for query processing
"""
import yaml
import os
import sys
import logging
from typing import Optional, List
from crewai import Agent, Task, Crew, Process, LLM
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.tdengine_tool import execute_tdengine_query, get_tdengine_schema
from tdengine_service import tdengine_service

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatbotCrew:
    """CrewAI crew for processing chatbot queries"""
    
    def __init__(self):
        """Initialize the crew with agents and tasks"""
        try:
            # Initialize LLM using CrewAI's LLM class (works with LiteLLM)
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                logger.warning("GEMINI_API_KEY not found in environment variables")
                api_key = "your_gemini_api_key_here"  # Fallback for testing
            
            # Use gemini-pro-latest (confirmed working with actual API calls)
            model_name = "gemini/gemini-pro-latest"
            self.llm = LLM(
                model=model_name,
                api_key=api_key,
                temperature=0.5
            )
            logger.info(f"Initialized LLM with model: {model_name}")
            
            # Load configurations
            self._load_configs()
            
            # Create agents
            self.agents = self._create_agents()
            
            # Create tasks
            self.tasks = self._create_tasks()
            
            # Create crew
            self.crew = Crew(
                agents=list(self.agents.values()),
                tasks=self.tasks,
                process=Process.sequential,  # Sequential execution: Agent 1 → Agent 2
                verbose=True
            )
            
            logger.info("ChatbotCrew initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ChatbotCrew: {e}")
            raise
    
    def _load_configs(self):
        """Load agent and task configurations from YAML files"""
        config_dir = os.path.join(os.path.dirname(__file__), 'config')
        
        agents_path = os.path.join(config_dir, 'agents.yaml')
        tasks_path = os.path.join(config_dir, 'tasks.yaml')
        
        if not os.path.exists(agents_path):
            raise FileNotFoundError(f"Agents config not found: {agents_path}")
        if not os.path.exists(tasks_path):
            raise FileNotFoundError(f"Tasks config not found: {tasks_path}")
        
        with open(agents_path, 'r') as f:
            self.agents_config = yaml.safe_load(f)
        
        with open(tasks_path, 'r') as f:
            self.tasks_config = yaml.safe_load(f)
    def _create_agents(self) -> dict:
        """Create agents from configuration"""
        agents = {}
        
        for agent_key, config in self.agents_config.items():
            try:
                # Get LLM for this agent (with specific temperature if provided)
                temperature = config.get('temperature', 0.5)
                # Use gemini-pro-latest (confirmed working with actual API calls)
                agent_llm = LLM(
                    model="gemini/gemini-pro-latest",
                    api_key=os.getenv("GEMINI_API_KEY", "your_gemini_api_key_here"),
                    temperature=temperature
                )
                
                # Prepare tools
                tools = []
                if 'tools' in config:
                    for tool_name in config['tools']:
                        if tool_name == 'execute_tdengine_query':
                            tools.append(execute_tdengine_query)
                        elif tool_name == 'get_tdengine_schema':
                            tools.append(get_tdengine_schema)
                
                # Create agent
                agent = Agent(
                    role=config['role'],
                    goal=config['goal'],
                    backstory=config['backstory'],
                    tools=tools,
                    verbose=config.get('verbose', False),
                    llm=agent_llm,
                    allow_delegation=False
                )
                
                agents[agent_key] = agent
                logger.info(f"Created agent: {agent_key}")
            except Exception as e:
                logger.error(f"Error creating agent {agent_key}: {e}")
                raise
        
        return agents
    
    def _create_tasks(self) -> list:
        """Create tasks from configuration"""
        tasks = []
        
        for task_key, config in self.tasks_config.items():
            try:
                # Find corresponding agent
                agent_name = task_key.replace('_task', '_agent')
                agent = self.agents.get(agent_name)
                
                if not agent:
                    raise ValueError(f"Agent '{agent_name}' not found for task '{task_key}'")
                
                # Create task
                task = Task(
                    description=config['description'],
                    expected_output=config['expected_output'],
                    agent=agent
                )
                
                tasks.append(task)
                logger.info(f"Created task: {task_key}")
            except Exception as e:
                logger.error(f"Error creating task {task_key}: {e}")
                raise
        
        return tasks
    
    def process_query(
        self, 
        user_query: str,
        page_type: str = "monitor",
        cell_id: Optional[str] = None,
        references: Optional[List[str]] = None
    ) -> str:
        """
        Process user query using CrewAI workflow
        
        Args:
            user_query: User's natural language query
            page_type: 'monitor' or 'equipment'
            cell_id: Optional cell_id if on equipment page
            references: List of @references from frontend
        
        Returns:
            Natural language response string
        """
        references = references or []
        
        try:
            # Build context for the query
            context_info = f"""
Page Type: {page_type}
Cell ID (if on equipment page): {cell_id or "N/A (monitor page)"}
@References: {', '.join(references) if references else "None"}
"""
            
            # Build full context string for first task
            full_context = f"""
User Query: "{user_query}"

Context:
{context_info}

IMPORTANT: 
- If @references are provided, use them to map to sensor subtopic names
- If no @references but sensors are mentioned in query, discover them from database schema
- Handle any query type: correlations, statistics, trends, comparisons, custom date ranges, filtering
- Generate appropriate SQL queries based on the query intent
"""
            
            # Create new tasks with updated descriptions for this specific query
            # We need to recreate tasks with the query-specific context
            data_extraction_task = Task(
                description=f"{full_context}\n\n{self.tasks_config['data_extraction_task']['description']}",
                expected_output=self.tasks_config['data_extraction_task']['expected_output'],
                agent=self.agents['data_extraction_agent']
            )
            
            response_generation_task = Task(
                description=f"Original User Query: \"{user_query}\"\n\n{self.tasks_config['response_generation_task']['description']}",
                expected_output=self.tasks_config['response_generation_task']['expected_output'],
                agent=self.agents['response_generation_agent']
            )
            
            # Create a temporary crew for this query
            query_crew = Crew(
                agents=list(self.agents.values()),
                tasks=[data_extraction_task, response_generation_task],
                process=Process.sequential,
                verbose=True
            )
            
            # Execute crew
            logger.info(f"Processing query with CrewAI: {user_query[:100]}...")
            result = query_crew.kickoff()
            
            # Extract final response (from Agent 2)
            response = str(result)
            logger.info(f"CrewAI response generated successfully")
            return response
            
        except Exception as e:
            logger.error(f"Error processing query with CrewAI: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

# Global instance (lazy initialization)
_chatbot_crew_instance = None

def get_chatbot_crew() -> ChatbotCrew:
    """Get or create global ChatbotCrew instance"""
    global _chatbot_crew_instance
    if _chatbot_crew_instance is None:
        _chatbot_crew_instance = ChatbotCrew()
    return _chatbot_crew_instance

