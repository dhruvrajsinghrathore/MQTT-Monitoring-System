#!/usr/bin/env python3
"""
Adaptive Schema Learner for MQTT Workflow Subscriber

This module provides universal parsing of MQTT messages to automatically
extract displayable information from any topic pattern and payload structure.
The goal is to intelligently determine what should be displayed on a node
without any hardcoded assumptions about field names or structures.
"""

import re
import json
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime

logger = logging.getLogger(__name__)

class AdaptiveSchemaLearner:
    """
    Universal MQTT message parser that intelligently extracts displayable information
    from any message structure. Focuses on what humans would want to see on a monitoring node.
    """
    
    def __init__(self):
        self.message_history = {}  # Track patterns over time
        self.confidence_boost_per_occurrence = 0.1
        
    def analyze_message(self, payload: Dict[str, Any], topic: str) -> Dict[str, Any]:
        """
        Universal analysis of any MQTT message structure.
        
        Returns a standardized display format that can be shown on any node,
        regardless of the original message structure.
        """
        try:
            # Parse topic to extract hierarchical information
            topic_info = self._parse_topic_hierarchy(topic)
            
            # Analyze payload structure to extract meaningful data
            payload_info = self._analyze_payload_structure(payload)
            
            # Combine and create a displayable result
            result = self._create_display_format(topic_info, payload_info, payload, topic)
            
            # Track this pattern for future learning
            self._track_message_pattern(topic, payload, result)
            
            logger.debug(f"Universal analysis: {topic} -> {result['equipment_id']}/{result['sensor_type']}")
            return result
            
        except Exception as e:
            logger.error(f"Error in universal message analysis: {e}")
            return self._create_fallback_result(topic, payload)

    def _parse_topic_hierarchy(self, topic: str) -> Dict[str, Any]:
        """
        Parse topic hierarchy to understand the organizational structure.
        Works with any topic pattern by analyzing the hierarchical relationships.
        """
        parts = topic.split('/')
        
        return {
            'parts': parts,
            'depth': len(parts),
            'last_part': parts[-1] if parts else 'unknown',
            'second_last': parts[-2] if len(parts) > 1 else None,
            'root': parts[0] if parts else 'unknown',
            'hierarchy': '/'.join(parts[:-1]) if len(parts) > 1 else '',
            'leaf': parts[-1] if parts else 'unknown'
        }

    def _analyze_payload_structure(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze payload structure to understand what information is available.
        Uses intelligent heuristics rather than hardcoded field names.
        """
        structure = {
            'fields': list(payload.keys()),
            'field_count': len(payload),
            'numeric_fields': {},
            'string_fields': {},
            'datetime_fields': {},
            'object_fields': {},
            'array_fields': {},
            'main_value_candidates': [],
            'identifier_candidates': [],
            'description_candidates': []
        }
        
        for key, value in payload.items():
            # Categorize by data type
            if isinstance(value, (int, float)):
                structure['numeric_fields'][key] = value
                # Numeric fields are often the main values to display
                if not self._looks_like_id_or_timestamp(key, value):
                    structure['main_value_candidates'].append({
                        'key': key, 'value': value, 'score': self._score_as_main_value(key, value)
                    })
            elif isinstance(value, str):
                structure['string_fields'][key] = value
                if self._looks_like_identifier(key, value):
                    structure['identifier_candidates'].append({
                        'key': key, 'value': value, 'score': self._score_as_identifier(key, value)
                    })
                elif self._looks_like_datetime(value):
                    structure['datetime_fields'][key] = value
                else:
                    structure['description_candidates'].append({
                        'key': key, 'value': value, 'score': self._score_as_description(key, value)
                    })
            elif isinstance(value, dict):
                structure['object_fields'][key] = value
            elif isinstance(value, list):
                structure['array_fields'][key] = value
        
        # Sort candidates by score
        structure['main_value_candidates'].sort(key=lambda x: x['score'], reverse=True)
        structure['identifier_candidates'].sort(key=lambda x: x['score'], reverse=True)
        structure['description_candidates'].sort(key=lambda x: x['score'], reverse=True)
        
        return structure

    def _create_display_format(self, topic_info: Dict[str, Any], 
                             payload_info: Dict[str, Any], 
                             payload: Dict[str, Any], 
                             topic: str) -> Dict[str, Any]:
        """
        Create a standardized display format from the analyzed information.
        This is what will be shown on the monitoring node.
        """
        
        # 1. Determine equipment_id (what device/entity this represents)
        equipment_id = self._determine_equipment_id(topic_info, payload_info, payload)
        
        # 2. Determine sensor_type (what aspect/measurement this represents)
        sensor_type = self._determine_sensor_type(topic_info, payload_info, payload)
        
        # 3. Extract the main value to display
        main_value = self._extract_main_value(payload_info, payload)
        
        # 4. Determine status/health
        status = self._determine_status(payload_info, payload, main_value)
        
        # 5. Extract any additional metadata
        metadata = self._extract_metadata(payload_info, payload)
        
        # 6. Calculate confidence in our parsing
        confidence = self._calculate_confidence(topic_info, payload_info, equipment_id, sensor_type)
        
        return {
            'equipment_id': equipment_id,
            'sensor_type': sensor_type,
            'value': main_value,
            'status': status,
            'confidence': confidence,
            'timestamp': self._extract_timestamp(payload),
            'topic': topic,
            'metadata': metadata,
            'raw_payload': payload,
            'unit': metadata.get('unit', ''),
            'display_name': f"{equipment_id} {sensor_type}".strip()
        }

    def _determine_equipment_id(self, topic_info: Dict[str, Any], 
                               payload_info: Dict[str, Any], 
                               payload: Dict[str, Any]) -> str:
        """
        Intelligently determine what equipment/device this message represents.
        """
        # Priority 1: Look for numeric IDs in topic combined with type
        parts = topic_info['parts']
        if len(parts) >= 2:
            # Check for patterns like: equipment_type/id, type/id/measurement
            for i in range(len(parts) - 1):
                if self._looks_like_identifier_in_topic(parts[i+1]):
                    equipment_type = parts[i]
                    equipment_id = parts[i+1]
                    return f"{equipment_type}_{equipment_id}"
        
        # Priority 2: Look for identifier-like fields in payload
        if payload_info['identifier_candidates']:
            best_id = payload_info['identifier_candidates'][0]
            # If we have numeric ID in payload, combine with topic root
            if isinstance(best_id['value'], (int, str)) and str(best_id['value']).isdigit():
                return f"{topic_info['root']}_{best_id['value']}"
            else:
                return str(best_id['value'])
        
        # Priority 3: Use topic hierarchy
        if len(parts) >= 2:
            return f"{parts[0]}_{parts[1]}"
        elif len(parts) == 1:
            return parts[0]
        
        # Fallback: generate from available data
        return topic_info['root'] or 'device_unknown'

    def _determine_sensor_type(self, topic_info: Dict[str, Any], 
                             payload_info: Dict[str, Any], 
                             payload: Dict[str, Any]) -> str:
        """
        Intelligently determine what type of measurement/sensor this represents.
        """
        # For cell/1/temperature pattern, always use the last part
        parts = topic_info['parts']
        if len(parts) == 3 and parts[0] == 'cell':
            return parts[2]  # Always use the measurement name
        
        # Priority 1: Last part of topic (most specific)
        leaf = topic_info['leaf']
        if leaf and not self._looks_like_identifier_in_topic(leaf):
            return leaf
        
        # Priority 2: Second to last part if last part looks like an ID
        if topic_info['second_last'] and self._looks_like_identifier_in_topic(leaf):
            return topic_info['second_last']
        
        # Priority 3: Look for descriptive string fields in payload
        if payload_info['description_candidates']:
            best_desc = payload_info['description_candidates'][0]
            return str(best_desc['value'])
        
        # Priority 4: Use the field name of the main value
        if payload_info['main_value_candidates']:
            return payload_info['main_value_candidates'][0]['key']
        
        # Fallback
        return 'sensor'

    def _extract_main_value(self, payload_info: Dict[str, Any], payload: Dict[str, Any]) -> Any:
        """
        Extract the main value that should be displayed prominently.
        """
        # Priority 1: Best scoring numeric value
        if payload_info['main_value_candidates']:
            return payload_info['main_value_candidates'][0]['value']
        
        # Priority 2: Any numeric value
        if payload_info['numeric_fields']:
            return list(payload_info['numeric_fields'].values())[0]
        
        # Priority 3: String values (but not identifiers or timestamps)
        non_id_strings = [v for k, v in payload_info['string_fields'].items() 
                         if not self._looks_like_identifier(k, v) and not self._looks_like_datetime(v)]
        if non_id_strings:
            return non_id_strings[0]
        
        # Fallback: first available value
        if payload:
            return list(payload.values())[0]
        
        return None

    def _determine_status(self, payload_info: Dict[str, Any], payload: Dict[str, Any], main_value: Any) -> str:
        """
        Intelligently determine the status/health of the equipment.
        """
        # Look for explicit status-like fields
        for key, value in payload_info['string_fields'].items():
            if any(indicator in key.lower() for indicator in ['status', 'state', 'health', 'condition']):
                return str(value)
        
        # Infer status from main value if it's numeric
        if isinstance(main_value, (int, float)):
            if main_value < 0:
                return 'error'
            elif main_value == 0:
                return 'idle'
            else:
                return 'active'
        
        return 'unknown'

    def _extract_metadata(self, payload_info: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract additional metadata that might be useful for display.
        """
        metadata = {}
        
        # Look for unit information
        for key, value in payload.items():
            if 'unit' in key.lower():
                metadata['unit'] = str(value)
                break
        
        # Look for min/max values
        for key, value in payload.items():
            if 'min' in key.lower() and isinstance(value, (int, float)):
                metadata['min_value'] = value
            elif 'max' in key.lower() and isinstance(value, (int, float)):
                metadata['max_value'] = value
        
        # Include any object fields as metadata
        metadata.update(payload_info['object_fields'])
        
        return metadata

    def _extract_timestamp(self, payload: Dict[str, Any]) -> str:
        """
        Extract timestamp from payload, with fallback to current time.
        """
        # Look for timestamp-like fields
        for key, value in payload.items():
            if any(indicator in key.lower() for indicator in ['time', 'stamp', 'date']):
                if isinstance(value, str) and self._looks_like_datetime(value):
                    return value
        
        # Fallback to current time
        return datetime.now().isoformat()

    def _calculate_confidence(self, topic_info: Dict[str, Any], 
                            payload_info: Dict[str, Any], 
                            equipment_id: str, 
                            sensor_type: str) -> float:
        """
        Calculate confidence in our parsing based on various factors.
        """
        confidence = 0.5  # Base confidence
        
        # Boost confidence based on topic structure
        if topic_info['depth'] >= 3:
            confidence += 0.2
        elif topic_info['depth'] == 2:
            confidence += 0.1
        
        # Boost confidence based on payload richness
        if payload_info['field_count'] >= 3:
            confidence += 0.1
        if payload_info['main_value_candidates']:
            confidence += 0.1
        if payload_info['identifier_candidates']:
            confidence += 0.1
        
        # Penalize if we had to use fallbacks
        if equipment_id == 'device_unknown':
            confidence -= 0.2
        if sensor_type == 'sensor':
            confidence -= 0.1
        
        return min(1.0, max(0.1, confidence))

    # Helper methods for intelligent analysis
    def _looks_like_identifier(self, key: str, value: Any) -> bool:
        """Check if a field looks like an identifier."""
        key_lower = key.lower()
        id_indicators = ['id', 'device', 'equipment', 'node', 'unit', 'machine']
        has_id_indicator = any(indicator in key_lower for indicator in id_indicators)
        
        # Check value characteristics
        if isinstance(value, str):
            # Short alphanumeric strings often IDs
            is_short_alphanum = len(value) <= 20 and (value.isalnum() or '_' in value)
            return has_id_indicator or is_short_alphanum
        elif isinstance(value, (int, float)):
            return has_id_indicator
        
        return False

    def _looks_like_identifier_in_topic(self, part: str) -> bool:
        """Check if a topic part looks like an identifier."""
        if not part:
            return False
        # Numeric or short alphanumeric = likely ID
        return part.isdigit() or (len(part) <= 10 and part.replace('_', '').isalnum())

    def _looks_like_datetime(self, value: str) -> bool:
        """Check if a string value looks like a datetime."""
        if not isinstance(value, str):
            return False
        # Simple heuristics for datetime strings
        datetime_indicators = ['T', 'Z', ':', '-', '+']
        return len(value) > 10 and any(indicator in value for indicator in datetime_indicators)

    def _looks_like_id_or_timestamp(self, key: str, value: Any) -> bool:
        """Check if this field is likely an ID or timestamp (not a main value)."""
        key_lower = key.lower()
        exclude_indicators = ['id', 'time', 'stamp', 'date', 'count', 'index']
        return any(indicator in key_lower for indicator in exclude_indicators)

    def _score_as_main_value(self, key: str, value: Any) -> float:
        """Score how likely this field is to be the main display value."""
        score = 0.5
        key_lower = key.lower()
        
        # Boost for value-like field names
        value_indicators = ['value', 'reading', 'measurement', 'level', 'amount', 'temperature', 'pressure']
        if any(indicator in key_lower for indicator in value_indicators):
            score += 0.3
        
        # Boost for reasonable numeric ranges
        if isinstance(value, (int, float)):
            if -1000 <= value <= 10000:  # Reasonable sensor range
                score += 0.2
        
        return score

    def _score_as_identifier(self, key: str, value: Any) -> float:
        """Score how likely this field is to be an identifier."""
        score = 0.3
        key_lower = key.lower()
        
        id_indicators = ['id', 'device', 'equipment', 'node', 'unit']
        if any(indicator in key_lower for indicator in id_indicators):
            score += 0.4
        
        if isinstance(value, str) and len(value) <= 20:
            score += 0.2
        
        return score

    def _score_as_description(self, key: str, value: Any) -> float:
        """Score how likely this field is to be a description/type."""
        score = 0.2
        key_lower = key.lower()
        
        desc_indicators = ['type', 'kind', 'category', 'class', 'name']
        if any(indicator in key_lower for indicator in desc_indicators):
            score += 0.3
        
        return score

    def _track_message_pattern(self, topic: str, payload: Dict[str, Any], result: Dict[str, Any]):
        """Track message patterns for learning (future enhancement)."""
        # This could be used to improve parsing over time
        pass

    def _create_fallback_result(self, topic: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a basic fallback result when analysis fails."""
        return {
            'equipment_id': topic.split('/')[0] if '/' in topic else 'unknown',
            'sensor_type': topic.split('/')[-1] if '/' in topic else 'sensor',
            'value': list(payload.values())[0] if payload else None,
            'status': 'unknown',
            'confidence': 0.1,
            'timestamp': datetime.now().isoformat(),
            'topic': topic,
            'metadata': {},
            'raw_payload': payload,
            'unit': '',
            'display_name': 'Unknown Device'
        } 