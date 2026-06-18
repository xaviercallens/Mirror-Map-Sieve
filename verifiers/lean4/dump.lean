import Agora.AlienMath.TensorDecomposition
import Lean

def main : IO Unit := do
  IO.println (Lean.toJson Agora.AlienMath.TensorDecomposition.extract_4x4_holographic_basis)
