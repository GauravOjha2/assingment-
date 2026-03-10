# Adaptive Diagnostic Engine

An AI-driven adaptive testing system that dynamically assesses student proficiency using **Item Response Theory (IRT)** and generates personalized study plans powered by **OpenAI's GPT**.

Built with **FastAPI**, **in-memory storage**, and a modern vanilla JS frontend. Deployable to **Vercel** as a serverless application.

---

## Architecture Overview

```
adaptive-diagnostic-engine/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py          # Pydantic settings (env vars)
│   │   │   └── database.py        # In-memory async database layer
│   │   ├── models/
│   │   │   └── models.py          # Question & UserSession schemas
│   │   ├── routes/
│   │   │   └── routes.py          # FastAPI endpoints (7 routes)
│   │   ├── schemas/
│   │   │   └── schemas.py         # Request/Response validation (Pydantic v2)
│   │   ├── services/
│   │   │   ├── adaptive_engine.py # IRT 3PL algorithm core
│   │   │   └── llm_service.py     # OpenAI study plan generation
│   │   ├── main.py                # FastAPI app entry point
│   │   └── seed.py                # Database seeder (25 GRE questions)
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── index.html                 # Single-page application
│   ├── styles.css                 # Modern dark theme UI
│   └── app.js                     # Frontend logic & chart rendering
├── api/
│   └── index.py                   # Vercel serverless entry point
├── vercel.json                    # Vercel deployment configuration
├── .gitignore
└── README.md
```

---

## Quick Start

### Prerequisites

- **Python 3.9+**
- **OpenAI API key** (optional, for AI-powered study plans)

> **Note:** No MongoDB installation required. The application uses an in-memory database that automatically seeds 25 GRE-style questions on startup.

### 1. Clone & Install

```bash
git clone https://github.com/GauravOjha2/assingment-.git
cd assingment-
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)

```bash
cp .env.example .env
```

Edit `.env` to add your OpenAI key for AI-powered study plans:

```env
OPENAI_API_KEY=sk-your-key-here    # Optional - enables AI study plans
```

Without an API key, the system generates rule-based study plans automatically.

### 3. Run the Server

```bash
uvicorn app.main:app --reload --port 8000
```

The database is automatically seeded with 25 GRE-style questions on startup.

### 4. Open the Application

Navigate to **http://localhost:8000** in your browser.

- Interactive API docs: **http://localhost:8000/docs** (Swagger UI)
- Alternative docs: **http://localhost:8000/redoc**

---

## Vercel Deployment

This project is configured for zero-config deployment to Vercel.

### Deploy Steps

1. Push your code to GitHub
2. Import the repo at [vercel.com/new](https://vercel.com/new)
3. Set the **Root Directory** to `.` (project root)
4. Add the `OPENAI_API_KEY` environment variable in Vercel's dashboard (optional)
5. Deploy

The `vercel.json` configuration handles routing:
- `/api/*` routes to the FastAPI serverless function
- `/static/*` serves frontend assets
- `/` serves `index.html`

> **Note:** Since Vercel uses serverless functions, the in-memory database resets between cold starts. Each function invocation re-seeds the questions. Session data persists within a warm function instance but not across cold starts. For production persistence, integrate MongoDB Atlas.

---

## API Documentation

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/sessions` | Start a new adaptive test session |
| `GET` | `/api/sessions/{id}/next-question` | Get the next adaptively-selected question |
| `POST` | `/api/sessions/{id}/submit-answer` | Submit an answer and receive feedback |
| `GET` | `/api/sessions/{id}/summary` | Get session summary with AI study plan |
| `GET` | `/api/sessions` | List all sessions |
| `GET` | `/api/questions` | List all questions (admin) |
| `GET` | `/api/health` | Health check |

### Example Flow

**1. Start a session:**
```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"student_name": "Alice", "max_questions": 10}'
```

**2. Get next question:**
```bash
curl http://localhost:8000/api/sessions/{session_id}/next-question
```

**3. Submit answer:**
```bash
curl -X POST http://localhost:8000/api/sessions/{session_id}/submit-answer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "{session_id}",
    "question_id": "{question_id}",
    "selected_answer": "5",
    "response_time_ms": 12000
  }'
```

**4. Get results & study plan:**
```bash
curl http://localhost:8000/api/sessions/{session_id}/summary
```

---

## Adaptive Algorithm: Deep Dive

### Mathematical Foundation

This system implements a **3-Parameter Logistic (3PL) Item Response Theory** model, the gold standard in Computerized Adaptive Testing (CAT).

#### The IRT Probability Model

The probability of student with ability theta answering an item correctly:

```
P(theta) = c + (1 - c) / (1 + exp(-a * (theta - b)))
```

Where:
- **theta** -- Student ability parameter (what we estimate, scaled 0-1)
- **b** -- Item difficulty parameter (0.1 = easy, 1.0 = hard)
- **a** -- Item discrimination (how well the item differentiates ability levels)
- **c** -- Pseudo-guessing parameter (probability of correct answer by chance, typically 0.25 for 4-option MCQ)

#### Ability Estimation (MLE with Bayesian Prior)

After each response, we update theta using **Newton-Raphson Maximum Likelihood Estimation**:

1. Compute the first derivative (gradient) of the log-likelihood across all responses
2. Compute the second derivative (Hessian) for curvature
3. Apply a Bayesian Gaussian prior centered at 0.5 (sigma=0.3) for early-stage regularization
4. Take a learning-rate-controlled step: `theta_new = theta - lr * (dL/dtheta) / (d2L/dtheta2)`
5. Iterate 15 times for convergence

The Bayesian prior prevents wild oscillations when few responses are available and gradually loses influence as evidence accumulates.

#### Blended Update Strategy

The final ability update blends two approaches:
- **70% MLE estimate** -- Mathematically rigorous, uses all response history
- **30% Simple heuristic** -- Provides intuitive, responsive feel (bigger step for hard correct / easy incorrect)

This ensures the system is both mathematically sound AND feels responsive to the student.

#### Final MLE Re-Estimation

When the session completes, the system performs a **full MLE re-estimation from scratch** using all response data. This produces the most statistically accurate final ability score, separate from the incremental updates during the test. The summary endpoint returns this clean re-estimated value.

#### Question Selection: Maximum Fisher Information

For each unanswered question, we compute **Fisher Information** at the current theta:

```
I(theta) = a^2 * [(P - c)^2 / ((1-c)^2 * P * Q)]
```

The question with the **highest Fisher Information** is selected -- this is the item that provides maximum statistical information about the student's true ability at their current estimated level. This is the standard approach used in professional CAT systems like the GRE itself.

### Algorithm Flow

```
1. Student starts -> theta = 0.5 (baseline)
2. Select question maximizing Fisher Information at current theta
3. Student answers
4. Update theta using MLE across ALL responses (not just the latest)
5. Blend with simple heuristic for responsiveness
6. Repeat from step 2 until max questions reached
7. Generate AI study plan based on performance profile
```

### Why This Approach Works

- **IRT is the same framework used by ETS for the actual GRE** -- this isn't a toy algorithm
- **Full MLE re-estimation** prevents the "path dependency" problem of incremental updates
- **Fisher Information selection** is mathematically optimal for minimizing standard error
- **Bayesian prior** handles the cold-start problem elegantly
- **Convergence decay** in the simple heuristic ensures estimates stabilize

---

## Database Schema Design

The application uses an in-memory database that mimics MongoDB's document model. The schema is designed for potential migration to MongoDB Atlas.

### Questions Collection

```javascript
{
  _id: ObjectId,
  question_text: String,        // The question prompt
  options: [String],             // 4-5 answer choices
  correct_answer: String,        // Must match one option exactly
  difficulty: Number,            // 0.1 (easy) to 1.0 (hard)
  topic: String,                 // "Algebra", "Vocabulary", etc.
  tags: [String],                // ["linear-equations", "basic"]
  discrimination: Number,        // IRT 'a' parameter (0.1-3.0)
  guessing: Number,              // IRT 'c' parameter (0.0-0.5)
  created_at: Date
}
```

### UserSessions Collection

```javascript
{
  _id: ObjectId,
  student_name: String,
  status: "active" | "completed",
  current_ability: Number,       // Current theta estimate
  initial_ability: Number,       // Starting theta (0.5)
  responses: [{                  // Full response history
    question_id: String,
    question_text: String,
    topic: String,
    difficulty: Number,
    selected_answer: String,
    correct_answer: String,
    is_correct: Boolean,
    ability_after: Number,       // theta after this response
    response_time_ms: Number,
    timestamp: Date
  }],
  questions_answered: Number,
  questions_correct: Number,
  max_questions: Number,
  topics_performance: {          // Per-topic breakdown
    "Algebra": { correct: 2, total: 3 },
    "Vocabulary": { correct: 0, total: 2 }
  },
  study_plan: Object,           // AI-generated study plan
  started_at: Date,
  completed_at: Date
}
```

### Design Decisions

1. **Embedded responses** -- Responses are embedded within the session document rather than normalized. For a 10-25 question test, this avoids expensive joins and keeps reads atomic.

2. **Denormalized topics_performance** -- Pre-aggregated per-topic stats avoid re-scanning the responses array on every summary request.

3. **In-memory with MongoDB API** -- The in-memory layer implements `$push`, `$set`, `$in`, and `$inc` operators, making migration to real MongoDB trivial.

4. **IRT parameters on questions** -- Storing `discrimination` and `guessing` per-question allows different calibrations without schema changes.

---

## AI Study Plan Generation (Phase 3)

### How It Works

When a session completes, the system:

1. **Collects performance data** -- topics missed, difficulty levels reached, per-topic accuracy, full question-by-question detail
2. **Builds a structured prompt** -- Sends a detailed performance summary to GPT-4o-mini
3. **Parses structured JSON** -- The LLM returns a validated JSON study plan with exactly 3 steps
4. **Stores the plan** -- Persisted in the session document for retrieval

### Fallback System

If the OpenAI API key is not configured or the API call fails, the system generates a **rule-based fallback plan** using the same performance data. This ensures the application always provides actionable feedback -- it degrades gracefully rather than failing.

### Study Plan Structure

```json
{
  "overall_assessment": "2-3 sentence assessment",
  "ability_level": "Beginner | Intermediate | Advanced",
  "strengths": ["topic1", "topic2"],
  "weaknesses": ["topic1", "topic2"],
  "study_plan": [
    {
      "step": 1,
      "title": "Actionable title",
      "description": "What to study and how",
      "focus_topics": ["topic"],
      "recommended_resources": ["specific resources"],
      "estimated_time": "2-3 hours"
    }
  ],
  "next_test_recommendation": "When to retest"
}
```

---

## Frontend Features

- **Dark theme** with smooth animations and transitions
- **Real-time ability tracking** with Canvas-based charts
- **Keyboard navigation** -- Press 1-5 to select answers, Enter/Space to advance
- **Loading states** during API calls
- **Responsive design** for mobile and desktop
- **Score visualization** with animated SVG ring and per-topic breakdown bars

---

## AI Development Log

### Tools Used

- **Claude (Anthropic)** -- Primary AI assistant for architecture design, algorithm implementation, and code generation
- **GitHub Copilot** -- Code completion and boilerplate acceleration

### How AI Accelerated Development

1. **Architecture Design** -- Used Claude to discuss the tradeoffs between embedded vs. referenced MongoDB schema designs for the session model. The AI helped reason through read/write patterns to justify embedding.

2. **IRT Algorithm** -- Claude helped translate the mathematical formulation of the 3PL model into Python code, including the Newton-Raphson MLE implementation. The AI was particularly helpful in deriving the correct gradient and Hessian formulas for the log-likelihood function.

3. **Prompt Engineering** -- Iterating on the LLM prompt for study plan generation. The AI helped design a prompt that produces consistently structured JSON output with actionable recommendations.

4. **Frontend Canvas Charts** -- Used AI to implement the ability progression chart using raw Canvas API, avoiding the need for a charting library dependency.

5. **Bug Fixes & Database Layer** -- AI identified critical bugs in the in-memory database layer (missing `$push` and `$in` operator support) and helped rewrite it with proper MongoDB operator compatibility.

### Challenges AI Couldn't Fully Solve

1. **Ability Update Tuning** -- The balance between MLE rigor and responsive feel required manual experimentation. Pure MLE updates felt sluggish in early questions; the 70/30 blending ratio was determined through iterative testing, not AI suggestion.

2. **Fisher Information Edge Cases** -- When ability is near the bounds (0 or 1), Fisher Information calculations can produce degenerate values. The clamping and epsilon handling required careful manual debugging.

3. **Frontend UX Flow** -- The exact timing of animations, feedback display, and screen transitions required human judgment about what "feels right."

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.9+, FastAPI |
| Database | In-memory (MongoDB-compatible API) |
| AI/LLM | OpenAI GPT-4o-mini |
| Frontend | Vanilla JS, HTML5 Canvas |
| Validation | Pydantic v2 |
| Algorithm | 3PL IRT, Newton-Raphson MLE |
| Deployment | Vercel (serverless) |

---

## License

MIT
