"""
Database seeding script for the Adaptive Diagnostic Engine.
Populates the questions collection with 25 GRE-style questions
spanning multiple topics and difficulty levels.

Usage:
    python -m app.seed
"""

import asyncio
from datetime import datetime
from app.core.database import database


QUESTIONS = [
    # ─── ALGEBRA (5 questions) ────────────────────────────────────────
    {
        "question_text": "If 3x + 7 = 22, what is the value of x?",
        "options": ["3", "4", "5", "6"],
        "correct_answer": "5",
        "difficulty": 0.2,
        "topic": "Algebra",
        "tags": ["linear-equations", "basic"],
        "discrimination": 1.0,
        "guessing": 0.25,
    },
    {
        "question_text": "What is the solution set for |2x - 5| = 9?",
        "options": ["{-2, 7}", "{7, -2}", "{2, -7}", "{-7, 2}"],
        "correct_answer": "{-2, 7}",
        "difficulty": 0.5,
        "topic": "Algebra",
        "tags": ["absolute-value", "equations"],
        "discrimination": 1.3,
        "guessing": 0.25,
    },
    {
        "question_text": "If f(x) = x² - 4x + 3, what are the roots of f(x)?",
        "options": ["x = 1, x = 3", "x = -1, x = -3", "x = 2, x = 3", "x = -1, x = 3"],
        "correct_answer": "x = 1, x = 3",
        "difficulty": 0.4,
        "topic": "Algebra",
        "tags": ["quadratic", "factoring", "roots"],
        "discrimination": 1.2,
        "guessing": 0.25,
    },
    {
        "question_text": "A system of equations: 2x + y = 10 and x - y = 2. What is x?",
        "options": ["3", "4", "5", "6"],
        "correct_answer": "4",
        "difficulty": 0.35,
        "topic": "Algebra",
        "tags": ["systems-of-equations", "linear"],
        "discrimination": 1.1,
        "guessing": 0.25,
    },
    {
        "question_text": "If log₂(x) + log₂(x-2) = 3, what is x?",
        "options": ["4", "2", "-2", "8"],
        "correct_answer": "4",
        "difficulty": 0.8,
        "topic": "Algebra",
        "tags": ["logarithms", "advanced"],
        "discrimination": 1.8,
        "guessing": 0.25,
    },

    # ─── GEOMETRY (4 questions) ───────────────────────────────────────
    {
        "question_text": "What is the area of a triangle with base 10 and height 6?",
        "options": ["30", "60", "16", "36"],
        "correct_answer": "30",
        "difficulty": 0.15,
        "topic": "Geometry",
        "tags": ["area", "triangle", "basic"],
        "discrimination": 0.9,
        "guessing": 0.25,
    },
    {
        "question_text": "A circle has a circumference of 31.4 cm. What is its approximate radius?",
        "options": ["5 cm", "10 cm", "15 cm", "3.14 cm"],
        "correct_answer": "5 cm",
        "difficulty": 0.4,
        "topic": "Geometry",
        "tags": ["circle", "circumference"],
        "discrimination": 1.1,
        "guessing": 0.25,
    },
    {
        "question_text": "In a right triangle, if one leg is 5 and the hypotenuse is 13, what is the other leg?",
        "options": ["12", "8", "10", "11"],
        "correct_answer": "12",
        "difficulty": 0.45,
        "topic": "Geometry",
        "tags": ["pythagorean-theorem", "right-triangle"],
        "discrimination": 1.2,
        "guessing": 0.25,
    },
    {
        "question_text": "What is the volume of a cylinder with radius 3 and height 7? (Use π ≈ 3.14)",
        "options": ["197.82", "65.94", "131.88", "63"],
        "correct_answer": "197.82",
        "difficulty": 0.55,
        "topic": "Geometry",
        "tags": ["volume", "cylinder", "3d"],
        "discrimination": 1.3,
        "guessing": 0.25,
    },

    # ─── ARITHMETIC (3 questions) ─────────────────────────────────────
    {
        "question_text": "What is 15% of 240?",
        "options": ["36", "24", "30", "40"],
        "correct_answer": "36",
        "difficulty": 0.2,
        "topic": "Arithmetic",
        "tags": ["percentages", "basic"],
        "discrimination": 0.8,
        "guessing": 0.25,
    },
    {
        "question_text": "If a product costs $80 after a 20% discount, what was the original price?",
        "options": ["$96", "$100", "$90", "$110"],
        "correct_answer": "$100",
        "difficulty": 0.45,
        "topic": "Arithmetic",
        "tags": ["percentages", "word-problem", "discount"],
        "discrimination": 1.2,
        "guessing": 0.25,
    },
    {
        "question_text": "The ratio of boys to girls in a class is 3:5. If there are 40 students total, how many boys are there?",
        "options": ["15", "24", "25", "18"],
        "correct_answer": "15",
        "difficulty": 0.35,
        "topic": "Arithmetic",
        "tags": ["ratios", "word-problem"],
        "discrimination": 1.1,
        "guessing": 0.25,
    },

    # ─── DATA ANALYSIS (3 questions) ──────────────────────────────────
    {
        "question_text": "The mean of five numbers is 20. If four of the numbers are 15, 18, 22, and 25, what is the fifth number?",
        "options": ["20", "15", "25", "18"],
        "correct_answer": "20",
        "difficulty": 0.4,
        "topic": "Data Analysis",
        "tags": ["mean", "statistics"],
        "discrimination": 1.0,
        "guessing": 0.25,
    },
    {
        "question_text": "What is the median of the set {3, 7, 1, 9, 5, 11, 2}?",
        "options": ["5", "7", "3", "6"],
        "correct_answer": "5",
        "difficulty": 0.3,
        "topic": "Data Analysis",
        "tags": ["median", "statistics", "basic"],
        "discrimination": 1.0,
        "guessing": 0.25,
    },
    {
        "question_text": "A dataset has a standard deviation of 0. What can you conclude?",
        "options": [
            "All values are equal",
            "The mean is 0",
            "There is only one data point",
            "The data is normally distributed",
        ],
        "correct_answer": "All values are equal",
        "difficulty": 0.65,
        "topic": "Data Analysis",
        "tags": ["standard-deviation", "statistics", "conceptual"],
        "discrimination": 1.5,
        "guessing": 0.25,
    },

    # ─── VOCABULARY (4 questions) ─────────────────────────────────────
    {
        "question_text": "Choose the word most similar in meaning to 'EPHEMERAL':",
        "options": ["Eternal", "Fleeting", "Sturdy", "Prominent"],
        "correct_answer": "Fleeting",
        "difficulty": 0.5,
        "topic": "Vocabulary",
        "tags": ["synonyms", "gre-words"],
        "discrimination": 1.2,
        "guessing": 0.25,
    },
    {
        "question_text": "Choose the word most opposite in meaning to 'LOQUACIOUS':",
        "options": ["Talkative", "Reticent", "Generous", "Ambitious"],
        "correct_answer": "Reticent",
        "difficulty": 0.6,
        "topic": "Vocabulary",
        "tags": ["antonyms", "gre-words"],
        "discrimination": 1.4,
        "guessing": 0.25,
    },
    {
        "question_text": "Select the word that best completes the sentence: 'The scientist's _____ approach ensured that every hypothesis was tested rigorously.'",
        "options": ["Haphazard", "Methodical", "Indifferent", "Whimsical"],
        "correct_answer": "Methodical",
        "difficulty": 0.35,
        "topic": "Vocabulary",
        "tags": ["sentence-completion", "context-clues"],
        "discrimination": 1.0,
        "guessing": 0.25,
    },
    {
        "question_text": "Choose the word most similar in meaning to 'OBFUSCATE':",
        "options": ["Clarify", "Confuse", "Decorate", "Eliminate"],
        "correct_answer": "Confuse",
        "difficulty": 0.7,
        "topic": "Vocabulary",
        "tags": ["synonyms", "gre-words", "advanced"],
        "discrimination": 1.5,
        "guessing": 0.25,
    },

    # ─── READING COMPREHENSION (2 questions) ──────────────────────────
    {
        "question_text": "A passage states: 'The proliferation of renewable energy sources has fundamentally altered the calculus of energy economics.' What does 'calculus' mean here?",
        "options": [
            "A branch of mathematics",
            "The system of reasoning or analysis",
            "A type of mineral deposit",
            "A medical condition",
        ],
        "correct_answer": "The system of reasoning or analysis",
        "difficulty": 0.55,
        "topic": "Reading Comprehension",
        "tags": ["vocabulary-in-context", "inference"],
        "discrimination": 1.3,
        "guessing": 0.25,
    },
    {
        "question_text": "An author argues that 'urbanization, while economically beneficial, engenders ecological fragility.' The author's tone is best described as:",
        "options": ["Enthusiastic", "Balanced and cautionary", "Dismissive", "Indifferent"],
        "correct_answer": "Balanced and cautionary",
        "difficulty": 0.6,
        "topic": "Reading Comprehension",
        "tags": ["tone", "author-purpose"],
        "discrimination": 1.4,
        "guessing": 0.25,
    },

    # ─── SENTENCE EQUIVALENCE (2 questions) ───────────────────────────
    {
        "question_text": "Select TWO words that best complete the sentence and produce similar meanings: 'The politician's speech was so _____ that even supporters found it hard to follow.'",
        "options": ["Convoluted", "Concise", "Tortuous", "Eloquent"],
        "correct_answer": "Convoluted",
        "difficulty": 0.75,
        "topic": "Sentence Equivalence",
        "tags": ["dual-answer", "gre-verbal"],
        "discrimination": 1.6,
        "guessing": 0.25,
    },
    {
        "question_text": "The researcher's findings were _____, challenging decades of established theory.",
        "options": ["Conventional", "Iconoclastic", "Predictable", "Mundane"],
        "correct_answer": "Iconoclastic",
        "difficulty": 0.85,
        "topic": "Sentence Equivalence",
        "tags": ["vocabulary", "gre-verbal", "advanced"],
        "discrimination": 1.8,
        "guessing": 0.25,
    },

    # ─── TEXT COMPLETION (2 questions) ─────────────────────────────────
    {
        "question_text": "Despite the _____ of evidence against the theory, a few scientists continued to advocate for it.",
        "options": ["Paucity", "Preponderance", "Ambiguity", "Irrelevance"],
        "correct_answer": "Preponderance",
        "difficulty": 0.7,
        "topic": "Text Completion",
        "tags": ["context-clues", "gre-verbal"],
        "discrimination": 1.5,
        "guessing": 0.25,
    },
    {
        "question_text": "The novel's narrative structure was deliberately _____; the author wanted readers to piece together the timeline themselves.",
        "options": ["Linear", "Fragmented", "Predictable", "Conventional"],
        "correct_answer": "Fragmented",
        "difficulty": 0.55,
        "topic": "Text Completion",
        "tags": ["context-clues", "inference"],
        "discrimination": 1.3,
        "guessing": 0.25,
    },
]


async def seed_questions() -> None:
    """Insert all questions into the database, clearing existing data first.
    
    Assumes database.connect() has already been called (e.g., by the app lifespan).
    When run standalone via __main__, connects and disconnects itself.
    """
    questions_col = database.get_collection("questions")
    sessions_col = database.get_collection("user_sessions")

    # Clear existing data
    await questions_col.delete_many({})
    await sessions_col.delete_many({})
    print("[Seed] Cleared existing collections")

    # Add timestamps (use copies to avoid mutating the module-level list)
    docs = []
    for q in QUESTIONS:
        doc = dict(q)
        doc["created_at"] = datetime.utcnow()
        docs.append(doc)

    # Insert questions
    result = await questions_col.insert_many(docs)
    print(f"[Seed] Inserted {len(result.inserted_ids)} questions")

    # Create indexes for efficient querying
    await questions_col.create_index("difficulty")
    await questions_col.create_index("topic")
    await questions_col.create_index([("difficulty", 1), ("topic", 1)])
    print("[Seed] Created indexes on questions collection")

    # Create indexes on sessions
    await sessions_col.create_index("status")
    await sessions_col.create_index("started_at")
    print("[Seed] Created indexes on user_sessions collection")

    print("[Seed] Seeding complete!")


if __name__ == "__main__":
    async def _run():
        await database.connect()
        await seed_questions()
        await database.disconnect()
    asyncio.run(_run())
