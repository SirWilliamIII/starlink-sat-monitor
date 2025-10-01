#!/usr/bin/env python3

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from dotenv import load_dotenv

# Load .env from backend directory
env_path = os.path.join(os.path.dirname(__file__), 'backend', '.env')
load_dotenv(env_path)

from collectors.spacetrack import SpaceTrackCollector

def test_spacetrack():
    print("🔐 Testing Space-Track.org connection...")
    
    # Check environment variables
    username = os.environ.get('SPACETRACK_USERNAME')
    password = os.environ.get('SPACETRACK_PASSWORD')
    
    if not username or not password:
        print("❌ Space-Track credentials not found in environment")
        print("💡 Make sure backend/.env has SPACETRACK_USERNAME and SPACETRACK_PASSWORD")
        return False
    
    print(f"📧 Username: {username}")
    print(f"🔑 Password: {'*' * len(password)}")
    
    # Test authentication
    collector = SpaceTrackCollector()
    
    if collector.authenticate():
        print("✅ Authentication successful!")
        
        # Test satellite data fetch
        print("🛰️ Fetching Starlink constellation...")
        data = collector.get_starlink_constellation()
        
        print(f"📊 Results:")
        print(f"  - Total satellites: {data.get('satellite_count', 0)}")
        print(f"  - Positions calculated: {data.get('positions_calculated', 0)}")
        print(f"  - Data source: {data.get('data_source', 'unknown')}")
        print(f"  - TLE age: {data.get('tle_age_hours', 0):.1f} hours")
        
        if data.get('positions'):
            first_sat = data['positions'][0]
            print(f"  - First satellite: {first_sat.get('name')} at {first_sat.get('lat'):.2f}, {first_sat.get('lng'):.2f}")
            return True
        else:
            print("❌ No satellite positions returned")
            return False
    else:
        print("❌ Authentication failed")
        return False

if __name__ == "__main__":
    test_spacetrack()