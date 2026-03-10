"""
MongoDB document models for the Adaptive Diagnostic Engine.
These define the schema for Questions and UserSessions stored in MongoDB.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


# ─── Enums ────────────────────────────────────────────────────────────

class Topic(str, Enum):
    """Supported question topics for GRE-style assessment."""
    ALGEBRA = "Algebra"
    GEOMETRY = "Geometry"
    ARITHMETIC = "Arithmetic"
    DATA_ANALYSIS = "Data Analysis"
    VOCABULARY = "Vocabulary"
    READING_COMPREHENSION = "Reading Comprehension"
    SENTENCE_EQUIVALENCE = "Sentence Equivalence"
    TEXT_COMPLETION = "Text Completion"


class SessionStatus(str, Enum):
    """Status of a user's testing session."""
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


# ─── Question Model ──────────────────────────────────────────────────

class Question(BaseModel):
    """
    Represents a single GRE-style question in the question bank.

    The difficulty score follows IRT conventions:
    - 0.1 = very easy
    - 0.5 = medium
    - 1.0 = very hard
    """
    id: Optional[str] = Field(None, alias="_id")
    question_text: str = Field(..., description="The question prompt")
    options: List[str] = Field(..., min_length=4, max_length=5, description="Answer choices")
    correct_answer: str = Field(..., description="The correct answer (must match one of the options)")
    difficulty: float = Field(..., ge=0.1, le=1.0, description="Difficulty score from 0.1 (easy) to 1.0 (hard)")
    topic: Topic = Field(..., description="Subject area of the question")
    tags: List[str] = Field(default_factory=list, description="Additional categorization tags")
    discrimination: float = Field(default=1.0, ge=0.1, le=3.0, description="IRT discrimination parameter (a)")
    guessing: float = Field(default=0.25, ge=0.0, le=0.5, description="IRT guessing parameter (c)")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "question_text": "If 3x + 7 = 22, what is x?",
                "options": ["3", "4", "5", "6"],
                "correct_answer": "5",
                "difficulty": 0.3,
                "topic": "Algebra",
                "tags": ["linear-equations", "basic"],
                "discrimination": 1.2,
                "guessing": 0.25,
            }
        },
    }


# ─── Response Record ─────────────────────────────────────────────────

class ResponseRecord(BaseModel):
    """A single question-response pair within a session."""
    question_id: str
    question_text: str
    topic: Topic
    difficulty: float
    selected_answer: str
    correct_answer: str
    is_correct: bool
    ability_after: float = Field(..., description="Estimated ability after this response")
    response_time_ms: Optional[int] = Field(None, description="Time taken to answer in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ─── User Session Model ──────────────────────────────────────────────

class UserSession(BaseModel):
    """
    Tracks a student's adaptive test session.

    The ability score is updated after every response using IRT.
    - 0.0 = very low proficiency
    - 0.5 = average
    - 1.0 = very high proficiency
    """
    id: Optional[str] = Field(None, alias="_id")
    student_name: str = Field(..., description="Name or identifier of the student")
    status: SessionStatus = Field(default=SessionStatus.ACTIVE)
    current_ability: float = Field(default=0.5, description="Current estimated ability (theta)")
    initial_ability: float = Field(default=0.5, description="Starting ability level")
    responses: List[ResponseRecord] = Field(default_factory=list)
    questions_answered: int = Field(default=0)
    questions_correct: int = Field(default=0)
    max_questions: int = Field(default=10)
    topics_performance: dict = Field(
        default_factory=dict,
        description="Per-topic accuracy: {topic: {correct: int, total: int}}",
    )
    study_plan: Optional[dict] = Field(None, description="AI-generated study plan")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,
    }
