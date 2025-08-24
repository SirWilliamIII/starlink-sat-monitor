from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
import time
import json
from datetime import datetime

from collectors.starlink import StarlinkCollector
from collectors.satellites import SatelliteCollector

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'starlink-monitor-secret-key'

# Enable CORS for frontend
CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000"])

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins=["http://localhost:3000", "http://127.0.0.1:3000"])

# Initialize collectors
starlink_collector = StarlinkCollector()
satellite_collector = SatelliteCollector()

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
                satellite_data = {}
                if hasattr(self, '_satellite_counter'):
                    self._satellite_counter += 1
                else:
                    self._satellite_counter = 0
                
                # Update satellite data every 6th iteration (1 minute)
                if self._satellite_counter % 6 == 0:
                    # Temporarily use sample data instead of real satellite collection
                    satellite_data = {
                        'timestamp': datetime.now().isoformat(),
                        'satellite_count': 3,
                        'positions_calculated': 3,
                        'positions': [
                            {'name': 'STARLINK-DEMO-1', 'lat': 40.0, 'lng': -100.0, 'altitude_km': 550},
                            {'name': 'STARLINK-DEMO-2', 'lat': 50.0, 'lng': -110.0, 'altitude_km': 550},
                            {'name': 'STARLINK-DEMO-3', 'lat': 30.0, 'lng': -90.0, 'altitude_km': 550}
                        ],
                        'data_source': 'sample_monitoring'
                    }
                    print(f"🛰️ Using sample satellite data: {satellite_data.get('positions_calculated', 0)} positions")
                
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
        # For now, return sample data to avoid hanging
        from datetime import datetime
        
        sample_data = {
            'timestamp': datetime.now().isoformat(),
            'satellite_count': 8,
            'positions_calculated': 8,
            'positions': [
                {'name': 'STARLINK-1001', 'norad_id': 50001, 'lat': 45.0, 'lng': -120.0, 'altitude_km': 550, 'velocity_kmh': 27000},
                {'name': 'STARLINK-1002', 'norad_id': 50002, 'lat': 30.0, 'lng': -100.0, 'altitude_km': 550, 'velocity_kmh': 27000},
                {'name': 'STARLINK-1003', 'norad_id': 50003, 'lat': 60.0, 'lng': -80.0, 'altitude_km': 550, 'velocity_kmh': 27000},
                {'name': 'STARLINK-1004', 'norad_id': 50004, 'lat': 20.0, 'lng': -60.0, 'altitude_km': 550, 'velocity_kmh': 27000},
                {'name': 'STARLINK-1005', 'norad_id': 50005, 'lat': 50.0, 'lng': -40.0, 'altitude_km': 550, 'velocity_kmh': 27000},
                {'name': 'STARLINK-1006', 'norad_id': 50006, 'lat': 35.0, 'lng': 10.0, 'altitude_km': 550, 'velocity_kmh': 27000},
                {'name': 'STARLINK-1007', 'norad_id': 50007, 'lat': 55.0, 'lng': 30.0, 'altitude_km': 550, 'velocity_kmh': 27000},
                {'name': 'STARLINK-1008', 'norad_id': 50008, 'lat': 25.0, 'lng': 50.0, 'altitude_km': 550, 'velocity_kmh': 27000}
            ],
            'data_source': 'sample_data_api',
            'tle_age_hours': 0,
            'note': 'Using sample data for demo - real TLE disabled temporarily'
        }
        
        return jsonify(sample_data)
        
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
        port=5050,
        debug=True,
        allow_unsafe_werkzeug=True
    )
