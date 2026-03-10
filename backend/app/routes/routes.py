"""
API routes for the Adaptive Diagnostic Engine.

Endpoints:
    POST /api/sessions          - Start a new adaptive test session
    GET  /api/sessions/{id}/next-question - Get the next adaptive question
    POST /api/sessions/{id}/submit-answer - Submit an answer and get feedback
    GET  /api/sessions/{id}/summary       - Get session summary & study plan
    GET  /api/sessions          - List all sessions
    GET  /api/questions         - List all questions (admin)
    GET  /api/health            - Health check
"""

from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime
from typing import List

from app.core.database import database
from app.core.config import settings
from app.schemas.schemas import (
    StartSessionRequest,
    SubmitAnswerRequest,
    SessionStartResponse,
    NextQuestionResponse,
    QuestionResponse,
    AnswerResult,
    SessionSummary,
)
from app.services.adaptive_engine import (
    select_next_question,
    irt_probability,
    update_ability,
    simple_ability_update,
    compute_ability_from_responses,
)
from app.services.llm_service import generate_study_plan

router = APIRouter(prefix="/api", tags=["Adaptive Test"])


# ─── Health Check ─────────────────────────────────────────────────────

@router.get("/health")
async def health_check():
    """Health check endpoint to verify API and database connectivity."""
    try:
        db_status = "in-memory"
        questions_col = database.get_collection("questions")
        q_count = len(questions_col._data)
        return {
            "status": "healthy",
            "database": db_status,
            "questions_loaded": q_count,
            "version": "1.0.0",
        }
    except Exception:
        raise HTTPException(status_code=503, detail="Database connection failed")


# ─── Session Management ──────────────────────────────────────────────

@router.post("/sessions", response_model=SessionStartResponse, status_code=201)
async def start_session(request: StartSessionRequest):
    """
    Start a new adaptive test session for a student.

    Creates a UserSession document with initial ability of 0.5
    and returns the session ID for subsequent requests.
    """
    sessions = database.get_collection("user_sessions")

    session_doc = {
        "student_name": request.student_name,
        "status": "active",
        "current_ability": settings.initial_ability,
        "initial_ability": settings.initial_ability,
        "responses": [],
        "questions_answered": 0,
        "questions_correct": 0,
        "max_questions": request.max_questions,
        "topics_performance": {},
        "study_plan": None,
        "started_at": datetime.utcnow(),
        "completed_at": None,
    }

    result = await sessions.insert_one(session_doc)

    return SessionStartResponse(
        session_id=str(result.inserted_id),
        student_name=request.student_name,
        initial_ability=settings.initial_ability,
        max_questions=request.max_questions,
        message="Session started. Request your first question via GET /api/sessions/{session_id}/next-question",
    )


@router.get("/sessions")
async def list_sessions():
    """List all test sessions, ordered by most recent."""
    sessions = database.get_collection("user_sessions")
    cursor = sessions.find().sort("started_at", -1).limit(50)

    results = []
    async for session in cursor:
        session["_id"] = str(session["_id"])
        # Convert datetime fields for JSON serialization
        for key in ("started_at", "completed_at"):
            if key in session and session[key] is not None:
                session[key] = session[key].isoformat()
        for r in session.get("responses", []):
            if "timestamp" in r and r["timestamp"] is not None:
                r["timestamp"] = r["timestamp"].isoformat()
        results.append(session)

    return results


# ─── Question Flow ────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/next-question", response_model=NextQuestionResponse)
async def get_next_question(session_id: str):
    """
    Get the next adaptively-selected question for the session.

    Uses Maximum Fisher Information criterion to select the question
    that provides the most information about the student's ability
    at their current estimated level.
    """
    # Validate session
    sessions = database.get_collection("user_sessions")
    try:
        session = await sessions.find_one({"_id": ObjectId(session_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["status"] != "active":
        raise HTTPException(
            status_code=400,
            detail=f"Session is {session['status']}. Start a new session.",
        )

    # Check if we've reached the question limit
    if session["questions_answered"] >= session["max_questions"]:
        # Auto-complete the session
        await _complete_session(sessions, session)
        return NextQuestionResponse(
            session_complete=True,
            question=None,
            current_ability=session["current_ability"],
            questions_answered=session["questions_answered"],
            questions_remaining=0,
        )

    # Fetch all questions from the bank
    questions_col = database.get_collection("questions")
    all_questions = await questions_col.find().to_list(length=100)

    # Get IDs of already-answered questions
    answered_ids = [r["question_id"] for r in session.get("responses", [])]

    # Select the optimal next question
    next_q = select_next_question(
        current_theta=session["current_ability"],
        available_questions=all_questions,
        answered_ids=answered_ids,
    )

    if not next_q:
        await _complete_session(sessions, session)
        return NextQuestionResponse(
            session_complete=True,
            question=None,
            current_ability=session["current_ability"],
            questions_answered=session["questions_answered"],
            questions_remaining=0,
        )

    questions_remaining = session["max_questions"] - session["questions_answered"]

    return NextQuestionResponse(
        session_complete=False,
        question=QuestionResponse(
            question_id=str(next_q["_id"]),
            question_text=next_q["question_text"],
            options=next_q["options"],
            topic=next_q["topic"],
            difficulty=next_q["difficulty"],
            question_number=session["questions_answered"] + 1,
            total_questions=session["max_questions"],
        ),
        current_ability=session["current_ability"],
        questions_answered=session["questions_answered"],
        questions_remaining=questions_remaining,
    )


@router.post("/sessions/{session_id}/submit-answer", response_model=AnswerResult)
async def submit_answer(session_id: str, request: SubmitAnswerRequest):
    """
    Submit an answer and receive immediate feedback.

    Updates the student's ability estimate using IRT and returns
    the result with the new ability score.
    """
    sessions = database.get_collection("user_sessions")
    questions_col = database.get_collection("questions")

    # Validate session
    try:
        session = await sessions.find_one({"_id": ObjectId(session_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["status"] != "active":
        raise HTTPException(status_code=400, detail="Session is not active")

    if request.session_id != session_id:
        raise HTTPException(status_code=400, detail="Session ID mismatch")

    # Validate question
    try:
        question = await questions_col.find_one({"_id": ObjectId(request.question_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid question ID format")

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # Check for duplicate submission
    answered_ids = [r["question_id"] for r in session.get("responses", [])]
    if request.question_id in answered_ids:
        raise HTTPException(status_code=400, detail="Question already answered in this session")

    # Evaluate answer
    is_correct = request.selected_answer.strip() == question["correct_answer"].strip()
    previous_ability = session["current_ability"]

    # ─── IRT Ability Update ───────────────────────────────────────
    # Build response history for full MLE estimation (batch query to avoid N+1)
    past_responses = session.get("responses", [])
    response_history = []

    if past_responses:
        past_q_ids = [ObjectId(r["question_id"]) for r in past_responses]
        past_q_docs = {}
        async for q_doc in questions_col.find({"_id": {"$in": past_q_ids}}):
            past_q_docs[str(q_doc["_id"])] = q_doc

        for r in past_responses:
            q_doc = past_q_docs.get(r["question_id"])
            if q_doc:
                response_history.append((
                    q_doc["difficulty"],
                    q_doc.get("discrimination", 1.0),
                    q_doc.get("guessing", 0.25),
                    r["is_correct"],
                ))

    # Add current response
    response_history.append((
        question["difficulty"],
        question.get("discrimination", 1.0),
        question.get("guessing", 0.25),
        is_correct,
    ))

    # Compute updated ability using full MLE
    updated_ability = update_ability(
        current_theta=previous_ability,
        responses=response_history,
    )

    # Also compute simple update for blending (adds intuitive behavior)
    simple_update = simple_ability_update(
        current_theta=previous_ability,
        is_correct=is_correct,
        question_difficulty=question["difficulty"],
        question_number=session["questions_answered"] + 1,
    )

    # Blend: 70% MLE + 30% simple (gives responsive feel while being mathematically sound)
    blended_ability = round(0.7 * updated_ability + 0.3 * simple_update, 4)
    blended_ability = max(0.05, min(0.95, blended_ability))

    # ─── Update Session ───────────────────────────────────────────
    question_number = session["questions_answered"] + 1
    topic = question["topic"]

    # Update topic performance
    topics_perf = session.get("topics_performance", {})
    if topic not in topics_perf:
        topics_perf[topic] = {"correct": 0, "total": 0}
    topics_perf[topic]["total"] += 1
    if is_correct:
        topics_perf[topic]["correct"] += 1

    # Create response record
    response_record = {
        "question_id": request.question_id,
        "question_text": question["question_text"],
        "topic": topic,
        "difficulty": question["difficulty"],
        "selected_answer": request.selected_answer,
        "correct_answer": question["correct_answer"],
        "is_correct": is_correct,
        "ability_after": blended_ability,
        "response_time_ms": request.response_time_ms,
        "timestamp": datetime.utcnow(),
    }

    # Update session in MongoDB
    update_fields = {
        "$set": {
            "current_ability": blended_ability,
            "questions_answered": question_number,
            "questions_correct": session["questions_correct"] + (1 if is_correct else 0),
            "topics_performance": topics_perf,
        },
        "$push": {"responses": response_record},
    }

    await sessions.update_one({"_id": ObjectId(session_id)}, update_fields)

    # Check if session is complete
    session_complete = question_number >= session["max_questions"]
    if session_complete:
        updated_session = await sessions.find_one({"_id": ObjectId(session_id)})
        if updated_session:
            await _complete_session(sessions, updated_session)

    return AnswerResult(
        is_correct=is_correct,
        correct_answer=question["correct_answer"],
        selected_answer=request.selected_answer,
        previous_ability=previous_ability,
        updated_ability=blended_ability,
        ability_change=round(blended_ability - previous_ability, 4),
        question_number=question_number,
        total_questions=session["max_questions"],
        session_complete=session_complete,
        difficulty=question["difficulty"],
        topic=topic,
    )


# ─── Session Summary ─────────────────────────────────────────────────

@router.get("/sessions/{session_id}/summary", response_model=SessionSummary)
async def get_session_summary(session_id: str):
    """
    Get a complete summary of the test session including the AI study plan.

    Available after the session is completed. Includes ability progression,
    per-topic performance, and a personalized 3-step study plan.
    """
    sessions = database.get_collection("user_sessions")

    try:
        session = await sessions.find_one({"_id": ObjectId(session_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Build ability progression
    ability_progression = [session["initial_ability"]]
    for r in session.get("responses", []):
        ability_progression.append(r["ability_after"])

    accuracy = (
        (session["questions_correct"] / session["questions_answered"] * 100)
        if session["questions_answered"] > 0
        else 0
    )

    return SessionSummary(
        session_id=str(session["_id"]),
        student_name=session["student_name"],
        status=session["status"],
        final_ability=session["current_ability"],
        initial_ability=session["initial_ability"],
        ability_change=round(session["current_ability"] - session["initial_ability"], 4),
        total_questions=session["questions_answered"],
        total_correct=session["questions_correct"],
        accuracy_percentage=round(accuracy, 1),
        topics_performance=session.get("topics_performance", {}),
        ability_progression=ability_progression,
        study_plan=session.get("study_plan"),
        started_at=session["started_at"],
        completed_at=session.get("completed_at"),
    )


# ─── Admin: Questions ─────────────────────────────────────────────────

@router.get("/questions")
async def list_questions():
    """List all questions in the question bank (admin endpoint)."""
    questions_col = database.get_collection("questions")
    cursor = questions_col.find().sort("difficulty", 1).limit(100)

    results = []
    async for q in cursor:
        q["_id"] = str(q["_id"])
        if "created_at" in q and q["created_at"] is not None:
            q["created_at"] = q["created_at"].isoformat()
        results.append(q)

    return results


# ─── Internal Helpers ─────────────────────────────────────────────────

async def _complete_session(sessions, session: dict) -> None:
    """Mark a session as completed, re-estimate final ability, and generate the study plan.

    Performs a full MLE re-estimation from all responses for the most
    accurate final ability score, then generates a personalized study plan.
    """
    # ─── Final MLE Re-Estimation ──────────────────────────────────
    # Re-compute ability from scratch using all response data.
    # This is more accurate than the incremental blended updates.
    questions_col = database.get_collection("questions")
    responses = session.get("responses", [])
    response_tuples = []

    if responses:
        q_ids = [ObjectId(r["question_id"]) for r in responses]
        q_docs = {}
        async for q_doc in questions_col.find({"_id": {"$in": q_ids}}):
            q_docs[str(q_doc["_id"])] = q_doc

        for r in responses:
            q_doc = q_docs.get(r["question_id"])
            if q_doc:
                response_tuples.append((
                    q_doc["difficulty"],
                    q_doc.get("discrimination", 1.0),
                    q_doc.get("guessing", 0.25),
                    r["is_correct"],
                ))

    final_ability = session["current_ability"]
    if response_tuples:
        final_ability = compute_ability_from_responses(response_tuples)

    # ─── Study Plan Generation ────────────────────────────────────
    study_plan = await generate_study_plan(
        student_name=session["student_name"],
        final_ability=final_ability,
        total_correct=session["questions_correct"],
        total_questions=session["questions_answered"],
        topics_performance=session.get("topics_performance", {}),
        responses=responses,
    )

    await sessions.update_one(
        {"_id": session["_id"]},
        {
            "$set": {
                "status": "completed",
                "completed_at": datetime.utcnow(),
                "current_ability": final_ability,
                "study_plan": study_plan,
            }
        },
    )
