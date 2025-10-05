#!/usr/bin/env python3
"""
Gemini LLM Service for MQTT Chatbot
Provides intelligent responses based on cell data and context
"""

import json
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GeminiLLMService:
    """Service for interacting with Gemini AI for MQTT chatbot responses"""
    
    def __init__(self):
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not found in environment variables")
            self.api_key = "your_gemini_api_key_here"  # Fallback for testing
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        
        # Try different model names in order of preference
        model_names = ['gemini-2.0-flash-exp', 'gemini-1.5-pro', 'gemini-1.5-flash']
        self.model = None
        
        for model_name in model_names:
            try:
                self.model = genai.GenerativeModel(model_name)
                logger.info(f"Successfully initialized Gemini model: {model_name}")
                break
            except Exception as e:
                logger.warning(f"Failed to initialize model {model_name}: {e}")
                continue
        
        if self.model is None:
            logger.error("Failed to initialize any Gemini model")
        
        # Load cell data
        self.cell_readings = self._load_cell_readings()
        self.cell_details = self._load_cell_details()
        
        # Debug logging
        logger.info(f"Loaded {len(self.cell_readings.get('cells', {}))} cells from readings")
        logger.info(f"Loaded {len(self.cell_details.get('cells', {}))} cells from details")
        
        logger.info("Gemini LLM Service initialized")
    
    def _load_cell_readings(self) -> Dict[str, Any]:
        """Load current cell readings from JSON file"""
        try:
            # Get the directory where this script is located
            script_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(script_dir, 'data', 'cell_readings.json')
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load cell readings: {e}")
            return {}
    
    def _load_cell_details(self) -> Dict[str, Any]:
        """Load cell details from JSON file"""
        try:
            # Get the directory where this script is located
            script_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(script_dir, 'data', 'cell_details.json')
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load cell details: {e}")
            return {}
    
    def _build_monitor_context(self) -> str:
        """Build context for monitor page queries"""
        context = f"""
# MQTT Cell Monitoring System Context

## Project Information
- Project: {self.cell_details.get('project_name', 'Unknown')}
- Description: {self.cell_details.get('description', 'Unknown')}
- Timestamp: {self.cell_readings.get('timestamp', 'Unknown')}

## Active Cells Overview
"""
        
        for cell_id, cell_data in self.cell_readings.get('cells', {}).items():
            cell_info = self.cell_details.get('cells', {}).get(cell_id, {})
            context += f"""
### {cell_id.upper()}
- Name: {cell_info.get('name', 'Unknown')}
- Status: {cell_data.get('status', 'Unknown')}
- Location: {cell_info.get('location', 'Unknown')}
- Last Updated: {cell_data.get('last_updated', 'Unknown')}

#### Current Sensor Readings:
"""
            for sensor_name, sensor_data in cell_data.get('sensors', {}).items():
                sensor_desc = self.cell_details.get('sensor_descriptions', {}).get(sensor_name, {})
                context += f"- {sensor_desc.get('name', sensor_name)}: {sensor_data.get('value')} {sensor_data.get('unit')} (Range: {sensor_data.get('min_val')}-{sensor_data.get('max_val')})\n"
        
        context += """
## Sensor Descriptions
"""
        for sensor_name, sensor_info in self.cell_details.get('sensor_descriptions', {}).items():
            context += f"""
- {sensor_info.get('name', sensor_name)}: {sensor_info.get('description', 'No description')}
  - Unit: {sensor_info.get('unit', 'Unknown')}
  - Normal Range: {sensor_info.get('normal_range', 'Unknown')}
  - Measurement Method: {sensor_info.get('measurement_method', 'Unknown')}
"""
        
        return context
    
    def _build_equipment_context(self, cell_id: str) -> str:
        """Build context for equipment detail page queries"""
        cell_data = self.cell_readings.get('cells', {}).get(cell_id, {})
        cell_info = self.cell_details.get('cells', {}).get(cell_id, {})
        
        if not cell_data:
            return f"No data found for {cell_id}"
        
        context = f"""
# {cell_id.upper()} Equipment Detail Context

## Cell Information
- Name: {cell_info.get('name', 'Unknown')}
- Description: {cell_info.get('description', 'Unknown')}
- Status: {cell_data.get('status', 'Unknown')}
- Location: {cell_info.get('location', 'Unknown')}
- Last Updated: {cell_data.get('last_updated', 'Unknown')}
- Last Maintenance: {cell_info.get('last_maintenance', 'Unknown')}

## Current Sensor Readings
"""
        
        for sensor_name, sensor_data in cell_data.get('sensors', {}).items():
            sensor_desc = self.cell_details.get('sensor_descriptions', {}).get(sensor_name, {})
            context += f"""
### {sensor_desc.get('name', sensor_name)}
- Current Value: {sensor_data.get('value')} {sensor_data.get('unit')}
- Range: {sensor_data.get('min_val')} - {sensor_data.get('max_val')}
- Normal Range: {sensor_desc.get('normal_range', 'Unknown')}
- Status: {sensor_data.get('status', 'Unknown')}
- Timestamp: {sensor_data.get('timestamp', 'Unknown')}
- Description: {sensor_desc.get('description', 'No description')}
- Measurement Method: {sensor_desc.get('measurement_method', 'Unknown')}
"""
        
        context += f"""
## Operational Ranges
{json.dumps(cell_info.get('operational_ranges', {}), indent=2)}

## Alert Thresholds
Critical Alerts: {', '.join(cell_info.get('alerts', {}).get('critical', []))}
Warning Alerts: {', '.join(cell_info.get('alerts', {}).get('warning', []))}
"""
        
        return context
    
    def _build_prompt(self, user_query: str, page_type: str, cell_id: Optional[str] = None) -> str:
        """Build the complete prompt for Gemini"""
        
        if page_type == "monitor":
            context = self._build_monitor_context()
            page_context = "monitoring dashboard showing all active cells"
        elif page_type == "equipment" and cell_id:
            context = self._build_equipment_context(cell_id)
            page_context = f"equipment detail page for {cell_id}"
        else:
            context = self._build_monitor_context()
            page_context = "monitoring dashboard"
        
        prompt = f"""
You are an AI assistant for an MQTT-based cell monitoring system. You help users understand their cell culture data, sensor readings, and system status.

## Current Context
You are currently on the {page_context}. Here's the relevant data:

{context}

## User Query
{user_query}

## Instructions
1. Provide a helpful, accurate response based on the data above
2. If asked about specific cells or sensors, reference the actual values
3. If values are outside normal ranges, mention this
4. If asked about trends, explain that this is current data (historical trends would need additional data)
5. Be conversational but informative
6. If you don't have enough information, say so
7. Focus on the biological/technical significance of the readings
8. **FORMATTING: Use simple, clean formatting like a normal chat response:**
   - Use headings with CAPS (e.g., "CELL STATUS SUMMARY:")
   - Use cell names like "CELL1:" or "CELL2:" for each cell section
   - Use property names like "Status:", "Location:", "Sensor Readings:" for subsections
   - **IMPORTANT: Add line breaks between each piece of information**
   - **IMPORTANT: Format sensor readings as "Sensor Name: value unit (range)" on separate lines**
   - Keep it simple and readable like a normal chat response
   - **CRITICAL: NO markdown symbols like #, **, *, or any special formatting characters**
   - **CRITICAL: NO bold text, NO asterisks, NO hashtags - just clean text with line breaks**

## Response Guidelines
- Use clear, professional language
- Include specific values when relevant
- Explain what the readings mean biologically
- Suggest actions if there are concerning values
- Keep responses concise but comprehensive
"""
        
        return prompt
    
    def _clean_markdown(self, text: str) -> str:
        """Clean up any markdown formatting that might slip through"""
        # Remove markdown bold formatting
        text = text.replace('**', '')
        text = text.replace('*', '')
        
        # Remove markdown headers
        text = text.replace('#', '')
        
        # Remove any remaining markdown symbols
        text = text.replace('`', '')
        text = text.replace('_', '')
        
        # Clean up extra spaces
        text = ' '.join(text.split())
        
        return text
    
    async def process_query(self, user_query: str, page_type: str, cell_id: Optional[str] = None) -> str:
        """Process user query and return AI response"""
        try:
            # Check if model is available
            if self.model is None:
                return "I apologize, but the AI service is currently unavailable. Please check the system configuration and try again later."
            
            # Build the prompt
            prompt = self._build_prompt(user_query, page_type, cell_id)
            
            # Configure safety settings
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            
            # Generate response
            response = self.model.generate_content(
                prompt,
                safety_settings=safety_settings,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    top_p=0.8,
                    top_k=40,
                    max_output_tokens=1024,
                )
            )
            
            # Clean up any markdown that might slip through
            cleaned_response = self._clean_markdown(response.text)
            return cleaned_response
            
        except Exception as e:
            logger.error(f"Error processing query with Gemini: {e}")
            return f"I apologize, but I encountered an error processing your query: {str(e)}. Please try again or check the system status."
    
    def get_available_cells(self) -> List[str]:
        """Get list of available cell IDs"""
        return list(self.cell_readings.get('cells', {}).keys())
    
    def get_cell_status(self, cell_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific cell"""
        return self.cell_readings.get('cells', {}).get(cell_id)
    
    def refresh_data(self):
        """Refresh cell data from JSON files"""
        self.cell_readings = self._load_cell_readings()
        self.cell_details = self._load_cell_details()
        logger.info("Cell data refreshed")

# Global instance
llm_service = GeminiLLMService()
