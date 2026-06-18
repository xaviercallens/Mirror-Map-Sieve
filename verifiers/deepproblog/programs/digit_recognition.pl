%% ============================================================================
%% SocrateAI Scientific Agora — DeepProbLog Digit Recognition Program
%% Copyright © 2025-2026 Socrate AI Lab, Paris, France
%% Author: Xavier Callens <callensxavier@gmail.com>
%% License: Apache-2.0 (framework) + CC-BY-NC-ND 4.0 (proprietary)
%% Patent:  US-PAT-PEND-2026-0525
%%
%% digit_recognition.pl — Reference MNIST digit classification and
%% addition verification, following the canonical DeepProbLog example.
%%
%% This is the standard benchmark from Manhaeve et al. (NeurIPS 2018,
%% arXiv:1805.10872). It demonstrates:
%%   1. Neural predicate integration (nn/3) for digit classification
%%   2. Probabilistic inference over neural outputs
%%   3. Arithmetic verification via logical rules
%%
%% The program is used as a calibration / smoke-test for the
%% DeepProbLog installation within the Agora framework.
%% ============================================================================

%% ---------------------------------------------------------------------------
%% Neural Predicates
%% ---------------------------------------------------------------------------

%% net_digit: A convolutional neural network that classifies an MNIST
%% image into one of 10 digit classes {0, 1, ..., 9}.
%%
%% Input:  28×28 grayscale image tensor (flattened or 2D)
%% Output: digit class D ∈ {0, 1, 2, 3, 4, 5, 6, 7, 8, 9}
%%
%% The nn/3 predicate is differentiable: during training, gradients
%% from the downstream logic flow back through the neural network.

nn(net_digit, [Image], Digit) :: digit(Image, Digit).

%% ---------------------------------------------------------------------------
%% Digit Domain
%% ---------------------------------------------------------------------------

%% Enumerate the valid digit values
digit_value(0).
digit_value(1).
digit_value(2).
digit_value(3).
digit_value(4).
digit_value(5).
digit_value(6).
digit_value(7).
digit_value(8).
digit_value(9).

%% ---------------------------------------------------------------------------
%% Single-Digit Classification
%% ---------------------------------------------------------------------------

%% Query the probability that image X depicts digit D.
%% P(digit(X, D)) is computed by the neural network and integrated
%% into the ProbLog semiring.

classify(Image, Digit) :-
    digit(Image, Digit),
    digit_value(Digit).

%% ---------------------------------------------------------------------------
%% Addition Verification
%% ---------------------------------------------------------------------------

%% The canonical DeepProbLog task: given two MNIST images X and Y,
%% verify that digit(X) + digit(Y) = Z.
%%
%% P(addition(X, Y, Z)) = Σ_{d1,d2: d1+d2=Z} P(digit(X,d1)) · P(digit(Y,d2))
%%
%% This computes a marginal probability over all digit combinations
%% that sum to Z, weighted by the neural network's confidence.

addition(X, Y, Z) :-
    digit(X, D1),
    digit(Y, D2),
    digit_value(D1),
    digit_value(D2),
    Z is D1 + D2.

%% ---------------------------------------------------------------------------
%% Multi-Digit Addition (Extended)
%% ---------------------------------------------------------------------------

%% Three-image addition: digit(X) + digit(Y) + digit(W) = Z
addition3(X, Y, W, Z) :-
    digit(X, D1),
    digit(Y, D2),
    digit(W, D3),
    digit_value(D1),
    digit_value(D2),
    digit_value(D3),
    Z is D1 + D2 + D3.

%% ---------------------------------------------------------------------------
%% Multiplication Verification
%% ---------------------------------------------------------------------------

%% Verify that digit(X) × digit(Y) = Z
multiplication(X, Y, Z) :-
    digit(X, D1),
    digit(Y, D2),
    digit_value(D1),
    digit_value(D2),
    Z is D1 * D2.

%% ---------------------------------------------------------------------------
%% Comparison Predicates
%% ---------------------------------------------------------------------------

%% Verify that digit(X) < digit(Y)
less_than(X, Y) :-
    digit(X, D1),
    digit(Y, D2),
    digit_value(D1),
    digit_value(D2),
    D1 < D2.

%% Verify that digit(X) = digit(Y) (same digit)
same_digit(X, Y) :-
    digit(X, D),
    digit(Y, D),
    digit_value(D).

%% ---------------------------------------------------------------------------
%% Parity Classification
%% ---------------------------------------------------------------------------

%% Classify a digit as even or odd (logical layer on top of neural pred)
even_digit(X) :-
    digit(X, D),
    digit_value(D),
    D mod 2 =:= 0.

odd_digit(X) :-
    digit(X, D),
    digit_value(D),
    D mod 2 =:= 1.

%% Verify that the sum of two digits is even
sum_is_even(X, Y) :-
    digit(X, D1),
    digit(Y, D2),
    digit_value(D1),
    digit_value(D2),
    (D1 + D2) mod 2 =:= 0.

%% ---------------------------------------------------------------------------
%% Confidence-Based Filtering
%% ---------------------------------------------------------------------------

%% A digit classification is "confident" if it has probability above
%% a threshold. This is implemented at the query level by filtering
%% on the computed probability.
%%
%% Usage (Python):
%%   result = model.solve(Term("confident_classify", img, digit))
%%   if result > 0.90:
%%       print(f"Confident: digit = {digit}")

confident_classify(Image, Digit) :-
    digit(Image, Digit),
    digit_value(Digit).
    %% Threshold filtering is done post-inference in Python.

%% ---------------------------------------------------------------------------
%% Training Queries
%% ---------------------------------------------------------------------------

%% Standard training query: provide ground-truth sums and let
%% DeepProbLog learn the digit classifier end-to-end.
%%
%% Training data format (Python):
%%   train_queries = [
%%       (Term("addition", img1, img2, 7), 1.0),  # digit(img1) + digit(img2) = 7
%%       (Term("addition", img3, img4, 3), 1.0),   # digit(img3) + digit(img4) = 3
%%       ...
%%   ]

%% ---------------------------------------------------------------------------
%% Query Interface
%% ---------------------------------------------------------------------------

%% Classify a single image
query(classify(Image, Digit)) :-
    classify(Image, Digit).

%% Verify addition of two images
query(addition(X, Y, Z)) :-
    addition(X, Y, Z).

%% Verify multiplication of two images
query(multiplication(X, Y, Z)) :-
    multiplication(X, Y, Z).

%% Check parity of a digit
query(parity(X, even)) :- even_digit(X).
query(parity(X, odd))  :- odd_digit(X).
