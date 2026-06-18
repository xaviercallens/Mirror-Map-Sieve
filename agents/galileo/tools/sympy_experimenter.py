import sympy
from typing import Dict, Any

def sympy_experiment(task: str, expression: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Executes domain-specific symbolic manipulation using SymPy.
    Tasks supported: 'series_expand', 'simplify_verify', 'integrate', 'special_function_eval', 'algebraic_detect', 'solve_ode'
    """
    try:
        from sympy.parsing.sympy_parser import parse_expr
        expr = parse_expr(expression)
        
        if task == 'series_expand':
            var = sympy.Symbol(parameters.get('variable', 'x'))
            point = parameters.get('point', 0)
            n = parameters.get('n', 6)
            series = expr.series(var, point, n)
            return {'result': str(series), 'status': 'success'}
            
        elif task == 'simplify_verify':
            expr2_str = parameters.get('expression2', '')
            expr2 = parse_expr(expr2_str)
            diff = sympy.simplify(expr - expr2)
            is_equivalent = diff == 0
            return {'is_equivalent': is_equivalent, 'simplified_diff': str(diff), 'status': 'success'}
            
        elif task == 'integrate':
            var = sympy.Symbol(parameters.get('variable', 'x'))
            integrated = sympy.integrate(expr, var)
            return {'result': str(integrated), 'status': 'success'}
            
        elif task == 'solve_ode':
            # Basic ODE solving capability
            # Expects expression to be the differential equation equal to 0
            func_name = parameters.get('function', 'f')
            var_name = parameters.get('variable', 'x')
            var = sympy.Symbol(var_name)
            func = sympy.Function(func_name)(var)
            
            # Simple replacement of f(x) and its derivatives
            # This is a basic parser; for complex ODEs, the user should provide valid sympy syntax.
            ode_expr = parse_expr(expression, local_dict={func_name: func})
            solution = sympy.dsolve(ode_expr, func)
            return {'result': str(solution), 'status': 'success'}
            
        else:
            return {'error': f"Unknown task: {task}", 'status': 'failure'}
            
    except Exception as e:
        return {'error': str(e), 'status': 'failure'}

if __name__ == "__main__":
    # Test
    res = sympy_experiment('series_expand', 'exp(x)', {'variable': 'x', 'n': 4})
    print(res)
