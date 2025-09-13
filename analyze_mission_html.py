#!/usr/bin/env python3
"""
HTML-Based AUV Mission Analysis Script

Creates interactive HTML visualizations of AUV mission data without requiring matplotlib.
Parses VTT telemetry files for actual vs planned path comparison.

Usage: python analyze_mission_html.py <session_folder_name>
Example: python analyze_mission_html.py session_0076
"""

import os
import sys
import json
import csv
import math
import datetime
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

class HTMLMissionAnalyzer:
    """Mission analyzer that creates HTML-based visualizations"""
    
    def __init__(self, session_folder: str, root_path: str = ".."):
        self.session_folder = session_folder
        self.root_path = Path(root_path)
        self.session_path = self.root_path / session_folder
        
        # Output to auvmap directory with timestamp
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        self.analysis_filename = f'mission_analysis_{timestamp}.html'
        self.analysis_path = Path(".")
        
        # Data containers
        self.mission_data = {}
        self.planned_waypoints = []
        self.behavior_data = []
        self.telemetry_data = []
        self.mission_stats = {}
        
    def parse_vtt_telemetry(self) -> List[Dict]:
        """Parse VTT telemetry files for actual path data"""
        videos_path = self.session_path / "videos"
        telemetry_data = []
        
        if not videos_path.exists():
            print("No videos folder found")
            return telemetry_data
        
        # Find VTT files
        vtt_files = list(videos_path.glob("*.vtt"))
        if not vtt_files:
            print("No VTT telemetry files found")
            return telemetry_data
        
        print(f"Found {len(vtt_files)} VTT telemetry files")
        
        for vtt_file in vtt_files:
            print(f"Parsing telemetry from: {vtt_file.name}")
            
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
                        
                        # Parse telemetry data
                        mission_name = lines[1] if len(lines) > 1 else ""
                        date_str = lines[2] if len(lines) > 2 else ""
                        
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
                                'mission_name': mission_name,
                                'date_str': date_str,
                                'heading': heading,
                                'latitude': latitude,
                                'longitude': longitude,
                                'depth': depth,
                                'altitude': altitude
                            })
                    
                    except Exception as e:
                        # Skip problematic blocks
                        continue
        
        print(f"Parsed {len(telemetry_data)} telemetry points")
        self.telemetry_data = telemetry_data
        return telemetry_data
    
    def load_mission_json(self) -> Dict:
        """Load and parse mission.json file"""
        mission_json_path = self.session_path / "missions" / "mission.json"
        
        if not mission_json_path.exists():
            raise FileNotFoundError(f"Mission JSON not found: {mission_json_path}")
            
        with open(mission_json_path, 'r') as f:
            mission_data = json.load(f)
            
        self.mission_data = mission_data
        
        # Extract planned waypoints
        self.planned_waypoints = []
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
                    self.planned_waypoints.append(waypoint)
        
        return mission_data
    
    def load_behavior_data(self) -> List[Dict]:
        """Load behavior states CSV"""
        behavior_csv_path = self.session_path / "logs" / "behaviour_states.csv"
        
        if not behavior_csv_path.exists():
            print(f"Warning: Behavior CSV not found: {behavior_csv_path}")
            return []
            
        behavior_data = []
        with open(behavior_csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'Timestamp' in row and 'Behaviour_String' in row:
                    # Convert timestamp from microseconds to datetime
                    timestamp_us = int(row['Timestamp'])
                    dt = datetime.datetime.fromtimestamp(timestamp_us / 1_000_000)
                    
                    behavior_data.append({
                        'timestamp': timestamp_us,
                        'datetime': dt,
                        'behavior': row['Behaviour_String']
                    })
        
        self.behavior_data = behavior_data
        return behavior_data
    
    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in meters using Haversine formula"""
        R = 6371000  # Earth's radius in meters
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat_rad = math.radians(lat2 - lat1)
        dlon_rad = math.radians(lon2 - lon1)
        
        a = (math.sin(dlat_rad/2) * math.sin(dlat_rad/2) + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * 
             math.sin(dlon_rad/2) * math.sin(dlon_rad/2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def calculate_mission_statistics(self) -> Dict:
        """Calculate comprehensive mission statistics"""
        stats = {}
        
        # Basic mission info
        if self.mission_data:
            stats['mission_name'] = self.mission_data.get('name', 'Unknown')
            stats['num_planned_waypoints'] = len(self.planned_waypoints)
            stats['mission_mode'] = self.mission_data.get('mode', 'Unknown')
        
        # Telemetry analysis
        if self.telemetry_data:
            stats['num_telemetry_points'] = len(self.telemetry_data)
            
            # Position analysis
            lats = [t['latitude'] for t in self.telemetry_data if t['latitude'] is not None]
            lons = [t['longitude'] for t in self.telemetry_data if t['longitude'] is not None]
            depths = [t['depth'] for t in self.telemetry_data if t['depth'] is not None]
            altitudes = [t['altitude'] for t in self.telemetry_data if t['altitude'] is not None]
            
            if lats and lons:
                stats['actual_lat_range'] = [min(lats), max(lats)]
                stats['actual_lon_range'] = [min(lons), max(lons)]
                stats['actual_center_lat'] = sum(lats) / len(lats)
                stats['actual_center_lon'] = sum(lons) / len(lons)
                
                # Calculate actual distance traveled
                total_distance = 0
                for i in range(1, len(self.telemetry_data)):
                    prev = self.telemetry_data[i-1]
                    curr = self.telemetry_data[i]
                    if (prev['latitude'] is not None and prev['longitude'] is not None and
                        curr['latitude'] is not None and curr['longitude'] is not None):
                        dist = self.calculate_distance(
                            prev['latitude'], prev['longitude'],
                            curr['latitude'], curr['longitude']
                        )
                        total_distance += dist
                
                stats['actual_distance_traveled_m'] = total_distance
                stats['actual_distance_traveled_km'] = total_distance / 1000
            
            if depths:
                stats['actual_depth_range'] = [min(depths), max(depths)]
                stats['actual_avg_depth'] = sum(depths) / len(depths)
            
            if altitudes:
                stats['actual_altitude_range'] = [min(altitudes), max(altitudes)]
                stats['actual_avg_altitude'] = sum(altitudes) / len(altitudes)
        
        # Planned path analysis
        if self.planned_waypoints:
            planned_lats = [wp['latitude'] for wp in self.planned_waypoints]
            planned_lons = [wp['longitude'] for wp in self.planned_waypoints]
            planned_depths = [wp['depth'] for wp in self.planned_waypoints]
            
            stats['planned_lat_range'] = [min(planned_lats), max(planned_lats)]
            stats['planned_lon_range'] = [min(planned_lons), max(planned_lons)]
            stats['planned_depth_range'] = [min(planned_depths), max(planned_depths)]
            
            # Calculate planned distance
            planned_distance = 0
            for i in range(1, len(self.planned_waypoints)):
                prev_wp = self.planned_waypoints[i-1]
                curr_wp = self.planned_waypoints[i]
                dist = self.calculate_distance(
                    prev_wp['latitude'], prev_wp['longitude'],
                    curr_wp['latitude'], curr_wp['longitude']
                )
                planned_distance += dist
            
            stats['planned_distance_m'] = planned_distance
            stats['planned_distance_km'] = planned_distance / 1000
        
        self.mission_stats = stats
        return stats
    
    def create_html_visualization(self):
        """Create comprehensive HTML visualization with interactive plots"""
        html_path = self.analysis_path / self.analysis_filename
        
        # Prepare data for JavaScript
        planned_data = []
        if self.planned_waypoints:
            for i, wp in enumerate(self.planned_waypoints):
                planned_data.append({
                    'id': i + 1,
                    'lat': wp['latitude'],
                    'lon': wp['longitude'],
                    'depth': wp['depth'],
                    'yaw': wp['yaw_deg'],
                    'mode': wp['control_mode']
                })
        
        telemetry_data_js = []
        if self.telemetry_data:
            # Subsample for performance (every 10th point)
            step = max(1, len(self.telemetry_data) // 1000)
            for i, t in enumerate(self.telemetry_data[::step]):
                if t['latitude'] is not None and t['longitude'] is not None:
                    telemetry_data_js.append({
                        'index': i,
                        'time': t['time_str'],
                        'lat': t['latitude'],
                        'lon': t['longitude'],
                        'depth': t['depth'] if t['depth'] is not None else 0,
                        'altitude': t['altitude'] if t['altitude'] is not None else 0,
                        'heading': t['heading'] if t['heading'] is not None else 0
                    })
        
        # Create HTML content
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AUV Mission Analysis - {self.session_folder}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            text-align: center;
            margin-bottom: 30px;
        }}
        h2 {{
            color: #34495e;
            border-bottom: 2px solid #3498db;
            padding-bottom: 5px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .stats-card {{
            background-color: #ecf0f1;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #3498db;
        }}
        .plot-container {{
            margin: 20px 0;
            height: 500px;
        }}
        .plot-container-large {{
            margin: 20px 0;
            height: 700px;
        }}
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        .data-table th, .data-table td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        .data-table th {{
            background-color: #3498db;
            color: white;
        }}
        .data-table tr:nth-child(even) {{
            background-color: #f2f2f2;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>AUV Mission Analysis - {self.session_folder}</h1>
        
        <div class="stats-grid">
            <div class="stats-card">
                <h3>Mission Overview</h3>
                <p><strong>Mission Name:</strong> {self.mission_stats.get('mission_name', 'Unknown')}</p>
                <p><strong>Mode:</strong> {self.mission_stats.get('mission_mode', 'Unknown')}</p>
                <p><strong>Analysis Date:</strong> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="stats-card">
                <h3>Data Points</h3>
                <p><strong>Planned Waypoints:</strong> {self.mission_stats.get('num_planned_waypoints', 0)}</p>
                <p><strong>Telemetry Points:</strong> {self.mission_stats.get('num_telemetry_points', 0)}</p>
                <p><strong>Behavior Changes:</strong> {len(self.behavior_data)}</p>
            </div>
            
            <div class="stats-card">
                <h3>Distance Analysis</h3>
                <p><strong>Planned Distance:</strong> {self.mission_stats.get('planned_distance_m', 0):.1f}m</p>
                <p><strong>Actual Distance:</strong> {self.mission_stats.get('actual_distance_traveled_m', 0):.1f}m</p>
                <p><strong>Efficiency:</strong> {(self.mission_stats.get('planned_distance_m', 1) / max(self.mission_stats.get('actual_distance_traveled_m', 1), 1) * 100):.1f}%</p>
            </div>
            
            <div class="stats-card">
                <h3>Depth & Altitude</h3>
                <p><strong>Avg Depth:</strong> {self.mission_stats.get('actual_avg_depth', 0):.1f}m</p>
                <p><strong>Avg Altitude:</strong> {self.mission_stats.get('actual_avg_altitude', 0):.1f}m</p>
                <p><strong>Depth Range:</strong> {self.mission_stats.get('actual_depth_range', [0,0])[0]:.1f} - {self.mission_stats.get('actual_depth_range', [0,0])[1]:.1f}m</p>
            </div>
        </div>
        
        <h2>Mission Path Visualization</h2>
        <div id="path-plot" class="plot-container-large"></div>
        
        <h2>Depth Profile</h2>
        <div id="depth-plot" class="plot-container"></div>
        
        <h2>Altitude Profile</h2>
        <div id="altitude-plot" class="plot-container"></div>
        
        <h2>Heading Profile</h2>
        <div id="heading-plot" class="plot-container"></div>
        
        <h2>3D Mission Path</h2>
        <div id="path-3d-plot" class="plot-container-large"></div>
        
        <h2>Planned Waypoints</h2>
        <table class="data-table">
            <tr>
                <th>WP#</th>
                <th>Latitude</th>
                <th>Longitude</th>
                <th>Depth (m)</th>
                <th>Yaw (°)</th>
                <th>Control Mode</th>
            </tr>
            {''.join([f"<tr><td>{wp['id']}</td><td>{wp['lat']:.6f}</td><td>{wp['lon']:.6f}</td><td>{wp['depth']:.1f}</td><td>{wp['yaw']:.1f}</td><td>{wp['mode']}</td></tr>" for wp in planned_data])}
        </table>
    </div>
    
    <script>
        // Data
        const plannedData = {json.dumps(planned_data)};
        const telemetryData = {json.dumps(telemetry_data_js)};
        
        // 2D Path Plot
        const pathPlot = document.getElementById('path-plot');
        const pathTraces = [];
        
        if (plannedData.length > 0) {{
            pathTraces.push({{
                x: plannedData.map(d => d.lon),
                y: plannedData.map(d => d.lat),
                mode: 'lines+markers',
                type: 'scatter',
                name: 'Planned Path',
                line: {{ color: 'blue', width: 3 }},
                marker: {{ size: 10, color: 'blue' }}
            }});
        }}
        
        if (telemetryData.length > 0) {{
            pathTraces.push({{
                x: telemetryData.map(d => d.lon),
                y: telemetryData.map(d => d.lat),
                mode: 'lines',
                type: 'scatter',
                name: 'Actual Path',
                line: {{ color: 'red', width: 2 }}
            }});
        }}
        
        Plotly.newPlot(pathPlot, pathTraces, {{
            title: 'Mission Path - Planned vs Actual',
            xaxis: {{ title: 'Longitude (degrees)' }},
            yaxis: {{ title: 'Latitude (degrees)' }},
            showlegend: true
        }});
        
        // Depth Profile
        const depthPlot = document.getElementById('depth-plot');
        const depthTraces = [];
        
        if (telemetryData.length > 0) {{
            depthTraces.push({{
                x: telemetryData.map((d, i) => i),
                y: telemetryData.map(d => d.depth),
                mode: 'lines',
                type: 'scatter',
                name: 'Actual Depth',
                line: {{ color: 'blue', width: 2 }},
                fill: 'tozeroy'
            }});
        }}
        
        if (plannedData.length > 0) {{
            const plannedDepthX = plannedData.map((d, i) => i * telemetryData.length / plannedData.length);
            depthTraces.push({{
                x: plannedDepthX,
                y: plannedData.map(d => d.depth),
                mode: 'lines+markers',
                type: 'scatter',
                name: 'Planned Depth',
                line: {{ color: 'red', width: 3 }},
                marker: {{ size: 8, color: 'red' }}
            }});
        }}
        
        Plotly.newPlot(depthPlot, depthTraces, {{
            title: 'Depth Profile Over Time',
            xaxis: {{ title: 'Time (telemetry points)' }},
            yaxis: {{ title: 'Depth (m)', autorange: 'reversed' }},
            showlegend: true
        }});
        
        // Altitude Profile
        const altitudePlot = document.getElementById('altitude-plot');
        if (telemetryData.length > 0) {{
            Plotly.newPlot(altitudePlot, [{{
                x: telemetryData.map((d, i) => i),
                y: telemetryData.map(d => d.altitude),
                mode: 'lines',
                type: 'scatter',
                name: 'Altitude Above Bottom',
                line: {{ color: 'green', width: 2 }},
                fill: 'tozeroy'
            }}], {{
                title: 'Altitude Above Bottom',
                xaxis: {{ title: 'Time (telemetry points)' }},
                yaxis: {{ title: 'Altitude (m)' }},
                showlegend: true
            }});
        }}
        
        // Heading Profile
        const headingPlot = document.getElementById('heading-plot');
        if (telemetryData.length > 0) {{
            Plotly.newPlot(headingPlot, [{{
                x: telemetryData.map((d, i) => i),
                y: telemetryData.map(d => d.heading),
                mode: 'lines',
                type: 'scatter',
                name: 'Vehicle Heading',
                line: {{ color: 'purple', width: 2 }}
            }}], {{
                title: 'Vehicle Heading Over Time',
                xaxis: {{ title: 'Time (telemetry points)' }},
                yaxis: {{ title: 'Heading (degrees)', range: [0, 360] }},
                showlegend: true
            }});
        }}
        
        // 3D Path Plot
        const path3dPlot = document.getElementById('path-3d-plot');
        const path3dTraces = [];
        
        if (plannedData.length > 0) {{
            path3dTraces.push({{
                x: plannedData.map(d => d.lon),
                y: plannedData.map(d => d.lat),
                z: plannedData.map(d => d.depth),
                mode: 'lines+markers',
                type: 'scatter3d',
                name: 'Planned Path',
                line: {{ color: 'blue', width: 6 }},
                marker: {{ size: 8, color: 'blue' }}
            }});
        }}
        
        if (telemetryData.length > 0) {{
            // Subsample for 3D plot performance
            const subsample = telemetryData.filter((d, i) => i % 5 === 0);
            path3dTraces.push({{
                x: subsample.map(d => d.lon),
                y: subsample.map(d => d.lat),
                z: subsample.map(d => d.depth),
                mode: 'lines',
                type: 'scatter3d',
                name: 'Actual Path',
                line: {{ color: 'red', width: 4 }}
            }});
        }}
        
        Plotly.newPlot(path3dPlot, path3dTraces, {{
            title: '3D Mission Path',
            scene: {{
                xaxis: {{ title: 'Longitude' }},
                yaxis: {{ title: 'Latitude' }},
                zaxis: {{ title: 'Depth (m)', autorange: 'reversed' }}
            }},
            showlegend: true
        }});
    </script>
</body>
</html>
        """
        
        with open(html_path, 'w') as f:
            f.write(html_content)
        
        print(f"Interactive HTML visualization created: {html_path}")
        print(f"Open this file in a web browser to view the plots!")
        
        return html_path
    
    def export_comprehensive_data(self):
        """Export all data to CSV files"""
        
        # Export telemetry data to data subfolder
        data_path = Path("data")
        data_path.mkdir(exist_ok=True)
        
        if self.telemetry_data:
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            csv_path = data_path / f'telemetry_data_{timestamp}.csv'
            with open(csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['time_str', 'latitude', 'longitude', 'depth', 'altitude', 'heading'])
                
                for t in self.telemetry_data:
                    writer.writerow([
                        t['time_str'],
                        t['latitude'],
                        t['longitude'], 
                        t['depth'],
                        t['altitude'],
                        t['heading']
                    ])
            print(f"Telemetry data exported to: {csv_path}")
        
        # Export planned waypoints
        if self.planned_waypoints:
            csv_path = data_path / f'planned_waypoints_{timestamp}.csv'
            with open(csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['waypoint_id', 'latitude', 'longitude', 'depth', 'yaw_deg', 'control_mode'])
                
                for i, wp in enumerate(self.planned_waypoints):
                    writer.writerow([i+1, wp['latitude'], wp['longitude'], wp['depth'], wp['yaw_deg'], wp['control_mode']])
            print(f"Planned waypoints exported to: {csv_path}")
    
    def analyze_mission(self):
        """Main analysis function"""
        print(f"HTML-Based Mission Analysis: {self.session_folder}")
        print(f"Session path: {self.session_path}")
        
        if not self.session_path.exists():
            raise FileNotFoundError(f"Session folder not found: {self.session_path}")
        
        # Load all data
        print("\\nLoading mission data...")
        try:
            self.load_mission_json()
            print(f"  ✓ Loaded mission.json with {len(self.planned_waypoints)} waypoints")
        except Exception as e:
            print(f"  ✗ Error loading mission.json: {e}")
        
        try:
            self.load_behavior_data()
            print(f"  ✓ Loaded behavior data with {len(self.behavior_data)} states")
        except Exception as e:
            print(f"  ✗ Error loading behavior data: {e}")
        
        try:
            self.parse_vtt_telemetry()
            print(f"  ✓ Parsed VTT telemetry with {len(self.telemetry_data)} points")
        except Exception as e:
            print(f"  ✗ Error parsing VTT telemetry: {e}")
        
        self.calculate_mission_statistics()
        print(f"  ✓ Calculated comprehensive mission statistics")
        
        # Create outputs
        print("\\nCreating analysis outputs...")
        
        try:
            html_path = self.create_html_visualization()
            print("  ✓ Created interactive HTML visualization")
        except Exception as e:
            print(f"  ✗ Error creating HTML visualization: {e}")
            import traceback
            traceback.print_exc()
        
        try:
            self.export_comprehensive_data()
            print("  ✓ Exported data to CSV files")
        except Exception as e:
            print(f"  ✗ Error exporting data: {e}")
        
        print(f"\\nAnalysis complete! Results saved in: {self.analysis_path}")
        print(f"Generated files:")
        if self.analysis_path.exists():
            for file in sorted(self.analysis_path.glob("*")):
                if file.is_file():
                    size_mb = file.stat().st_size / (1024 * 1024)
                    print(f"  - {file.name} ({size_mb:.2f} MB)")


def main():
    """Main function"""
    if len(sys.argv) != 2:
        print("Usage: python analyze_mission_html.py <session_folder>")
        print("Example: python analyze_mission_html.py session_0076")
        sys.exit(1)
    
    session_folder = sys.argv[1]
    
    try:
        analyzer = HTMLMissionAnalyzer(session_folder, "..")
        analyzer.analyze_mission()
        
    except Exception as e:
        print(f"Error analyzing mission: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
