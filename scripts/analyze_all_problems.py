import json
from pathlib import Path

# Load full problem list
problems_full = json.loads(Path('scratch/HorizonMath/data/problems_full.json').read_text())
pids = [p['pid'] for p in problems_full]

v14_dir = Path('achievement_output/v14_results')
v16_dir = Path('achievement_output/v16_offline')
v3_dir = Path('../brain/142e4281-5564-4819-8826-7d615d389330/achievement_output/v3_results')  # from artifacts
v14_brain = Path('../brain/142e4281-5564-4819-8826-7d615d389330/achievement_output/v14_results')

def get_sketch(file_path):
    if not file_path.exists(): return None, -1
    try:
        d = json.loads(file_path.read_text())
    except:
        return None, -1
    sketch = d.get('lean4_sketch', '')
    if not sketch: return '', -1
    return sketch, sketch.lower().count('sorry')

results = []
for pid in pids:
    # Check v14
    sketch_14, sorry_14 = get_sketch(v14_dir / f"{pid}_v14.json")
    if sorry_14 < 0:
        sketch_14, sorry_14 = get_sketch(v14_brain / f"{pid}_v14.json")
        
    # Check v16 offline
    sketch_16, sorry_16 = get_sketch(v16_dir / f"{pid}_v16_offline.json")
    
    # Check v12/v3
    sketch_v3, sorry_v3 = get_sketch(v3_dir / f"problem_*_{pid}.json_") # won't work perfectly with wildcard in Path

    best_sorry = -1
    best_source = "missing"
    if sorry_16 >= 0:
        best_sorry = sorry_16
        best_source = "v16_offline"
    elif sorry_14 >= 0:
        best_sorry = sorry_14
        best_source = "v14"
    elif sorry_v3 >= 0:
        best_sorry = sorry_v3
        best_source = "v12"
        
    results.append({
        'pid': pid,
        'v14_sorry': sorry_14,
        'v16_sorry': sorry_16,
        'v12_sorry': sorry_v3,
        'best_sorry': best_sorry,
        'best_source': best_source
    })

print(f"Total problems: {len(results)}")
print(f"Missing completely: {sum(1 for r in results if r['best_source'] == 'missing')}")
print(f"Has sorry > 0: {sum(1 for r in results if r['best_sorry'] > 0)}")
print(f"Has 0 sorry: {sum(1 for r in results if r['best_sorry'] == 0)}")
print("Missing problems:", [r['pid'] for r in results if r['best_source'] == 'missing'])
