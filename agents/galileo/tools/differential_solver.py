import numpy as np
from scipy.integrate import solve_ivp, solve_bvp
from typing import Dict, Any, Callable

def solve_differential(problem_type: str, equation_func: Callable, domain: tuple, boundary_conditions: Any = None, method: str = 'auto', **kwargs) -> Dict[str, Any]:
    """
    Enhanced ODE/BVP solver.
    problem_type: 'ivp', 'bvp'
    equation_func: For IVP: f(t, y). For BVP: f(x, y).
    domain: (t0, tf) for IVP or (x0, xf) for BVP.
    boundary_conditions: For IVP: y0 array. For BVP: bc(ya, yb) function.
    """
    try:
        if problem_type == 'ivp':
            y0 = boundary_conditions
            if method == 'auto':
                method = 'RK45' # default
            sol = solve_ivp(equation_func, domain, y0, method=method, **kwargs)
            if sol.success:
                return {'t': sol.t.tolist(), 'y': sol.y.tolist(), 'status': 'success'}
            else:
                return {'error': sol.message, 'status': 'failure'}
                
        elif problem_type == 'bvp':
            bc = boundary_conditions
            # Need an initial mesh and guess for BVP
            x_init = np.linspace(domain[0], domain[1], kwargs.get('nodes', 100))
            y_init = kwargs.get('y_guess', np.zeros((1, len(x_init))))
            
            sol = solve_bvp(equation_func, bc, x_init, y_init, **kwargs)
            if sol.success:
                return {'x': sol.x.tolist(), 'y': sol.y.tolist(), 'status': 'success'}
            else:
                return {'error': sol.message, 'status': 'failure'}
                
        else:
            return {'error': f"Unknown problem type: {problem_type}", 'status': 'failure'}
            
    except Exception as e:
        return {'error': str(e), 'status': 'failure'}
