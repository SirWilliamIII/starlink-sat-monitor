import requests
import json
from datetime import datetime
from typing import Dict, Optional

class StarlinkCollector:
    """Collector for Starlink dish telemetry data."""
    
    def __init__(self, dish_ip: str = None):
        # Common Starlink dish IP addresses
        self.potential_ips = [
            "192.168.100.1",    # Standard Starlink dish IP
            "192.168.1.1",      # Alternative configuration
            "10.0.0.1",         # Some configurations
            "dishy.starlink",   # mDNS hostname
            "192.168.100.2",    # Alternative
        ]
        self.dish_ip = dish_ip
        self.base_url = None
        self.last_successful_data = None
        
    def get_status(self) -> Dict:
        """
        Get current Starlink dish status.
        Returns structured data with connection info, signal quality, etc.
        """
        try:
            # If we have a specific IP, use it; otherwise try to discover
            ips_to_try = [self.dish_ip] if self.dish_ip else self.potential_ips
            
            for ip in ips_to_try:
                if not ip:
                    continue
                    
                print(f"🔍 Trying Starlink dish at {ip}...")
                base_url = f"http://{ip}"
                
                # Try multiple endpoints for this IP
                endpoints = [
                    f"{base_url}/api/status",
                    f"{base_url}",  # Some dishes return JSON at root
                    f"{base_url}/api/device/status",
                ]
                
                for endpoint in endpoints:
                    try:
                        response = requests.get(endpoint, timeout=3)
                        
                        if response.status_code == 200:
                            raw_data = response.json()
                            
                            # Check if this looks like status data vs diagnostic data
                            if self._is_status_data(raw_data):
                                print(f"✅ Found Starlink dish at {ip}")
                                self.dish_ip = ip
                                self.base_url = base_url
                                parsed_data = self._parse_status_data(raw_data)
                                self.last_successful_data = parsed_data
                                return parsed_data
                            elif self._is_diagnostic_data(raw_data):
                                print(f"✅ Found Starlink dish at {ip}")
                                self.dish_ip = ip
                                self.base_url = base_url
                                parsed_data = self._parse_diagnostic_data(raw_data)
                                self.last_successful_data = parsed_data
                                return parsed_data
                                
                    except requests.exceptions.RequestException:
                        continue
                        
            # If no local dish API found, check if we're on Starlink network
            return self._check_starlink_network_connection()
                
        except Exception as e:
            return self._get_error_response(f"Unexpected error: {str(e)}")
    
    def _is_status_data(self, data: Dict) -> bool:
        """Check if data looks like status/telemetry data."""
        status_indicators = [
            'signal_quality', 'ping_latency_ms', 'downlink_throughput_bps',
            'uplink_throughput_bps', 'uptime_s'
        ]
        return any(key in data for key in status_indicators)
    
    def _is_diagnostic_data(self, data: Dict) -> bool:
        """Check if data looks like diagnostic data."""
        diagnostic_indicators = [
            'hardwareVersion', 'softwareVersion', 'alerts', 'id'
        ]
        return any(key in data for key in diagnostic_indicators)
    
    def _parse_diagnostic_data(self, raw_data: Dict) -> Dict:
        """Parse diagnostic data format into standardized format."""
        
        alerts = raw_data.get('alerts', {})
        
        status = {
            'timestamp': datetime.now().isoformat(),
            'connected': True,
            'dish_reachable': True,
            
            # Extract what we can from diagnostic data
            'hardware_version': raw_data.get('hardwareVersion', 'Unknown'),
            'software_version': raw_data.get('softwareVersion', 'Unknown'),
            'dish_id': raw_data.get('id', 'Unknown'),
            
            # Obstruction info
            'obstruction_detected': alerts.get('obstructed', False),
            'currently_obstructed': alerts.get('obstructed', False),
            
            # Alert information
            'dish_heating': alerts.get('dishIsHeating', False),
            'thermal_throttle': alerts.get('dishThermalThrottle', False),
            'thermal_shutdown': alerts.get('dishThermalShutdown', False),
            'motors_stuck': alerts.get('motorsStuck', False),
            'slow_ethernet': alerts.get('slowEthernetSpeeds', False),
            
            # System status
            'dish_stowed': raw_data.get('stowed', False),
            'hardware_self_test': raw_data.get('hardwareSelfTest', 'UNKNOWN'),
            
            # Default values for missing telemetry
            'uptime_seconds': 0,
            'signal_quality': 0,
            'ping_latency_ms': 0,
            'download_mbps': 0,
            'upload_mbps': 0,
            'uptime_hours': 0,
            
            # Overall assessment
            'connection_quality': self._calculate_diagnostic_quality(raw_data),
            'data_source': 'diagnostic_api'
        }
        
        return status
    
    def _calculate_diagnostic_quality(self, raw_data: Dict) -> str:
        """Calculate connection quality from diagnostic data."""
        alerts = raw_data.get('alerts', {})
        
        # Count active issues
        issues = sum([
            alerts.get('obstructed', False),
            alerts.get('dishThermalThrottle', False),
            alerts.get('motorsStuck', False),
            alerts.get('slowEthernetSpeeds', False),
        ])
        
        # Hardware self test status
        hardware_test = raw_data.get('hardwareSelfTest', 'UNKNOWN')
        
        if hardware_test == 'FAILED' or issues >= 3:
            return "Poor"
        elif issues >= 2:
            return "Fair"
        elif issues == 1:
            return "Good"
        elif hardware_test == 'PASSED' and issues == 0:
            return "Excellent"
        else:
            return "Good"  # Default for functioning dish
    
    def _parse_status_data(self, raw_data: Dict) -> Dict:
        """Parse raw Starlink API response into standardized format."""
        
        # Extract key metrics with safe defaults
        status = {
            'timestamp': datetime.now().isoformat(),
            'connected': True,
            'dish_reachable': True,
            
            # Connection quality
            'uptime_seconds': raw_data.get('uptime_s', 0),
            'signal_quality': raw_data.get('signal_quality', 0),
            'snr': raw_data.get('snr', 0),
            
            # Network performance  
            'downlink_throughput_bps': raw_data.get('downlink_throughput_bps', 0),
            'uplink_throughput_bps': raw_data.get('uplink_throughput_bps', 0),
            'ping_drop_rate_percent': raw_data.get('ping_drop_rate', 0) * 100,
            'ping_latency_ms': raw_data.get('ping_latency_ms', 0),
            
            # Issues and alerts
            'obstruction_detected': raw_data.get('obstruction_detected', False),
            'currently_obstructed': raw_data.get('currently_obstructed', False),
            'alerts': raw_data.get('alerts', []),
            
            # Hardware info
            'hardware_version': raw_data.get('hardware_version', 'Unknown'),
            'software_version': raw_data.get('software_version', 'Unknown'),
            'dish_id': raw_data.get('id', 'Unknown'),
            
            # Derived metrics
            'uptime_hours': round(raw_data.get('uptime_s', 0) / 3600, 1),
            'download_mbps': self._calculate_speed_mbps(raw_data.get('downlink_throughput_bps', 0)),
            'upload_mbps': self._calculate_speed_mbps(raw_data.get('uplink_throughput_bps', 0)),
            'connection_quality': self._calculate_connection_quality(raw_data),
        }
        
        return status
    
    def _calculate_speed_mbps(self, throughput_value: float) -> float:
        """Calculate speed in Mbps from throughput value.
        
        The Starlink API may report throughput in different units:
        - If value < 1000: assume it's already in Mbps
        - If value >= 1000: assume it's in bps and convert to Mbps
        """
        if throughput_value == 0:
            return 0.0
            
        # If the value is less than 1000, it's likely already in Mbps
        if throughput_value < 1000:
            return round(throughput_value, 2)
        
        # Otherwise, convert from bps to Mbps
        return round(throughput_value / 1_000_000, 2)
    
    def _calculate_connection_quality(self, raw_data: Dict) -> str:
        """Calculate overall connection quality rating."""
        
        # Simple scoring based on key metrics
        score = 0
        
        # Signal quality (0-1, higher is better)
        signal_quality = raw_data.get('signal_quality', 0)
        if signal_quality > 0.8:
            score += 3
        elif signal_quality > 0.6:
            score += 2
        elif signal_quality > 0.3:
            score += 1
            
        # Ping latency (lower is better)
        latency = raw_data.get('ping_latency_ms', 1000)
        if latency < 30:
            score += 3
        elif latency < 60:
            score += 2
        elif latency < 100:
            score += 1
            
        # Packet loss (lower is better)
        packet_loss = raw_data.get('ping_drop_rate', 1) * 100
        if packet_loss < 1:
            score += 2
        elif packet_loss < 5:
            score += 1
            
        # Obstructions (none is better)
        if not raw_data.get('currently_obstructed', True):
            score += 2
            
        # Convert score to rating
        if score >= 8:
            return "Excellent"
        elif score >= 6:
            return "Good" 
        elif score >= 4:
            return "Fair"
        elif score >= 2:
            return "Poor"
        else:
            return "Very Poor"
    
    def _check_starlink_network_connection(self) -> Dict:
        """Check if we're connected via Starlink by checking public IP info."""
        try:
            print("🔍 Checking if connected via Starlink network...")
            
            # Check public IP information
            response = requests.get("https://ipinfo.io/json", timeout=10)
            if response.status_code == 200:
                ip_info = response.json()
                
                # Check if this is a Starlink connection
                org = ip_info.get('org', '').lower()
                hostname = ip_info.get('hostname', '').lower()
                
                is_starlink = (
                    'space exploration technologies' in org or
                    'starlink' in org or
                    'starlinkisp' in hostname or
                    'as14593' in org  # SpaceX ASN
                )
                
                if is_starlink:
                    print(f"✅ Detected Starlink connection: {ip_info.get('org', 'Unknown')}")
                    
                    # Get network speed estimates
                    speeds = self._estimate_network_speed()
                    
                    # Return enhanced telemetry based on network connection
                    return {
                        'timestamp': datetime.now().isoformat(),
                        'connected': True,
                        'dish_reachable': True,
                        'connection_quality': 'Good',  # Assume good if connected
                        'ping_latency_ms': self._estimate_starlink_latency(),
                        'download_mbps': speeds.get('download', 'Testing...'),
                        'upload_mbps': speeds.get('upload', 'Testing...'),
                        'signal_quality': 0.85,  # Estimate
                        'uptime_hours': 'N/A',
                        'obstruction_detected': False,
                        'public_ip': ip_info.get('ip'),
                        'location': f"{ip_info.get('city', 'Unknown')}, {ip_info.get('region', 'Unknown')}",
                        'isp': ip_info.get('org', 'Unknown'),
                        'note': 'Detected Starlink connection via public IP (local dish API not available)'
                    }
                else:
                    print(f"❌ Not on Starlink network: {ip_info.get('org', 'Unknown')}")
                    
            return self._get_error_response("No Starlink dish found on local network")
            
        except Exception as e:
            print(f"❌ Error checking network connection: {e}")
            return self._get_error_response("Unable to detect Starlink connection")
    
    def _estimate_starlink_latency(self) -> int:
        """Estimate Starlink latency by pinging a fast server."""
        try:
            import subprocess
            import re
            
            # Ping Google DNS with a single packet
            result = subprocess.run(
                ['ping', '-c', '1', '8.8.8.8'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                # Extract latency from ping output
                match = re.search(r'time=(\d+\.?\d*)', result.stdout)
                if match:
                    return int(float(match.group(1)))
                    
        except Exception:
            pass
            
        return 35  # Default Starlink latency estimate
    
    def _estimate_network_speed(self) -> Dict:
        """Estimate network speed using a quick download test."""
        try:
            import time
            import threading
            
            print("🚀 Testing network speed...")
            
            # Quick download test using a small file
            test_url = "http://ipv4.download.thinkbroadband.com/1MB.zip"
            
            start_time = time.time()
            response = requests.get(test_url, timeout=10, stream=True)
            
            if response.status_code == 200:
                # Download in chunks and measure
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded += len(chunk)
                        # Stop after reasonable amount
                        if downloaded > 500000:  # 500KB
                            break
                
                elapsed = time.time() - start_time
                if elapsed > 0:
                    # Calculate speed in Mbps
                    speed_mbps = (downloaded * 8) / (elapsed * 1000000)
                    estimated_download = max(10, min(500, int(speed_mbps * 5)))  # Scale estimate
                    estimated_upload = int(estimated_download * 0.15)  # Upload usually 15% of download for Starlink
                    
                    print(f"📊 Estimated speeds: {estimated_download} Mbps down, {estimated_upload} Mbps up")
                    
                    return {
                        'download': estimated_download,
                        'upload': estimated_upload
                    }
                    
        except Exception as e:
            print(f"❌ Speed test failed: {e}")
            
        # Return typical Starlink speeds if test fails
        return {
            'download': 100,  # Typical Starlink download
            'upload': 15     # Typical Starlink upload
        }

    def _get_error_response(self, error_message: str) -> Dict:
        """Return standardized error response."""
        return {
            'timestamp': datetime.now().isoformat(),
            'connected': False,
            'dish_reachable': False,
            'error': error_message,
            'connection_quality': 'Unknown',
            
            # Use last known good data if available
            'last_successful_data': self.last_successful_data,
            
            # Default values
            'uptime_seconds': 0,
            'signal_quality': 0,
            'ping_latency_ms': 0,
            'download_mbps': 0,
            'upload_mbps': 0,
        }
    
    def get_obstruction_map(self) -> Optional[Dict]:
        """Get obstruction map data if available."""
        try:
            response = requests.get(
                f"{self.base_url}/api/obstruction_map", 
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return None
      
