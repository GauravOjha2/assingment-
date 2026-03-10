/**
 * Adaptive Diagnostic Engine - Frontend Application
 * 
 * Manages the full test lifecycle: session creation, adaptive question flow,
 * answer submission, and results visualization with ability charts.
 */

// ─── State ───────────────────────────────────────────────────────────
const state = {
    sessionId: null,
    studentName: '',
    currentQuestion: null,
    selectedAnswer: null,
    questionStartTime: null,
    correctCount: 0,
    questionsAnswered: 0,
    totalQuestions: 10,
    abilityHistory: [0.5],
    timerInterval: null,
    elapsedSeconds: 0,
    isLoading: false,
};

// ─── API Client ──────────────────────────────────────────────────────
const API_BASE = '/api';

async function apiRequest(method, endpoint, body = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body) options.body = JSON.stringify(body);

    const response = await fetch(`${API_BASE}${endpoint}`, options);
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
    }
    return response.json();
}

// ─── DOM References ──────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

const screens = {
    landing: $('landing-screen'),
    test: $('test-screen'),
    results: $('results-screen'),
};

// ─── Screen Navigation ──────────────────────────────────────────────
function showScreen(name) {
    Object.values(screens).forEach(s => s.classList.remove('active'));
    screens[name].classList.add('active');
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ─── Loading Overlay ─────────────────────────────────────────────────
function setLoading(isLoading, target = null) {
    state.isLoading = isLoading;
    if (target) {
        if (isLoading) {
            target.classList.add('loading');
            target.setAttribute('aria-busy', 'true');
        } else {
            target.classList.remove('loading');
            target.removeAttribute('aria-busy');
        }
    }
}

// ─── Landing Screen Logic ────────────────────────────────────────────
const nameInput = $('student-name');
const startBtn = $('start-btn');
const numQuestionsSelect = $('num-questions');

nameInput.addEventListener('input', () => {
    startBtn.disabled = nameInput.value.trim().length === 0;
});

nameInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !startBtn.disabled) {
        startSession();
    }
});

startBtn.addEventListener('click', startSession);

async function startSession() {
    const name = nameInput.value.trim();
    if (!name) return;

    startBtn.disabled = true;
    startBtn.textContent = 'Starting...';
    setLoading(true, startBtn);

    try {
        const data = await apiRequest('POST', '/sessions', {
            student_name: name,
            max_questions: parseInt(numQuestionsSelect.value),
        });

        state.sessionId = data.session_id;
        state.studentName = name;
        state.totalQuestions = data.max_questions;
        state.correctCount = 0;
        state.questionsAnswered = 0;
        state.abilityHistory = [data.initial_ability];
        state.elapsedSeconds = 0;

        showScreen('test');
        startTimer();
        await loadNextQuestion();
    } catch (err) {
        alert(`Failed to start session: ${err.message}`);
    } finally {
        setLoading(false, startBtn);
        startBtn.disabled = false;
        startBtn.innerHTML = 'Start Assessment <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>';
    }
}

// ─── Timer ───────────────────────────────────────────────────────────
function startTimer() {
    if (state.timerInterval) clearInterval(state.timerInterval);
    state.timerInterval = setInterval(() => {
        state.elapsedSeconds++;
        const mins = Math.floor(state.elapsedSeconds / 60);
        const secs = state.elapsedSeconds % 60;
        $('timer-display').textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
    }, 1000);
}

function stopTimer() {
    if (state.timerInterval) {
        clearInterval(state.timerInterval);
        state.timerInterval = null;
    }
}

// ─── Question Loading ────────────────────────────────────────────────
async function loadNextQuestion() {
    const questionCard = $('question-card');
    questionCard.classList.remove('hidden');
    $('feedback-card').classList.add('hidden');
    state.selectedAnswer = null;

    // Show loading state
    $('question-text').textContent = 'Loading question...';
    $('options-list').innerHTML = '<div class="loading-spinner">Loading...</div>';
    setLoading(true, questionCard);

    try {
        const data = await apiRequest('GET', `/sessions/${state.sessionId}/next-question`);

        if (data.session_complete) {
            await showResults();
            return;
        }

        state.currentQuestion = data.question;
        state.questionStartTime = Date.now();

        renderQuestion(data.question);
        updateProgress(data);
    } catch (err) {
        alert(`Error loading question: ${err.message}`);
    } finally {
        setLoading(false, questionCard);
    }
}

function renderQuestion(q) {
    $('question-text').textContent = q.question_text;
    $('question-counter').textContent = `Question ${q.question_number} of ${q.total_questions}`;
    $('difficulty-display').textContent = q.difficulty.toFixed(2);
    $('topic-display').textContent = q.topic;

    const labels = ['A', 'B', 'C', 'D', 'E'];
    const optionsList = $('options-list');
    optionsList.innerHTML = '';

    q.options.forEach((option, i) => {
        const btn = document.createElement('button');
        btn.className = 'option-btn';
        btn.innerHTML = `
            <span class="option-label">${labels[i]}</span>
            <span class="option-text">${option}</span>
            <span class="option-shortcut">${i + 1}</span>
        `;
        btn.addEventListener('click', () => selectOption(btn, option));
        optionsList.appendChild(btn);
    });

    // Re-animate question card
    const card = $('question-card');
    card.style.animation = 'none';
    card.offsetHeight; // Force reflow
    card.style.animation = 'slideUp 0.3s ease';
}

// ─── Keyboard Navigation ─────────────────────────────────────────────
document.addEventListener('keydown', (e) => {
    // Only handle during test screen and when not loading
    if (!screens.test.classList.contains('active') || state.isLoading) return;

    // Number keys 1-5 to select options
    const num = parseInt(e.key);
    if (num >= 1 && num <= 5 && state.selectedAnswer === null) {
        const buttons = document.querySelectorAll('.option-btn');
        if (num <= buttons.length) {
            const btn = buttons[num - 1];
            const text = btn.querySelector('.option-text').textContent;
            selectOption(btn, text);
        }
        return;
    }

    // Enter or Space to advance to next question when feedback is shown
    if ((e.key === 'Enter' || e.key === ' ') && !$('feedback-card').classList.contains('hidden')) {
        e.preventDefault();
        const nextBtn = $('next-btn');
        if (nextBtn && nextBtn.onclick) nextBtn.onclick();
    }
});

function selectOption(btn, answer) {
    if (state.selectedAnswer !== null || state.isLoading) return;

    state.selectedAnswer = answer;

    // Mark selected
    document.querySelectorAll('.option-btn').forEach(b => b.classList.add('disabled'));
    btn.classList.add('selected');

    // Submit after brief delay
    setTimeout(() => submitAnswer(), 200);
}

// ─── Answer Submission ───────────────────────────────────────────────
async function submitAnswer() {
    const responseTime = Date.now() - state.questionStartTime;
    setLoading(true);

    try {
        const result = await apiRequest('POST', `/sessions/${state.sessionId}/submit-answer`, {
            session_id: state.sessionId,
            question_id: state.currentQuestion.question_id,
            selected_answer: state.selectedAnswer,
            response_time_ms: responseTime,
        });

        state.questionsAnswered = result.question_number;
        state.abilityHistory.push(result.updated_ability);

        if (result.is_correct) state.correctCount++;

        // Show correct/incorrect on options
        document.querySelectorAll('.option-btn').forEach(btn => {
            const text = btn.querySelector('.option-text').textContent;
            if (text === result.correct_answer) {
                btn.classList.add('correct');
            } else if (text === state.selectedAnswer && !result.is_correct) {
                btn.classList.add('incorrect');
            }
        });

        // Update stats
        $('correct-count').textContent = state.correctCount;
        $('ability-display').textContent = result.updated_ability.toFixed(2);

        // Draw chart
        drawAbilityChart('ability-chart', state.abilityHistory);

        // Show feedback
        showFeedback(result);

    } catch (err) {
        alert(`Error submitting answer: ${err.message}`);
    } finally {
        setLoading(false);
    }
}

function showFeedback(result) {
    const feedbackCard = $('feedback-card');
    const feedbackIcon = $('feedback-icon');
    const feedbackText = $('feedback-text');
    const feedbackDetails = $('feedback-details');

    feedbackCard.classList.remove('hidden');

    if (result.is_correct) {
        feedbackIcon.innerHTML = '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9 12l2 2 4-4"/></svg>';
        feedbackText.textContent = 'Correct!';
        feedbackText.className = 'feedback-text correct';
    } else {
        feedbackIcon.innerHTML = '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg>';
        feedbackText.textContent = 'Incorrect';
        feedbackText.className = 'feedback-text incorrect';
    }

    const direction = result.ability_change >= 0 ? '+' : '';
    feedbackDetails.innerHTML = `
        <strong>Correct answer:</strong> ${result.correct_answer}<br>
        <strong>Ability:</strong> ${result.previous_ability.toFixed(3)} &rarr; ${result.updated_ability.toFixed(3)} 
        (${direction}${result.ability_change.toFixed(3)})<br>
        <strong>Topic:</strong> ${result.topic} &bull; <strong>Difficulty:</strong> ${result.difficulty.toFixed(2)}
    `;

    const nextBtn = $('next-btn');
    if (result.session_complete) {
        nextBtn.textContent = 'View Results';
        nextBtn.onclick = showResults;
    } else {
        nextBtn.innerHTML = 'Next Question <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>';
        nextBtn.onclick = loadNextQuestion;
    }

    // Focus next button for keyboard navigation
    nextBtn.focus();
}

function updateProgress(data) {
    const progress = (data.questions_answered / state.totalQuestions) * 100;
    $('progress-bar').style.width = `${progress}%`;
}

// ─── Results ─────────────────────────────────────────────────────────
async function showResults() {
    stopTimer();
    showScreen('results');

    // Show loading state
    $('study-plan-content').innerHTML = '<div class="loading-spinner">Loading your results...</div>';

    try {
        const summary = await apiRequest('GET', `/sessions/${state.sessionId}/summary`);
        renderResults(summary);
    } catch (err) {
        alert(`Error loading results: ${err.message}`);
    }
}

function renderResults(summary) {
    $('results-student-name').textContent = `Results for ${summary.student_name}`;

    // Score circle animation
    const finalScore = summary.final_ability;
    $('final-score').textContent = finalScore.toFixed(2);

    const circumference = 2 * Math.PI * 54; // 339.292
    const offset = circumference * (1 - finalScore);
    const ring = $('score-ring');
    ring.style.setProperty('--target-offset', offset);
    ring.style.transition = 'stroke-dashoffset 1.5s ease';
    setTimeout(() => {
        ring.style.strokeDashoffset = offset;
    }, 100);

    // Stats
    $('result-accuracy').textContent = `${summary.accuracy_percentage.toFixed(0)}%`;
    $('result-correct').textContent = `${summary.total_correct}/${summary.total_questions}`;

    let level = 'Beginner';
    if (finalScore >= 0.65) level = 'Advanced';
    else if (finalScore >= 0.35) level = 'Intermediate';
    $('result-level').textContent = level;

    // Topic cards
    const topicsGrid = $('topics-grid');
    topicsGrid.innerHTML = '';
    for (const [topic, stats] of Object.entries(summary.topics_performance)) {
        const accuracy = stats.total > 0 ? (stats.correct / stats.total * 100) : 0;
        let grade = 'low';
        if (accuracy >= 70) grade = 'high';
        else if (accuracy >= 40) grade = 'medium';

        const card = document.createElement('div');
        card.className = 'topic-card';
        card.innerHTML = `
            <div class="topic-card-header">
                <span class="topic-name">${topic}</span>
                <span class="topic-score ${grade}">${stats.correct}/${stats.total}</span>
            </div>
            <div class="topic-bar-bg">
                <div class="topic-bar-fill ${grade}" style="width: 0%"></div>
            </div>
        `;
        topicsGrid.appendChild(card);

        // Animate bar fill
        setTimeout(() => {
            card.querySelector('.topic-bar-fill').style.width = `${accuracy}%`;
        }, 200);
    }

    // Ability chart
    if (summary.ability_progression && summary.ability_progression.length > 0) {
        // Use requestAnimationFrame to ensure the canvas parent has dimensions
        requestAnimationFrame(() => {
            drawAbilityChart('results-chart', summary.ability_progression, true);
        });
    }

    // Study plan
    renderStudyPlan(summary.study_plan);
}

function renderStudyPlan(plan) {
    const container = $('study-plan-content');

    if (!plan) {
        container.innerHTML = '<p class="plan-assessment">Study plan generation requires an OpenAI API key. Configure it in .env to enable AI-powered recommendations.</p>';
        return;
    }

    let html = '';

    // Overall assessment
    if (plan.overall_assessment) {
        html += `<div class="plan-assessment">${plan.overall_assessment}</div>`;
    }

    // Steps
    if (plan.study_plan && plan.study_plan.length > 0) {
        plan.study_plan.forEach(step => {
            html += `
                <div class="plan-step">
                    <div class="plan-step-header">
                        <div class="plan-step-number">${step.step}</div>
                        <div class="plan-step-title">${step.title}</div>
                    </div>
                    <div class="plan-step-desc">${step.description}</div>
                    <div class="plan-step-meta">
                        ${step.estimated_time ? `<span class="plan-meta-item"><strong>Time:</strong> ${step.estimated_time}</span>` : ''}
                    </div>
                    ${step.focus_topics ? `
                        <div class="plan-tags">
                            ${step.focus_topics.map(t => `<span class="plan-tag">${t}</span>`).join('')}
                        </div>
                    ` : ''}
                    ${step.recommended_resources ? `
                        <div class="plan-step-meta" style="margin-top: 8px;">
                            <span class="plan-meta-item"><strong>Resources:</strong> ${step.recommended_resources.join(', ')}</span>
                        </div>
                    ` : ''}
                </div>
            `;
        });
    }

    // Next test recommendation
    if (plan.next_test_recommendation) {
        html += `<div class="plan-recommendation">${plan.next_test_recommendation}</div>`;
    }

    container.innerHTML = html;
}

// ─── Chart Drawing (Canvas) ─────────────────────────────────────────
function drawAbilityChart(canvasId, data, large = false) {
    const canvas = $(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;

    // Set canvas size properly for high-DPI displays
    const rect = canvas.parentElement.getBoundingClientRect();
    const width = Math.max(rect.width - 40, 200); // min 200px to avoid zero-width
    const height = large ? 220 : 160;

    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.scale(dpr, dpr);

    // Clear
    ctx.clearRect(0, 0, width, height);

    if (data.length < 2) return;

    const padding = { top: 20, right: 20, bottom: 30, left: 45 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    // Y-axis range
    const yMin = 0;
    const yMax = 1;

    // Scale functions
    const xScale = (i) => padding.left + (i / (data.length - 1)) * chartW;
    const yScale = (v) => padding.top + (1 - (v - yMin) / (yMax - yMin)) * chartH;

    // Grid lines
    ctx.strokeStyle = '#334155';
    ctx.lineWidth = 0.5;
    ctx.setLineDash([4, 4]);
    for (let v = 0; v <= 1; v += 0.25) {
        const y = yScale(v);
        ctx.beginPath();
        ctx.moveTo(padding.left, y);
        ctx.lineTo(width - padding.right, y);
        ctx.stroke();
    }
    ctx.setLineDash([]);

    // 0.5 baseline
    ctx.strokeStyle = '#475569';
    ctx.lineWidth = 1;
    ctx.setLineDash([6, 4]);
    ctx.beginPath();
    ctx.moveTo(padding.left, yScale(0.5));
    ctx.lineTo(width - padding.right, yScale(0.5));
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw area fill
    const gradient = ctx.createLinearGradient(0, padding.top, 0, height - padding.bottom);
    gradient.addColorStop(0, 'rgba(99, 102, 241, 0.15)');
    gradient.addColorStop(1, 'rgba(99, 102, 241, 0.02)');

    ctx.beginPath();
    ctx.moveTo(xScale(0), yScale(data[0]));
    for (let i = 1; i < data.length; i++) {
        ctx.lineTo(xScale(i), yScale(data[i]));
    }
    ctx.lineTo(xScale(data.length - 1), height - padding.bottom);
    ctx.lineTo(xScale(0), height - padding.bottom);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Draw line
    ctx.beginPath();
    ctx.moveTo(xScale(0), yScale(data[0]));
    for (let i = 1; i < data.length; i++) {
        ctx.lineTo(xScale(i), yScale(data[i]));
    }
    ctx.strokeStyle = '#6366f1';
    ctx.lineWidth = 2.5;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.stroke();

    // Draw data points
    data.forEach((v, i) => {
        const x = xScale(i);
        const y = yScale(v);

        // Outer glow
        ctx.beginPath();
        ctx.arc(x, y, 5, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(99, 102, 241, 0.3)';
        ctx.fill();

        // Inner dot
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fillStyle = i === data.length - 1 ? '#818cf8' : '#6366f1';
        ctx.fill();
    });

    // Y-axis labels
    ctx.fillStyle = '#64748b';
    ctx.font = '11px Inter, sans-serif';
    ctx.textAlign = 'right';
    for (let v = 0; v <= 1; v += 0.25) {
        ctx.fillText(v.toFixed(2), padding.left - 8, yScale(v) + 4);
    }

    // X-axis labels
    ctx.textAlign = 'center';
    data.forEach((_, i) => {
        if (data.length <= 12 || i % 2 === 0) {
            ctx.fillText(i === 0 ? 'Start' : `Q${i}`, xScale(i), height - 8);
        }
    });
}

// ─── Retake ──────────────────────────────────────────────────────────
$('retake-btn').addEventListener('click', () => {
    // Reset state
    state.sessionId = null;
    state.currentQuestion = null;
    state.selectedAnswer = null;
    state.correctCount = 0;
    state.questionsAnswered = 0;
    state.abilityHistory = [0.5];
    state.elapsedSeconds = 0;

    // Reset UI
    nameInput.value = '';
    startBtn.disabled = true;
    startBtn.innerHTML = 'Start Assessment <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>';
    $('timer-display').textContent = '0:00';
    $('correct-count').textContent = '0';
    $('ability-display').textContent = '0.50';
    $('progress-bar').style.width = '0%';

    showScreen('landing');
    nameInput.focus();
});

// ─── Initial Setup ───────────────────────────────────────────────────
showScreen('landing');
nameInput.focus();
