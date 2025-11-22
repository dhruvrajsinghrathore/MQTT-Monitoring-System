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
from tools.vector_search_tool import search_domain_knowledge
from tdengine_service import tdengine_service
from tamu_agent_demo import TAMUSAILLM

# Load environment variables from project root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatbotCrew:
    """CrewAI crew for processing chatbot queries"""
    
    def __init__(self):
        """Initialize the crew with agents and tasks"""
        try:
            # Initialize LLM using provider switching
            self.llm = self._create_llm(temperature=0.5)
            
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

    def _create_llm(self, temperature: float = 0.5) -> LLM:
        """
        Create LLM instance based on LLM_PROVIDER environment variable

        Args:
            temperature: Temperature for generation

        Returns:
            CrewAI LLM instance
        """
        provider = os.getenv("LLM_PROVIDER", "tamus").lower()

        if provider == "tamus":
            # Use TAMUS AI with custom LLM class
            try:
                logger.info("Initializing TAMUS AI LLM...")
                return TAMUSAILLM(temperature=temperature)
            except Exception as e:
                logger.error(f"Failed to initialize TAMUS AI LLM: {e}")
                logger.warning("Falling back to Gemini...")
                provider = "gemini"

        if provider == "gemini":
            # Use Gemini API - prioritize GEMINI_API_KEY, fallback to GROQ_API_KEY
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                logger.warning("GEMINI_API_KEY not found in environment variables")
                # Fallback to GROQ_API_KEY
                api_key = os.getenv("GROQ_API_KEY")
                if api_key:
                    logger.warning("Using GROQ_API_KEY as fallback. Please set GEMINI_API_KEY for Gemini models.")
                    model_name = "groq/llama-3.3-70b-versatile"
                else:
                    raise ValueError("Neither GEMINI_API_KEY nor GROQ_API_KEY found in environment variables")
            else:
                # Use Gemini 2.5 Flash (different model from 2.5-pro, haven't tried this yet)
                model_name = "gemini/gemini-2.5-flash"

            logger.info(f"Initializing Gemini LLM with model: {model_name}")
            return LLM(
                model=model_name,
                api_key=api_key,
                temperature=temperature
            )

        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}. Supported: tamus, gemini")

    def _create_agents(self) -> dict:
        """Create agents from configuration"""
        agents = {}
        
        for agent_key, config in self.agents_config.items():
            try:
                # Get LLM for this agent (with specific temperature if provided)
                temperature = config.get('temperature', 0.5)
                agent_llm = self._create_llm(temperature=temperature)
                
                # Prepare tools
                tools = []
                if 'tools' in config:
                    for tool_name in config['tools']:
                        if tool_name == 'execute_tdengine_query':
                            tools.append(execute_tdengine_query)
                        elif tool_name == 'get_tdengine_schema':
                            tools.append(get_tdengine_schema)
                        elif tool_name == 'search_domain_knowledge':
                            tools.append(search_domain_knowledge)
                
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
            
            # Execute crew with retry logic for rate limits
            logger.info(f"Processing query with CrewAI: {user_query[:100]}...")
            
            import time
            import re
            max_retries = 3
            retry_delay = 20  # Start with 20 seconds
            
            for attempt in range(max_retries):
                try:
                    result = query_crew.kickoff()
                    # Extract final response (from Agent 2)
                    response = str(result)
                    logger.info(f"CrewAI response generated successfully")
                    return response
                except Exception as e:
                    error_str = str(e)
                    # Check if it's a rate limit error (Groq or Gemini)
                    if "429" in error_str or "rate_limit" in error_str.lower() or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
                        if attempt < max_retries - 1:
                            # Extract retry delay from error if available
                            if "try again in" in error_str.lower():
                                try:
                                    delay_match = re.search(r'try again in ([\d.]+)s', error_str.lower())
                                    if delay_match:
                                        retry_delay = float(delay_match.group(1)) + 5  # Add 5 seconds buffer
                                except:
                                    pass
                            
                            logger.warning(f"Rate limit exceeded (attempt {attempt + 1}/{max_retries}). Retrying in {retry_delay:.1f} seconds...")
                            time.sleep(retry_delay)
                            retry_delay *= 1.5  # Exponential backoff (less aggressive than before)
                            continue
                        else:
                            logger.error(f"Rate limit exceeded after {max_retries} attempts")
                            raise Exception(
                                "I apologize, but the AI service is currently experiencing rate limitations. "
                                "Please try again in a few minutes. "
                                "If this persists, you may need to upgrade your API plan or wait for the rate limit to reset."
                            )
                    else:
                        # Not a rate limit error, raise immediately
                        raise
            
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

