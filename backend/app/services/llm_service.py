"""
LLM Integration Service for generating personalized study plans.

Uses OpenAI's API to analyze student performance data and generate
targeted, actionable study recommendations.
"""

from typing import Dict, List, Optional
from openai import AsyncOpenAI
from app.core.config import settings


async def generate_study_plan(
    student_name: str,
    final_ability: float,
    total_correct: int,
    total_questions: int,
    topics_performance: Dict[str, Dict[str, int]],
    responses: List[dict],
) -> Optional[dict]:
    """
    Generate a personalized 3-step study plan using an LLM.

    Analyzes the student's performance across topics, identifies
    weaknesses, and creates actionable recommendations.

    Args:
        student_name: Student identifier
        final_ability: Final estimated ability score (0-1)
        total_correct: Number of correct answers
        total_questions: Total questions answered
        topics_performance: Per-topic breakdown {topic: {correct, total}}
        responses: Full response history with question details

    Returns:
        Structured study plan dict, or None if API unavailable
    """
    if not settings.openai_api_key or settings.openai_api_key == "your-openai-api-key-here":
        return _generate_fallback_plan(
            student_name, final_ability, total_correct,
            total_questions, topics_performance
        )

    # Build performance summary for the LLM
    performance_summary = _build_performance_summary(
        student_name, final_ability, total_correct,
        total_questions, topics_performance, responses
    )

    prompt = f"""You are an expert GRE tutor and educational psychologist. Analyze the following 
student's adaptive test performance and generate a personalized study plan.

{performance_summary}

Based on this data, provide a JSON response with EXACTLY this structure:
{{
    "overall_assessment": "A 2-3 sentence assessment of the student's current level",
    "ability_level": "Beginner" | "Intermediate" | "Advanced",
    "strengths": ["topic1", "topic2"],
    "weaknesses": ["topic1", "topic2"],
    "study_plan": [
        {{
            "step": 1,
            "title": "Short actionable title",
            "description": "Detailed 2-3 sentence description of what to study and how",
            "focus_topics": ["topic1"],
            "recommended_resources": ["specific resource or activity"],
            "estimated_time": "e.g., 2-3 hours"
        }},
        {{
            "step": 2,
            "title": "...",
            "description": "...",
            "focus_topics": ["..."],
            "recommended_resources": ["..."],
            "estimated_time": "..."
        }},
        {{
            "step": 3,
            "title": "...",
            "description": "...",
            "focus_topics": ["..."],
            "recommended_resources": ["..."],
            "estimated_time": "..."
        }}
    ],
    "next_test_recommendation": "When and what the student should test next"
}}

Respond ONLY with valid JSON, no markdown formatting or extra text."""

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise educational AI that outputs only valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000,
        )

        import json
        content = response.choices[0].message.content.strip()
        # Handle potential markdown code blocks
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]
        plan = json.loads(content)
        return plan

    except Exception as e:
        print(f"[LLM] OpenAI API error: {e}")
        return _generate_fallback_plan(
            student_name, final_ability, total_correct,
            total_questions, topics_performance
        )


def _build_performance_summary(
    student_name: str,
    final_ability: float,
    total_correct: int,
    total_questions: int,
    topics_performance: Dict[str, Dict[str, int]],
    responses: List[dict],
) -> str:
    """Build a detailed text summary of the student's performance."""
    accuracy = (total_correct / total_questions * 100) if total_questions > 0 else 0

    lines = [
        f"Student: {student_name}",
        f"Final Ability Score: {final_ability:.2f} / 1.00",
        f"Overall Accuracy: {total_correct}/{total_questions} ({accuracy:.1f}%)",
        "",
        "Performance by Topic:",
    ]

    for topic, stats in topics_performance.items():
        correct = stats.get("correct", 0)
        total = stats.get("total", 0)
        topic_acc = (correct / total * 100) if total > 0 else 0
        lines.append(f"  - {topic}: {correct}/{total} ({topic_acc:.0f}%)")

    lines.append("")
    lines.append("Question-by-Question Detail:")
    for i, r in enumerate(responses, 1):
        status = "CORRECT" if r.get("is_correct") else "WRONG"
        lines.append(
            f"  Q{i}. [{r.get('topic', 'Unknown')}] "
            f"Difficulty: {r.get('difficulty', 0):.2f} → {status} "
            f"(Ability after: {r.get('ability_after', 0):.2f})"
        )

    return "\n".join(lines)


def _generate_fallback_plan(
    student_name: str,
    final_ability: float,
    total_correct: int,
    total_questions: int,
    topics_performance: Dict[str, Dict[str, int]],
) -> dict:
    """
    Generate a rule-based study plan when OpenAI API is unavailable.
    This ensures the system always provides actionable feedback.
    """
    accuracy = (total_correct / total_questions * 100) if total_questions > 0 else 0

    # Determine ability level
    if final_ability < 0.35:
        ability_level = "Beginner"
    elif final_ability < 0.65:
        ability_level = "Intermediate"
    else:
        ability_level = "Advanced"

    # Find weakest and strongest topics
    topic_scores = {}
    for topic, stats in topics_performance.items():
        total = stats.get("total", 0)
        correct = stats.get("correct", 0)
        if total > 0:
            topic_scores[topic] = correct / total

    sorted_topics = sorted(topic_scores.items(), key=lambda x: x[1])
    weaknesses = [t[0] for t in sorted_topics[:2]] if sorted_topics else ["General"]
    strengths = [t[0] for t in sorted_topics[-2:]] if len(sorted_topics) >= 2 else ["General"]

    # Build study plan based on weaknesses
    study_steps = []

    if weaknesses:
        study_steps.append({
            "step": 1,
            "title": f"Master the Fundamentals of {weaknesses[0]}",
            "description": (
                f"Your performance in {weaknesses[0]} indicates gaps in foundational concepts. "
                f"Start by reviewing core principles and work through practice problems at a "
                f"comfortable difficulty level before advancing."
            ),
            "focus_topics": [weaknesses[0]],
            "recommended_resources": [
                f"GRE {weaknesses[0]} review guide",
                "Khan Academy fundamentals",
                "Practice problems (easy to medium difficulty)",
            ],
            "estimated_time": "3-4 hours",
        })

    if len(weaknesses) > 1:
        study_steps.append({
            "step": 2,
            "title": f"Build Confidence in {weaknesses[1]}",
            "description": (
                f"After strengthening {weaknesses[0]}, focus on {weaknesses[1]}. "
                f"Use timed practice sets to build both accuracy and speed. "
                f"Review wrong answers to understand error patterns."
            ),
            "focus_topics": [weaknesses[1]],
            "recommended_resources": [
                f"GRE {weaknesses[1]} practice tests",
                "Error analysis worksheet",
                "Targeted drill exercises",
            ],
            "estimated_time": "2-3 hours",
        })
    else:
        study_steps.append({
            "step": 2,
            "title": "Strengthen Problem-Solving Strategies",
            "description": (
                "Focus on developing systematic approaches to GRE questions. "
                "Practice elimination techniques, time management, and "
                "recognizing question patterns."
            ),
            "focus_topics": weaknesses,
            "recommended_resources": [
                "GRE strategy guide",
                "Timed practice sets",
                "Process of elimination drills",
            ],
            "estimated_time": "2-3 hours",
        })

    study_steps.append({
        "step": 3,
        "title": "Integrated Practice & Review",
        "description": (
            "Take a full-length mixed practice test covering all topics. "
            "This simulates real test conditions and helps identify any "
            "remaining weak areas. Review every wrong answer thoroughly."
        ),
        "focus_topics": list(topics_performance.keys()),
        "recommended_resources": [
            "Full-length GRE practice test",
            "Performance review checklist",
            "Spaced repetition flashcards for missed concepts",
        ],
        "estimated_time": "3-4 hours",
    })

    return {
        "overall_assessment": (
            f"{student_name} achieved an ability score of {final_ability:.2f}/1.00 "
            f"with {accuracy:.0f}% accuracy across {total_questions} questions. "
            f"{'Strong performance overall. Focus on advancing to harder material.' if ability_level == 'Advanced' else 'Room for improvement exists, particularly in weaker topic areas.'}"
        ),
        "ability_level": ability_level,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "study_plan": study_steps,
        "next_test_recommendation": (
            f"Retake the adaptive assessment in 1 week after completing the study plan "
            f"to measure improvement, focusing especially on {weaknesses[0] if weaknesses else 'all topics'}."
        ),
    }
