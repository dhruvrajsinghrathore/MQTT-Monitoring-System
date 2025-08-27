#!/usr/bin/env python3
"""
Debug script to test equipment discovery logic
"""

import sys
import json
from pathlib import Path

# Add the Scenario_2 directory to Python path
scenario_2_path = Path(__file__).parent.parent / "Scenario_2"
sys.path.append(str(scenario_2_path))

from dynamic_workflow_subscriber import AdaptiveSchemaLearner

def test_equipment_detection():
    """Test equipment detection with sample messages from workflow publisher"""
    
    schema_learner = AdaptiveSchemaLearner()
    
    # Sample messages that the workflow publisher would send
    test_messages = [
        {
            "topic": "lab/furnace/temperature",
            "data": {
                "equipment_id": "furnace_01",
                "timestamp": "2024-01-01T10:00:00Z",
                "type": "temperature",
                "value": 850.5,
                "unit": "celsius",
                "status": "heating",
                "workflow_step": "heating"
            }
        },
        {
            "topic": "lab/melter/temperature", 
            "data": {
                "equipment_id": "melter_01",
                "timestamp": "2024-01-01T10:00:00Z",
                "type": "temperature",
                "value": 1200.0,
                "unit": "celsius",
                "status": "melting",
                "workflow_step": "melting"
            }
        },
        {
            "topic": "lab/anvil/force",
            "data": {
                "equipment_id": "anvil_01",
                "timestamp": "2024-01-01T10:00:00Z", 
                "type": "force",
                "value": 2500.0,
                "unit": "newtons",
                "status": "positioning",
                "workflow_step": "positioning"
            }
        },
        {
            "topic": "lab/conveyor/speed",
            "data": {
                "equipment_id": "conveyor_01",
                "timestamp": "2024-01-01T10:00:00Z",
                "type": "speed", 
                "value": 1.5,
                "unit": "m/s",
                "status": "transporting",
                "workflow_step": "transporting"
            }
        },
        {
            "topic": "lab/conveyor/position",
            "data": {
                "equipment_id": "conveyor_01",
                "timestamp": "2024-01-01T10:00:00Z",
                "type": "position",
                "value": 45.0,
                "unit": "degrees", 
                "status": "transporting",
                "workflow_step": "transporting"
            }
        }
    ]
    
    print("🧪 Testing Equipment Discovery Logic")
    print("=" * 50)
    
    discovered_equipment = {}
    
    for test_case in test_messages:
        topic = test_case["topic"]
        data = test_case["data"]
        
        print(f"\n📡 Processing: {topic}")
        print(f"   Data: {json.dumps(data, indent=6)}")
        
        # Use the schema learner to extract equipment info
        extracted = schema_learner.analyze_message(data, topic)
        equipment_id = extracted.get('equipment_id', 'unknown')
        
        print(f"   Extracted equipment_id: {equipment_id}")
        print(f"   Extracted sensor_type: {extracted.get('sensor_type', 'unknown')}")
        print(f"   Extracted value: {extracted.get('value', 'unknown')}")
        
        if equipment_id != 'unknown':
            if equipment_id not in discovered_equipment:
                discovered_equipment[equipment_id] = {
                    'id': equipment_id,
                    'equipment_id': equipment_id,
                    'equipment_type': extracted.get('sensor_type', 'unknown'),
                    'topics': [topic],
                    'sample_data': data,
                    'message_count': 1
                }
                print(f"   ✅ NEW equipment discovered: {equipment_id}")
            else:
                discovered_equipment[equipment_id]['message_count'] += 1
                if topic not in discovered_equipment[equipment_id]['topics']:
                    discovered_equipment[equipment_id]['topics'].append(topic)
                print(f"   ⚡ Updated existing equipment: {equipment_id}")
        else:
            print(f"   ❌ Failed to extract equipment_id")
    
    print(f"\n🎯 Discovery Results:")
    print("=" * 50)
    print(f"Total equipment discovered: {len(discovered_equipment)}")
    
    for equipment_id, details in discovered_equipment.items():
        print(f"\n📋 {equipment_id}:")
        print(f"   - Type: {details['equipment_type']}")
        print(f"   - Topics: {details['topics']}")
        print(f"   - Messages: {details['message_count']}")
    
    if len(discovered_equipment) < 4:
        print(f"\n⚠️  Expected 4 equipment, but only found {len(discovered_equipment)}")
        missing = set(['furnace_01', 'melter_01', 'anvil_01', 'conveyor_01']) - set(discovered_equipment.keys())
        if missing:
            print(f"   Missing: {', '.join(missing)}")
    else:
        print(f"\n✅ All 4 equipment detected successfully!")

if __name__ == "__main__":
    test_equipment_detection() 