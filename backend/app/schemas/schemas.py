"""
Pydantic schemas for API request/response validation.
Separate from MongoDB models to maintain clean API contracts.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


# ─── Request Schemas ──────────────────────────────────────────────────

class StartSessionRequest(BaseModel):
    """Request body for starting a new adaptive test session."""
    student_name: str = Field(..., min_length=1, max_length=100, description="Student identifier")
    max_questions: int = Field(default=10, ge=5, le=25, description="Maximum questions in session")


class SubmitAnswerRequest(BaseModel):
    """Request body for submitting an answer to a question."""
    session_id: str = Field(..., description="Active session ID")
    question_id: str = Field(..., description="ID of the question being answered")
    selected_answer: str = Field(..., description="Student's selected answer")
    response_time_ms: Optional[int] = Field(None, ge=0, description="Time taken in milliseconds")


# ─── Response Schemas ─────────────────────────────────────────────────

class QuestionResponse(BaseModel):
    """A question presented to the student (without the correct answer)."""
    question_id: str
    question_text: str
    options: List[str]
    topic: str
    difficulty: float
    question_number: int
    total_questions: int


class AnswerResult(BaseModel):
    """Result returned after submitting an answer."""
    is_correct: bool
    correct_answer: str
    selected_answer: str
    previous_ability: float
    updated_ability: float
    ability_change: float
    question_number: int
    total_questions: int
    session_complete: bool
    difficulty: float
    topic: str


class SessionSummary(BaseModel):
    """Complete summary of a finished test session."""
    session_id: str
    student_name: str
    status: str
    final_ability: float
    initial_ability: float
    ability_change: float
    total_questions: int
    total_correct: int
    accuracy_percentage: float
    topics_performance: dict
    ability_progression: List[float]
    study_plan: Optional[dict] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class SessionStartResponse(BaseModel):
    """Response when a new session is created."""
    session_id: str
    student_name: str
    initial_ability: float
    max_questions: int
    message: str


class NextQuestionResponse(BaseModel):
    """Response containing the next question or session completion notice."""
    session_complete: bool = False
    question: Optional[QuestionResponse] = None
    current_ability: float
    questions_answered: int
    questions_remaining: int


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    error_code: Optional[str] = None
