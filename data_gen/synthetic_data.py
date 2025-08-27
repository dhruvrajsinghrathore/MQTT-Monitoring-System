#!/usr/bin/env python3
"""
Stream synthetic cell-on-a-chip sensor data for multiple cells via MQTT.

Usage examples:
  # 2 Hz for 30 s, 4 cells with custom ranges for O2 and pH
  python synthetic_data.py --hz 2 --duration 30 --cells 4 \
    --range o2_percent=65:95 --range pH=7.2:7.5

  # 5 Hz for 10 s, custom flow and pressure ranges, 3 cells
  python synthetic_data.py --hz 5 --duration 10 --cells 3 \
    --range flow_uL_min=2:12 --range pressure_mbar=40:120

  # Infinite stream for 8 cells at 1 Hz
  python synthetic_data.py --hz 1 --cells 8

Notes:
- All values evolve via bounded random walks. Noise scales with sqrt(dt), drift scales with dt.
- Ranges can be overridden via --range name=min:max (repeatable) and apply to every cell.
- Publishes to MQTT topics in format: cell/<cell_id>/<field_name>
- Publishing order is randomized per cycle for uniform distribution.
- Each message includes timestamp, value, unit, and sensor metadata.
"""

import argparse
import json
import math
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional
from mqtt_client_helper import create_mqtt_client

# MQTT Configuration
MQTT_BROKER = "cloud.dtkit.org"
MQTT_PORT = 1883

def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

@dataclass
class Sensor:
    name: str
    value: float
    min_val: float
    max_val: float
    noise_per_sec: float  # standard deviation per second
    drift_per_sec: float = 0.0  # signed drift per second
    decimals: int = 3
    integer: bool = False
    unit: str = ""  # Add unit field
    sensor_type: str = ""  # Add sensor type for metadata

    def clamp(self, x: float) -> float:
        if x < self.min_val:
            return self.min_val
        if x > self.max_val:
            return self.max_val
        return x

    def update(self, dt: float) -> float:
        # Brownian noise scaling with sqrt(dt)
        sigma = self.noise_per_sec * math.sqrt(max(dt, 1e-9))
        step = random.gauss(0.0, sigma) + self.drift_per_sec * dt
        self.value = self.clamp(self.value + step)
        return self.value

    def formatted(self) -> float:
        if self.integer:
            return int(round(self.value))
        return round(self.value, self.decimals)

@dataclass
class Model:
    sensors: Dict[str, Sensor] = field(default_factory=dict)

    def update(self, dt: float):
        # Update base random walks first
        for s in self.sensors.values():
            s.update(dt)

        # Weak couplings to make it more realistic (still bounded by ranges)
        flow = self.sensors["flow_uL_min"].value

        # Pressure tracks flow a bit
        p = self.sensors["pressure_mbar"]
        p.value = p.clamp(p.value + 0.10 * (flow - 5.0) * dt + random.gauss(0, p.noise_per_sec * math.sqrt(dt)))

        # Oxygen drifts down slowly; slightly recovers at higher flow
        o2 = self.sensors["o2_percent"]
        o2.value = o2.clamp(
            o2.value + (-0.03 + 0.02 * (flow - 5.0) / 10.0) * dt + random.gauss(0, o2.noise_per_sec * math.sqrt(dt))
        )

        # Glucose drifts downward slowly
        glu = self.sensors["glucose_mM"]
        glu.value = glu.clamp(glu.value - 0.002 * dt + random.gauss(0, glu.noise_per_sec * math.sqrt(dt)))

        # Viability drifts down very slowly
        v = self.sensors["hcs_viability_pct"]
        v.value = v.clamp(v.value - 0.0005 * dt + random.gauss(0, v.noise_per_sec * math.sqrt(dt)))

        # Cell count as a slow random walk with integer output
        cc = self.sensors["qpi_cell_count"]
        cc.value = cc.clamp(cc.value + random.gauss(0, 0.01) * dt)  # tiny changes

def build_default_model() -> Tuple[Model, List[str]]:
    # Default initial values and ranges (override with --range)
    fields = [
        "barrier_impedance_kOhm",
        "o2_percent",
        "pH",
        "glucose_mM",
        "flow_uL_min",
        "pressure_mbar",
        "aptamer_IL6_nM",
        "aptamer_TNFa_nM",
        "tumor_EMT_index",
        "tumor_prolif_index",
        "qpi_confluence_pct",
        "qpi_dry_mass_pg",
        "qpi_cell_count",
        "hcs_ROS_AU",
        "hcs_Ca_ratio",
        "hcs_viability_pct",
    ]

    sensors = {
        # 1) Barrier & adhesion (impedance)
        "barrier_impedance_kOhm": Sensor("barrier_impedance_kOhm", 3.8, 2.0, 6.0, noise_per_sec=0.02, drift_per_sec=-0.002, decimals=3, unit="kOhm", sensor_type="impedance"),
        # 2) Oxygen (O2 optodes)
        "o2_percent": Sensor("o2_percent", 75.0, 40.0, 100.0, noise_per_sec=0.25, drift_per_sec=-0.01, decimals=1, unit="percent", sensor_type="optical"),
        # 3) pH (optodes)
        "pH": Sensor("pH", 7.40, 6.80, 7.60, noise_per_sec=0.002, drift_per_sec=-0.0005, decimals=3, unit="pH", sensor_type="optical"),
        # 4) Glucose (amperometric)
        "glucose_mM": Sensor("glucose_mM", 10.0, 0.0, 25.0, noise_per_sec=0.01, drift_per_sec=-0.002, decimals=3, unit="mM", sensor_type="amperometric"),
        # 5) Microflow
        "flow_uL_min": Sensor("flow_uL_min", 5.0, 0.0, 20.0, noise_per_sec=0.20, drift_per_sec=0.0, decimals=2, unit="µL/min", sensor_type="flow"),
        # 6) Micropressure
        "pressure_mbar": Sensor("pressure_mbar", 58.0, 30.0, 200.0, noise_per_sec=0.5, drift_per_sec=0.0, decimals=1, unit="mbar", sensor_type="pressure"),
        # 7) Aptamer/electrochemical (example: IL-6, TNF-α)
        "aptamer_IL6_nM": Sensor("aptamer_IL6_nM", 0.20, 0.0, 5.0, noise_per_sec=0.01, drift_per_sec=0.005, decimals=3, unit="nM", sensor_type="electrochemical"),
        "aptamer_TNFa_nM": Sensor("aptamer_TNFa_nM", 0.06, 0.0, 5.0, noise_per_sec=0.006, drift_per_sec=0.003, decimals=3, unit="nM", sensor_type="electrochemical"),
        # 8) Tumor phenotype & signaling (indices 0–1)
        "tumor_EMT_index": Sensor("tumor_EMT_index", 0.25, 0.0, 1.0, noise_per_sec=0.002, drift_per_sec=0.001, decimals=3, unit="index", sensor_type="imaging"),
        "tumor_prolif_index": Sensor("tumor_prolif_index", 0.60, 0.0, 1.0, noise_per_sec=0.002, drift_per_sec=-0.001, decimals=3, unit="index", sensor_type="imaging"),
        # 9) Quantitative phase imaging
        "qpi_confluence_pct": Sensor("qpi_confluence_pct", 55.0, 0.0, 100.0, noise_per_sec=0.02, drift_per_sec=0.01, decimals=2, unit="percent", sensor_type="imaging"),
        "qpi_dry_mass_pg": Sensor("qpi_dry_mass_pg", 250.0, 100.0, 500.0, noise_per_sec=0.2, drift_per_sec=0.05, decimals=2, unit="pg", sensor_type="imaging"),
        "qpi_cell_count": Sensor("qpi_cell_count", 220.0, 0.0, 10000.0, noise_per_sec=0.0, drift_per_sec=0.0, integer=True, unit="count", sensor_type="imaging"),
        # 10) High-content fluorescence
        "hcs_ROS_AU": Sensor("hcs_ROS_AU", 1200.0, 0.0, 5000.0, noise_per_sec=5.0, drift_per_sec=2.0, decimals=0, unit="AU", sensor_type="fluorescence"),
        "hcs_Ca_ratio": Sensor("hcs_Ca_ratio", 0.95, 0.5, 2.0, noise_per_sec=0.01, drift_per_sec=0.0, decimals=3, unit="ratio", sensor_type="fluorescence"),
        "hcs_viability_pct": Sensor("hcs_viability_pct", 98.5, 0.0, 100.0, noise_per_sec=0.01, drift_per_sec=-0.001, decimals=2, unit="percent", sensor_type="fluorescence"),
    }

    return Model(sensors=sensors), fields

def parse_ranges(overrides: List[str], sensors: Dict[str, Sensor]):
    if not overrides:
        return
    for spec in overrides:
        if "=" not in spec or ":" not in spec:
            raise ValueError(f"Bad --range '{spec}', expected name=min:max")
        name, rng = spec.split("=", 1)
        if name not in sensors:
            valid = ", ".join(sensors.keys())
            raise ValueError(f"Unknown sensor '{name}'. Valid names: {valid}")
        try:
            smin_str, smax_str = rng.split(":", 1)
            smin = float(smin_str)
            smax = float(smax_str)
            if smin >= smax:
                raise ValueError
        except Exception:
            raise ValueError(f"Bad range for {name}: '{rng}', expected min:max with min<max")
        sensors[name].min_val = smin
        sensors[name].max_val = smax
        # Clamp current value to the new range
        sensors[name].value = sensors[name].clamp(sensors[name].value)

class MQTTCellPublisher:
    def __init__(self):
        self.client = None
        self.running = False
        
    def connect_mqtt(self):
        """Connect to MQTT broker"""
        try:
            client_id = f'cell-data-publisher-{random.randint(0, 1000)}'
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
            print(f"🔗 Cell Data Publisher connected to {MQTT_BROKER}:{MQTT_PORT}")
            self.running = True
        else:
            print(f"❌ Failed to connect, return code {rc}")
    
    def on_disconnect(self, client, userdata, rc):
        print("🔌 Disconnected from MQTT broker")
        self.running = False
    
    def publish_sensor_data(self, cell_id: int, field_name: str, sensor: Sensor):
        """Publish sensor data to MQTT topic"""
        topic = f"cell/{cell_id}/{field_name}"
        
        message = {
            "timestamp": now_iso(),
            "value": sensor.formatted(),
            "unit": sensor.unit,
            "sensor_type": sensor.sensor_type,
            "cell_id": cell_id,
            "field": field_name,
            "min_val": sensor.min_val,
            "max_val": sensor.max_val
        }
        
        try:
            result = self.client.publish(topic, json.dumps(message))
            if result[0] == 0:
                print(f"📡 Cell {cell_id:2d} → {field_name:20s}: {sensor.formatted():8} {sensor.unit}")
            else:
                print(f"❌ Failed to publish to {topic}")
        except Exception as e:
            print(f"❌ Error publishing {topic}: {e}")
    
    def publish_randomized_cycle(self, models: List[Model], field_order: List[str]):
        """Publish all sensor data in randomized order"""
        # Create list of all (cell_id, field_name) combinations
        cell_field_combinations = []
        for cell_idx, model in enumerate(models, start=1):
            for field_name in field_order:
                cell_field_combinations.append((cell_idx, field_name, model))
        
        # Randomize the order
        random.shuffle(cell_field_combinations)
        
        # Publish in randomized order
        for cell_id, field_name, model in cell_field_combinations:
            sensor = model.sensors[field_name]
            self.publish_sensor_data(cell_id, field_name, sensor)
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.running = False
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

def main():
    parser = argparse.ArgumentParser(description="Stream synthetic cell-on-a-chip sensor data via MQTT for multiple cells.")
    parser.add_argument("--hz", type=float, default=1, help="Samples per second (default: 1.0)")
    parser.add_argument("--duration", type=float, default=None, help="Seconds to run; omit for infinite")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--range", dest="ranges", action="append", help="Override range: name=min:max (repeatable)")
    parser.add_argument("--cells", type=int, default=10, help="Number of cells to simulate (default: 10)")
    args = parser.parse_args()

    if args.hz <= 0:
        print("hz must be > 0", file=sys.stderr)
        sys.exit(2)
    if args.cells <= 0:
        print("--cells must be >= 1", file=sys.stderr)
        sys.exit(2)
    if args.seed is not None:
        random.seed(args.seed)

    # Build one model per cell and apply range overrides to each
    models: List[Model] = []
    field_order: List[str] = []
    for _ in range(args.cells):
        m, fields = build_default_model()
        models.append(m)
        field_order = fields  # same for all cells
    for m in models:
        parse_ranges(args.ranges, m.sensors)

    # Set up MQTT publisher
    mqtt_publisher = MQTTCellPublisher()
    if not mqtt_publisher.connect_mqtt():
        print("❌ Failed to connect to MQTT broker")
        sys.exit(1)
    
    # Wait for connection to establish
    time.sleep(2)
    
    print(f"🚀 Starting cell data publisher")
    print(f"📊 Publishing data for {args.cells} cells at {args.hz} Hz")
    print(f"🌐 MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"📡 Topic format: cell/<cell_id>/<field_name>")
    print("🔀 Publishing order randomized per cycle")
    print("Press Ctrl+C to stop\n")

    dt = 1.0 / args.hz
    next_time = time.perf_counter()
    end_time: Optional[float] = None if args.duration is None else (next_time + args.duration)

    try:
        while mqtt_publisher.running:
            now = time.perf_counter()
            if end_time is not None and now >= end_time:
                break

            # Update all cells first (so their state is at the same logical time)
            for m in models:
                m.update(dt)

            # Publish all sensor data in randomized order
            mqtt_publisher.publish_randomized_cycle(models, field_order)
            
            print()  # Add blank line between cycles for readability

            # Sleep until next tick
            next_time += dt
            sleep_s = max(0.0, next_time - time.perf_counter())
            if sleep_s > 0:
                time.sleep(sleep_s)
            else:
                # If behind, skip sleep and reschedule next tick from current time
                next_time = time.perf_counter()
    except KeyboardInterrupt:
        print("\n🛑 Stopping publisher...")
    finally:
        mqtt_publisher.disconnect()

if __name__ == "__main__":
    main()

 