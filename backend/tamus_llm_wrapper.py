"""
TAMUS AI LLM Wrapper
Wrapper for TAMUS AI OpenAI-compatible API to work with CrewAI
"""

import os
import logging
from typing import Optional, Dict, Any
from crewai import LLM
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class TAMUSAILLM(LLM):
    """TAMUS AI LLM wrapper for CrewAI integration"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.5,
        **kwargs
    ):
        """
        Initialize TAMUS AI LLM wrapper

        Args:
            api_key: TAMUS AI API key (defaults to TAMUS_AI_CHAT_API_KEY env var)
            base_url: Base URL for TAMUS AI API (defaults to TAMUS_AI_CHAT_API_ENDPOINT env var or https://chat-api.tamu.ai)
            model: Model name (defaults to TAMUS_AI_MODEL env var or protected.gemini-2.0-flash-lite)
            temperature: Temperature for generation
            **kwargs: Additional parameters for LLM
        """
        # Get configuration from environment variables
        self.api_key = api_key or os.getenv("TAMUS_AI_CHAT_API_KEY")
        self._base_url = base_url or os.getenv("TAMUS_AI_CHAT_API_ENDPOINT", "https://chat-api.tamu.ai")
        self.model = model or os.getenv("TAMUS_AI_MODEL", "protected.gemini-2.0-flash-lite")

        # Validate required configuration
        if not self.api_key:
            raise ValueError("TAMUS_AI_CHAT_API_KEY environment variable is required")

        logger.info(f"Initializing TAMUS AI LLM with model: {self.model}")
        logger.info(f"Using base URL: {self.base_url}")

        # Initialize CrewAI LLM with OpenAI-compatible format
        # Use LiteLLM's OpenAI support with custom base URL
        try:
            self.llm = LLM(
                model=f"openai/{self.model}",  # LiteLLM format for OpenAI-compatible APIs
                api_key=self.api_key,
                api_base=self.base_url,
                temperature=temperature,
                **kwargs
            )
            logger.info("TAMUS AI LLM initialized successfully with LiteLLM")
        except Exception as e:
            logger.warning(f"Failed to initialize TAMUS AI with LiteLLM: {e}")
            logger.info("TAMUS AI wrapper will use direct HTTP requests for calls")
            # Keep the wrapper alive but mark that LiteLLM failed
            self.llm = None

    def __call__(self, *args, **kwargs):
        """Make the wrapper callable like a CrewAI LLM"""
        return self.call(*args, **kwargs)

    def call(self, messages, **kwargs):
        """
        Call the TAMUS AI API directly if LiteLLM failed
        Compatible with CrewAI LLM interface
        """
        if self.llm is not None:
            # Use LiteLLM if available
            try:
                return self.llm.call(messages, **kwargs)
            except Exception as e:
                logger.warning(f"LiteLLM call failed: {e}, falling back to direct HTTP")

        # Fallback to direct HTTP requests
        return self._call_direct_http(messages, **kwargs)

    def _call_direct_http(self, messages, **kwargs):
        """
        Make direct HTTP request to TAMUS AI API
        """
        import requests

        try:
            url = f"{self.base_url}/api/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            data = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                **kwargs
            }

            logger.info(f"Making direct HTTP request to TAMUS AI: {url}")
            response = requests.post(url, headers=headers, json=data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                # Convert to CrewAI expected format
                return result["choices"][0]["message"]["content"]
            else:
                error_msg = f"TAMUS AI API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)

        except requests.exceptions.RequestException as e:
            error_msg = f"TAMUS AI connection failed: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)

    @property
    def model_name(self) -> str:
        """Get the model name"""
        return self.model

    @property
    def base_url(self) -> str:
        """Get the base URL"""
        return self._base_url

    def get_available_models(self) -> Dict[str, Any]:
        """
        Get available models from TAMUS AI API
        Returns list of available models
        """
        import requests

        try:
            response = requests.get(
                f"{self.base_url}/api/models",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get models: {response.status_code} - {response.text}")
                return {}
        except Exception as e:
            logger.error(f"Error getting available models: {e}")
            return {}

    def test_connection(self) -> bool:
        """
        Test connection to TAMUS AI API
        Returns True if connection is successful
        """
        try:
            # Try a simple chat completion
            response = self.call([
                {"role": "user", "content": "Hello, this is a test message."}
            ])

            if response and len(str(response).strip()) > 0:
                logger.info("TAMUS AI connection test successful")
                return True
            else:
                logger.error("TAMUS AI connection test failed - empty response")
                return False

        except Exception as e:
            logger.error(f"TAMUS AI connection test failed: {e}")
            return False


def create_tamus_llm(temperature: float = 0.5, **kwargs) -> LLM:
    """
    Factory function to create TAMUS AI LLM instance

    Args:
        temperature: Temperature for generation
        **kwargs: Additional parameters

    Returns:
        CrewAI LLM instance configured for TAMUS AI
    """
    wrapper = TAMUSAILLM(temperature=temperature, **kwargs)
    # Return the wrapper itself if llm is None, otherwise return the llm
    return wrapper if wrapper.llm is None else wrapper.llm
