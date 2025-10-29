#!/usr/bin/env python3
"""
Gemini LLM Service for MQTT Chatbot
Provides intelligent responses based on real-time TDengine data
"""

import json
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from dotenv import load_dotenv
from tdengine_service import tdengine_service

# Load environment variables
load_dotenv()

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
        
        # Initialize TDengine service for real-time data
        self.tdengine = tdengine_service
        
        # Debug logging
        available_cells = self.tdengine.get_available_cells()
        logger.info(f"TDengine connection established. Available cells: {available_cells}")
        
        logger.info("Gemini LLM Service initialized with TDengine integration")
    
    def _build_monitor_context(self, user_query: str = "", references: List[str] = None) -> str:
        """Build context for monitor page queries - SIMPLIFIED VERSION"""
        available_cells = self.tdengine.get_available_cells()
        
        # Extract query parameters
        query_cell_ids = self.tdengine.extract_cell_ids_from_query(user_query)
        referenced_features = self.tdengine.extract_referenced_features(user_query, references or [])
        time_range = self.tdengine.extract_time_range_from_query(user_query)
        
        context = ""
        
        # SIMPLE HISTORICAL DATA DETECTION
        is_trend_query = any(word in user_query.lower() for word in ['trend', 'pattern', 'day', 'week', 'month', 'past', 'ago', 'over time', 'change'])
        
        if is_trend_query and referenced_features and query_cell_ids:
            # Handle multiple cells for comparison
            if len(query_cell_ids) > 1:
                # Multi-cell comparison
                context += f"HISTORICAL TREND COMPARISON:\n"
                for cell_id in query_cell_ids:
                    sensor_name = referenced_features[0]  # Use first sensor for now
                    trend_summary = self.tdengine.get_simple_trend_summary(cell_id, sensor_name, time_range)
                    
                    if trend_summary.get("status") == "success":
                        context += f"\n{cell_id.upper()}:\n"
                        context += f"- Sensor: {trend_summary['sensor_name']}\n"
                        context += f"- Time Period: {trend_summary['time_range']}\n"
                        context += f"- Data Points: {trend_summary['data_points']}\n"
                        context += f"- Start Value: {trend_summary['first_value']} {trend_summary['unit']}\n"
                        context += f"- End Value: {trend_summary['last_value']} {trend_summary['unit']}\n"
                        context += f"- Min Value: {trend_summary['min_value']} {trend_summary['unit']}\n"
                        context += f"- Max Value: {trend_summary['max_value']} {trend_summary['unit']}\n"
                        context += f"- Average Value: {trend_summary['avg_value']} {trend_summary['unit']}\n"
                        context += f"- Trend: {trend_summary['trend_direction']}\n"
                        context += f"- Change: {trend_summary['change_percent']}%\n"
                        context += f"- Period: {trend_summary['start_time']} to {trend_summary['end_time']}\n"
                    elif trend_summary.get("status") == "insufficient_data":
                        context += f"\n{cell_id.upper()}: Only 1 data point available for {sensor_name} in {time_range}\n"
                    elif trend_summary.get("status") == "no_data":
                        context += f"\n{cell_id.upper()}: No data found for {sensor_name} in {time_range}\n"
                context += "\n"
            else:
                # Single cell analysis
                cell_id = query_cell_ids[0]
                sensor_name = referenced_features[0]
                
                trend_summary = self.tdengine.get_simple_trend_summary(cell_id, sensor_name, time_range)
                
                if trend_summary.get("status") == "success":
                    context += f"HISTORICAL TREND ANALYSIS:\n"
                    context += f"Cell: {trend_summary['cell_id']}\n"
                    context += f"Sensor: {trend_summary['sensor_name']}\n"
                    context += f"Time Period: {trend_summary['time_range']}\n"
                    context += f"Data Points: {trend_summary['data_points']}\n"
                    context += f"Start Value: {trend_summary['first_value']} {trend_summary['unit']}\n"
                    context += f"End Value: {trend_summary['last_value']} {trend_summary['unit']}\n"
                    context += f"Min Value: {trend_summary['min_value']} {trend_summary['unit']}\n"
                    context += f"Max Value: {trend_summary['max_value']} {trend_summary['unit']}\n"
                    context += f"Average Value: {trend_summary['avg_value']} {trend_summary['unit']}\n"
                    context += f"Trend: {trend_summary['trend_direction']}\n"
                    context += f"Change: {trend_summary['change_percent']}%\n"
                    context += f"Period: {trend_summary['start_time']} to {trend_summary['end_time']}\n\n"
                elif trend_summary.get("status") == "insufficient_data":
                    context += f"HISTORICAL DATA: Only 1 data point available for {cell_id} {sensor_name} in {time_range}\n\n"
                elif trend_summary.get("status") == "no_data":
                    context += f"HISTORICAL DATA: No data found for {cell_id} {sensor_name} in {time_range}\n\n"
        
        # Add current real-time data
        context += f"CURRENT REAL-TIME DATA:\n"
        if query_cell_ids:
            if len(query_cell_ids) > 1:
                # Multi-cell current data
                for cell_id in query_cell_ids:
                    latest_data = self.tdengine.get_latest_readings(cell_id)
                    if latest_data and latest_data.get('sensors'):
                        context += f"\n{cell_id.upper()}:\n"
                        if referenced_features:
                            for sensor_name in referenced_features:
                                if sensor_name in latest_data['sensors']:
                                    sensor_data = latest_data['sensors'][sensor_name]
                                    context += f"- {sensor_name}: {sensor_data['value']} {sensor_data['unit']}\n"
                        else:
                            for sensor_name, sensor_data in latest_data['sensors'].items():
                                context += f"- {sensor_name}: {sensor_data['value']} {sensor_data['unit']}\n"
            else:
                # Single cell current data
                cell_id = query_cell_ids[0]
                latest_data = self.tdengine.get_latest_readings(cell_id)
                if latest_data and latest_data.get('sensors'):
                    context += f"Cell: {cell_id}\n"
                    if referenced_features:
                        for sensor_name in referenced_features:
                            if sensor_name in latest_data['sensors']:
                                sensor_data = latest_data['sensors'][sensor_name]
                                context += f"- {sensor_name}: {sensor_data['value']} {sensor_data['unit']}\n"
                    else:
                        for sensor_name, sensor_data in latest_data['sensors'].items():
                            context += f"- {sensor_name}: {sensor_data['value']} {sensor_data['unit']}\n"
        else:
            context += "No specific cell mentioned in query\n"
        
        return context
    
    def _build_equipment_context(self, cell_id: str) -> str:
        """Build context for equipment detail page queries using real-time TDengine data"""
        # Get real-time data from TDengine
        cell_data = self.tdengine.get_latest_readings(cell_id)
        
        if not cell_data:
            return f"No real-time data found for {cell_id}"
        
        context = f"""
# {cell_id.upper()} Equipment Detail Context

## Cell Information
- Status: {cell_data.get('status', 'Unknown')}
- Last Updated: {cell_data.get('last_updated', 'Unknown')}

## Current Sensor Readings (Real-time)
"""
        
        sensors = cell_data.get('sensors', {})
        for sensor_name, sensor_data in sensors.items():
            context += f"""
### {sensor_name}
- Current Value: {sensor_data.get('value')} {sensor_data.get('unit')}
- Range: {sensor_data.get('min_val')} - {sensor_data.get('max_val')}
- Unit: {sensor_data.get('unit')}
- Sensor Type: {sensor_data.get('sensor_type', 'Unknown')}
- Status: {sensor_data.get('status', 'Unknown')}
- Timestamp: {sensor_data.get('timestamp', 'Unknown')}
"""
        
        context += f"""
## Notes
- All data is retrieved from TDengine database in real-time
- Data is collected from active sensors
"""
        
        return context
    
    def _build_prompt(self, user_query: str, page_type: str, cell_id: Optional[str] = None, references: List[str] = None) -> str:
        """Build the complete prompt for Gemini - SIMPLIFIED VERSION"""
        
        if page_type == "monitor":
            context = self._build_monitor_context(user_query, references)
        elif page_type == "equipment" and cell_id:
            context = self._build_equipment_context(cell_id)
        else:
            context = self._build_monitor_context(user_query, references)
        
        # ULTRA SIMPLIFIED PROMPT - Put historical data first
        prompt = f"""Answer this question: {user_query}

HISTORICAL DATA AVAILABLE:
{context}

ANSWER:"""
        
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
    
    async def process_query(self, user_query: str, page_type: str, cell_id: Optional[str] = None, references: List[str] = None) -> str:
        """Process user query and return AI response"""
        try:
            # Check if model is available
            if self.model is None:
                return "I apologize, but the AI service is currently unavailable. Please check the system configuration and try again later."
            
            # Build the prompt (now includes references)
            prompt = self._build_prompt(user_query, page_type, cell_id, references or [])
            
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
        """Get list of available cell IDs from TDengine"""
        return self.tdengine.get_available_cells()
    
    def get_cell_status(self, cell_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific cell from TDengine"""
        return self.tdengine.get_latest_readings(cell_id)
    
    def refresh_data(self):
        """Refresh cell data from TDengine (no-op since we query real-time)"""
        logger.info("TDengine data is queried in real-time - no refresh needed")

# Global instance
llm_service = GeminiLLMService()
