#!/usr/bin/env python3
"""
SMR (Small Modular Reactor) Digital Twin Data Generator

This script generates synthetic sensor data for a complete SMR thermal energy system
based on the Virtual Sensors Excel file and workflow diagram. It simulates realistic
thermal dynamics and interdependencies between subsystems.

The system includes:
- Compressor System (7 sensors)
- Heat Pipe-to-Air HX (6 sensors) 
- Orifice (4 sensors)
- Pneumatic Control Valves (4 sensors)
- Reactor Core (5 sensors)
- Recuperator (6 sensors)
- Stirling Engine (7 sensors)
- Thermal Energy Storage System (8 sensors)

Topic Pattern: smr/<subsystem>/<sensor_name>
Message Format: Rich JSON with timestamp, value, unit, status, and metadata
"""

import json
import time
import random
import argparse
import math
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
import paho.mqtt.client as mqtt

# MQTT Configuration
MQTT_BROKER = "cloud.dtkit.org"
MQTT_PORT = 1883

def now_iso() -> str:
    """Get current timestamp in ISO format"""
    return datetime.now().isoformat() + "Z"

@dataclass
class SMRSensor:
    """Represents a sensor in the SMR digital twin system"""
    name: str
    subsystem: str
    unit: str
    min_val: float
    max_val: float
    description: str
    current_value: float = 0.0
    target_value: float = 0.0
    noise_level: float = 0.02  # 2% noise by default
    response_rate: float = 0.1  # How quickly sensor responds to changes
    operational_status: str = "normal"
    
    def __post_init__(self):
        # Initialize current value to a reasonable starting point
        if self.min_val == 0 and self.max_val == 1:
            # Binary/switch sensor
            self.current_value = random.choice([0, 1])
            self.target_value = self.current_value
        else:
            # Analog sensor - start at 30-70% of range
            range_span = self.max_val - self.min_val
            self.current_value = self.min_val + range_span * random.uniform(0.3, 0.7)
            self.target_value = self.current_value
    
    def update(self, dt: float, external_influences: Dict[str, float] = None):
        """Update sensor value with realistic dynamics"""
        # Apply external influences (thermal coupling, pressure relationships, etc.)
        if external_influences:
            for influence, factor in external_influences.items():
                if influence in self.name.lower() or influence in self.subsystem.lower():
                    self.target_value += factor * dt
        
        # Random walk for target value (slow drift)
        drift_rate = 0.05  # 5% per second maximum drift
        range_span = self.max_val - self.min_val
        max_drift = range_span * drift_rate * dt
        drift = random.uniform(-max_drift, max_drift)
        self.target_value += drift
        
        # Keep target within bounds
        self.target_value = max(self.min_val, min(self.max_val, self.target_value))
        
        # Exponential approach to target with response rate
        response = self.response_rate * dt
        self.current_value += (self.target_value - self.current_value) * response
        
        # Add measurement noise
        noise_amplitude = (self.max_val - self.min_val) * self.noise_level
        noise = random.gauss(0, noise_amplitude / 3)  # 3-sigma noise
        measured_value = self.current_value + noise
        
        # Clamp to sensor limits
        self.current_value = max(self.min_val, min(self.max_val, measured_value))
    
    def formatted(self) -> str:
        """Format the sensor value appropriately"""
        if self.min_val == 0 and self.max_val == 1:
            return str(int(self.current_value))
        elif abs(self.current_value) < 0.1:
            return f"{self.current_value:.4f}"
        elif abs(self.current_value) < 10:
            return f"{self.current_value:.3f}"
        else:
            return f"{self.current_value:.2f}"
    
    def get_status(self) -> str:
        """Determine operational status based on current value"""
        range_span = self.max_val - self.min_val
        normalized = (self.current_value - self.min_val) / range_span
        
        if normalized < 0.05 or normalized > 0.95:
            return "alarm"
        elif normalized < 0.15 or normalized > 0.85:
            return "warning" 
        else:
            return "normal"

class SMRSystemModel:
    """Models the complete SMR thermal energy system with realistic physics"""
    
    def __init__(self):
        self.sensors = self._initialize_sensors()
        self.system_state = {
            'reactor_power_level': 0.75,  # 75% power
            'primary_loop_temperature': 550,  # °C
            'thermal_storage_charge': 0.60,  # 60% charged
            'stirling_load': 0.80,  # 80% load
            'ambient_temperature': 25,  # °C
            'operating_mode': 'normal'
        }
        
    def _initialize_sensors(self) -> Dict[str, SMRSensor]:
        """Initialize all SMR sensors based on the Virtual Sensors specification"""
        sensors = {}
        
        # Compressor System
        sensors.update({
            'inlet_pressure': SMRSensor(
                "inlet_pressure", "compressor", "psi(a)", 0, 100,
                "Measures compressor suction pressure for density correction"
            ),
            'discharge_pressure': SMRSensor(
                "discharge_pressure", "compressor", "psi(g)", 0, 145,
                "Tracks receiver/regulator outlet pressure"
            ),
            'filter_diff_pressure': SMRSensor(
                "filter_diff_pressure", "compressor", "psi", 0, 15,
                "Indicates fouling of intake or coalescing elements"
            ),
            'suction_temperature': SMRSensor(
                "suction_temperature", "compressor", "°C", -20, 60,
                "Captures ambient/suction temperature"
            ),
            'discharge_temperature': SMRSensor(
                "discharge_temperature", "compressor", "°C", 0, 150,
                "Monitors compressor discharge heating"
            ),
            'air_mass_flow': SMRSensor(
                "air_mass_flow", "compressor", "SCFM", 0, 500,
                "Compressed air mass flow rate"
            ),
            'condensate_level': SMRSensor(
                "condensate_level", "compressor", "binary", 0, 1,
                "Receiver condensate level switch"
            )
        })
        
        # Heat Pipe-to-Air HX
        sensors.update({
            'hp_evaporator_temp': SMRSensor(
                "hp_evaporator_temp", "heat_pipe_hx", "°C", 50, 700,
                "Heat-pipe evaporator temperature"
            ),
            'hp_condenser_temp': SMRSensor(
                "hp_condenser_temp", "heat_pipe_hx", "°C", 20, 500,
                "Heat-pipe condenser temperature"
            ),
            'fiber_optic_temp': SMRSensor(
                "fiber_optic_temp", "heat_pipe_hx", "°C", -200, 250,
                "Fiber-optic temperature probes on pipes"
            ),
            'air_hx_inlet_temp': SMRSensor(
                "air_hx_inlet_temp", "heat_pipe_hx", "°C", 20, 400,
                "Air HX inlet temperature"
            ),
            'air_hx_outlet_temp': SMRSensor(
                "air_hx_outlet_temp", "heat_pipe_hx", "°C", 20, 500,
                "Air HX outlet temperature"
            ),
            'air_diff_pressure': SMRSensor(
                "air_diff_pressure", "heat_pipe_hx", "inH2O", 0, 40,
                "Air-side differential pressure"
            )
        })
        
        # Orifice
        sensors.update({
            'orifice_diff_pressure': SMRSensor(
                "orifice_diff_pressure", "orifice", "inH2O", 0, 200,
                "Orifice differential pressure"
            ),
            'upstream_pressure': SMRSensor(
                "upstream_pressure", "orifice", "psi(a)", 0, 100,
                "Upstream static pressure"
            ),
            'upstream_gas_temp': SMRSensor(
                "upstream_gas_temp", "orifice", "°C", 0, 300,
                "Upstream gas temperature"
            ),
            'stack_temperature': SMRSensor(
                "stack_temperature", "orifice", "°C", 0, 200,
                "Stack temperature"
            )
        })
        
        # Pneumatic Control Valves
        sensors.update({
            'valve_position': SMRSensor(
                "valve_position", "control_valves", "% open", 0, 100,
                "Valve position feedback"
            ),
            'actuator_pressure': SMRSensor(
                "actuator_pressure", "control_valves", "psi(g)", 0, 120,
                "Actuator supply pressure"
            ),
            'valve_diff_pressure': SMRSensor(
                "valve_diff_pressure", "control_valves", "psi", 0, 50,
                "Valve differential pressure"
            ),
            'command_signal': SMRSensor(
                "command_signal", "control_valves", "mA", 4, 20,
                "Command signal monitor"
            )
        })
        
        # Reactor Core
        sensors.update({
            'heater_sheath_temp': SMRSensor(
                "heater_sheath_temp", "reactor_core", "°C", 20, 900,
                "Heater cartridge sheath thermocouples"
            ),
            'core_wall_temp': SMRSensor(
                "core_wall_temp", "reactor_core", "°C", 20, 800,
                "Core wall thermocouples (axial array)"
            ),
            'heater_current': SMRSensor(
                "heater_current", "reactor_core", "A", 0, 50,
                "Heater current transducer"
            ),
            'heater_voltage': SMRSensor(
                "heater_voltage", "reactor_core", "VAC", 0, 300,
                "Heater voltage monitor"
            ),
            'hp_interface_temp': SMRSensor(
                "hp_interface_temp", "reactor_core", "°C", 50, 700,
                "Heat-pipe interface temperature"
            )
        })
        
        # Recuperator
        sensors.update({
            'hot_inlet_temp': SMRSensor(
                "hot_inlet_temp", "recuperator", "°C", 20, 400,
                "Hot-side inlet temperature"
            ),
            'hot_outlet_temp': SMRSensor(
                "hot_outlet_temp", "recuperator", "°C", 20, 450,
                "Hot-side outlet temperature"
            ),
            'exhaust_inlet_temp': SMRSensor(
                "exhaust_inlet_temp", "recuperator", "°C", 50, 500,
                "Exhaust inlet temperature"
            ),
            'exhaust_outlet_temp': SMRSensor(
                "exhaust_outlet_temp", "recuperator", "°C", 20, 200,
                "Exhaust outlet temperature"
            ),
            'recup_air_diff_pressure': SMRSensor(
                "recup_air_diff_pressure", "recuperator", "inH2O", 0, 40,
                "Air-side differential pressure"
            ),
            'diff_temp_pair': SMRSensor(
                "diff_temp_pair", "recuperator", "°C", 0, 300,
                "Differential temperature pair"
            )
        })
        
        # Stirling Engine
        sensors.update({
            'stirling_hot_temp': SMRSensor(
                "stirling_hot_temp", "stirling_engine", "°C", 100, 700,
                "Hot-end temperature"
            ),
            'stirling_cold_temp': SMRSensor(
                "stirling_cold_temp", "stirling_engine", "°C", 10, 120,
                "Cold-end temperature"
            ),
            'shaft_speed': SMRSensor(
                "shaft_speed", "stirling_engine", "rpm", 0, 4000,
                "Shaft speed sensor"
            ),
            'power_output': SMRSensor(
                "power_output", "stirling_engine", "kW", 0, 5,
                "Electric power output meter"
            ),
            'cooling_water_temp': SMRSensor(
                "cooling_water_temp", "stirling_engine", "°C", 5, 40,
                "Cooling-water inlet temperature"
            ),
            'cooling_water_flow': SMRSensor(
                "cooling_water_flow", "stirling_engine", "L/min", 0, 50,
                "Cooling-water flow meter"
            ),
            'exhaust_gas_temp': SMRSensor(
                "exhaust_gas_temp", "stirling_engine", "°C", 50, 300,
                "Exhaust gas temperature (to recuperator)"
            )
        })
        
        # Thermal Energy Storage System
        sensors.update({
            'salt_temp_top': SMRSensor(
                "salt_temp_top", "thermal_storage", "°C", 150, 600,
                "Salt bulk temperature (top)"
            ),
            'salt_temp_mid': SMRSensor(
                "salt_temp_mid", "thermal_storage", "°C", 150, 600,
                "Salt bulk temperature (mid)"
            ),
            'salt_temp_bottom': SMRSensor(
                "salt_temp_bottom", "thermal_storage", "°C", 150, 600,
                "Salt bulk temperature (bottom)"
            ),
            'charge_interface_temp': SMRSensor(
                "charge_interface_temp", "thermal_storage", "°C", 150, 600,
                "Charge interface temperature (HP in)"
            ),
            'discharge_interface_temp': SMRSensor(
                "discharge_interface_temp", "thermal_storage", "°C", 150, 600,
                "Discharge interface temperature (HP out)"
            ),
            'salt_level': SMRSensor(
                "salt_level", "thermal_storage", "%", 0, 100,
                "Salt level transmitter"
            ),
            'salt_loop_pressure': SMRSensor(
                "salt_loop_pressure", "thermal_storage", "psi(g)", 0, 150,
                "Salt loop pressure"
            ),
            'salt_flow': SMRSensor(
                "salt_flow", "thermal_storage", "kg/s", 0, 2,
                "Secondary-loop salt flow"
            )
        })
        
        return sensors
    
    def update_system_dynamics(self, dt: float):
        """Update system-wide thermal and operational dynamics"""
        # Update reactor power based on control demand
        power_variation = random.uniform(-0.005, 0.005)  # ±0.5% variation
        self.system_state['reactor_power_level'] = max(0.1, min(1.0, 
            self.system_state['reactor_power_level'] + power_variation))
        
        # Primary loop temperature follows reactor power
        target_temp = 300 + 300 * self.system_state['reactor_power_level']
        self.system_state['primary_loop_temperature'] += (target_temp - 
            self.system_state['primary_loop_temperature']) * 0.02 * dt
        
        # Thermal storage charge/discharge dynamics
        charge_rate = random.uniform(-0.01, 0.01)  # ±1% per second
        self.system_state['thermal_storage_charge'] = max(0.0, min(1.0,
            self.system_state['thermal_storage_charge'] + charge_rate * dt))
        
        # Stirling engine load follows thermal conditions
        load_variation = random.uniform(-0.02, 0.02)
        self.system_state['stirling_load'] = max(0.2, min(1.0,
            self.system_state['stirling_load'] + load_variation))
    
    def get_thermal_influences(self) -> Dict[str, float]:
        """Calculate thermal coupling effects between subsystems"""
        influences = {}
        
        # Reactor core influences
        reactor_power = self.system_state['reactor_power_level']
        influences['reactor_core'] = reactor_power * 50  # Temperature boost from reactor
        influences['heat_pipe'] = reactor_power * 30     # Heat pipe temperatures
        
        # Thermal storage influences
        storage_charge = self.system_state['thermal_storage_charge']
        influences['thermal_storage'] = (storage_charge - 0.5) * 20  # Temperature delta
        
        # Stirling engine influences
        stirling_load = self.system_state['stirling_load']
        influences['stirling_engine'] = stirling_load * 25  # Temperature from operation
        influences['cooling'] = -stirling_load * 10  # Cooling demand
        
        return influences
    
    def update(self, dt: float):
        """Update the complete SMR system state"""
        self.update_system_dynamics(dt)
        thermal_influences = self.get_thermal_influences()
        
        # Update all sensors with thermal coupling
        for sensor in self.sensors.values():
            sensor.update(dt, thermal_influences)

class SMRMQTTPublisher:
    """Publishes SMR digital twin data to MQTT broker"""
    
    def __init__(self, broker_host: str = MQTT_BROKER, broker_port: int = MQTT_PORT):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = None
        self.is_connected = False
        
    def connect_mqtt(self):
        """Connect to MQTT broker"""
        try:
            self.client = mqtt.Client()
            self.client.on_connect = self.on_connect
            self.client.on_disconnect = self.on_disconnect
            
            print(f"🔌 Connecting to MQTT broker at {self.broker_host}:{self.broker_port}")
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            
            # Wait for connection
            timeout = 10
            start_time = time.time()
            while not self.is_connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
                
            if not self.is_connected:
                raise Exception("Failed to connect to MQTT broker within timeout")
                
        except Exception as e:
            print(f"❌ MQTT connection failed: {e}")
            raise
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("✅ Connected to MQTT broker successfully")
            self.is_connected = True
        else:
            print(f"❌ MQTT connection failed with code {rc}")
    
    def on_disconnect(self, client, userdata, rc):
        print("📤 Disconnected from MQTT broker")
        self.is_connected = False
    
    def publish_sensor_data(self, subsystem: str, sensor_name: str, sensor: SMRSensor):
        """Publish sensor data to MQTT topic"""
        topic = f"smr/{subsystem}/{sensor_name}"
        
        message = {
            "timestamp": now_iso(),
            "value": sensor.formatted(),
            "unit": sensor.unit,
            "status": sensor.get_status(),
            "subsystem": sensor.subsystem,
            "sensor_name": sensor.name,
            "description": sensor.description,
            "min_val": sensor.min_val,
            "max_val": sensor.max_val,
            "raw_value": sensor.current_value,
            "target_value": sensor.target_value
        }
        
        try:
            result = self.client.publish(topic, json.dumps(message))
            if result[0] == 0:
                status_indicator = "🟢" if sensor.get_status() == "normal" else "🟡" if sensor.get_status() == "warning" else "🔴"
                print(f"{status_indicator} SMR {subsystem:15s} → {sensor_name:25s}: {sensor.formatted():>8s} {sensor.unit}")
            else:
                print(f"❌ Failed to publish to {topic}")
        except Exception as e:
            print(f"❌ Error publishing {topic}: {e}")
    
    def publish_randomized_cycle(self, model: SMRSystemModel, subsystem_order: List[str]):
        """Publish all sensor data in randomized order"""
        # Randomize sensors within each subsystem
        for subsystem in subsystem_order:
            subsystem_sensors = [(name, sensor) for name, sensor in model.sensors.items() 
                               if sensor.subsystem == subsystem]
            random.shuffle(subsystem_sensors)
            
            for sensor_name, sensor in subsystem_sensors:
                self.publish_sensor_data(subsystem, sensor_name, sensor)
                # Small delay to simulate real sensor polling
                time.sleep(random.uniform(0.01, 0.05))
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client and self.is_connected:
            self.client.loop_stop()
            self.client.disconnect()

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Stream SMR Digital Twin sensor data via MQTT")
    parser.add_argument("--hz", type=float, default=0.5, help="Samples per second (default: 0.5)")
    parser.add_argument("--duration", type=float, default=None, help="Seconds to run; omit for infinite")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--broker", type=str, default=MQTT_BROKER, help="MQTT broker host")
    parser.add_argument("--port", type=int, default=MQTT_PORT, help="MQTT broker port")
    args = parser.parse_args()
    
    # Set random seed for reproducibility
    if args.seed:
        random.seed(args.seed)
        print(f"🎲 Random seed set to: {args.seed}")
    
    print("🏭 SMR Digital Twin Data Generator")
    print("=" * 60)
    print(f"📊 Sample rate: {args.hz} Hz ({1/args.hz:.1f}s intervals)")
    if args.duration:
        print(f"⏱️  Duration: {args.duration} seconds")
    else:
        print("⏱️  Duration: Infinite (Ctrl+C to stop)")
    print(f"🌐 MQTT Broker: {args.broker}:{args.port}")
    print("=" * 60)
    
    # Initialize SMR system model
    model = SMRSystemModel()
    print(f"🔧 Initialized SMR system with {len(model.sensors)} sensors across 8 subsystems")
    
    # Initialize MQTT publisher
    publisher = SMRMQTTPublisher(args.broker, args.port)
    publisher.connect_mqtt()
    
    # Define subsystem processing order (following thermal flow)
    subsystem_order = [
        "reactor_core",
        "heat_pipe_hx", 
        "thermal_storage",
        "stirling_engine",
        "recuperator",
        "control_valves",
        "compressor",
        "orifice"
    ]
    
    try:
        start_time = time.time()
        cycle_count = 0
        
        print("\n🚀 Starting SMR digital twin simulation...")
        print("💡 Topics published to: smr/<subsystem>/<sensor_name>")
        print("-" * 60)
        
        while True:
            cycle_start = time.time()
            
            # Update system model
            dt = 1.0 / args.hz
            model.update(dt)
            
            # Publish all sensor data
            publisher.publish_randomized_cycle(model, subsystem_order)
            
            cycle_count += 1
            elapsed = time.time() - start_time
            
            # Check duration limit
            if args.duration and elapsed >= args.duration:
                print(f"\n⏹️  Reached duration limit of {args.duration} seconds")
                break
            
            # Sleep to maintain sample rate
            cycle_time = time.time() - cycle_start
            sleep_time = max(0, (1.0 / args.hz) - cycle_time)
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            # Status update every 100 cycles
            if cycle_count % 100 == 0:
                runtime = time.time() - start_time
                print(f"📈 Cycles: {cycle_count}, Runtime: {runtime:.1f}s, Rate: {cycle_count/runtime:.2f} Hz")
                
    except KeyboardInterrupt:
        print(f"\n⏹️  Stopped by user after {cycle_count} cycles")
    except Exception as e:
        print(f"\n❌ Error during simulation: {e}")
    finally:
        publisher.disconnect()
        total_time = time.time() - start_time
        print(f"📊 Final stats: {cycle_count} cycles in {total_time:.1f}s")
        print("🏁 SMR Digital Twin simulation complete")

if __name__ == "__main__":
    main()