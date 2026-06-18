import os
import json
import importlib.util
from typing import Dict, Any

# Assuming HorizonMath data is accessible relative to project root or via absolute path
HORIZONMATH_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'scratch', 'HorizonMath')

def validate_against_horizonmath(problem_id: str, proposed_solution: str, precision_digits: int = 50) -> Dict[str, Any]:
    """
    Validates a proposed solution against the HorizonMath ground truth (numerics or validators).
    """
    result = {'valid': False, 'message': '', 'metrics': {}}
    
    # Check if problems_full.json exists
    data_file = os.path.join(HORIZONMATH_DIR, 'data', 'problems_full.json')
    if not os.path.exists(data_file):
        return {'error': f"HorizonMath data not found at {data_file}", 'status': 'failure'}
        
    try:
        with open(data_file, 'r') as f:
            problems = json.load(f)
            
        problem = next((p for p in problems if p.get('id') == problem_id), None)
        if not problem:
            return {'error': f"Problem {problem_id} not found in HorizonMath data.", 'status': 'failure'}
            
        evaluation_mode = problem.get('evaluation_mode')
        output_type = problem.get('output_type')
        
        if evaluation_mode == 'ground_truth_computable' and output_type == 'constant':
            expected_val_str = problem.get('numeric_value')
            if not expected_val_str:
                return {'error': 'No numeric_value found for ground_truth_computable problem.', 'status': 'failure'}
                
            from mpmath import mp
            mp.dps = precision_digits
            expected_val = mp.mpf(expected_val_str)
            
            # Execute proposed solution safely (in a real scenario, use cas_sandbox for isolation)
            # For this MVP, we assume proposed_solution is a python function string `def proposed_solution(): ...`
            local_scope = {}
            exec(proposed_solution, {'mp': mp}, local_scope)
            if 'proposed_solution' not in local_scope:
                return {'error': "Proposed solution must define a function named 'proposed_solution'.", 'status': 'failure'}
                
            actual_val = local_scope['proposed_solution']()
            actual_val = mp.mpf(actual_val)
            
            # Compare up to precision_digits
            diff = abs(expected_val - actual_val)
            threshold = mp.power(10, -precision_digits + 2)
            
            is_valid = diff < threshold
            result['valid'] = is_valid
            result['message'] = 'Match' if is_valid else f'Mismatch. Expected: {expected_val}, Got: {actual_val}, Diff: {diff}'
            result['metrics']['diff'] = str(diff)
            result['status'] = 'success'
            
        else:
            # Placeholder for other modes (validators, test_points)
            result['message'] = f"Validation for mode {evaluation_mode} and type {output_type} not fully implemented yet."
            result['status'] = 'partial'
            
        return result

    except Exception as e:
        return {'error': str(e), 'status': 'failure'}
