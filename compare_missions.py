#!/usr/bin/env python3
"""
Mission Comparison and Precision Analysis Script

Compares multiple repeated AUV missions to analyze:
1. Precision: How closely repeated missions follow each other
2. Accuracy: How closely actual missions follow the planned path
3. Statistical analysis of path deviations

Usage: python compare_missions.py <session1> <session2> [session3] [session4] ...
Example: python compare_missions.py session_0074 session_0076 session_0079
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
import statistics

class MissionComparator:
    """Analyzes precision and accuracy of repeated AUV missions"""
    
    def __init__(self, session_folders: List[str], root_path: str = ".."):
        self.session_folders = session_folders
        self.root_path = Path(root_path)
        self.sessions_data = {}
        self.comparison_stats = {}
        
        # Output to auvmap directory
        self.output_path = Path(".")
        
    def parse_vtt_telemetry(self, session_folder: str) -> List[Dict]:
        """Parse VTT telemetry files for actual path data"""
        session_path = self.root_path / session_folder
        videos_path = session_path / "videos"
        telemetry_data = []
        
        if not videos_path.exists():
            print(f"No videos folder found in {session_folder}")
            return telemetry_data
        
        # Find VTT files
        vtt_files = list(videos_path.glob("*.vtt"))
        if not vtt_files:
            print(f"No VTT telemetry files found in {session_folder}")
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
                        
                        # Convert to seconds for easier comparison
                        time_parts = time_str.split(':')
                        time_seconds = (float(time_parts[0]) * 3600 + 
                                      float(time_parts[1]) * 60 + 
                                      float(time_parts[2]))
                        
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
                                'time_seconds': time_seconds,
                                'time_str': time_str,
                                'heading': heading,
                                'latitude': latitude,
                                'longitude': longitude,
                                'depth': depth,
                                'altitude': altitude
                            })
                    
                    except Exception as e:
                        continue
        
        # Sort by time
        telemetry_data.sort(key=lambda x: x['time_seconds'])
        print(f"  Parsed {len(telemetry_data)} telemetry points from {session_folder}")
        return telemetry_data
    
    def load_mission_json(self, session_folder: str) -> Dict:
        """Load and parse mission.json file"""
        session_path = self.root_path / session_folder
        mission_json_path = session_path / "missions" / "mission.json"
        
        if not mission_json_path.exists():
            print(f"Warning: Mission JSON not found in {session_folder}")
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
    
    def find_closest_point(self, target_point: Dict, path_points: List[Dict]) -> Tuple[Dict, float]:
        """Find the closest point in a path to a target point"""
        min_distance = float('inf')
        closest_point = None
        
        for point in path_points:
            if point['latitude'] is not None and point['longitude'] is not None:
                distance = self.calculate_distance(
                    target_point['latitude'], target_point['longitude'],
                    point['latitude'], point['longitude']
                )
                if distance < min_distance:
                    min_distance = distance
                    closest_point = point
        
        return closest_point, min_distance
    
    def resample_path_by_distance(self, telemetry_data: List[Dict], interval_m: float = 1.0) -> List[Dict]:
        """Resample telemetry path at regular distance intervals"""
        if not telemetry_data:
            return []
        
        resampled = [telemetry_data[0]]  # Start with first point
        current_distance = 0.0
        
        for i in range(1, len(telemetry_data)):
            prev_point = telemetry_data[i-1]
            curr_point = telemetry_data[i]
            
            if (prev_point['latitude'] is not None and prev_point['longitude'] is not None and
                curr_point['latitude'] is not None and curr_point['longitude'] is not None):
                
                segment_distance = self.calculate_distance(
                    prev_point['latitude'], prev_point['longitude'],
                    curr_point['latitude'], curr_point['longitude']
                )
                
                current_distance += segment_distance
                
                if current_distance >= interval_m:
                    resampled.append(curr_point)
                    current_distance = 0.0
        
        return resampled
    
    def calculate_path_statistics(self, path1: List[Dict], path2: List[Dict]) -> Dict:
        """Calculate statistical comparison between two paths"""
        if not path1 or not path2:
            return {}
        
        # Resample both paths at regular intervals for fair comparison
        resampled_path1 = self.resample_path_by_distance(path1, 0.5)  # Every 0.5m
        resampled_path2 = self.resample_path_by_distance(path2, 0.5)
        
        distances = []
        depth_differences = []
        altitude_differences = []
        heading_differences = []
        
        # Compare each point in path1 to closest point in path2
        for point1 in resampled_path1:
            if point1['latitude'] is not None and point1['longitude'] is not None:
                closest_point2, distance = self.find_closest_point(point1, resampled_path2)
                
                if closest_point2 is not None:
                    distances.append(distance)
                    
                    # Depth comparison
                    if point1['depth'] is not None and closest_point2['depth'] is not None:
                        depth_differences.append(abs(point1['depth'] - closest_point2['depth']))
                    
                    # Altitude comparison
                    if point1['altitude'] is not None and closest_point2['altitude'] is not None:
                        altitude_differences.append(abs(point1['altitude'] - closest_point2['altitude']))
                    
                    # Heading comparison (handle wraparound)
                    if point1['heading'] is not None and closest_point2['heading'] is not None:
                        heading_diff = abs(point1['heading'] - closest_point2['heading'])
                        if heading_diff > 180:
                            heading_diff = 360 - heading_diff
                        heading_differences.append(heading_diff)
        
        stats = {}
        
        if distances:
            stats['position_stats'] = {
                'mean_distance_m': statistics.mean(distances),
                'median_distance_m': statistics.median(distances),
                'std_distance_m': statistics.stdev(distances) if len(distances) > 1 else 0,
                'max_distance_m': max(distances),
                'min_distance_m': min(distances),
                'rms_distance_m': math.sqrt(sum(d**2 for d in distances) / len(distances)),
                'percentile_95_m': sorted(distances)[int(0.95 * len(distances))] if len(distances) > 20 else max(distances)
            }
        
        if depth_differences:
            stats['depth_stats'] = {
                'mean_diff_m': statistics.mean(depth_differences),
                'median_diff_m': statistics.median(depth_differences),
                'std_diff_m': statistics.stdev(depth_differences) if len(depth_differences) > 1 else 0,
                'max_diff_m': max(depth_differences)
            }
        
        if altitude_differences:
            stats['altitude_stats'] = {
                'mean_diff_m': statistics.mean(altitude_differences),
                'median_diff_m': statistics.median(altitude_differences),
                'std_diff_m': statistics.stdev(altitude_differences) if len(altitude_differences) > 1 else 0,
                'max_diff_m': max(altitude_differences)
            }
        
        if heading_differences:
            stats['heading_stats'] = {
                'mean_diff_deg': statistics.mean(heading_differences),
                'median_diff_deg': statistics.median(heading_differences),
                'std_diff_deg': statistics.stdev(heading_differences) if len(heading_differences) > 1 else 0,
                'max_diff_deg': max(heading_differences)
            }
        
        return stats
    
    def calculate_accuracy_to_planned(self, telemetry_data: List[Dict], planned_waypoints: List[Dict]) -> Dict:
        """Calculate how accurately actual path follows planned waypoints"""
        if not telemetry_data or not planned_waypoints:
            return {}
        
        # Resample telemetry for consistent analysis
        resampled_telemetry = self.resample_path_by_distance(telemetry_data, 0.5)
        
        distances_to_planned = []
        depth_errors = []
        
        for telem_point in resampled_telemetry:
            if telem_point['latitude'] is not None and telem_point['longitude'] is not None:
                # Find closest planned waypoint
                min_distance = float('inf')
                closest_waypoint = None
                
                for waypoint in planned_waypoints:
                    distance = self.calculate_distance(
                        telem_point['latitude'], telem_point['longitude'],
                        waypoint['latitude'], waypoint['longitude']
                    )
                    if distance < min_distance:
                        min_distance = distance
                        closest_waypoint = waypoint
                
                if closest_waypoint is not None:
                    distances_to_planned.append(min_distance)
                    
                    # Depth error
                    if telem_point['depth'] is not None:
                        depth_error = abs(telem_point['depth'] - closest_waypoint['depth'])
                        depth_errors.append(depth_error)
        
        accuracy_stats = {}
        
        if distances_to_planned:
            accuracy_stats['position_accuracy'] = {
                'mean_error_m': statistics.mean(distances_to_planned),
                'median_error_m': statistics.median(distances_to_planned),
                'std_error_m': statistics.stdev(distances_to_planned) if len(distances_to_planned) > 1 else 0,
                'max_error_m': max(distances_to_planned),
                'rms_error_m': math.sqrt(sum(d**2 for d in distances_to_planned) / len(distances_to_planned)),
                'percentile_95_m': sorted(distances_to_planned)[int(0.95 * len(distances_to_planned))] if len(distances_to_planned) > 20 else max(distances_to_planned)
            }
        
        if depth_errors:
            accuracy_stats['depth_accuracy'] = {
                'mean_error_m': statistics.mean(depth_errors),
                'median_error_m': statistics.median(depth_errors),
                'std_error_m': statistics.stdev(depth_errors) if len(depth_errors) > 1 else 0,
                'max_error_m': max(depth_errors)
            }
        
        return accuracy_stats
    
    def load_all_sessions(self):
        """Load data from all specified sessions"""
        print(f"Loading data from {len(self.session_folders)} sessions...")
        
        for session in self.session_folders:
            print(f"\nProcessing {session}...")
            
            session_data = {
                'session_name': session,
                'mission_data': self.load_mission_json(session),
                'telemetry_data': self.parse_vtt_telemetry(session)
            }
            
            self.sessions_data[session] = session_data
    
    def compare_all_sessions(self):
        """Perform comprehensive comparison analysis"""
        print("\n" + "="*60)
        print("MISSION COMPARISON ANALYSIS")
        print("="*60)
        
        sessions_with_telemetry = {k: v for k, v in self.sessions_data.items() 
                                 if v['telemetry_data']}
        
        if len(sessions_with_telemetry) < 2:
            print("ERROR: Need at least 2 sessions with VTT telemetry data for comparison")
            return
        
        session_names = list(sessions_with_telemetry.keys())
        
        # Pairwise precision analysis (mission vs mission)
        print(f"\nPRECISION ANALYSIS (Mission-to-Mission Comparison)")
        print("-" * 50)
        
        precision_results = {}
        
        for i in range(len(session_names)):
            for j in range(i + 1, len(session_names)):
                session1 = session_names[i]
                session2 = session_names[j]
                
                print(f"\nComparing {session1} vs {session2}:")
                
                telemetry1 = sessions_with_telemetry[session1]['telemetry_data']
                telemetry2 = sessions_with_telemetry[session2]['telemetry_data']
                
                precision_stats = self.calculate_path_statistics(telemetry1, telemetry2)
                precision_results[f"{session1}_vs_{session2}"] = precision_stats
                
                if 'position_stats' in precision_stats:
                    pos_stats = precision_stats['position_stats']
                    print(f"  Position Precision:")
                    print(f"    Mean deviation: {pos_stats['mean_distance_m']:.2f}m")
                    print(f"    RMS deviation:  {pos_stats['rms_distance_m']:.2f}m")
                    print(f"    Max deviation:  {pos_stats['max_distance_m']:.2f}m")
                    print(f"    95th percentile: {pos_stats['percentile_95_m']:.2f}m")
                
                if 'depth_stats' in precision_stats:
                    depth_stats = precision_stats['depth_stats']
                    print(f"  Depth Precision:")
                    print(f"    Mean difference: {depth_stats['mean_diff_m']:.2f}m")
                    print(f"    Max difference:  {depth_stats['max_diff_m']:.2f}m")
                
                if 'heading_stats' in precision_stats:
                    heading_stats = precision_stats['heading_stats']
                    print(f"  Heading Precision:")
                    print(f"    Mean difference: {heading_stats['mean_diff_deg']:.1f}°")
                    print(f"    Max difference:  {heading_stats['max_diff_deg']:.1f}°")
        
        # Accuracy analysis (actual vs planned)
        print(f"\n\nACCURACY ANALYSIS (Actual vs Planned Path)")
        print("-" * 50)
        
        accuracy_results = {}
        
        for session_name, session_data in sessions_with_telemetry.items():
            if session_data['mission_data'] and 'planned_waypoints' in session_data['mission_data']:
                planned_waypoints = session_data['mission_data']['planned_waypoints']
                telemetry_data = session_data['telemetry_data']
                
                print(f"\n{session_name} accuracy to planned path:")
                
                accuracy_stats = self.calculate_accuracy_to_planned(telemetry_data, planned_waypoints)
                accuracy_results[session_name] = accuracy_stats
                
                if 'position_accuracy' in accuracy_stats:
                    pos_acc = accuracy_stats['position_accuracy']
                    print(f"  Position Accuracy:")
                    print(f"    Mean error: {pos_acc['mean_error_m']:.2f}m")
                    print(f"    RMS error:  {pos_acc['rms_error_m']:.2f}m")
                    print(f"    Max error:  {pos_acc['max_error_m']:.2f}m")
                    print(f"    95th percentile: {pos_acc['percentile_95_m']:.2f}m")
                
                if 'depth_accuracy' in accuracy_stats:
                    depth_acc = accuracy_stats['depth_accuracy']
                    print(f"  Depth Accuracy:")
                    print(f"    Mean error: {depth_acc['mean_error_m']:.2f}m")
                    print(f"    Max error:  {depth_acc['max_error_m']:.2f}m")
        
        # Store results
        self.comparison_stats = {
            'precision_results': precision_results,
            'accuracy_results': accuracy_results,
            'sessions_analyzed': list(sessions_with_telemetry.keys()),
            'analysis_date': datetime.datetime.now().isoformat()
        }
    
    def create_html_comparison(self):
        """Create interactive HTML visualization comparing missions"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        html_path = self.output_path / f'mission_comparison_{timestamp}.html'
        
        # Prepare data for JavaScript
        sessions_js_data = {}
        
        for session_name, session_data in self.sessions_data.items():
            if session_data['telemetry_data']:
                # Subsample telemetry for performance
                telemetry = session_data['telemetry_data']
                step = max(1, len(telemetry) // 500)  # Max 500 points per mission
                
                sessions_js_data[session_name] = {
                    'telemetry': [
                        {
                            'lat': t['latitude'],
                            'lon': t['longitude'],
                            'depth': t['depth'] if t['depth'] is not None else 0,
                            'altitude': t['altitude'] if t['altitude'] is not None else 0,
                            'heading': t['heading'] if t['heading'] is not None else 0,
                            'time': t['time_str']
                        }
                        for t in telemetry[::step]
                        if t['latitude'] is not None and t['longitude'] is not None
                    ],
                    'planned': [
                        {
                            'lat': wp['latitude'],
                            'lon': wp['longitude'],
                            'depth': wp['depth']
                        }
                        for wp in session_data['mission_data'].get('planned_waypoints', [])
                    ] if session_data['mission_data'] else []
                }
        
        # Generate colors for different missions
        colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']
        
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mission Comparison Analysis</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
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
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
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
            height: 600px;
        }}
        .plot-container-large {{
            margin: 20px 0;
            height: 800px;
        }}
        .precision-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 12px;
        }}
        .precision-table th, .precision-table td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: center;
        }}
        .precision-table th {{
            background-color: #3498db;
            color: white;
        }}
        .precision-table tr:nth-child(even) {{
            background-color: #f2f2f2;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Mission Comparison Analysis</h1>
        <p><strong>Sessions Compared:</strong> {', '.join(self.sessions_data.keys())}</p>
        <p><strong>Analysis Date:</strong> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <h2>Mission Path Overlay</h2>
        <div id="path-comparison-plot" class="plot-container-large"></div>
        
        <h2>Depth Profile Comparison</h2>
        <div id="depth-comparison-plot" class="plot-container"></div>
        
        <h2>3D Mission Comparison</h2>
        <div id="path-3d-comparison" class="plot-container-large"></div>
        
        <h2>Precision Statistics</h2>
        <div class="stats-grid">
            {self.generate_precision_cards()}
        </div>
        
        <h2>Accuracy Statistics</h2>
        <div class="stats-grid">
            {self.generate_accuracy_cards()}
        </div>
    </div>
    
    <script>
        // Data
        const sessionsData = {json.dumps(sessions_js_data)};
        const colors = {json.dumps(colors[:len(sessions_js_data)])};
        
        // 2D Path Comparison
        const pathComparisonPlot = document.getElementById('path-comparison-plot');
        const pathTraces = [];
        
        let colorIndex = 0;
        Object.keys(sessionsData).forEach(sessionName => {{
            const sessionData = sessionsData[sessionName];
            const color = colors[colorIndex % colors.length];
            
            // Planned path
            if (sessionData.planned.length > 0) {{
                pathTraces.push({{
                    x: sessionData.planned.map(d => d.lon),
                    y: sessionData.planned.map(d => d.lat),
                    mode: 'lines+markers',
                    type: 'scatter',
                    name: `${{sessionName}} (Planned)`,
                    line: {{ color: color, width: 3, dash: 'dash' }},
                    marker: {{ size: 8, color: color, symbol: 'square' }}
                }});
            }}
            
            // Actual path
            if (sessionData.telemetry.length > 0) {{
                pathTraces.push({{
                    x: sessionData.telemetry.map(d => d.lon),
                    y: sessionData.telemetry.map(d => d.lat),
                    mode: 'lines',
                    type: 'scatter',
                    name: `${{sessionName}} (Actual)`,
                    line: {{ color: color, width: 2 }}
                }});
            }}
            
            colorIndex++;
        }});
        
        Plotly.newPlot(pathComparisonPlot, pathTraces, {{
            title: 'Mission Path Comparison - All Sessions',
            xaxis: {{ title: 'Longitude (degrees)' }},
            yaxis: {{ title: 'Latitude (degrees)' }},
            showlegend: true,
            legend: {{ orientation: 'h', y: -0.2 }}
        }});
        
        // Depth Comparison
        const depthComparisonPlot = document.getElementById('depth-comparison-plot');
        const depthTraces = [];
        
        colorIndex = 0;
        Object.keys(sessionsData).forEach(sessionName => {{
            const sessionData = sessionsData[sessionName];
            const color = colors[colorIndex % colors.length];
            
            if (sessionData.telemetry.length > 0) {{
                depthTraces.push({{
                    x: sessionData.telemetry.map((d, i) => i),
                    y: sessionData.telemetry.map(d => d.depth),
                    mode: 'lines',
                    type: 'scatter',
                    name: sessionName,
                    line: {{ color: color, width: 2 }}
                }});
            }}
            
            colorIndex++;
        }});
        
        Plotly.newPlot(depthComparisonPlot, depthTraces, {{
            title: 'Depth Profile Comparison',
            xaxis: {{ title: 'Telemetry Points' }},
            yaxis: {{ title: 'Depth (m)', autorange: 'reversed' }},
            showlegend: true
        }});
        
        // 3D Comparison
        const path3dComparisonPlot = document.getElementById('path-3d-comparison');
        const path3dTraces = [];
        
        colorIndex = 0;
        Object.keys(sessionsData).forEach(sessionName => {{
            const sessionData = sessionsData[sessionName];
            const color = colors[colorIndex % colors.length];
            
            // Planned path
            if (sessionData.planned.length > 0) {{
                path3dTraces.push({{
                    x: sessionData.planned.map(d => d.lon),
                    y: sessionData.planned.map(d => d.lat),
                    z: sessionData.planned.map(d => d.depth),
                    mode: 'lines+markers',
                    type: 'scatter3d',
                    name: `${{sessionName}} (Planned)`,
                    line: {{ color: color, width: 6, dash: 'dash' }},
                    marker: {{ size: 6, color: color, symbol: 'square' }}
                }});
            }}
            
            // Actual path (subsampled for 3D performance)
            if (sessionData.telemetry.length > 0) {{
                const subsample = sessionData.telemetry.filter((d, i) => i % 3 === 0);
                path3dTraces.push({{
                    x: subsample.map(d => d.lon),
                    y: subsample.map(d => d.lat),
                    z: subsample.map(d => d.depth),
                    mode: 'lines',
                    type: 'scatter3d',
                    name: `${{sessionName}} (Actual)`,
                    line: {{ color: color, width: 4 }}
                }});
            }}
            
            colorIndex++;
        }});
        
        Plotly.newPlot(path3dComparisonPlot, path3dTraces, {{
            title: '3D Mission Path Comparison',
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
        
        print(f"\nInteractive comparison visualization created: {html_path}")
        return html_path
    
    def generate_precision_cards(self) -> str:
        """Generate HTML cards for precision statistics"""
        if 'precision_results' not in self.comparison_stats:
            return "<p>No precision data available</p>"
        
        cards_html = ""
        for comparison, stats in self.comparison_stats['precision_results'].items():
            if 'position_stats' in stats:
                pos_stats = stats['position_stats']
                cards_html += f"""
                <div class="stats-card">
                    <h3>{comparison}</h3>
                    <p><strong>Mean Deviation:</strong> {pos_stats['mean_distance_m']:.2f}m</p>
                    <p><strong>RMS Deviation:</strong> {pos_stats['rms_distance_m']:.2f}m</p>
                    <p><strong>Max Deviation:</strong> {pos_stats['max_distance_m']:.2f}m</p>
                    <p><strong>95th Percentile:</strong> {pos_stats['percentile_95_m']:.2f}m</p>
                </div>
                """
        
        return cards_html
    
    def generate_accuracy_cards(self) -> str:
        """Generate HTML cards for accuracy statistics"""
        if 'accuracy_results' not in self.comparison_stats:
            return "<p>No accuracy data available</p>"
        
        cards_html = ""
        for session, stats in self.comparison_stats['accuracy_results'].items():
            if 'position_accuracy' in stats:
                pos_acc = stats['position_accuracy']
                cards_html += f"""
                <div class="stats-card">
                    <h3>{session} vs Planned</h3>
                    <p><strong>Mean Error:</strong> {pos_acc['mean_error_m']:.2f}m</p>
                    <p><strong>RMS Error:</strong> {pos_acc['rms_error_m']:.2f}m</p>
                    <p><strong>Max Error:</strong> {pos_acc['max_error_m']:.2f}m</p>
                    <p><strong>95th Percentile:</strong> {pos_acc['percentile_95_m']:.2f}m</p>
                </div>
                """
        
        return cards_html
    
    def export_comparison_data(self):
        """Export comparison statistics to CSV files"""
        
        # Export precision statistics to data subfolder
        data_path = Path("data")
        data_path.mkdir(exist_ok=True)
        
        if 'precision_results' in self.comparison_stats:
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            precision_csv = data_path / f'precision_statistics_{timestamp}.csv'
            with open(precision_csv, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Comparison', 'Mean_Distance_m', 'RMS_Distance_m', 'Max_Distance_m', 
                               'Std_Distance_m', 'Percentile_95_m', 'Mean_Depth_Diff_m', 'Mean_Heading_Diff_deg'])
                
                for comparison, stats in self.comparison_stats['precision_results'].items():
                    row = [comparison]
                    
                    if 'position_stats' in stats:
                        pos_stats = stats['position_stats']
                        row.extend([
                            pos_stats['mean_distance_m'],
                            pos_stats['rms_distance_m'],
                            pos_stats['max_distance_m'],
                            pos_stats['std_distance_m'],
                            pos_stats['percentile_95_m']
                        ])
                    else:
                        row.extend([None, None, None, None, None])
                    
                    if 'depth_stats' in stats:
                        row.append(stats['depth_stats']['mean_diff_m'])
                    else:
                        row.append(None)
                    
                    if 'heading_stats' in stats:
                        row.append(stats['heading_stats']['mean_diff_deg'])
                    else:
                        row.append(None)
                    
                    writer.writerow(row)
            
            print(f"Precision statistics exported to: {precision_csv}")
        
        # Export accuracy statistics
        if 'accuracy_results' in self.comparison_stats:
            accuracy_csv = data_path / f'accuracy_statistics_{timestamp}.csv'
            with open(accuracy_csv, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Session', 'Mean_Error_m', 'RMS_Error_m', 'Max_Error_m', 
                               'Std_Error_m', 'Percentile_95_m', 'Mean_Depth_Error_m'])
                
                for session, stats in self.comparison_stats['accuracy_results'].items():
                    row = [session]
                    
                    if 'position_accuracy' in stats:
                        pos_acc = stats['position_accuracy']
                        row.extend([
                            pos_acc['mean_error_m'],
                            pos_acc['rms_error_m'],
                            pos_acc['max_error_m'],
                            pos_acc['std_error_m'],
                            pos_acc['percentile_95_m']
                        ])
                    else:
                        row.extend([None, None, None, None, None])
                    
                    if 'depth_accuracy' in stats:
                        row.append(stats['depth_accuracy']['mean_error_m'])
                    else:
                        row.append(None)
                    
                    writer.writerow(row)
            
            print(f"Accuracy statistics exported to: {accuracy_csv}")
    
    def run_comparison(self):
        """Run complete comparison analysis"""
        print("MISSION PRECISION AND ACCURACY COMPARISON")
        print("=" * 50)
        
        # Load all session data
        self.load_all_sessions()
        
        # Perform comparisons
        self.compare_all_sessions()
        
        # Create visualizations
        try:
            self.create_html_comparison()
        except Exception as e:
            print(f"Error creating HTML visualization: {e}")
        
        # Export data
        try:
            self.export_comparison_data()
        except Exception as e:
            print(f"Error exporting data: {e}")
        
        print(f"\nComparison analysis complete!")
        print(f"Results saved in: {self.output_path}")
        print(f"Open mission_comparison.html in a web browser to view interactive plots.")


def main():
    """Main function"""
    if len(sys.argv) < 3:
        print("Usage: python compare_missions.py <session1> <session2> [session3] [session4] ...")
        print("Example: python compare_missions.py session_0074 session_0076 session_0079")
        print("\nThis script compares repeated AUV missions to analyze:")
        print("  - Precision: How closely repeated missions follow each other")
        print("  - Accuracy: How closely actual missions follow the planned path")
        sys.exit(1)
    
    session_folders = sys.argv[1:]
    
    try:
        comparator = MissionComparator(session_folders, "..")
        comparator.run_comparison()
        
    except Exception as e:
        print(f"Error in mission comparison: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
