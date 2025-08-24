from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
import time
import json
import os
from datetime import datetime
from dotenv import load_dotenv

from collectors.starlink import StarlinkCollector
from collectors.satellites import SatelliteCollector
from collectors.spacetrack import SpaceTrackCollector
from collectors.enhanced_satellites import EnhancedSatelliteCollector

# Load environment variables from .env file
load_dotenv('.env')

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'starlink-monitor-secret-key'

# Enable CORS for frontend
CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000"])

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins=["http://localhost:3000", "http://127.0.0.1:3000"])

# Initialize collectors
starlink_collector = StarlinkCollector()

# Choose satellite data source based on configuration
data_source = os.environ.get('SATELLITE_DATA_SOURCE', 'enhanced').lower()
print(f"🔧 Data source configured as: {data_source}")
print(f"🔑 Username configured: {os.environ.get('SPACETRACK_USERNAME', 'NOT_SET')}")

if data_source == 'enhanced':
    satellite_collector = EnhancedSatelliteCollector()
    print("🚀 Using Enhanced Multi-Source Satellite Collector")
elif data_source == 'spacetrack':
    satellite_collector = SpaceTrackCollector()
    print("🛰️ Using Space-Track.org for satellite data")
else:
    satellite_collector = SatelliteCollector()
    print("🛰️ Using CelesTrak for satellite data")

# Global state
monitoring_active = False
monitoring_thread = None
latest_data = {}

class MonitoringService:
    """Background service to collect data and emit updates."""
    
    def __init__(self):
        self.running = False
        self.update_interval = 10  # seconds
        
    def start(self):
        """Start the monitoring loop."""
        if self.running:
            return
            
        self.running = True
        thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        thread.start()
        print("🚀 Monitoring service started")
        
    def stop(self):
        """Stop the monitoring loop."""
        self.running = False
        print("⏹️  Monitoring service stopped")
        
    def _monitoring_loop(self):
        """Main monitoring loop that runs in background."""
        global latest_data
        
        while self.running:
            try:
                # Collect Starlink data
                starlink_data = starlink_collector.get_status()
                
                # Collect satellite constellation data (less frequently)
                if hasattr(self, '_satellite_counter'):
                    self._satellite_counter += 1
                else:
                    self._satellite_counter = 0
                    # Initialize satellite data on first run
                    if not hasattr(self, '_cached_satellite_data'):
                        self._cached_satellite_data = {}
                
                # Update satellite data every iteration (10 seconds) for real-time movement
                if self._satellite_counter % 1 == 0 or not hasattr(self, '_cached_satellite_data') or not self._cached_satellite_data:
                    print("🛰️ Calculating real-time satellite positions...")
                    self._cached_satellite_data = satellite_collector.get_starlink_constellation()
                    print(f"🛰️ Updated satellite positions: {self._cached_satellite_data.get('positions_calculated', 0)} calculated")
                    print(f"📊 Data source: {self._cached_satellite_data.get('data_source', 'unknown')}")
                
                satellite_data = self._cached_satellite_data
                
                # Combine all data
                combined_data = {
                    'timestamp': datetime.now().isoformat(),
                    'starlink': starlink_data,
                    'satellites': satellite_data,
                    'monitoring_active': True,
                }
                
                # Update global state
                latest_data = combined_data
                
                # Emit to all connected clients
                socketio.emit('data_update', combined_data)
                
                # Log status
                if starlink_data.get('connected', False):
                    quality = starlink_data.get('connection_quality', 'Unknown')
                    latency = starlink_data.get('ping_latency_ms', 0)
                    print(f"📡 Starlink: {quality} | {latency}ms latency")
                else:
                    error = starlink_data.get('error', 'Unknown error')
                    print(f"❌ Starlink: {error}")
                    
                # Wait before next update
                time.sleep(self.update_interval)
                
            except Exception as e:
                print(f"❗ Monitoring error: {e}")
                time.sleep(5)  # Wait a bit before retrying

# Initialize monitoring service
monitor = MonitoringService()

# REST API Routes
@app.route('/api/status')
def get_status():
    """Get current status of all systems."""
    try:
        starlink_data = starlink_collector.get_status()
        
        response = {
            'timestamp': datetime.now().isoformat(),
            'starlink': starlink_data,
            'monitoring_active': monitoring_active,
            'server_status': 'running'
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/monitoring/start', methods=['POST'])
def start_monitoring():
    """Start the monitoring service."""
    global monitoring_active
    
    try:
        monitor.start()
        monitoring_active = True
        
        return jsonify({
            'message': 'Monitoring started',
            'monitoring_active': True,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/monitoring/stop', methods=['POST'])
def stop_monitoring():
    """Stop the monitoring service."""
    global monitoring_active
    
    try:
        monitor.stop()
        monitoring_active = False
        
        return jsonify({
            'message': 'Monitoring stopped',
            'monitoring_active': False,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/satellites')
def get_satellites():
    """Get current Starlink satellite constellation positions."""
    try:
        # Get real satellite data
        satellite_data = satellite_collector.get_starlink_constellation()
        return jsonify(satellite_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/satellites/catalog')
def get_satellite_catalog():
    """Get detailed catalog information for Starlink satellites."""
    try:
        # Only available with Space-Track
        if hasattr(satellite_collector, 'get_satellite_catalog_info'):
            catalog_info = satellite_collector.get_satellite_catalog_info()
            return jsonify({
                'count': len(catalog_info),
                'satellites': catalog_info,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'error': 'Catalog info only available with Space-Track data source',
                'hint': 'Set SATELLITE_DATA_SOURCE=spacetrack in your environment'
            }), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/satellites/visible')
def get_visible_satellites():
    """Get satellites visible from a specific location."""
    try:
        lat = float(request.args.get('lat', 0))
        lon = float(request.args.get('lon', 0))
        min_elevation = float(request.args.get('elevation', 10))
        
        visible_sats = satellite_collector.get_satellites_over_location(lat, lon, min_elevation)
        
        return jsonify({
            'observer_location': {'lat': lat, 'lon': lon},
            'min_elevation_degrees': min_elevation,
            'visible_count': len(visible_sats),
            'satellites': visible_sats,
            'timestamp': datetime.now().isoformat()
        })
        
    except ValueError as e:
        return jsonify({'error': 'Invalid coordinates provided'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/latest')
def get_latest_data():
    """Get the latest collected data."""
    global latest_data
    
    if latest_data:
        return jsonify(latest_data)
    else:
        return jsonify({
            'message': 'No data available yet',
            'timestamp': datetime.now().isoformat()
        })

# WebSocket Events
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    global monitoring_active
    
    print(f"🔌 Client connected: {request.sid}")
    
    # Send current status to new client
    if latest_data:
        emit('data_update', latest_data)
    
    # Auto-start monitoring if not already running
    if not monitoring_active:
        monitor.start()
        monitoring_active = True
        
@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print(f"🔌 Client disconnected: {request.sid}")

@socketio.on('request_update')
def handle_update_request():
    """Handle manual update requests from client."""
    try:
        starlink_data = starlink_collector.get_status()
        
        response = {
            'timestamp': datetime.now().isoformat(),
            'starlink': starlink_data,
            'monitoring_active': monitoring_active,
        }
        
        emit('data_update', response)
        
    except Exception as e:
        emit('error', {'message': str(e)})

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print("🛰️  Starting Starlink Monitor Backend")
    print("📡 Testing Starlink connection...")
    
    # Test Starlink connection on startup
    test_data = starlink_collector.get_status()
    if test_data.get('connected', False):
        print(f"✅ Starlink dish reachable - Quality: {test_data.get('connection_quality', 'Unknown')}")
    else:
        print(f"❌ Starlink dish not reachable: {test_data.get('error', 'Unknown error')}")
        print("💡 Make sure you're connected to your Starlink network")
    
    print("🚀 Starting server on http://localhost:5050")
    print("📊 API available at http://localhost:5050/api/status")
    
    # Start the Flask-SocketIO server
    socketio.run(
        app,
        host='0.0.0.0',
        port=5511,
        debug=True,
        allow_unsafe_werkzeug=True
    )
