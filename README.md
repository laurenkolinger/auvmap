# VICAR AUV Mission Analysis Tools

Quick analysis tools for Hydrus AUV mission data.

## Usage

Place session folders (session_XXXX) in the parent directory, then run:

### Mission Maps
```python
python AUV_mission_map_html.py session_0079
python AUV_mission_map_html.py session_0081 session_0079 session_0083
```

### Mission Analysis
```python
python analyze_mission_html.py session_0079
```

### Mission Comparison
```python
python compare_missions.py session_0079 session_0083
```

### Dashboard
```python
python generate_index.py
```

Then open `index.html` in your browser.

## Files Generated

- `AUV_mission_map_YYYYMMDD_HHMMSS.html` - Interactive satellite maps
- `mission_analysis_YYYYMMDD_HHMMSS.html` - Statistical analysis plots  
- `mission_comparison_YYYYMMDD_HHMMSS.html` - Precision comparison reports
- `index.html` - Dashboard with links to all reports
