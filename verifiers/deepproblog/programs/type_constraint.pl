%% ============================================================================
%% SocrateAI Scientific Agora — DeepProbLog Type Constraint Program
%% Copyright © 2025-2026 Socrate AI Lab, Paris, France
%% Author: Xavier Callens <callensxavier@gmail.com>
%% License: Apache-2.0 (framework) + CC-BY-NC-ND 4.0 (proprietary)
%% Patent:  US-PAT-PEND-2026-0525
%%
%% type_constraint.pl — Neural-symbolic type checking for tensor
%% operations in the SymBrain computation graph.
%%
%% This program uses DeepProbLog's neural predicates to classify
%% tensor types and enforces logical type rules. Derivation paths
%% that violate type constraints receive probability P(π) = 0,
%% effectively pruning them from the semiring computation.
%%
%% Syntax follows DeepProbLog / ProbLog conventions:
%%   - nn(NetworkId, Input, Output) : neural predicate
%%   - P :: Fact                    : probabilistic fact
%%   - Rule :- Body                 : definite clause
%%
%% Reference: arXiv:1805.10872 (Manhaeve et al., NeurIPS 2018)
%% ============================================================================

%% ---------------------------------------------------------------------------
%% Neural Predicates
%% ---------------------------------------------------------------------------
%% net_type: classifies a tensor descriptor into a base type.
%% Input:  tensor descriptor (embedding vector)
%% Output: one of {integer, real, complex, matrix, tensor}

nn(net_type, [TensorDesc], Type) :: type_pred(TensorDesc, Type).

%% net_shape: infers the shape signature of a tensor.
%% Input:  tensor descriptor
%% Output: shape tag (scalar, vector, matrix_2d, nd_tensor)

nn(net_shape, [TensorDesc], Shape) :: shape_pred(TensorDesc, Shape).

%% net_device: infers the device placement of a tensor.
%% Input:  tensor descriptor
%% Output: device tag (cpu, cuda, edge_tpu)

nn(net_device, [TensorDesc], Device) :: device_pred(TensorDesc, Device).

%% ---------------------------------------------------------------------------
%% Base Type Hierarchy
%% ---------------------------------------------------------------------------
%% Define a subtype lattice: integer <: real <: complex
%% Matrices and tensors are parameterised by their element type.

base_type(integer).
base_type(real).
base_type(complex).
base_type(matrix).
base_type(tensor).

%% Subtype relation (reflexive, transitive closure)
subtype(integer, integer).
subtype(integer, real).
subtype(integer, complex).
subtype(real, real).
subtype(real, complex).
subtype(complex, complex).
subtype(matrix, matrix).
subtype(tensor, tensor).
subtype(matrix, tensor).    % every matrix is a tensor

%% Transitivity of subtype
subtype(X, Z) :-
    subtype(X, Y),
    subtype(Y, Z),
    X \= Y, Y \= Z.

%% ---------------------------------------------------------------------------
%% Shape Compatibility
%% ---------------------------------------------------------------------------
%% Two shapes are compatible for element-wise operations if they are
%% identical or one is broadcastable to the other.

shape_compatible(S, S).                     % identical shapes
shape_compatible(scalar, _).               % scalar broadcasts to anything
shape_compatible(_, scalar).
shape_compatible(vector, matrix_2d).       % vector broadcasts along rows
shape_compatible(matrix_2d, nd_tensor).    % matrix broadcasts into batch dim

%% ---------------------------------------------------------------------------
%% Type Rules for Binary Operations
%% ---------------------------------------------------------------------------
%% An operation op(X, Y) → Z is type-valid if:
%%   1. X and Y have compatible types (via subtype join)
%%   2. X and Y have compatible shapes
%%   3. X and Y are on the same device

%% Type join: the least upper bound in the subtype lattice
type_join(T1, T2, T2) :- subtype(T1, T2).
type_join(T1, T2, T1) :- subtype(T2, T1).

%% Addition: type-preserving, requires shape compatibility
type_valid(add, X, Y) :-
    type_pred(X, T1),
    type_pred(Y, T2),
    type_join(T1, T2, _),
    shape_pred(X, S1),
    shape_pred(Y, S2),
    shape_compatible(S1, S2),
    device_pred(X, D),
    device_pred(Y, D).     % same device

%% Multiplication (element-wise): same rules as addition
type_valid(mul, X, Y) :-
    type_pred(X, T1),
    type_pred(Y, T2),
    type_join(T1, T2, _),
    shape_pred(X, S1),
    shape_pred(Y, S2),
    shape_compatible(S1, S2),
    device_pred(X, D),
    device_pred(Y, D).

%% Matrix multiplication: requires matrix/tensor types and matching
%% inner dimensions (checked by shape network)
type_valid(matmul, X, Y) :-
    type_pred(X, T1),
    type_pred(Y, T2),
    (T1 = matrix ; T1 = tensor),
    (T2 = matrix ; T2 = tensor),
    type_join(T1, T2, _),
    device_pred(X, D),
    device_pred(Y, D).

%% Division: requires non-integer denominator (to avoid truncation bugs)
type_valid(div, X, Y) :-
    type_pred(X, T1),
    type_pred(Y, T2),
    T2 \= integer,          % prevent integer division silently
    type_join(T1, T2, _),
    shape_pred(X, S1),
    shape_pred(Y, S2),
    shape_compatible(S1, S2),
    device_pred(X, D),
    device_pred(Y, D).

%% ---------------------------------------------------------------------------
%% Type Violation Detection
%% ---------------------------------------------------------------------------
%% A type violation occurs when no valid typing derivation exists.
%% In DeepProbLog, P(π) = 0 for inconsistent paths — the semiring
%% computation automatically prunes them.

type_violation(Op, X, Y) :-
    \+ type_valid(Op, X, Y).

%% Specific violation: cross-device operation
device_violation(X, Y) :-
    device_pred(X, D1),
    device_pred(Y, D2),
    D1 \= D2.

%% Specific violation: integer division
integer_division_violation(X, Y) :-
    type_pred(Y, integer),
    type_pred(X, _).

%% ---------------------------------------------------------------------------
%% Pruning Rules for Contradictions
%% ---------------------------------------------------------------------------
%% DeepProbLog assigns P = 0 to paths containing contradictions.
%% We explicitly declare contradictory states as `fail` predicates.

%% A tensor cannot simultaneously be integer and complex
contradiction(X) :-
    type_pred(X, integer),
    type_pred(X, complex).

%% A tensor cannot be on both CPU and CUDA
contradiction(X) :-
    device_pred(X, cpu),
    device_pred(X, cuda).

%% A scalar cannot be a matrix
contradiction(X) :-
    shape_pred(X, scalar),
    shape_pred(X, matrix_2d).

%% Prune any derivation containing a contradiction
0 :: pruned_path(X) :- contradiction(X).

%% ---------------------------------------------------------------------------
%% Query Interface
%% ---------------------------------------------------------------------------
%% The Euler Agent queries these predicates to verify computation graphs.

%% Check if an operation is type-safe
query(type_safe(Op, X, Y)) :-
    type_valid(Op, X, Y),
    \+ contradiction(X),
    \+ contradiction(Y).

%% Get the result type of a valid operation
query(result_type(Op, X, Y, T)) :-
    type_valid(Op, X, Y),
    type_pred(X, T1),
    type_pred(Y, T2),
    type_join(T1, T2, T).

%% Enumerate all violations in a computation graph
query(all_violations(Op, X, Y)) :-
    type_violation(Op, X, Y).
