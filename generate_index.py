#!/usr/bin/env python3
"""
Generate VICAR AUV Mission Dashboard

Creates comprehensive index.html with links to all mission maps, analysis plots,
and comparison reports organized by mission dates.

Usage: python generate_index.py
"""

import os
import re
import json
import datetime
from pathlib import Path
from typing import Dict, List, Tuple

def extract_sessions_from_html(html_file: Path) -> List[str]:
    """Extract session names from HTML file content"""
    try:
        with open(html_file, 'r') as f:
            content = f.read()
        
        # Look for session names in the JavaScript data
        session_matches = re.findall(r'session_\d+', content)
        return list(set(session_matches))  # Remove duplicates
        
    except Exception as e:
        print(f"Error reading {html_file}: {e}")
        return []

def get_mission_info_from_vtt(session_folder: str) -> Dict:
    """Extract mission information from VTT files"""
    session_path = Path("..") / session_folder
    videos_path = session_path / "videos"
    
    if not videos_path.exists():
        return {}
    
    vtt_files = list(videos_path.glob("*.vtt"))
    if not vtt_files:
        return {}
    
    # Parse first VTT file for mission info
    vtt_file = vtt_files[0]
    try:
        with open(vtt_file, 'r') as f:
            content = f.read()
        
        # Find first telemetry block
        blocks = content.split('\n\n')
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 3 and '-->' in lines[0]:
                mission_name = lines[1] if len(lines) > 1 else ""
                
                # Extract date from VTT
                if len(lines) > 2:
                    date_match = re.search(r'(\w{3} \w{3} \d{1,2} \d{2}:\d{2}:\d{2} \d{4})', lines[2])
                    if date_match:
                        date_str = date_match.group(1)
                        try:
                            mission_date = datetime.datetime.strptime(date_str, '%a %b %d %H:%M:%S %Y')
                            return {
                                'mission_name': mission_name,
                                'mission_date': mission_date,
                                'date_str': date_str
                            }
                        except:
                            pass
        
        return {}
    except Exception as e:
        return {}

def get_mission_name_from_file(session_folder: str) -> str:
    """Get mission name from mission_name.txt file"""
    session_path = Path("..") / session_folder
    mission_name_path = session_path / "missions" / "mission_name.txt"
    
    if mission_name_path.exists():
        try:
            with open(mission_name_path, 'r') as f:
                return f.read().strip()
        except:
            pass
    
    return "Unknown Mission"

def generate_dashboard_index():
    """Generate comprehensive dashboard index.html"""
    current_dir = Path(".")
    
    # Find all files
    map_files = list(current_dir.glob("AUV_mission_map_*.html"))
    analysis_files = list(current_dir.glob("mission_analysis_*.html"))
    comparison_files = list(current_dir.glob("mission_comparison_*.html"))
    
    print(f"Found {len(map_files)} mission maps, {len(analysis_files)} analysis reports, {len(comparison_files)} comparison reports")
    
    # Process mission maps
    map_info = []
    for map_file in map_files:
        sessions = extract_sessions_from_html(map_file)
        
        mission_data = []
        earliest_date = None
        
        for session in sessions:
            session_path = Path("..") / session
            if session_path.exists():
                vtt_info = get_mission_info_from_vtt(session)
                mission_name = get_mission_name_from_file(session)
                
                if vtt_info and 'mission_date' in vtt_info:
                    mission_data.append({
                        'session': session,
                        'mission_name': mission_name,
                        'date': vtt_info['mission_date'],
                        'date_str': vtt_info['date_str']
                    })
                    
                    if earliest_date is None or vtt_info['mission_date'] < earliest_date:
                        earliest_date = vtt_info['mission_date']
                else:
                    mission_data.append({
                        'session': session,
                        'mission_name': mission_name,
                        'date': None,
                        'date_str': 'Unknown'
                    })
        
        file_time = datetime.datetime.fromtimestamp(map_file.stat().st_mtime)
        
        map_info.append({
            'filename': map_file.name,
            'sessions': sessions,
            'mission_data': mission_data,
            'earliest_date': earliest_date or file_time,
            'file_time': file_time
        })
    
    # Process analysis files
    analysis_info = []
    for analysis_file in analysis_files:
        sessions = extract_sessions_from_html(analysis_file)
        file_time = datetime.datetime.fromtimestamp(analysis_file.stat().st_mtime)
        
        mission_data = []
        for session in sessions:
            mission_name = get_mission_name_from_file(session)
            mission_data.append({
                'session': session,
                'mission_name': mission_name
            })
        
        analysis_info.append({
            'filename': analysis_file.name,
            'sessions': sessions,
            'mission_data': mission_data,
            'file_time': file_time
        })
    
    # Process comparison files
    comparison_info = []
    for comp_file in comparison_files:
        sessions = extract_sessions_from_html(comp_file)
        file_time = datetime.datetime.fromtimestamp(comp_file.stat().st_mtime)
        
        comparison_info.append({
            'filename': comp_file.name,
            'sessions': sessions,
            'file_time': file_time
        })
    
    # Sort by date
    map_info.sort(key=lambda x: x['earliest_date'])
    analysis_info.sort(key=lambda x: x['file_time'])
    comparison_info.sort(key=lambda x: x['file_time'])
    
    # Generate HTML
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VICAR AUV Mission Dashboard</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a0a;
            color: #ffffff;
            margin: 0;
            padding: 40px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: rgba(15, 15, 15, 0.95);
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        h1 {{
            color: #E20074;
            text-align: center;
            margin-bottom: 10px;
            font-size: 32px;
            font-weight: 700;
        }}
        h2 {{
            color: #ffffff;
            text-align: center;
            margin-bottom: 30px;
            font-size: 18px;
            font-weight: normal;
        }}
        h3 {{
            color: #E20074;
            margin-top: 40px;
            margin-bottom: 20px;
            font-size: 20px;
            border-bottom: 2px solid #E20074;
            padding-bottom: 10px;
        }}
        .card {{
            background: rgba(30, 30, 30, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            transition: transform 0.2s ease;
        }}
        .card:hover {{
            transform: translateY(-2px);
            border-color: #E20074;
        }}
        .card-title {{
            color: #E20074;
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 10px;
        }}
        .card-info {{
            color: #ccc;
            font-size: 14px;
            margin-bottom: 15px;
        }}
        .session-list {{
            margin: 10px 0;
        }}
        .session-item {{
            background: rgba(0, 123, 255, 0.1);
            padding: 8px 12px;
            border-radius: 4px;
            margin: 5px 0;
            border-left: 3px solid #007bff;
        }}
        .button {{
            display: inline-block;
            background: linear-gradient(135deg, #E20074, #ff4081);
            color: white;
            text-decoration: none;
            padding: 12px 25px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.2s ease;
            margin: 5px 10px 5px 0;
        }}
        .button:hover {{
            background: linear-gradient(135deg, #ff4081, #E20074);
            box-shadow: 0 4px 15px rgba(226, 0, 116, 0.4);
        }}
        .button.secondary {{
            background: linear-gradient(135deg, #007bff, #0056b3);
        }}
        .button.secondary:hover {{
            background: linear-gradient(135deg, #0056b3, #007bff);
            box-shadow: 0 4px 15px rgba(0, 123, 255, 0.4);
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            color: #666;
            font-size: 12px;
        }}
        .no-data {{
            text-align: center;
            color: #666;
            font-style: italic;
            padding: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>VICAR</h1>
        <h2>AUV Mission Dashboard</h2>
        
        <h3>Mission Maps</h3>
"""
    
    # Add mission maps
    if map_info:
        for info in map_info:
            # Create mission summary
            session_summary = []
            for mission in info['mission_data']:
                date_display = mission['date_str'] if mission['date_str'] != 'Unknown' else 'No date'
                session_summary.append(f"{mission['session']}: {mission['mission_name']}")
            
            # Format earliest date
            if info['earliest_date']:
                date_display = info['earliest_date'].strftime('%Y-%m-%d %H:%M UTC')
            else:
                date_display = "Unknown date"
            
            html_content += f"""
        <div class="card">
            <div class="card-title">{', '.join(info['sessions'])}</div>
            <div class="card-info">
                <strong>Mission Date:</strong> {date_display}<br>
                <strong>Created:</strong> {info['file_time'].strftime('%Y-%m-%d %H:%M')}
            </div>
            
            <div class="session-list">
"""
            
            for mission in info['mission_data']:
                html_content += f"""
                <div class="session-item">
                    <strong>{mission['session']}:</strong> {mission['mission_name']}<br>
                    <small>{mission['date_str'] if mission['date_str'] != 'Unknown' else 'No telemetry date'}</small>
                </div>
"""
            
            html_content += f"""
            </div>
            
            <a href="{info['filename']}" class="button">View Mission Map</a>
        </div>
"""
    else:
        html_content += '<div class="no-data">No mission maps found</div>'
    
    # Add analysis section
    html_content += '\n        <h3>Mission Analysis</h3>\n'
    
    if analysis_info:
        for info in analysis_info:
            html_content += f"""
        <div class="card">
            <div class="card-title">Analysis: {', '.join(info['sessions'])}</div>
            <div class="card-info">
                <strong>Created:</strong> {info['file_time'].strftime('%Y-%m-%d %H:%M')}
            </div>
            
            <div class="session-list">
"""
            
            for mission in info['mission_data']:
                html_content += f"""
                <div class="session-item">
                    <strong>{mission['session']}:</strong> {mission['mission_name']}
                </div>
"""
            
            html_content += f"""
            </div>
            
            <a href="{info['filename']}" class="button secondary">View Analysis Plots</a>
        </div>
"""
    else:
        html_content += '<div class="no-data">No analysis reports found</div>'
    
    # Add comparison section
    html_content += '\n        <h3>Mission Comparisons</h3>\n'
    
    if comparison_info:
        for info in comparison_info:
            html_content += f"""
        <div class="card">
            <div class="card-title">Comparison: {', '.join(info['sessions'])}</div>
            <div class="card-info">
                <strong>Sessions Compared:</strong> {len(info['sessions'])}<br>
                <strong>Created:</strong> {info['file_time'].strftime('%Y-%m-%d %H:%M')}
            </div>
            
            <a href="{info['filename']}" class="button secondary">View Comparison</a>
        </div>
"""
    else:
        html_content += '<div class="no-data">No comparison reports found</div>'
    
    html_content += f"""
        
        <div class="footer">
            VICAR AUV Mission Dashboard<br>
            Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
            Autonomous Underwater Vehicle Operations
        </div>
    </div>
</body>
</html>
"""
    
    # Write the index.html
    index_path = Path("index.html")
    with open(index_path, 'w') as f:
        f.write(html_content)
    
    print(f"VICAR dashboard created: {index_path}")
    print(f"Mission maps: {len(map_info)}")
    print(f"Analysis reports: {len(analysis_info)}")
    print(f"Comparison reports: {len(comparison_info)}")
    
    return index_path

def main():
    """Main function"""
    try:
        index_path = generate_dashboard_index()
        print(f"\\nSuccess! Open {index_path} in your browser")
        
    except Exception as e:
        print(f"Error generating dashboard: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
