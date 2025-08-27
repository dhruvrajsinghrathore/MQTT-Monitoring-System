"""
MQTT Client Helper - Handles paho-mqtt version compatibility and authentication
Supports both paho-mqtt 1.6.x and 2.x+ versions with dynamic configuration
"""

import paho.mqtt.client as mqtt
from typing import Optional

def create_mqtt_client(client_id=None, mqtt_config=None):
    """
    Create an MQTT client with proper version compatibility and authentication
    
    Args:
        client_id (str): Optional client ID
        mqtt_config (MQTTConfig): Optional MQTT configuration
        
    Returns:
        mqtt.Client: Configured MQTT client
    """
    try:
        # Try paho-mqtt 1.6.x API (with CallbackAPIVersion)
        if hasattr(mqtt, 'CallbackAPIVersion'):
            client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION1, 
                client_id=client_id
            )
        else:
            # Fall back to paho-mqtt 2.x+ API (without CallbackAPIVersion)
            client = mqtt.Client(client_id=client_id)
            
        # Configure authentication if provided
        if mqtt_config:
            if mqtt_config.username and mqtt_config.password:
                client.username_pw_set(mqtt_config.username, mqtt_config.password)
                print(f"🔐 MQTT authentication configured for user: {mqtt_config.username}")
            
            # Configure SSL if required
            if mqtt_config.use_ssl:
                client.tls_set()
                print("🔒 MQTT SSL/TLS configured")
        
        return client
        
    except Exception as e:
        # Ultimate fallback for any other issues
        print(f"⚠️ MQTT client creation warning: {e}")
        return mqtt.Client(client_id=client_id)

def create_authenticated_client(mqtt_config):
    """
    Create an authenticated MQTT client with full configuration
    
    Args:
        mqtt_config (MQTTConfig): MQTT configuration
        
    Returns:
        mqtt.Client: Configured and authenticated MQTT client
    """
    return create_mqtt_client(
        client_id=mqtt_config.client_id,
        mqtt_config=mqtt_config
    )

def test_connection(mqtt_config) -> tuple[bool, str]:
    """
    Test MQTT connection with given configuration
    
    Args:
        mqtt_config (MQTTConfig): Configuration to test
        
    Returns:
        tuple[bool, str]: (success, message)
    """
    try:
        client = create_authenticated_client(mqtt_config)
        
        # Set up connection test callbacks
        connection_result = {"connected": False, "error": None}
        
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                connection_result["connected"] = True
            else:
                connection_result["error"] = f"Connection failed with code {rc}"
            client.disconnect()
        
        def on_disconnect(client, userdata, rc):
            client.loop_stop()
        
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        
        # Attempt connection
        client.connect(mqtt_config.broker_host, mqtt_config.broker_port, mqtt_config.keepalive)
        client.loop_start()
        
        # Wait for connection result (timeout after 10 seconds)
        import time
        timeout = 10
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if connection_result["connected"]:
                return True, "Connection successful"
            if connection_result["error"]:
                return False, connection_result["error"]
            time.sleep(0.1)
        
        client.loop_stop()
        return False, "Connection timeout"
        
    except Exception as e:
        return False, f"Connection test failed: {str(e)}"

def get_mqtt_version():
    """Get the installed paho-mqtt version"""
    try:
        import paho.mqtt
        return getattr(paho.mqtt, '__version__', 'unknown')
    except:
        return 'unknown' 