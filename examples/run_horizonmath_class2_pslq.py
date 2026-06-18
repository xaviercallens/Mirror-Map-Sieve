#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""
Orchestration Script for HorizonMath Solvability Class 2 targets.
Uses SymBrain v12 with PSLQ-at-leaf evaluation to snap heuristic MCTS paths
into exact integer relations.
"""

import mpmath
from mpmath import mp
import structlog
from typing import Dict, Any

from agents.galois.symbrain.cortex_v4 import GaloisCortexConfig
from agents.galois.symbrain.cortex_v12 import SymBrainV12Cortex
from agents.galois.tools.pslq_leaf_evaluator import PSLQLeafEvaluator
from agents.galois.tools.mcts_reasoner import MCTSReasoner

logger = structlog.get_logger(__name__)

# Config
mp.dps = 500

CLASS_2_TARGETS = {
    "catalan_G": {
        "value": mp.catalan,
        "domain": "number_theory",
        "description": "Catalan's Constant G"
    },
    "zeta_5": {
        "value": mp.zeta(5),
        "domain": "number_theory",
        "description": "Apéry's cousin ζ(5)"
    },
    "bessel_moment_c5_1": {
        "value": mp.mpf('2.49659920359871790695054946328639552'),
        "domain": "analysis",
        "description": "Bessel Moment c_{5,1}"
    },
    "mertens_M": {
        "value": mp.mpf('0.26149721284764278375542683860869585'),
        "domain": "number_theory",
        "description": "Mertens constant M"
    },
    "landau_ramanujan_K": {
        "value": mp.mpf('0.76422365358922066299069873125009232'),
        "domain": "number_theory",
        "description": "Landau-Ramanujan constant K"
    }
}


def run_experiment():
    logger.info("starting_horizonmath_class2_experiment")
    
    config = GaloisCortexConfig()
    cortex = SymBrainV12Cortex(config)
    
    # Initialize the PSLQ Leaf Evaluator with the domain registry from Cortex v12
    pslq_evaluator = PSLQLeafEvaluator(dps=500, basis_registry=cortex.PSLQ_BASIS_REGISTRY)
    
    reasoner = MCTSReasoner(
        max_iterations=10, 
        expansion_width=3, 
        cortex=cortex, 
        pslq_evaluator=pslq_evaluator
    )

    results: Dict[str, Any] = {}

    for name, data in CLASS_2_TARGETS.items():
        logger.info("processing_target", target=name)
        problem_statement = f"Find an exact closed-form algebraic or rational linear relation for {data['description']}."
        
        best_path = reasoner.run(
            problem_statement=problem_statement,
            target_constant=data["value"],
            pslq_domain=data["domain"]
        )
        
        results[name] = {
            "best_path": best_path,
            "pslq_hits": len(cortex.pslq_discovery_log)
        }
        
    logger.info("experiment_completed", results=results)


if __name__ == "__main__":
    run_experiment()
