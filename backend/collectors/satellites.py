import requests
import math
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class SatellitePosition:
    """Represents a satellite's position at a specific time."""
    name: str
    norad_id: int
    latitude: float
    longitude: float
    altitude_km: float
    velocity_kmh: float
    timestamp: datetime

class SatelliteCollector:
    """Collector for real-time satellite tracking data."""
    
    def __init__(self):
        self.celestrak_base = "https://celestrak.org/NORAD/elements/"
        self.starlink_satellites = []
        self.last_tle_fetch = None
        self.tle_cache_duration = 3600  # Cache TLE data for 1 hour
        
    def get_starlink_constellation(self) -> Dict:
        """Get current positions of Starlink satellites."""
        try:
            # Fetch latest TLE data if cache is stale
            if self._should_update_tle():
                success = self._fetch_starlink_tle_data()
                if not success:
                    # Return sample data for demo if fetching fails
                    return self._get_sample_satellite_data()
            
            if not self.starlink_satellites:
                return self._get_sample_satellite_data()
            
            # Calculate current positions
            current_time = datetime.now(timezone.utc)
            positions = []
            
            # Limit to 20 satellites for performance
            sample_satellites = self.starlink_satellites[:20]
            
            for sat in sample_satellites:
                try:
                    position = self._calculate_satellite_position(sat, current_time)
                    if position:
                        positions.append({
                            'name': position.name,
                            'norad_id': position.norad_id,
                            'lat': position.latitude,
                            'lng': position.longitude,
                            'altitude_km': position.altitude_km,
                            'velocity_kmh': position.velocity_kmh,
                            'timestamp': position.timestamp.isoformat()
                        })
                except Exception as e:
                    print(f"Error calculating position for {sat.get('name', 'unknown')}: {e}")
                    continue
            
            return {
                'timestamp': current_time.isoformat(),
                'satellite_count': len(self.starlink_satellites),
                'positions_calculated': len(positions),
                'positions': positions,
                'data_source': 'celestrak_tle',
                'tle_age_hours': self._get_tle_age_hours()
            }
            
        except Exception as e:
            print(f"Error in get_starlink_constellation: {e}")
            return self._get_sample_satellite_data()
    
    def _get_sample_satellite_data(self) -> Dict:
        """Return sample satellite data for demo purposes."""
        current_time = datetime.now(timezone.utc)
        
        # Generate some sample satellite positions
        sample_positions = []
        for i in range(10):
            sample_positions.append({
                'name': f'STARLINK-{1000 + i}',
                'norad_id': 50000 + i,
                'lat': -60 + (i * 15),  # Spread across latitudes
                'lng': -180 + (i * 36),  # Spread across longitudes  
                'altitude_km': 550,
                'velocity_kmh': 27000,
                'timestamp': current_time.isoformat()
            })
        
        return {
            'timestamp': current_time.isoformat(),
            'satellite_count': 10,
            'positions_calculated': 10,
            'positions': sample_positions,
            'data_source': 'sample_data',
            'tle_age_hours': 0,
            'note': 'Sample data - real TLE fetch failed'
        }
    
    def get_satellites_over_location(self, lat: float, lon: float, elevation_degrees: float = 10) -> List[Dict]:
        """Get satellites currently visible from a specific location."""
        try:
            current_time = datetime.now(timezone.utc)
            visible_satellites = []
            
            for sat in self.starlink_satellites:
                try:
                    position = self._calculate_satellite_position(sat, current_time)
                    if not position:
                        continue
                    
                    # Calculate elevation angle from observer location
                    elevation = self._calculate_elevation_angle(
                        lat, lon, 0,  # observer location (altitude = 0)
                        position.latitude, position.longitude, position.altitude_km
                    )
                    
                    if elevation >= elevation_degrees:
                        azimuth = self._calculate_azimuth(
                            lat, lon, position.latitude, position.longitude
                        )
                        
                        visible_satellites.append({
                            'name': position.name,
                            'norad_id': position.norad_id,
                            'elevation_degrees': elevation,
                            'azimuth_degrees': azimuth,
                            'distance_km': self._calculate_distance(
                                lat, lon, 0, position.latitude, position.longitude, position.altitude_km
                            ),
                            'lat': position.latitude,
                            'lng': position.longitude,
                            'altitude_km': position.altitude_km
                        })
                        
                except Exception as e:
                    continue
            
            # Sort by elevation (highest first)
            visible_satellites.sort(key=lambda x: x['elevation_degrees'], reverse=True)
            
            return visible_satellites
            
        except Exception as e:
            print(f"Error finding visible satellites: {e}")
            return []
    
    def _should_update_tle(self) -> bool:
        """Check if TLE data needs to be refreshed."""
        if not self.last_tle_fetch:
            return True
        
        time_since_fetch = time.time() - self.last_tle_fetch
        return time_since_fetch > self.tle_cache_duration
    
    def _fetch_starlink_tle_data(self) -> bool:
        """Fetch latest Starlink TLE data from CelesTrak."""
        try:
            print("🛰️ Fetching latest Starlink constellation data...")
            
            # CelesTrak Starlink constellation endpoint
            response = requests.get(
                f"{self.celestrak_base}supplemental/starlink.txt", 
                timeout=10,  # Shorter timeout
                stream=True  # Stream large file
            )
            
            if response.status_code != 200:
                print(f"Failed to fetch TLE data: HTTP {response.status_code}")
                return False
            
            # Read content with progress indication
            content = ""
            size = 0
            for chunk in response.iter_content(chunk_size=8192, decode_unicode=True):
                if chunk:
                    content += chunk
                    size += len(chunk)
                    if size > 50_000_000:  # 50MB limit
                        print("❌ TLE file too large, aborting")
                        return False
            
            # Parse TLE format (3 lines per satellite)
            lines = content.strip().split('\n')
            satellites = []
            
            print(f"📡 Processing {len(lines)} lines of TLE data...")
            
            for i in range(0, len(lines), 3):
                if i + 2 < len(lines):
                    name = lines[i].strip()
                    line1 = lines[i + 1].strip()
                    line2 = lines[i + 2].strip()
                    
                    # Basic validation
                    if len(line1) == 69 and len(line2) == 69 and line1[0] == '1' and line2[0] == '2':
                        try:
                            satellites.append({
                                'name': name,
                                'line1': line1,
                                'line2': line2,
                                'norad_id': int(line1[2:7]),
                                'epoch': self._parse_tle_epoch(line1[18:32])
                            })
                        except (ValueError, IndexError):
                            continue  # Skip invalid entries
            
            if len(satellites) == 0:
                print("❌ No valid satellite data found")
                return False
                
            self.starlink_satellites = satellites
            self.last_tle_fetch = time.time()
            
            print(f"✅ Successfully loaded {len(satellites)} Starlink satellites")
            return True
            
        except requests.exceptions.Timeout:
            print("❌ Timeout fetching satellite data (network slow/unreachable)")
            return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error fetching satellite data: {e}")
            return False
        except Exception as e:
            print(f"❌ Error fetching Starlink TLE data: {e}")
            return False
    
    def _calculate_satellite_position(self, sat_data: Dict, timestamp: datetime) -> Optional[SatellitePosition]:
        """Calculate satellite position using simplified orbital mechanics."""
        try:
            # This is a simplified calculation for demonstration
            # For production, you'd want to use SGP4 library for accurate propagation
            
            line1 = sat_data['line1']
            line2 = sat_data['line2']
            
            # Extract orbital parameters from TLE
            inclination = float(line2[8:16])  # degrees
            raan = float(line2[17:25])       # Right Ascension of Ascending Node
            eccentricity = float('0.' + line2[26:33])
            arg_perigee = float(line2[34:42])
            mean_anomaly = float(line2[43:51])
            mean_motion = float(line2[52:63])  # revolutions per day
            
            # Calculate time since epoch
            epoch = sat_data['epoch']
            time_diff = (timestamp - epoch).total_seconds() / 86400.0  # days
            
            # Update mean anomaly for current time
            current_mean_anomaly = (mean_anomaly + mean_motion * 360.0 * time_diff) % 360.0
            
            # Simplified position calculation (circular orbit assumption)
            # This is NOT accurate for real satellite tracking - use SGP4 for production
            
            # Semi-major axis estimation
            mu = 398600.4418  # Earth's gravitational parameter
            n = mean_motion * 2 * math.pi / 86400  # mean motion in rad/s
            a = (mu / (n ** 2)) ** (1/3)  # semi-major axis in km
            
            # Convert mean anomaly to radians
            M = math.radians(current_mean_anomaly)
            
            # Solve for eccentric anomaly (simplified)
            E = M + eccentricity * math.sin(M)
            
            # True anomaly
            nu = 2 * math.atan2(
                math.sqrt(1 + eccentricity) * math.sin(E/2),
                math.sqrt(1 - eccentricity) * math.cos(E/2)
            )
            
            # Distance from Earth center
            r = a * (1 - eccentricity * math.cos(E))
            
            # Position in orbital plane
            x_orbit = r * math.cos(nu)
            y_orbit = r * math.sin(nu)
            
            # Convert to Earth-centered coordinates (simplified)
            # This is a very basic transformation - real implementation needs full 3D rotation
            lat = math.degrees(math.asin(math.sin(math.radians(inclination)) * math.sin(nu)))
            lon = math.degrees(math.atan2(y_orbit, x_orbit) + math.radians(raan))
            
            # Normalize longitude
            while lon > 180:
                lon -= 360
            while lon < -180:
                lon += 360
            
            # Clamp latitude
            lat = max(-90, min(90, lat))
            
            # Calculate velocity (simplified)
            velocity = math.sqrt(mu / r) * 3.6  # km/h
            
            return SatellitePosition(
                name=sat_data['name'],
                norad_id=sat_data['norad_id'],
                latitude=lat,
                longitude=lon,
                altitude_km=r - 6371,  # Subtract Earth radius
                velocity_kmh=velocity,
                timestamp=timestamp
            )
            
        except Exception as e:
            print(f"Error calculating satellite position: {e}")
            return None
    
    def _parse_tle_epoch(self, epoch_str: str) -> datetime:
        """Parse TLE epoch to datetime."""
        try:
            year = int(epoch_str[:2])
            if year < 57:  # Y2K handling
                year += 2000
            else:
                year += 1900
            
            day_of_year = float(epoch_str[2:])
            
            # Convert day of year to date
            base_date = datetime(year, 1, 1, tzinfo=timezone.utc)
            epoch = base_date + timedelta(days=day_of_year - 1)
            
            return epoch
            
        except Exception as e:
            print(f"Error parsing TLE epoch: {e}")
            return datetime.now(timezone.utc)
    
    def _calculate_elevation_angle(self, obs_lat: float, obs_lon: float, obs_alt: float,
                                 sat_lat: float, sat_lon: float, sat_alt: float) -> float:
        """Calculate elevation angle from observer to satellite."""
        try:
            # Convert to radians
            obs_lat_rad = math.radians(obs_lat)
            obs_lon_rad = math.radians(obs_lon)
            sat_lat_rad = math.radians(sat_lat)
            sat_lon_rad = math.radians(sat_lon)
            
            # Earth radius
            R = 6371.0
            
            # Observer position (ECEF)
            obs_x = (R + obs_alt) * math.cos(obs_lat_rad) * math.cos(obs_lon_rad)
            obs_y = (R + obs_alt) * math.cos(obs_lat_rad) * math.sin(obs_lon_rad)
            obs_z = (R + obs_alt) * math.sin(obs_lat_rad)
            
            # Satellite position (ECEF)
            sat_x = (R + sat_alt) * math.cos(sat_lat_rad) * math.cos(sat_lon_rad)
            sat_y = (R + sat_alt) * math.cos(sat_lat_rad) * math.sin(sat_lon_rad)
            sat_z = (R + sat_alt) * math.sin(sat_lat_rad)
            
            # Vector from observer to satellite
            dx = sat_x - obs_x
            dy = sat_y - obs_y
            dz = sat_z - obs_z
            
            # Distance
            distance = math.sqrt(dx*dx + dy*dy + dz*dz)
            
            # Local horizon vectors
            up_x = obs_x / (R + obs_alt)
            up_y = obs_y / (R + obs_alt)
            up_z = obs_z / (R + obs_alt)
            
            # Dot product for elevation
            dot_product = (dx * up_x + dy * up_y + dz * up_z) / distance
            elevation = math.degrees(math.asin(max(-1, min(1, dot_product))))
            
            return elevation
            
        except Exception as e:
            return 0.0
    
    def _calculate_azimuth(self, obs_lat: float, obs_lon: float, 
                          sat_lat: float, sat_lon: float) -> float:
        """Calculate azimuth from observer to satellite."""
        try:
            obs_lat_rad = math.radians(obs_lat)
            obs_lon_rad = math.radians(obs_lon)
            sat_lat_rad = math.radians(sat_lat)
            sat_lon_rad = math.radians(sat_lon)
            
            dlon = sat_lon_rad - obs_lon_rad
            
            y = math.sin(dlon) * math.cos(sat_lat_rad)
            x = (math.cos(obs_lat_rad) * math.sin(sat_lat_rad) - 
                 math.sin(obs_lat_rad) * math.cos(sat_lat_rad) * math.cos(dlon))
            
            azimuth = math.degrees(math.atan2(y, x))
            return (azimuth + 360) % 360
            
        except Exception as e:
            return 0.0
    
    def _calculate_distance(self, lat1: float, lon1: float, alt1: float,
                           lat2: float, lon2: float, alt2: float) -> float:
        """Calculate 3D distance between two points."""
        try:
            R = 6371.0  # Earth radius
            
            # Convert to ECEF coordinates
            lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
            lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
            
            x1 = (R + alt1) * math.cos(lat1_rad) * math.cos(lon1_rad)
            y1 = (R + alt1) * math.cos(lat1_rad) * math.sin(lon1_rad)
            z1 = (R + alt1) * math.sin(lat1_rad)
            
            x2 = (R + alt2) * math.cos(lat2_rad) * math.cos(lon2_rad)
            y2 = (R + alt2) * math.cos(lat2_rad) * math.sin(lon2_rad)
            z2 = (R + alt2) * math.sin(lat2_rad)
            
            return math.sqrt((x2-x1)**2 + (y2-y1)**2 + (z2-z1)**2)
            
        except Exception as e:
            return 0.0
    
    def _get_tle_age_hours(self) -> float:
        """Get age of TLE data in hours."""
        if not self.last_tle_fetch:
            return 0.0
        return (time.time() - self.last_tle_fetch) / 3600.0
