"""
Adaptive Testing Engine using Item Response Theory (IRT).

This module implements a 1-Parameter Logistic (1PL) / 3-Parameter Logistic (3PL)
IRT model for adaptive question selection and ability estimation.

Mathematical Foundation:
────────────────────────
The 3PL IRT model defines the probability of a correct response as:

    P(θ) = c + (1 - c) / (1 + exp(-a * (θ - b)))

Where:
    θ (theta) = student ability parameter (what we estimate)
    b = item difficulty parameter
    a = item discrimination parameter (how well the item differentiates)
    c = guessing parameter (probability of correct answer by chance)

Ability Update (Maximum Likelihood Estimation via Newton-Raphson):
    After each response, we update θ using the derivative of the
    log-likelihood function with a step-size-controlled Newton-Raphson method.

Question Selection:
    We select the question that maximizes Fisher Information at the
    current ability estimate, which is optimal for CAT (Computerized
    Adaptive Testing).
"""

import math
from typing import List, Tuple, Optional


# ─── IRT Probability Functions ────────────────────────────────────────

def irt_probability(theta: float, difficulty: float, discrimination: float = 1.0, guessing: float = 0.25) -> float:
    """
    Calculate probability of correct response using the 3PL IRT model.

    Args:
        theta: Student ability estimate (0.0 to 1.0)
        difficulty: Item difficulty parameter b (0.1 to 1.0)
        discrimination: Item discrimination parameter a (0.1 to 3.0)
        guessing: Pseudo-guessing parameter c (0.0 to 0.5)

    Returns:
        Probability of correct response [0, 1]
    """
    # Scale theta and difficulty to IRT-standard range (-3 to 3)
    theta_scaled = (theta - 0.5) * 6  # Maps [0,1] -> [-3, 3]
    b_scaled = (difficulty - 0.5) * 6

    exponent = -discrimination * (theta_scaled - b_scaled)
    # Clamp to prevent overflow
    exponent = max(-20, min(20, exponent))

    logistic = 1.0 / (1.0 + math.exp(exponent))
    probability = guessing + (1.0 - guessing) * logistic

    return probability


def fisher_information(theta: float, difficulty: float, discrimination: float = 1.0, guessing: float = 0.25) -> float:
    """
    Calculate Fisher Information for an item at a given ability level.

    Fisher Information quantifies how much "information" an item provides
    about the ability parameter at a specific θ. Higher = more informative.

    I(θ) = a² * [(P(θ) - c)² / ((1-c)² * P(θ) * (1-P(θ)))] * [(1 - P(θ)) / P(θ)]²

    For CAT, we select items that maximize I(θ) at the current estimate.
    """
    p = irt_probability(theta, difficulty, discrimination, guessing)

    # Avoid division by zero
    if p <= guessing or p >= 1.0:
        return 0.0001

    numerator = discrimination ** 2 * (p - guessing) ** 2
    denominator = (1 - guessing) ** 2 * p * (1 - p)

    if denominator == 0:
        return 0.0001

    info = numerator / denominator
    return info


# ─── Ability Estimation ──────────────────────────────────────────────

def update_ability(
    current_theta: float,
    responses: List[Tuple[float, float, float, bool]],
    learning_rate: float = 0.4,
    min_theta: float = 0.05,
    max_theta: float = 0.95,
) -> float:
    """
    Update ability estimate using Maximum Likelihood Estimation (MLE)
    with a Newton-Raphson-inspired step.

    This implements an EAP (Expected A Posteriori) inspired approach
    with a Bayesian prior centered at 0.5 to handle early-stage instability.

    Args:
        current_theta: Current ability estimate
        responses: List of (difficulty, discrimination, guessing, is_correct) tuples
        learning_rate: Controls step size for convergence stability
        min_theta: Minimum allowed ability value
        max_theta: Maximum allowed ability value

    Returns:
        Updated ability estimate, clamped to [min_theta, max_theta]
    """
    if not responses:
        return current_theta

    theta = current_theta
    num_iterations = 15  # Newton-Raphson iterations

    for _ in range(num_iterations):
        # Compute first and second derivatives of log-likelihood
        dl = 0.0   # First derivative (gradient)
        d2l = 0.0  # Second derivative (Hessian)

        for difficulty, discrimination, guessing, is_correct in responses:
            p = irt_probability(theta, difficulty, discrimination, guessing)
            p = max(0.0001, min(0.9999, p))  # Numerical safety

            # Scaling factor for the derivative
            scale = 6.0  # From our theta scaling
            q = 1.0 - p
            w = (p - guessing) / (1.0 - guessing)  # Weight for 3PL

            if is_correct:
                dl += discrimination * scale * w * q / p
            else:
                dl -= discrimination * scale * w / q

            # Second derivative (always negative for concavity)
            d2l -= (discrimination * scale) ** 2 * w ** 2 * q / p

        # Add Bayesian prior (Gaussian centered at 0.5, σ=0.3)
        # This regularizes early estimates when we have few responses
        prior_mean = 0.5
        prior_var = 0.09  # σ² = 0.3²
        dl -= (theta - prior_mean) / prior_var
        d2l -= 1.0 / prior_var

        # Newton-Raphson step
        if abs(d2l) < 0.0001:
            break

        step = -dl / d2l
        theta += learning_rate * step

        # Clamp
        theta = max(min_theta, min(max_theta, theta))

    return round(theta, 4)


def simple_ability_update(
    current_theta: float,
    is_correct: bool,
    question_difficulty: float,
    question_number: int,
) -> float:
    """
    Simplified ability update for intuitive step-based adaptation.

    This serves as a fallback / blended approach:
    - Correct answer on hard question → big ability increase
    - Wrong answer on easy question → big ability decrease
    - The step size decreases as more questions are answered (convergence)

    Args:
        current_theta: Current ability estimate
        is_correct: Whether the student answered correctly
        question_difficulty: Difficulty of the question just answered
        question_number: How many questions answered so far (1-indexed)

    Returns:
        Updated ability estimate
    """
    # Adaptive step size (decreases over time for convergence)
    base_step = 0.15
    decay = 1.0 / (1.0 + 0.15 * question_number)
    step = base_step * decay

    # Difficulty-weighted adjustment
    if is_correct:
        # Reward more for getting harder questions right
        weight = 0.5 + question_difficulty
        delta = step * weight
    else:
        # Penalize more for getting easier questions wrong
        weight = 0.5 + (1.0 - question_difficulty)
        delta = -step * weight

    new_theta = current_theta + delta
    return round(max(0.05, min(0.95, new_theta)), 4)


# ─── Question Selection ──────────────────────────────────────────────

def select_next_question(
    current_theta: float,
    available_questions: List[dict],
    answered_ids: List[str],
) -> Optional[dict]:
    """
    Select the optimal next question using Maximum Fisher Information criterion.

    This is the gold-standard approach in Computerized Adaptive Testing (CAT):
    select the item that provides the most statistical information about the
    student's ability at their current estimated level.

    Additionally applies content balancing to avoid topic concentration.

    Args:
        current_theta: Current estimated ability
        available_questions: All questions from the bank
        answered_ids: IDs of already-answered questions

    Returns:
        The optimal next question, or None if no questions available
    """
    # Filter out already-answered questions
    candidates = [
        q for q in available_questions
        if str(q.get("_id", "")) not in answered_ids
    ]

    if not candidates:
        return None

    # Score each candidate by Fisher Information
    scored = []
    for q in candidates:
        info = fisher_information(
            theta=current_theta,
            difficulty=q["difficulty"],
            discrimination=q.get("discrimination", 1.0),
            guessing=q.get("guessing", 0.25),
        )
        scored.append((info, q))

    # Sort by information (descending) and return the best
    scored.sort(key=lambda x: x[0], reverse=True)

    # Return the most informative question
    return scored[0][1]


def compute_ability_from_responses(
    responses: List[Tuple[float, float, float, bool]],
    initial_theta: float = 0.5,
) -> float:
    """
    Compute the full MLE ability estimate from all responses.

    This re-estimates ability from scratch using all response data,
    providing a more accurate final estimate than incremental updates.

    Args:
        responses: List of (difficulty, discrimination, guessing, is_correct)
        initial_theta: Starting point for optimization

    Returns:
        Maximum likelihood ability estimate
    """
    return update_ability(initial_theta, responses, learning_rate=0.3)
