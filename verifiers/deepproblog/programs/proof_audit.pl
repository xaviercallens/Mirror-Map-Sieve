%% ============================================================================
%% SocrateAI Scientific Agora — DeepProbLog Proof Audit Program
%% Copyright © 2025-2026 Socrate AI Lab, Paris, France
%% Author: Xavier Callens <callensxavier@gmail.com>
%% License: Apache-2.0 (framework) + CC-BY-NC-ND 4.0 (proprietary)
%% Patent:  US-PAT-PEND-2026-0525
%%
%% proof_audit.pl — Neuro-symbolic proof auditing for mathematical
%% derivations produced by the Euler Agent.
%%
%% This program validates individual proof steps and checks the
%% overall logical consistency of a proof chain. Neural predicates
%% classify step types and detect common errors (vagueness, division
%% by zero, unstated assumptions). Logical rules enforce structural
%% validity.
%%
%% Reference: arXiv:1805.10872, arXiv:2508.13697
%% ============================================================================

%% ---------------------------------------------------------------------------
%% Neural Predicates
%% ---------------------------------------------------------------------------

%% net_step_type: classifies a proof step into a reasoning category.
%% Input:  step embedding (natural language + formal representation)
%% Output: step type tag

nn(net_step_type, [StepEmbed], StepType) :: step_type(StepEmbed, StepType).

%% Possible step types:
%%   axiom         — invocation of a known axiom or definition
%%   hypothesis    — introduction of a hypothesis
%%   deduction     — modus ponens / universal instantiation
%%   induction     — structural or strong induction
%%   contradiction — proof by contradiction (reductio)
%%   computation   — algebraic or numeric calculation
%%   substitution  — variable substitution / rewriting
%%   case_split    — case analysis / disjunction elimination
%%   reference     — citation of a previously proved lemma

%% net_validity: neural assessment of step correctness.
%% Input:  (premise_embeddings, conclusion_embedding)
%% Output: validity confidence in {valid, suspicious, invalid}

nn(net_validity, [Premises, Conclusion], Validity) ::
    step_validity(Premises, Conclusion, Validity).

%% net_vagueness: detects vague or hand-wavy reasoning.
%% Input:  step natural language text
%% Output: vagueness tag in {precise, somewhat_vague, very_vague}

nn(net_vagueness, [StepText], VagueLevel) ::
    vagueness_level(StepText, VagueLevel).

%% ---------------------------------------------------------------------------
%% Proof Structure
%% ---------------------------------------------------------------------------

%% A proof is a sequence of steps, each referencing earlier steps as premises.
%% step(ProofId, StepIdx, StepEmbed, PremiseIdxList)

%% A proof is complete if it has a final step deriving the goal.
proof_complete(ProofId, Goal) :-
    step(ProofId, FinalIdx, GoalEmbed, _),
    final_step(ProofId, FinalIdx),
    step_derives(GoalEmbed, Goal).

%% ---------------------------------------------------------------------------
%% Step Validity Predicates
%% ---------------------------------------------------------------------------

%% A step is locally valid if:
%%   1. Its type is recognised
%%   2. The neural validity classifier says "valid"
%%   3. It is not flagged as very vague

step_locally_valid(ProofId, StepIdx) :-
    step(ProofId, StepIdx, StepEmbed, PremiseIdxs),
    step_type(StepEmbed, Type),
    valid_step_type(Type),
    collect_premises(ProofId, PremiseIdxs, PremiseEmbeds),
    step_validity(PremiseEmbeds, StepEmbed, valid),
    vagueness_level(StepEmbed, VLevel),
    VLevel \= very_vague.

%% Recognised step types
valid_step_type(axiom).
valid_step_type(hypothesis).
valid_step_type(deduction).
valid_step_type(induction).
valid_step_type(contradiction).
valid_step_type(computation).
valid_step_type(substitution).
valid_step_type(case_split).
valid_step_type(reference).

%% Collect premise embeddings by index
collect_premises(_, [], []).
collect_premises(ProofId, [Idx | Rest], [Embed | RestEmbeds]) :-
    step(ProofId, Idx, Embed, _),
    collect_premises(ProofId, Rest, RestEmbeds).

%% ---------------------------------------------------------------------------
%% Logical Consistency Checks
%% ---------------------------------------------------------------------------

%% A proof is logically consistent if:
%%   1. No step contradicts a previous step (unless in a reductio block)
%%   2. All premises are derived before they are used (no circular deps)
%%   3. Hypotheses introduced in sub-proofs are discharged

%% No circular dependencies: step i can only reference steps j < i
acyclic_step(ProofId, StepIdx) :-
    step(ProofId, StepIdx, _, PremiseIdxs),
    all_less_than(PremiseIdxs, StepIdx).

all_less_than([], _).
all_less_than([Idx | Rest], Bound) :-
    Idx < Bound,
    all_less_than(Rest, Bound).

%% Full proof acyclicity
proof_acyclic(ProofId) :-
    \+ (step(ProofId, StepIdx, _, _),
        \+ acyclic_step(ProofId, StepIdx)).

%% Hypothesis tracking: each hypothesis must be discharged
hypothesis_discharged(ProofId, HypIdx) :-
    step(ProofId, HypIdx, HypEmbed, []),
    step_type(HypEmbed, hypothesis),
    step(ProofId, DischargeIdx, _, PremiseIdxs),
    DischargeIdx > HypIdx,
    member(HypIdx, PremiseIdxs),
    step_type(_, contradiction).   % discharged via reductio

hypothesis_discharged(ProofId, HypIdx) :-
    step(ProofId, HypIdx, HypEmbed, []),
    step_type(HypEmbed, hypothesis),
    step(ProofId, DischargeIdx, DischargeEmbed, PremiseIdxs),
    DischargeIdx > HypIdx,
    member(HypIdx, PremiseIdxs),
    step_type(DischargeEmbed, deduction).  % discharged via conditional proof

%% ---------------------------------------------------------------------------
%% Denominator Non-Zero Checks
%% ---------------------------------------------------------------------------
%% Division and fraction operations require the denominator to be provably
%% non-zero. We detect division steps and verify the non-zero condition.

%% Neural predicate to detect division in a computation step
nn(net_has_division, [StepEmbed], HasDiv) ::
    step_has_division(StepEmbed, HasDiv).

%% Neural predicate to extract the denominator expression
nn(net_denominator, [StepEmbed], DenomEmbed) ::
    step_denominator(StepEmbed, DenomEmbed).

%% Neural predicate to check if a quantity is provably non-zero
nn(net_nonzero, [ExprEmbed, Context], NonZeroStatus) ::
    expr_nonzero(ExprEmbed, Context, NonZeroStatus).

%% Division safety check
division_safe(ProofId, StepIdx) :-
    step(ProofId, StepIdx, StepEmbed, _),
    step_has_division(StepEmbed, true),
    step_denominator(StepEmbed, DenomEmbed),
    proof_context(ProofId, StepIdx, Context),
    expr_nonzero(DenomEmbed, Context, confirmed).

%% Division safety violation
division_unsafe(ProofId, StepIdx) :-
    step(ProofId, StepIdx, StepEmbed, _),
    step_has_division(StepEmbed, true),
    \+ division_safe(ProofId, StepIdx).

%% Proof context: collect all established facts up to a given step
proof_context(ProofId, StepIdx, Context) :-
    findall(Embed,
            (step(ProofId, J, Embed, _), J < StepIdx),
            Context).

%% ---------------------------------------------------------------------------
%% Vagueness Detection Rules
%% ---------------------------------------------------------------------------
%% Steps classified as vague by the neural network are flagged.
%% The Socrates Agent uses these flags to request clarification.

vague_step(ProofId, StepIdx, VLevel) :-
    step(ProofId, StepIdx, StepEmbed, _),
    vagueness_level(StepEmbed, VLevel),
    (VLevel = somewhat_vague ; VLevel = very_vague).

%% Count vague steps in a proof
proof_vagueness_count(ProofId, Count) :-
    findall(StepIdx, vague_step(ProofId, StepIdx, _), VagueSteps),
    length(VagueSteps, Count).

%% A proof is "crisp" if it has no vague steps
proof_is_crisp(ProofId) :-
    proof_vagueness_count(ProofId, 0).

%% ---------------------------------------------------------------------------
%% Overall Proof Audit
%% ---------------------------------------------------------------------------

%% A proof passes the audit if:
%%   1. Every step is locally valid
%%   2. The proof is acyclic
%%   3. No unsafe divisions exist
%%   4. Vagueness count is below threshold (≤ 2 somewhat_vague, 0 very_vague)

proof_audit_pass(ProofId) :-
    %% All steps locally valid
    \+ (step(ProofId, StepIdx, _, _),
        \+ step_locally_valid(ProofId, StepIdx)),
    %% Acyclic
    proof_acyclic(ProofId),
    %% No unsafe divisions
    \+ division_unsafe(ProofId, _),
    %% No very vague steps
    \+ vague_step(ProofId, _, very_vague),
    %% At most 2 somewhat vague steps
    findall(Idx, vague_step(ProofId, Idx, somewhat_vague), VagueList),
    length(VagueList, VCount),
    VCount =< 2.

%% Audit failure reasons (for diagnostic reporting)
audit_failure_reason(ProofId, invalid_step, StepIdx) :-
    step(ProofId, StepIdx, _, _),
    \+ step_locally_valid(ProofId, StepIdx).

audit_failure_reason(ProofId, cyclic_dependency, StepIdx) :-
    step(ProofId, StepIdx, _, _),
    \+ acyclic_step(ProofId, StepIdx).

audit_failure_reason(ProofId, unsafe_division, StepIdx) :-
    division_unsafe(ProofId, StepIdx).

audit_failure_reason(ProofId, excessive_vagueness, StepIdx) :-
    vague_step(ProofId, StepIdx, very_vague).

%% ---------------------------------------------------------------------------
%% Query Interface
%% ---------------------------------------------------------------------------

%% Full audit
query(audit(ProofId, Result)) :-
    (proof_audit_pass(ProofId) ->
        Result = pass
    ;
        Result = fail
    ).

%% List all failure reasons
query(audit_failures(ProofId, Reason, StepIdx)) :-
    audit_failure_reason(ProofId, Reason, StepIdx).

%% Check a specific step
query(step_valid(ProofId, StepIdx)) :-
    step_locally_valid(ProofId, StepIdx).

%% Count vagueness
query(vagueness(ProofId, Count)) :-
    proof_vagueness_count(ProofId, Count).
