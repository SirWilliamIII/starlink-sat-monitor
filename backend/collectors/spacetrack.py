import requests
import os
import json
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import time
from sgp4.api import Satrec, jday
from .satellites import SatellitePosition, SatelliteCollector

class SpaceTrackCollector(SatelliteCollector):
    """Collector for Space-Track.org satellite data with authentication."""
    
    def __init__(self, username: str = None, password: str = None):
        super().__init__()
        self.base_url = "https://www.space-track.org"
        self.username = username or os.environ.get('SPACETRACK_USERNAME')
        self.password = password or os.environ.get('SPACETRACK_PASSWORD')
        self.session = None
        self.auth_token = None
        self.auth_time = None
        self.auth_duration = 3600  # Auth token valid for 1 hour
        self.satellite_records = {}  # Store SGP4 satellite records
        
    def authenticate(self) -> bool:
        """Authenticate with Space-Track.org API."""
        if not self.username or not self.password:
            print("❌ Space-Track credentials not configured")
            print("💡 Set SPACETRACK_USERNAME and SPACETRACK_PASSWORD environment variables")
            return False
            
        try:
            # Check if we have a valid auth token
            if self.auth_token and self.auth_time:
                if time.time() - self.auth_time < self.auth_duration:
                    return True
            
            print("🔐 Authenticating with Space-Track.org...")
            
            # Create new session
            self.session = requests.Session()
            
            # Login
            auth_data = {
                'identity': self.username,
                'password': self.password
            }
            
            response = self.session.post(
                f"{self.base_url}/ajaxauth/login",
                data=auth_data,
                timeout=10
            )
            
            if response.status_code == 200:
                self.auth_token = self.session.cookies.get('chocolatechip')
                self.auth_time = time.time()
                print("✅ Space-Track authentication successful")
                return True
            else:
                print(f"❌ Space-Track authentication failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error authenticating with Space-Track: {e}")
            return False
    
    def fetch_starlink_tle_data(self) -> bool:
        """Fetch Starlink TLE data from Space-Track.org."""
        try:
            # Authenticate first
            if not self.authenticate():
                return False
            
            print("🛰️ Fetching Starlink data from Space-Track.org...")
            
            # Query for current Starlink satellites (high NORAD IDs = newer)
            query_url = (
                f"{self.base_url}/basicspacedata/query/class/tle_latest/"
                "ORDINAL/1/"  # Latest TLE only
                "OBJECT_NAME/~~STARLINK/"  # Name contains STARLINK
                "NORAD_CAT_ID/>50000/"  # High NORAD IDs (newer satellites)
                "orderby/NORAD_CAT_ID desc/"  # Get newest first
                "limit/50/"  # Limit to 50 satellites for testing
                "format/json"
            )
            
            print(f"🔗 Query URL: {query_url}")
            response = self.session.get(query_url, timeout=30)
            
            if response.status_code != 200:
                print(f"❌ Failed to fetch data: HTTP {response.status_code}")
                print(f"📝 Response: {response.text[:500]}")
                return False
            
            # Parse JSON response
            tle_data = response.json()
            
            if not tle_data:
                print("❌ No Starlink satellites found")
                return False
            
            # Convert to our format and create SGP4 records
            satellites = []
            satellite_records = {}
            
            for sat in tle_data:
                try:
                    name = sat['OBJECT_NAME']
                    line1 = sat['TLE_LINE1']
                    line2 = sat['TLE_LINE2']
                    norad_id = int(sat['NORAD_CAT_ID'])
                    
                    # Create SGP4 satellite record for accurate orbit propagation
                    satellite_record = Satrec.twoline2rv(line1, line2)
                    
                    satellites.append({
                        'name': name,
                        'line1': line1,
                        'line2': line2,
                        'norad_id': norad_id,
                        'epoch': self._parse_tle_epoch(line1[18:32])
                    })
                    
                    satellite_records[norad_id] = satellite_record
                    
                except (KeyError, ValueError) as e:
                    continue
            
            self.starlink_satellites = satellites
            self.satellite_records = satellite_records
            self.last_tle_fetch = time.time()
            
            print(f"✅ Successfully loaded {len(satellites)} Starlink satellites from Space-Track")
            print(f"📡 Created {len(satellite_records)} SGP4 satellite records")
            return True
            
        except requests.exceptions.Timeout:
            print("❌ Timeout fetching from Space-Track (slow connection)")
            return False
        except Exception as e:
            print(f"❌ Error fetching from Space-Track: {e}")
            return False
    
    def get_satellite_catalog_info(self) -> List[Dict]:
        """Get detailed catalog information for Starlink satellites."""
        try:
            if not self.authenticate():
                return []
            
            print("📊 Fetching satellite catalog information...")
            
            # Query satellite catalog for Starlink
            query_url = (
                f"{self.base_url}/basicspacedata/query/class/satcat/"
                "OBJECT_NAME/~~STARLINK/"
                "COUNTRY/US/"
                "CURRENT/Y/"
                "orderby/LAUNCH desc/"
                "limit/100/"
                "format/json"
            )
            
            response = self.session.get(query_url, timeout=30)
            
            if response.status_code != 200:
                return []
            
            catalog_data = response.json()
            
            # Format catalog info
            satellites = []
            for sat in catalog_data:
                satellites.append({
                    'norad_id': sat.get('NORAD_CAT_ID'),
                    'name': sat.get('OBJECT_NAME'),
                    'launch_date': sat.get('LAUNCH'),
                    'site': sat.get('SITE'),
                    'decay_date': sat.get('DECAY'),
                    'period_minutes': sat.get('PERIOD'),
                    'inclination_deg': sat.get('INCLINATION'),
                    'apogee_km': sat.get('APOGEE'),
                    'perigee_km': sat.get('PERIGEE')
                })
            
            return satellites
            
        except Exception as e:
            print(f"❌ Error fetching catalog info: {e}")
            return []
    
    def calculate_realtime_positions(self, timestamp: datetime = None) -> List[Dict]:
        """Calculate real-time satellite positions using SGP4."""
        if not self.satellite_records:
            return []
        
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        # Convert to Julian date for SGP4
        jd, fr = self._datetime_to_jd(timestamp)
        
        positions = []
        
        for norad_id, sat_record in self.satellite_records.items():
            try:
                # Find satellite info
                sat_info = next((s for s in self.starlink_satellites if s['norad_id'] == norad_id), None)
                if not sat_info:
                    continue
                
                # Calculate position using SGP4
                error_code, r, v = sat_record.sgp4(jd, fr)
                
                if error_code != 0:
                    print(f"SGP4 error {error_code} for satellite {norad_id}")
                    continue
                
                # Convert ECI coordinates to lat/lon/alt
                lat, lon, alt = self._eci_to_geodetic(r, timestamp)
                
                # Calculate velocity in km/h
                velocity_kmh = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2) * 3.6
                
                positions.append({
                    'name': sat_info['name'],
                    'norad_id': norad_id,
                    'lat': lat,
                    'lng': lon,
                    'altitude_km': alt,
                    'velocity_kmh': velocity_kmh,
                    'timestamp': timestamp.isoformat()
                })
                
            except Exception as e:
                continue
        
        return positions
    
    def get_starlink_constellation(self) -> Dict:
        """Get current positions of Starlink satellites using real-time SGP4."""
        try:
            # Fetch latest TLE data if cache is stale
            if self._should_update_tle():
                success = self.fetch_starlink_tle_data()
                if not success:
                    # Return sample data for demo if fetching fails
                    return self._get_sample_satellite_data()
            
            # Calculate real-time positions
            current_time = datetime.now(timezone.utc)
            positions = self.calculate_realtime_positions(current_time)
            
            return {
                'timestamp': current_time.isoformat(),
                'satellite_count': len(self.starlink_satellites),
                'positions_calculated': len(positions),
                'positions': positions,
                'data_source': 'spacetrack_sgp4',
                'tle_age_hours': self._get_tle_age_hours()
            }
            
        except Exception as e:
            print(f"Error in get_starlink_constellation: {e}")
            return self._get_sample_satellite_data()
    
    def _datetime_to_jd(self, dt: datetime) -> Tuple[float, float]:
        """Convert datetime to Julian date for SGP4."""
        # SGP4 expects separate Julian day and fraction
        jd, fr = jday(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
        
        return jd, fr
    
    def _eci_to_geodetic(self, r: Tuple[float, float, float], timestamp: datetime) -> Tuple[float, float, float]:
        """Convert ECI coordinates to geodetic lat/lon/alt."""
        x, y, z = r
        
        # Earth radius and flattening
        a = 6378.137  # Earth semi-major axis in km
        f = 1.0 / 298.257223563  # Earth flattening
        e2 = 2 * f - f * f  # First eccentricity squared
        
        # Calculate longitude
        lon = math.atan2(y, x)
        
        # Calculate latitude (iterative method)
        p = math.sqrt(x**2 + y**2)
        lat = math.atan2(z, p * (1 - e2))
        
        for _ in range(5):  # Usually converges quickly
            N = a / math.sqrt(1 - e2 * math.sin(lat)**2)
            alt = p / math.cos(lat) - N
            lat = math.atan2(z, p * (1 - e2 * N / (N + alt)))
        
        # Final altitude calculation
        N = a / math.sqrt(1 - e2 * math.sin(lat)**2)
        alt = p / math.cos(lat) - N
        
        # Convert to degrees
        lat_deg = math.degrees(lat)
        lon_deg = math.degrees(lon)
        
        # Normalize longitude to [-180, 180]
        while lon_deg > 180:
            lon_deg -= 360
        while lon_deg < -180:
            lon_deg += 360
        
        return lat_deg, lon_deg, alt
    
    def _should_update_tle(self) -> bool:
        """Check if TLE data needs to be refreshed."""
        if not self.last_tle_fetch:
            return True
        
        time_since_fetch = time.time() - self.last_tle_fetch
        return time_since_fetch > self.tle_cache_duration
    
    def _fetch_starlink_tle_data(self) -> bool:
        """Override parent method to use Space-Track."""
        return self.fetch_starlink_tle_data()

# Example usage
if __name__ == "__main__":
    # Test the collector
    collector = SpaceTrackCollector()
    
    # Test authentication
    if collector.authenticate():
        print("✅ Authentication test passed")
        
        # Test fetching satellites
        data = collector.get_starlink_constellation()
        print(f"📊 Found {data['satellite_count']} satellites")
        print(f"📍 Calculated {data['positions_calculated']} positions")
        
        # Test catalog info
        catalog = collector.get_satellite_catalog_info()
        print(f"📚 Retrieved {len(catalog)} catalog entries")
    else:
        print("❌ Authentication test failed")