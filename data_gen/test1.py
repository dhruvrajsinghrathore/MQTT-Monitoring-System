#!/usr/bin/env python3
"""
MQTT Workflow Publisher - Test Equipment Simulator
Simulates various lab equipment sending workflow status messages
"""

import json
import time
import random
from datetime import datetime
import paho.mqtt.client as mqtt
import threading
from mqtt_client_helper import create_mqtt_client

# MQTT Configuration
MQTT_BROKER = "cloud.dtkit.org"
MQTT_PORT = 1883

# Equipment configurations
EQUIPMENT_CONFIG = {
    "furnace_01": {
        "topics": ["lab/furnace/temperature", "lab/furnace/pressure", "lab/furnace/composition"],
        "workflow_steps": ["idle", "heating", "melting", "composition_analysis", "cooling"]
    },
    "melter_01": {
        "topics": ["lab/melter/temperature", "lab/melter/flow_rate"],
        "workflow_steps": ["idle", "preheating", "melting", "pouring", "cleaning"]
    },
    "anvil_01": {
        "topics": ["lab/anvil/force", "lab/anvil/position"],
        "workflow_steps": ["idle", "positioning", "forging", "shaping", "finishing"]
    },
    "conveyor_01": {
        "topics": ["lab/conveyor/speed", "lab/conveyor/position"],
        "workflow_steps": ["idle", "loading", "transporting", "unloading"]
    }
}

class WorkflowPublisher:
    def __init__(self):
        self.client = None
        self.running = False
        self.equipment_states = {}
        
        # Initialize equipment states
        for equipment_id in EQUIPMENT_CONFIG.keys():
            self.equipment_states[equipment_id] = {
                "current_step": 0,
                "status": "normal",
                "last_update": datetime.now()
            }
    
    def connect_mqtt(self):
        """Connect to MQTT broker"""
        try:
            client_id = f'workflow-publisher-{random.randint(0, 1000)}'
            self.client = create_mqtt_client(client_id=client_id)
            self.client.on_connect = self.on_connect
            self.client.on_disconnect = self.on_disconnect
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()
            return True
        except Exception as e:
            print(f"❌ Failed to connect to MQTT broker: {e}")
            return False
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"🔗 Workflow Publisher connected to {MQTT_BROKER}:{MQTT_PORT}")
            self.running = True
        else:
            print(f"❌ Failed to connect, return code {rc}")
    
    def on_disconnect(self, client, userdata, rc):
        print("🔌 Disconnected from MQTT broker")
        self.running = False
    
    def generate_sensor_data(self, equipment_id, topic, workflow_step):
        """Generate realistic sensor data based on equipment and workflow step"""
        equipment_type = topic.split('/')[-1]  # temperature, pressure, force, etc.
        
        if equipment_type == "temperature":
            if workflow_step in ["heating", "melting"]:
                value = random.uniform(800, 1600)
                status = "active"
            elif workflow_step == "cooling":
                value = random.uniform(200, 500)
                status = "active"
            else:
                value = random.uniform(20, 100)
                status = "idle" if workflow_step == "idle" else "normal"
                
        elif equipment_type == "pressure":
            if workflow_step in ["melting", "pouring"]:
                value = random.uniform(2.0, 5.0)
                status = "active"
            else:
                value = random.uniform(0.8, 1.2)
                status = "idle" if workflow_step == "idle" else "normal"
                
        elif equipment_type == "force":
            if workflow_step in ["forging", "shaping"]:
                value = random.uniform(1000, 5000)
                status = "active"
            elif workflow_step == "positioning":
                value = random.uniform(100, 300)
                status = "active"
            else:
                value = random.uniform(0, 50)
                status = "idle" if workflow_step == "idle" else "normal"
                
        elif equipment_type == "flow_rate":
            if workflow_step == "pouring":
                value = random.uniform(5.0, 15.0)
                status = "active"
            else:
                value = random.uniform(0, 1.0)
                status = "idle" if workflow_step == "idle" else "normal"
                
        elif equipment_type == "speed":
            if workflow_step in ["loading", "transporting", "unloading"]:
                value = random.uniform(0.5, 2.0)
                status = "active"
            else:
                value = 0.0
                status = "idle"
                
        elif equipment_type == "position":
            value = random.uniform(0, 100)
            status = "active" if workflow_step != "idle" else "idle"
            
        elif equipment_type == "composition":
            # Special case for composition analysis
            value = {
                "Al": round(random.uniform(10, 20), 2),
                "Fe": round(random.uniform(15, 25), 2),
                "Cr": round(random.uniform(18, 22), 2),
                "Ni": round(random.uniform(20, 30), 2),
                "Co": round(random.uniform(15, 25), 2)
            }
            status = "analysis_complete" if workflow_step == "composition_analysis" else "normal"
        else:
            value = random.uniform(0, 100)
            status = "normal"
        
        return value, status
    
    def publish_equipment_data(self, equipment_id):
        """Publish data for a specific piece of equipment"""
        config = EQUIPMENT_CONFIG[equipment_id]
        state = self.equipment_states[equipment_id]
        
        # Get current workflow step
        workflow_steps = config["workflow_steps"]
        current_step_name = workflow_steps[state["current_step"]]
        
        # Publish data for each topic
        for topic in config["topics"]:
            value, status = self.generate_sensor_data(equipment_id, topic, current_step_name)
            
            # Determine unit based on sensor type
            sensor_type = topic.split('/')[-1]
            unit_map = {
                "temperature": "celsius",
                "pressure": "atm", 
                "force": "newtons",
                "flow_rate": "L/min",
                "speed": "m/s",
                "position": "degrees",
                "composition": "atomic_percent"
            }
            
            message = {
                "equipment_id": equipment_id,
                "timestamp": datetime.now().isoformat() + "Z",
                "type": sensor_type,
                "value": value,
                "unit": unit_map.get(sensor_type, "unknown"),
                "status": status,
                "workflow_step": current_step_name
            }
            
            try:
                result = self.client.publish(topic, json.dumps(message))
                if result[0] == 0:
                    print(f"📡 {equipment_id} → {topic}: {current_step_name} ({status})")
                else:
                    print(f"❌ Failed to publish to {topic}")
            except Exception as e:
                print(f"❌ Error publishing {topic}: {e}")
        
        # Progress workflow step (sometimes)
        if random.random() < 0.3:  # 30% chance to progress
            state["current_step"] = (state["current_step"] + 1) % len(workflow_steps)
            if state["current_step"] == 0:
                print(f"🔄 {equipment_id} completed full workflow cycle")
    
    def publish_all_equipment(self):
        """Publish data for all equipment"""
        for equipment_id in EQUIPMENT_CONFIG.keys():
            self.publish_equipment_data(equipment_id)
    
    def run_publisher(self, interval=5):
        """Run the publisher with specified interval"""
        print(f"🚀 Starting workflow publisher (interval: {interval}s)")
        print(f"📊 Equipment: {list(EQUIPMENT_CONFIG.keys())}")
        print("🔥 Publishing workflow data...")
        print("Press Ctrl+C to stop\n")
        
        try:
            while self.running:
                self.publish_all_equipment()
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n🛑 Stopping publisher...")
        finally:
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()

def main():
    publisher = WorkflowPublisher()
    
    if publisher.connect_mqtt():
        time.sleep(2)  # Allow connection to establish
        publisher.run_publisher(interval=5)  # Publish every 5 seconds
    else:
        print("❌ Failed to start publisher")

if __name__ == "__main__":
    main() 
# ============================================================================
# DIVERSE SCHEMA TEST PUBLISHER - Enhanced for Adaptive Subscriber Testing
# ============================================================================

class DiverseSchemaPublisher:
    """Publisher that generates messages with diverse JSON schemas to test adaptive subscriber"""
    
    def __init__(self):
        self.client = None
        self.running = False
        self.schema_templates = self._create_schema_templates()
        
    def _create_schema_templates(self):
        """Create diverse message schema templates for testing"""
        return {
            # IoT Sensor Format
            "iot_sensor": {
                "topics": ["sensors/building1/temperature", "sensors/building2/humidity", "sensors/outdoor/pressure"],
                "schema": {
                    "device_id": "temp_sensor_{id}",
                    "reading": "{value}",
                    "timestamp": "{timestamp}",
                    "location": "building_{location}",
                    "battery_level": "{battery}",
                    "signal_strength": "{signal}"
                }
            },
            
            # Industrial Machine Format
            "industrial_machine": {
                "topics": ["factory/line1/machine{id}/status", "factory/line2/robot{id}/metrics"],
                "schema": {
                    "machine_name": "machine_{id}",
                    "operational_status": "{status}",
                    "production_rate": "{rate}",
                    "error_count": "{errors}",
                    "maintenance_due": "{maintenance}",
                    "last_service": "{service_date}",
                    "operator_id": "op_{operator}"
                }
            },
            
            # Vehicle Telemetry Format
            "vehicle_telemetry": {
                "topics": ["fleet/truck{id}/position", "fleet/car{id}/diagnostics"],
                "schema": {
                    "vehicle_id": "VEH_{id:04d}",
                    "coordinates": {"lat": "{lat}", "lng": "{lng}"},
                    "speed_kmh": "{speed}",
                    "fuel_percentage": "{fuel}",
                    "engine_temp": "{temp}",
                    "mileage": "{mileage}",
                    "driver": "driver_{driver_id}"
                }
            },
            
            # Smart Home Format
            "smart_home": {
                "topics": ["home/livingroom/{device}", "home/kitchen/{device}", "home/bedroom/{device}"],
                "schema": {
                    "device_name": "{device}_{room}",
                    "power_state": "{power}",
                    "consumption_watts": "{consumption}",
                    "temperature_setpoint": "{setpoint}",
                    "current_temp": "{current}",
                    "mode": "{mode}",
                    "scheduled": "{scheduled}"
                }
            },
            
            # Medical Device Format
            "medical_device": {
                "topics": ["hospital/room{room}/monitor", "hospital/icu/device{id}"],
                "schema": {
                    "patient_id": "P{patient:05d}",
                    "heart_rate": "{hr}",
                    "blood_pressure": {"systolic": "{sys}", "diastolic": "{dia}"},
                    "oxygen_saturation": "{o2}",
                    "alert_level": "{alert}",
                    "nurse_station": "NS{station}",
                    "last_check": "{check_time}"
                }
            },
            
            # Weather Station Format
            "weather_station": {
                "topics": ["weather/station{id}/current", "weather/region/forecast"],
                "schema": {
                    "station_code": "WS{id:03d}",
                    "temp_celsius": "{temp}",
                    "humidity_percent": "{humidity}",
                    "wind": {"speed": "{wind_speed}", "direction": "{wind_dir}"},
                    "precipitation_mm": "{rain}",
                    "visibility_km": "{visibility}",
                    "conditions": "{conditions}"
                }
            },
            
            # Financial Trading Format
            "trading_system": {
                "topics": ["trading/stocks/{symbol}", "trading/crypto/{symbol}"],
                "schema": {
                    "symbol": "{symbol}",
                    "price_usd": "{price}",
                    "volume": "{volume}",
                    "change_percent": "{change}",
                    "market_cap": "{market_cap}",
                    "exchange": "{exchange}",
                    "trade_time": "{trade_time}"
                }
            },
            
            # Minimal Format (just value)
            "minimal": {
                "topics": ["simple/data", "basic/reading"],
                "schema": "{value}"
            },
            
            # Complex Nested Format
            "complex_nested": {
                "topics": ["complex/system{id}/telemetry"],
                "schema": {
                    "system": {
                        "id": "SYS_{id}",
                        "type": "monitoring",
                        "location": {"building": "B{building}", "floor": "{floor}", "room": "R{room}"}
                    },
                    "data": {
                        "primary": {"value": "{value1}", "unit": "{unit1}", "quality": "{quality1}"},
                        "secondary": [
                            {"metric": "cpu", "value": "{cpu}", "threshold": 80},
                            {"metric": "memory", "value": "{memory}", "threshold": 90},
                            {"metric": "disk", "value": "{disk}", "threshold": 85}
                        ]
                    },
                    "metadata": {
                        "version": "2.1.0",
                        "checksum": "{checksum}",
                        "compressed": False
                    }
                }
            }
        }
    
    def connect_mqtt(self):
        """Connect to MQTT broker"""
        try:
            print(f"🔌 Connecting diverse schema publisher to {MQTT_BROKER}:{MQTT_PORT}")
            self.client = create_mqtt_client(client_id="diverse_schema_publisher")
            
            def on_connect(client, userdata, flags, rc):
                if rc == 0:
                    print("✅ Diverse schema publisher connected successfully")
                else:
                    print(f"❌ Connection failed with code {rc}")
            
            self.client.on_connect = on_connect
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()
            return True
            
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            return False
    
    def _fill_template(self, template, values):
        """Fill template with actual values"""
        if isinstance(template, dict):
            return {k: self._fill_template(v, values) for k, v in template.items()}
        elif isinstance(template, list):
            return [self._fill_template(item, values) for item in template]
        elif isinstance(template, str):
            return template.format(**values)
        else:
            return template
    
    def _generate_random_values(self, schema_type):
        """Generate random values for different schema types"""
        values = {
            "id": random.randint(1, 999),
            "timestamp": datetime.now().isoformat() + "Z",
            "value": round(random.uniform(10, 100), 2),
            "value1": round(random.uniform(20, 80), 2),
            "temp": round(random.uniform(-10, 40), 1),
            "humidity": round(random.uniform(30, 90), 1),
            "pressure": round(random.uniform(980, 1020), 2),
            "battery": random.randint(20, 100),
            "signal": random.randint(-90, -30),
            "location": random.randint(1, 5),
            "status": random.choice(["running", "idle", "maintenance", "error"]),
            "rate": round(random.uniform(50, 150), 2),
            "errors": random.randint(0, 5),
            "maintenance": random.choice([True, False]),
            "service_date": (datetime.now()).strftime("%Y-%m-%d"),
            "operator": random.randint(100, 999),
            "lat": round(random.uniform(40.0, 41.0), 6),
            "lng": round(random.uniform(-74.0, -73.0), 6),
            "speed": round(random.uniform(0, 120), 1),
            "fuel": round(random.uniform(10, 100), 1),
            "mileage": random.randint(50000, 200000),
            "driver_id": random.randint(1000, 9999),
            "device": random.choice(["thermostat", "lights", "security", "doorbell"]),
            "room": random.choice(["living", "kitchen", "bedroom", "office"]),
            "power": random.choice(["on", "off", "standby"]),
            "consumption": round(random.uniform(10, 500), 2),
            "setpoint": round(random.uniform(18, 26), 1),
            "current": round(random.uniform(15, 30), 1),
            "mode": random.choice(["heat", "cool", "auto", "off"]),
            "scheduled": random.choice([True, False]),
            "patient": random.randint(1, 99999),
            "hr": random.randint(60, 120),
            "sys": random.randint(110, 160),
            "dia": random.randint(70, 100),
            "o2": round(random.uniform(95, 100), 1),
            "alert": random.choice(["normal", "warning", "critical"]),
            "station": random.randint(1, 10),
            "check_time": datetime.now().strftime("%H:%M:%S"),
            "wind_speed": round(random.uniform(0, 25), 1),
            "wind_dir": random.choice(["N", "NE", "E", "SE", "S", "SW", "W", "NW"]),
            "rain": round(random.uniform(0, 10), 2),
            "visibility": round(random.uniform(1, 15), 1),
            "conditions": random.choice(["clear", "cloudy", "rainy", "foggy"]),
            "symbol": random.choice(["AAPL", "GOOGL", "TSLA", "MSFT", "BTC", "ETH"]),
            "price": round(random.uniform(100, 5000), 2),
            "volume": random.randint(1000, 1000000),
            "change": round(random.uniform(-5, 5), 2),
            "market_cap": random.randint(1000000, 1000000000),
            "exchange": random.choice(["NYSE", "NASDAQ", "BINANCE"]),
            "trade_time": datetime.now().strftime("%H:%M:%S"),
            "building": random.randint(1, 5),
            "floor": random.randint(1, 10),
            "unit1": random.choice(["celsius", "fahrenheit", "kelvin"]),
            "quality1": random.choice(["good", "fair", "poor"]),
            "cpu": round(random.uniform(20, 95), 1),
            "memory": round(random.uniform(30, 85), 1),
            "disk": round(random.uniform(40, 90), 1),
            "checksum": f"md5_{random.randint(100000, 999999)}"
        }
        
        return values
    
    def publish_diverse_schemas(self):
        """Publish messages with diverse schemas"""
        print("🌈 Publishing diverse schema messages...")
        
        for schema_name, config in self.schema_templates.items():
            try:
                # Generate random values
                values = self._generate_random_values(schema_name)
                
                # Fill template with values
                message = self._fill_template(config["schema"], values)
                
                # Choose a random topic from the template
                topic_template = random.choice(config["topics"])
                topic = topic_template.format(**values)
                
                # Handle minimal format (just a value)
                if schema_name == "minimal":
                    message_json = str(message)
                else:
                    message_json = json.dumps(message, indent=None)
                
                # Publish message
                result = self.client.publish(topic, message_json)
                if result[0] == 0:
                    print(f"📤 {schema_name:15} → {topic:40} | {message_json[:80]}...")
                else:
                    print(f"❌ Failed to publish {schema_name} to {topic}")
                    
            except Exception as e:
                print(f"❌ Error publishing {schema_name}: {e}")
    
    def run_diverse_publisher(self, interval=8):
        """Run the diverse schema publisher"""
        print(f"🚀 Starting diverse schema publisher (interval: {interval}s)")
        print("🧪 Testing adaptive subscriber with various JSON schemas")
        print("📊 Schema types:", list(self.schema_templates.keys()))
        print("Press Ctrl+C to stop\n")
        
        self.running = True
        try:
            while self.running:
                self.publish_diverse_schemas()
                print(f"⏰ Waiting {interval}s before next diverse batch...\n")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n🛑 Stopping diverse schema publisher...")
        finally:
            self.running = False
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()

def run_diverse_test():
    """Run the diverse schema test publisher"""
    print("🧪 Starting Diverse Schema Test Publisher")
    print("=" * 60)
    
    publisher = DiverseSchemaPublisher()
    
    if publisher.connect_mqtt():
        time.sleep(2)  # Allow connection to establish
        publisher.run_diverse_publisher(interval=8)  # Publish every 8 seconds
    else:
        print("❌ Failed to start diverse schema publisher")

# Modified main function to choose publisher type
def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--diverse":
        run_diverse_test()
    else:
        # Original publisher
        publisher = WorkflowPublisher()
        
        if publisher.connect_mqtt():
            time.sleep(2)  # Allow connection to establish
            publisher.run_publisher(interval=5)  # Publish every 5 seconds
        else:
            print("❌ Failed to start publisher")

