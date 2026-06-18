import pytest
import sys
import os
from fractions import Fraction

# Add src to the path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from mirror_map.verify_mirror_map import S20, compute_mirror_map

def test_S20_initial_values():
    """Test the first few values of the S20 sequence."""
    assert S20(0) == 1
    assert S20(1) == 3
    assert S20(2) == 43
    assert S20(3) == 915
    
def test_mirror_map_coefficients():
    """Test the first few mirror map coefficients q_d."""
    q = compute_mirror_map(3)
    assert q[0] == 0
    assert q[1] == 1
    assert q[2] == 9
    assert q[3] == 165
