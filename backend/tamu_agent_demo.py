#!/usr/bin/env python3
"""
Standalone TAMUS AI CrewAI Agent Demo
A simple example showing CrewAI agent with TAMUS AI inference and 2 tools
"""

import os
from typing import Any, Dict
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
from dotenv import load_dotenv

# Load environment variables from backend/.env
load_dotenv(dotenv_path='.env')

# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

@tool
def calculator_tool(expression: str) -> str:
    """
    A simple calculator tool that can evaluate mathematical expressions.

    Args:
        expression: Mathematical expression to evaluate (e.g., "2 + 3 * 4")

    Returns:
        The result of the calculation as a string
    """
    try:
        # Use eval for simple calculations (in production, use a safer method)
        result = eval(expression)
        return f"The result of {expression} is {result}"
    except Exception as e:
        return f"Error calculating {expression}: {str(e)}"

@tool
def text_analyzer_tool(text: str) -> Dict[str, Any]:
    """
    Analyze text and return statistics.

    Args:
        text: Text to analyze

    Returns:
        Dictionary with text statistics
    """
    try:
        words = text.split()
        sentences = text.split('.')
        chars = len(text)

        analysis = {
            "word_count": len(words),
            "sentence_count": len([s for s in sentences if s.strip()]),
            "character_count": chars,
            "average_word_length": round(chars / len(words), 2) if words else 0,
            "text_preview": text[:100] + "..." if len(text) > 100 else text
        }

        return analysis
    except Exception as e:
        return {"error": f"Failed to analyze text: {str(e)}"}

# =============================================================================
# TAMUS AI LLM SETUP
# =============================================================================

from crewai.llm import LLM

class TAMUSAILLM(LLM):
    """Custom TAMUS AI LLM class that properly inherits from CrewAI's LLM"""

    def __init__(self, model="tamus/protected.gemini-2.0-flash-lite", temperature: float = 0.5, api_key=None, api_base=None, **kwargs):
        # Get configuration from environment or parameters FIRST
        self.custom_api_key = api_key or os.getenv('TAMUS_AI_CHAT_API_KEY')
        self.custom_base_url = api_base or os.getenv('TAMUS_AI_CHAT_API_ENDPOINT', 'https://chat-api.tamu.ai')
        self.custom_model_name = os.getenv('TAMUS_AI_MODEL', 'protected.gemini-2.0-flash-lite')

        if not self.custom_api_key:
            raise ValueError("TAMUS_AI_CHAT_API_KEY environment variable is required")

        # Initialize parent class with minimal required parameters
        # We'll override the call method to bypass LiteLLM
        super().__init__(
            model="gpt-3.5-turbo",  # Dummy model name for parent class
            temperature=temperature,
            **kwargs
        )

        print(f"🔧 Configuring TAMUS AI LLM:")
        print(f"   Model: {self.custom_model_name}")
        print(f"   Base URL: {self.custom_base_url}")
        print(f"   Temperature: {temperature}")

    def call(self, messages, **kwargs):
        """Override the parent call method to use TAMUS AI directly"""
        import requests

        headers = {
            "Authorization": f"Bearer {self.custom_api_key}",
            "Content-Type": "application/json"
        }

        # Ensure messages is in the right format
        if isinstance(messages, str):
            formatted_messages = [{"role": "user", "content": messages}]
        elif isinstance(messages, list):
            formatted_messages = messages
        else:
            formatted_messages = [{"role": "user", "content": str(messages)}]

        payload = {
            "model": self.custom_model_name,
            "stream": False,
            "messages": formatted_messages,
            "temperature": kwargs.get('temperature', self.temperature)
        }

        try:
            response = requests.post(
                f"{self.custom_base_url}/api/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()

                # Extract content from TAMUS AI response
                if 'choices' in result and len(result['choices']) > 0:
                    content = result['choices'][0]['message']['content']
                    return content
                else:
                    return "No response content received from TAMUS AI"
            else:
                error_msg = f"TAMUS AI API Error {response.status_code}: {response.text}"
                print(f"❌ {error_msg}")
                raise Exception(error_msg)

        except requests.RequestException as e:
            error_msg = f"TAMUS AI API request failed: {e}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"TAMUS AI API call failed: {e}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)

def create_tamus_llm(temperature: float = 0.5):
    """
    Create a TAMUS AI LLM instance that inherits from CrewAI's LLM class.

    Returns:
        TAMUSAILLM instance compatible with CrewAI
    """
    return TAMUSAILLM(temperature=temperature)

# =============================================================================
# AGENT AND CREW SETUP
# =============================================================================

def create_demo_agent(llm: LLM) -> Agent:
    """
    Create a demo agent with calculator and text analysis tools.

    Args:
        llm: The LLM instance to use

    Returns:
        Configured CrewAI agent
    """
    agent = Agent(
        role="Mathematical and Text Analysis Assistant",
        goal="Help users with calculations and text analysis tasks",
        backstory="You are an expert assistant skilled in mathematics and text analysis. "
                 "You can perform calculations and analyze text to provide insights.",
        tools=[calculator_tool, text_analyzer_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False
    )

    return agent

def create_demo_crew(agent: Agent, task: Task) -> Crew:
    """
    Create a demo crew with the agent and task.

    Args:
        agent: The agent to include in the crew
        task: The task to execute

    Returns:
        Configured CrewAI crew
    """
    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True
    )

    return crew

# =============================================================================
# DEMO TASKS
# =============================================================================

def run_calculation_demo(agent: Agent, llm: LLM) -> str:
    """
    Run a calculation demo task.

    Args:
        agent: The agent to execute the task
        llm: The LLM instance

    Returns:
        Task result
    """
    task = Task(
        description="Calculate the result of: (15 + 27) * 3 - 10, and explain the steps.",
        expected_output="A clear explanation of the calculation with the final result.",
        agent=agent
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True
    )

    print("\n🧮 Running Calculation Demo...")
    print("Task: Calculate the result of: (15 + 27) * 3 - 10, and explain the steps.")

    result = crew.kickoff()
    return str(result)

def run_text_analysis_demo(agent: Agent, llm: LLM) -> str:
    """
    Run a text analysis demo task.

    Args:
        agent: The agent to execute the task
        llm: The LLM instance

    Returns:
        Task result
    """
    task = Task(
        description="Analyze this text: 'The quick brown fox jumps over the lazy dog. "
                   "This sentence contains every letter of the English alphabet.' "
                   "Provide statistics and insights about the text.",
        expected_output="Detailed analysis including word count, statistics, and insights.",
        agent=agent
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True
    )

    print("\n📝 Running Text Analysis Demo...")
    print("Task: Analyze the pangram text and provide statistics.")

    result = crew.kickoff()
    return str(result)

def run_combined_demo(agent: Agent, llm: LLM) -> str:
    """
    Run a combined task that uses both tools.

    Args:
        agent: The agent to execute the task
        llm: The LLM instance

    Returns:
        Task result
    """
    task = Task(
        description="First, analyze this text: 'Python programming is powerful and versatile.' "
                   "Then calculate: word_count * 2 + character_count / 10. "
                   "Finally, explain what this combined calculation represents.",
        expected_output="Complete analysis including text stats, calculation result, and explanation.",
        agent=agent
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True
    )

    print("\n🔄 Running Combined Demo...")
    print("Task: Analyze text, perform calculation with results, and explain.")

    result = crew.kickoff()
    return str(result)

# =============================================================================
# MAIN DEMO
# =============================================================================

def main():
    """
    Main demo function - run all examples
    """
    print("🚀 TAMUS AI CrewAI Agent Demo")
    print("=" * 50)
    print("This demo shows a CrewAI agent using TAMUS AI as the LLM provider")
    print("with calculator and text analysis tools.")
    print()

    try:
        # 1. Check environment
        print("1️⃣ Checking environment configuration...")
        provider = os.getenv('LLM_PROVIDER', 'tamus')
        tamus_key = os.getenv('TAMUS_AI_CHAT_API_KEY')

        print(f"   LLM Provider: {provider}")
        print(f"   TAMUS AI Key: {'✅ Set' if tamus_key else '❌ Not set'}")

        if not tamus_key:
            print("\n❌ TAMUS_AI_CHAT_API_KEY not found in environment!")
            print("   Please set it in your .env file:")
            print("   TAMUS_AI_CHAT_API_KEY=your_api_key_here")
            return

        # 2. Create LLM
        print("\n2️⃣ Initializing TAMUS AI LLM...")
        llm = create_tamus_llm(temperature=0.7)

        # 3. Create agent
        print("\n3️⃣ Creating agent...")
        agent = create_demo_agent(llm)

        print("   ✅ Agent created with 2 tools: calculator, text_analyzer")

        # 4. Run demos
        print("\n4️⃣ Running demos...")

        # Demo 1: Calculation
        result1 = run_calculation_demo(agent, llm)
        print(f"Result: {result1[:200]}...")

        # Demo 2: Text Analysis
        result2 = run_text_analysis_demo(agent, llm)
        print(f"Result: {result2[:200]}...")

        # Demo 3: Combined
        result3 = run_combined_demo(agent, llm)
        print(f"Result: {result3[:200]}...")

        print("\n🎉 All demos completed successfully!")
        print("✅ TAMUS AI integration is working with CrewAI!")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
