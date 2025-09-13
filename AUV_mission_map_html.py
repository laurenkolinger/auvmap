#!/usr/bin/env python3
"""
AUV Mission Mapping Tool

Interactive satellite mapping for autonomous underwater vehicle missions.

Usage: python AUV_mission_map_html.py <session1> [session2] [session3] ...
Example: python AUV_mission_map_html.py session_0081 session_0079 session_0083
"""

import os
import sys
import json
import re
import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

class AUVMissionMapper:
    """AUV mission mapping tool"""
    
    def __init__(self, session_folders: List[str], root_path: str = ".."):
        self.session_folders = session_folders
        self.root_path = Path(root_path)
        self.sessions_data = {}
        
        # Output to current auvmap directory
        self.output_path = Path(".")
        
        # High contrast colors for precision analysis
        self.planned_colors = ['#FFD700', '#FF6B35', '#7B68EE', '#FF1493', '#00FF7F', '#FF4500', '#9370DB', '#32CD32', '#FF69B4', '#20B2AA']
        self.actual_colors = ['#DC143C', '#0000FF', '#228B22', '#FF8C00', '#8A2BE2', '#B22222', '#4B0082', '#006400', '#C71585', '#008B8B']
    
    def parse_vtt_telemetry(self, session_folder: str) -> List[Dict]:
        """Parse VTT telemetry files for actual path data"""
        session_path = self.root_path / session_folder
        videos_path = session_path / "videos"
        telemetry_data = []
        
        if not videos_path.exists():
            return telemetry_data
        
        # Find VTT files
        vtt_files = list(videos_path.glob("*.vtt"))
        if not vtt_files:
            return telemetry_data
        
        print(f"Parsing VTT from {session_folder}: {len(vtt_files)} files")
        
        for vtt_file in vtt_files:
            with open(vtt_file, 'r') as f:
                content = f.read()
            
            # Split into cue blocks
            blocks = content.split('\n\n')
            
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) < 6:
                    continue
                
                # Check if this is a telemetry block
                if '-->' in lines[0]:
                    try:
                        # Parse timestamp
                        timestamp_line = lines[0]
                        time_match = re.match(r'(\d{2}:\d{2}:\d{2}\.\d{3})', timestamp_line)
                        if not time_match:
                            continue
                        
                        time_str = time_match.group(1)
                        
                        # Extract actual date/time from VTT - format like "Thu Sep 11 20:03:06 2025 UTC"
                        vtt_datetime_str = None
                        if len(lines) > 2:
                            # Look for full datetime in the format "Day Mon DD HH:MM:SS YYYY UTC"
                            date_match = re.search(r'(\w{3} \w{3} \d{1,2} \d{2}:\d{2}:\d{2} \d{4}) UTC', lines[2])
                            if date_match:
                                vtt_datetime_str = date_match.group(1)
                        
                        # Extract numeric data
                        heading = None
                        latitude = None
                        longitude = None
                        depth = None
                        altitude = None
                        
                        for line in lines[3:]:
                            if "Heading:" in line:
                                heading_match = re.search(r'Heading:\s*([\d.-]+)', line)
                                if heading_match:
                                    heading = float(heading_match.group(1))
                            elif "Latitude:" in line:
                                lat_match = re.search(r'Latitude:\s*([\d.-]+)', line)
                                if lat_match:
                                    latitude = float(lat_match.group(1))
                            elif "Longitude:" in line:
                                lon_match = re.search(r'Longitude:\s*([\d.-]+)', line)
                                if lon_match:
                                    longitude = float(lon_match.group(1))
                            elif "Depth:" in line:
                                depth_match = re.search(r'Depth:\s*([\d.-]+)', line)
                                if depth_match:
                                    depth = float(depth_match.group(1))
                            elif "Altitude:" in line:
                                alt_match = re.search(r'Altitude:\s*([\d.-]+)', line)
                                if alt_match:
                                    altitude = float(alt_match.group(1))
                        
                        # Only add if we have position data
                        if latitude is not None and longitude is not None:
                            telemetry_data.append({
                                'time_str': time_str,
                                'vtt_datetime_str': vtt_datetime_str,
                                'heading': heading,
                                'latitude': latitude,
                                'longitude': longitude,
                                'depth': depth,
                                'altitude': altitude
                            })
                    
                    except Exception as e:
                        continue
        
        print(f"  Parsed {len(telemetry_data)} telemetry points from {session_folder}")
        return telemetry_data
    
    def load_mission_json(self, session_folder: str) -> Dict:
        """Load and parse mission.json file"""
        session_path = self.root_path / session_folder
        mission_json_path = session_path / "missions" / "mission.json"
        
        if not mission_json_path.exists():
            return {}
            
        with open(mission_json_path, 'r') as f:
            mission_data = json.load(f)
            
        # Extract planned waypoints
        planned_waypoints = []
        if 'compiled_waypoints' in mission_data:
            for wp in mission_data['compiled_waypoints']:
                if 'lat_deg' in wp and 'lon_deg' in wp:
                    waypoint = {
                        'latitude': wp['lat_deg'],
                        'longitude': wp['lon_deg'],
                        'depth': wp.get('vertical', 0),
                        'control_mode': wp.get('control_mode', 'unknown'),
                        'yaw_deg': wp.get('yaw_deg', 0)
                    }
                    planned_waypoints.append(waypoint)
        
        mission_data['planned_waypoints'] = planned_waypoints
        return mission_data
    
    def load_mission_metadata(self, session_folder: str) -> Dict:
        """Load mission metadata including name"""
        session_path = self.root_path / session_folder
        missions_path = session_path / "missions"
        metadata = {}
        
        # Load mission name
        mission_name_path = missions_path / "mission_name.txt"
        if mission_name_path.exists():
            with open(mission_name_path, 'r') as f:
                metadata['mission_name'] = f.read().strip()
        
        return metadata
    
    def calculate_map_bounds(self):
        """Calculate the bounds for the map based on all mission data"""
        all_lats = []
        all_lons = []
        
        for session_data in self.sessions_data.values():
            # Add telemetry points
            for point in session_data['telemetry_data']:
                if point['latitude'] is not None and point['longitude'] is not None:
                    all_lats.append(point['latitude'])
                    all_lons.append(point['longitude'])
            
            # Add planned waypoints
            for waypoint in session_data['mission_data'].get('planned_waypoints', []):
                all_lats.append(waypoint['latitude'])
                all_lons.append(waypoint['longitude'])
        
        if not all_lats or not all_lons:
            return None, None, None, None
        
        lat_min, lat_max = min(all_lats), max(all_lats)
        lon_min, lon_max = min(all_lons), max(all_lons)
        
        # Add padding
        lat_padding = (lat_max - lat_min) * 0.1 if lat_max != lat_min else 0.001
        lon_padding = (lon_max - lon_min) * 0.1 if lon_max != lon_min else 0.001
        
        return (lat_min - lat_padding, lat_max + lat_padding, 
                lon_min - lon_padding, lon_max + lon_padding)
    
    def get_mission_date_range(self):
        """Get date range from actual VTT data"""
        all_dates = []
        all_depths = []
        
        for session_data in self.sessions_data.values():
            for point in session_data['telemetry_data']:
                if point['vtt_datetime_str']:
                    try:
                        # Parse VTT datetime and convert to AST
                        utc_dt = datetime.datetime.strptime(point['vtt_datetime_str'], '%a %b %d %H:%M:%S %Y')
                        ast_dt = utc_dt - datetime.timedelta(hours=4)
                        all_dates.append(ast_dt)
                    except:
                        pass
                
                if point['depth'] is not None:
                    all_depths.append(point['depth'])
        
        date_range = ""
        depth_range = ""
        
        if all_dates:
            min_date = min(all_dates)
            max_date = max(all_dates)
            if min_date.date() == max_date.date():
                date_range = min_date.strftime('%Y-%m-%d')
            else:
                date_range = f"{min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}"
        
        if all_depths:
            depth_range = f"{min(all_depths):.1f}m to {max(all_depths):.1f}m"
        
        return date_range, depth_range
    
    def create_auv_map(self):
        """Create AUV mission map"""
        # Calculate map center and bounds
        lat_min, lat_max, lon_min, lon_max = self.calculate_map_bounds()
        if lat_min is None:
            print("No valid coordinates found for mapping")
            return None
        
        center_lat = (lat_min + lat_max) / 2
        center_lon = (lon_min + lon_max) / 2
        
        # Get date and depth ranges
        date_range, depth_range = self.get_mission_date_range()
        map_creation_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        
        # Prepare mission data for JavaScript
        missions_data = {}
        for session_name, session_data in self.sessions_data.items():
            missions_data[session_name] = {
                'planned': [
                    {'lat': wp['latitude'], 'lon': wp['longitude'], 'depth': wp['depth'], 'mode': wp['control_mode'], 'yaw': wp['yaw_deg']}
                    for wp in session_data['mission_data'].get('planned_waypoints', [])
                ],
                'actual': [
                    {'lat': point['latitude'], 'lon': point['longitude'], 
                     'depth': point['depth'] if point['depth'] is not None else 0,
                     'altitude': point['altitude'] if point['altitude'] is not None else 0,
                     'heading': point['heading'] if point['heading'] is not None else 0,
                     'time': point['time_str'],
                     'vtt_datetime_str': point['vtt_datetime_str']}
                    for point in session_data['telemetry_data']
                    if point['latitude'] is not None and point['longitude'] is not None
                ],
                'metadata': {
                    'mission_name': session_data['metadata'].get('mission_name', 'Mission'),
                }
            }
        
        # Generate output filename with timestamp
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f'AUV_mission_map_{timestamp}.html'
        
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AUV Mission Map</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a0a;
            color: #ffffff;
        }}
        #map {{
            height: 100vh;
            width: 100vw;
        }}
        .info-panel {{
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(15, 15, 15, 0.95);
            color: #ffffff;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            z-index: 1000;
            max-width: 300px;
            font-size: 14px;
        }}
        .coordinates {{
            position: absolute;
            bottom: 20px;
            right: 20px;
            background: rgba(15, 15, 15, 0.95);
            color: #ffffff;
            padding: 12px 18px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            z-index: 1000;
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
        }}
        .leaflet-control-layers {{
            background: rgba(15, 15, 15, 0.95);
            color: #ffffff;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .leaflet-control-layers-expanded {{
            padding: 15px;
        }}
        .leaflet-control-layers label {{
            color: #ffffff;
        }}
        .vicar-title {{
            font-size: 18px;
            font-weight: 700;
            color: #E20074;
            margin-bottom: 15px;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    
    <div class="info-panel">
        <div class="vicar-title">VICAR</div>
        <div>Hydrus Mission Map</div>
        
        <div style="margin-top: 15px;">
            <strong>Date Range:</strong> {date_range}<br>
            <strong>Depth Range:</strong> {depth_range}<br>
            <strong>Map Created:</strong> {map_creation_date}
        </div>
    </div>
    
    <div class="coordinates" id="coordinates">
        Position tracking
    </div>
    
    <script>
        // Initialize main map with Google Satellite as default
        const map = L.map('map').setView([{center_lat}, {center_lon}], 18);
        
        // Base tile layers
        const googleSatellite = L.tileLayer('https://mt1.google.com/vt/lyrs=s&x={{x}}&y={{y}}&z={{z}}', {{
            attribution: '&copy; Google',
            maxZoom: 22
        }});
        
        const esriSatellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
            attribution: '&copy; Esri',
            maxZoom: 20
        }});
        
        const googleHybrid = L.tileLayer('https://mt1.google.com/vt/lyrs=s,h&x={{x}}&y={{y}}&z={{z}}', {{
            attribution: '&copy; Google',
            maxZoom: 22
        }});
        
        const openStreetMap = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 19
        }});
        
        // Add default layer
        googleSatellite.addTo(map);
        
        // Function to display VTT datetime as UTC (no conversion)
        function formatVTTTime(vttDatetimeStr) {{
            if (!vttDatetimeStr) return 'Unknown';
            return vttDatetimeStr + ' UTC';
        }}
        
        // Mission data
        const missionsData = {json.dumps(missions_data)};
        const plannedColors = {json.dumps(self.planned_colors[:len(self.sessions_data)])};
        const actualColors = {json.dumps(self.actual_colors[:len(self.sessions_data)])};
        
        // Create layer groups for each mission component
        const layerGroups = {{}};
        const overlayMaps = {{}};
        
        // Add mission data to map
        let colorIndex = 0;
        Object.keys(missionsData).forEach(sessionName => {{
            const sessionData = missionsData[sessionName];
            const plannedColor = plannedColors[colorIndex % plannedColors.length];
            const actualColor = actualColors[colorIndex % actualColors.length];
            const metadata = sessionData.metadata || {{}};
            
            // Create layer groups for this mission
            layerGroups[sessionName] = {{
                planned: L.layerGroup(),
                actual: L.layerGroup(),
                markers: L.layerGroup()
            }};
            
            // Mission title with session and name
            const missionTitle = `${{sessionName}}: ${{metadata.mission_name}}`;
            
            // Planned path - add FIRST so actual is on top
            if (sessionData.planned.length > 0) {{
                const plannedCoords = sessionData.planned.map(p => [p.lat, p.lon]);
                
                const plannedPath = L.polyline(plannedCoords, {{
                    color: plannedColor,
                    weight: 2,
                    opacity: 0.9,
                    dashArray: '8, 4'
                }}).bindPopup(`<div style="color: #000;">
                    <h4>${{missionTitle}}</h4>
                    <strong>Planned Route</strong>
                </div>`);
                
                layerGroups[sessionName].planned.addLayer(plannedPath);
                
                // Smaller waypoint markers with same color as planned path
                sessionData.planned.forEach((wp, i) => {{
                    const waypoint = L.marker([wp.lat, wp.lon], {{
                        icon: L.divIcon({{
                            html: `<div style="background-color: ${{plannedColor}}; color: #000000; border-radius: 50%; width: 14px; height: 14px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 9px; border: 2px solid white; box-shadow: 0 1px 3px rgba(0,0,0,0.4);">${{i+1}}</div>`,
                            iconSize: [14, 14],
                            iconAnchor: [7, 7],
                            className: 'waypoint-marker'
                        }})
                    }}).bindPopup(`<div style="color: #000;">
                        <h4>${{missionTitle}} - WP${{i+1}}</h4>
                        <strong>Position:</strong> ${{wp.lat.toFixed(6)}}°N, ${{Math.abs(wp.lon).toFixed(6)}}°W<br>
                        <strong>Depth:</strong> ${{wp.depth.toFixed(1)}}m<br>
                        <strong>Yaw:</strong> ${{wp.yaw.toFixed(1)}}°
                    </div>`);
                    
                    layerGroups[sessionName].markers.addLayer(waypoint);
                }});
            }}
            
            // Actual path - add SECOND so it appears on top
            if (sessionData.actual.length > 0) {{
                const actualCoords = sessionData.actual.map(p => [p.lat, p.lon]);
                
                // Create actual path with detailed popups for each segment
                const actualPath = L.polyline(actualCoords, {{
                    color: actualColor,
                    weight: 2,
                    opacity: 1.0
                }});
                
                // Add click handler to show detailed telemetry at clicked point
                actualPath.on('click', function(e) {{
                    const clickedLatLng = e.latlng;
                    let closestPoint = null;
                    let minDistance = Infinity;
                    
                    // Find closest telemetry point to click
                    sessionData.actual.forEach(point => {{
                        const distance = map.distance([point.lat, point.lon], clickedLatLng);
                        if (distance < minDistance) {{
                            minDistance = distance;
                            closestPoint = point;
                        }}
                    }});
                    
                    if (closestPoint) {{
                        const popup = L.popup()
                            .setLatLng(clickedLatLng)
                            .setContent(`<div style="color: #000;">
                                <h4>${{missionTitle}}</h4>
                                <strong>${{formatVTTTime(closestPoint.vtt_datetime_str)}}</strong><br>
                                <strong>Heading:</strong> ${{closestPoint.heading.toFixed(1)}}°<br>
                                <strong>Latitude:</strong> ${{closestPoint.lat.toFixed(6)}}°<br>
                                <strong>Longitude:</strong> ${{closestPoint.lon.toFixed(6)}}°<br>
                                <strong>Depth:</strong> ${{closestPoint.depth.toFixed(2)}}m<br>
                                <strong>Altitude:</strong> ${{closestPoint.altitude.toFixed(2)}}m
                            </div>`)
                            .openOn(map);
                    }}
                }});
                
                layerGroups[sessionName].actual.addLayer(actualPath);
                
                // Enhanced start marker
                const start = sessionData.actual[0];
                const startMarker = L.marker([start.lat, start.lon], {{
                    icon: L.divIcon({{
                        html: `<div style="background-color: #4CAF50; color: white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid white; box-shadow: 0 2px 6px rgba(0,0,0,0.4);">▶</div>`,
                        iconSize: [24, 24],
                        iconAnchor: [12, 12],
                        className: 'start-marker'
                    }})
                }}).bindPopup(`<div style="color: #000;">
                    <h4>${{missionTitle}} - Start</h4>
                    <strong>Position:</strong> ${{start.lat.toFixed(6)}}°N, ${{Math.abs(start.lon).toFixed(6)}}°W<br>
                    <strong>Time:</strong> ${{formatVTTTime(start.vtt_datetime_str)}}<br>
                    <strong>Heading:</strong> ${{start.heading.toFixed(1)}}°<br>
                    <strong>Depth:</strong> ${{start.depth.toFixed(2)}}m<br>
                    <strong>Altitude:</strong> ${{start.altitude.toFixed(2)}}m
                </div>`);
                
                layerGroups[sessionName].markers.addLayer(startMarker);
                
                // Enhanced end marker
                const end = sessionData.actual[sessionData.actual.length - 1];
                const endMarker = L.marker([end.lat, end.lon], {{
                    icon: L.divIcon({{
                        html: `<div style="background-color: #f44336; color: white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid white; box-shadow: 0 2px 6px rgba(0,0,0,0.4);">⏹</div>`,
                        iconSize: [24, 24],
                        iconAnchor: [12, 12],
                        className: 'end-marker'
                    }})
                }}).bindPopup(`<div style="color: #000;">
                    <h4>${{missionTitle}} - End</h4>
                    <strong>Position:</strong> ${{end.lat.toFixed(6)}}°N, ${{Math.abs(end.lon).toFixed(6)}}°W<br>
                    <strong>Time:</strong> ${{formatVTTTime(end.vtt_datetime_str)}}<br>
                    <strong>Heading:</strong> ${{end.heading.toFixed(1)}}°<br>
                    <strong>Depth:</strong> ${{end.depth.toFixed(2)}}m<br>
                    <strong>Altitude:</strong> ${{end.altitude.toFixed(2)}}m
                </div>`);
                
                layerGroups[sessionName].markers.addLayer(endMarker);
            }}
            
            colorIndex++;
        }});
        
        // Add layers to map - PLANNED FIRST, then ACTUAL on top
        Object.keys(missionsData).forEach(sessionName => {{
            if (layerGroups[sessionName].planned) {{
                layerGroups[sessionName].planned.addTo(map);
            }}
        }});
        
        Object.keys(missionsData).forEach(sessionName => {{
            if (layerGroups[sessionName].actual) {{
                layerGroups[sessionName].actual.addTo(map);
            }}
            layerGroups[sessionName].markers.addTo(map);
        }});
        
        // Create overlay maps with proper mission organization
        Object.keys(missionsData).forEach(sessionName => {{
            const sessionData = missionsData[sessionName];
            const metadata = sessionData.metadata || {{}};
            const missionName = metadata.mission_name || 'Mission';
            
            // Add mission header
            overlayMaps[`---- ${{sessionName}}: ${{missionName}} ----`] = L.layerGroup(); // Mission header
            
            if (sessionData.planned.length > 0) {{
                overlayMaps[`${{sessionName}} Planned Track`] = layerGroups[sessionName].planned;
            }}
            overlayMaps[`${{sessionName}} Markers`] = layerGroups[sessionName].markers;
            if (sessionData.actual.length > 0) {{
                overlayMaps[`${{sessionName}} Actual Track`] = layerGroups[sessionName].actual;
            }}
        }});
        
        // Base map layers
        const baseMaps = {{
            "Satellite (Google)": googleSatellite,
            "Satellite (Esri)": esriSatellite,
            "Hybrid (Google)": googleHybrid,
            "Street Map": openStreetMap
        }};
        
        // Layer control
        const layerControl = L.control.layers(baseMaps, overlayMaps, {{
            position: 'topright',
            collapsed: false
        }}).addTo(map);
        
        // Additional controls
        L.control.scale({{
            position: 'bottomleft',
            metric: true,
            imperial: true
        }}).addTo(map);
        
        // Mouse position display
        map.on('mousemove', function(e) {{
            const coords = document.getElementById('coordinates');
            coords.innerHTML = `${{e.latlng.lat.toFixed(6)}}°N ${{Math.abs(e.latlng.lng).toFixed(6)}}°W`;
        }});
        
        // Fit map to mission bounds
        const bounds = [
            [{lat_min}, {lon_min}],
            [{lat_max}, {lon_max}]
        ];
        map.fitBounds(bounds, {{padding: [50, 50]}});
        
        // Helper function to calculate path distance
        function calculatePathDistance(coords) {{
            let distance = 0;
            for (let i = 1; i < coords.length; i++) {{
                distance += map.distance(coords[i-1], coords[i]);
            }}
            return distance;
        }}
        
        console.log('AUV Mission Map Loaded');
        console.log('Sessions:', Object.keys(missionsData));
    </script>
</body>
</html>
        """
        
        map_path = self.output_path / output_filename
        with open(map_path, 'w') as f:
            f.write(html_content)
        
        print(f"AUV mission map created: {map_path}")
        return map_path
    
    def load_all_sessions(self):
        """Load data from all specified sessions"""
        print(f"Loading mission data...")
        
        for session in self.session_folders:
            print(f"Processing {session}...")
            
            session_data = {
                'session_name': session,
                'mission_data': self.load_mission_json(session),
                'telemetry_data': self.parse_vtt_telemetry(session),
                'metadata': self.load_mission_metadata(session)
            }
            
            self.sessions_data[session] = session_data
    
    def run_mapping(self):
        """Run complete mapping process"""
        print("AUV Mission Mapping")
        print("=" * 20)
        
        # Load all session data
        self.load_all_sessions()
        
        # Check if we have any data
        has_data = any(
            session_data['telemetry_data'] or session_data['mission_data'].get('planned_waypoints', [])
            for session_data in self.sessions_data.values()
        )
        
        if not has_data:
            print("ERROR: No mission data found")
            return
        
        # Create map
        try:
            map_path = self.create_auv_map()
            print("SUCCESS: Mission map created")
        except Exception as e:
            print(f"ERROR: Map creation failed: {e}")
            import traceback
            traceback.print_exc()
            return
        
        print(f"\\nMap File: {map_path}")
        
        # Print summary
        lat_min, lat_max, lon_min, lon_max = self.calculate_map_bounds()
        if lat_min is not None:
            center_lat = (lat_min + lat_max) / 2
            center_lon = (lon_min + lon_max) / 2
            print(f"Center: {center_lat:.6f}°N, {abs(center_lon):.6f}°W")
            print(f"Area: {abs(lat_max-lat_min)*111000:.0f}m x {abs(lon_max-lon_min)*111000:.0f}m")
        
        # Print data summary
        sessions_with_telemetry = sum(1 for s in self.sessions_data.values() if s['telemetry_data'])
        total_gps_points = sum(len(s['telemetry_data']) for s in self.sessions_data.values())
        
        print(f"GPS Points: {total_gps_points}")


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python AUV_mission_map_html.py <session1> [session2] [session3] ...")
        print("Example: python AUV_mission_map_html.py session_0081 session_0079 session_0083")
        sys.exit(1)
    
    session_folders = sys.argv[1:]
    
    try:
        mapper = AUVMissionMapper(session_folders, "..")
        mapper.run_mapping()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
