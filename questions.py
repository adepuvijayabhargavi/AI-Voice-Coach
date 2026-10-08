# ==========================================
# Dynamic Interview Question Generation
# Questions are generated on the fly with the OpenAI API, based on the
# selected skill/category, difficulty, job role, experience level and any
# previously asked questions. A SMALL local fallback bank is kept so the
# app still works when the API is temporarily unavailable.
#
# The OpenAI API key is read from .env (OPENAI_API_KEY) and lives only on
# the server — it is never sent to the frontend.
# ==========================================

import json
import os
import random
import re
import time

from dotenv import load_dotenv

load_dotenv()

# ----------------------------------------------------------
# OpenAI configuration (server-side only)
# ----------------------------------------------------------

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
OPENAI_TIMEOUT = 60

try:
    import openai
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False
    openai = None


class QuestionAPIError(Exception):
    """Raised when OpenAI question generation fails.

    `category` is one of: "quota", "auth", "config", "network", "server".
    """
    def __init__(self, message, category="server"):
        super().__init__(message)
        self.category = category


# ----------------------------------------------------------
# Job roles (used by the UI dropdowns and the prompts)
# ----------------------------------------------------------

ROLES = [
    {"value": "python_developer", "label": "Python Developer"},
    {"value": "full_stack_developer", "label": "Full Stack Developer"},
    {"value": "frontend_developer", "label": "Frontend Developer"},
    {"value": "backend_developer", "label": "Backend Developer"},
    {"value": "data_analyst", "label": "Data Analyst"},
    {"value": "ml_engineer", "label": "Machine Learning Engineer"},
    {"value": "ai_ml_engineer", "label": "AI/ML Engineer"},
    {"value": "software_developer", "label": "Software Developer"}
]

ROLE_DESCRIPTIONS = {
    "python_developer": "Python Developer with expertise in Django, Flask, data structures, algorithms, and Python ecosystem",
    "full_stack_developer": "Full Stack Developer proficient in both frontend and backend technologies",
    "frontend_developer": "Frontend Developer specializing in HTML, CSS, JavaScript, React, and UI/UX",
    "backend_developer": "Backend Developer focused on APIs, databases, server architecture, and system design",
    "data_analyst": "Data Analyst skilled in SQL, data visualization, statistics, and business intelligence",
    "ml_engineer": "Machine Learning Engineer with expertise in ML models, data pipelines, and model deployment",
    "ai_ml_engineer": "AI/ML Engineer working on deep learning, NLP, computer vision, and AI systems",
    "software_developer": "Software Developer with general software engineering skills"
}


# ----------------------------------------------------------
# Small local fallback bank (used only if the API is unavailable)
# ----------------------------------------------------------

FALLBACK_QUESTION_BANK = {
    "hr": {
        "beginner": [
            "Tell me about yourself and your background.",
            "What are your greatest strengths and weaknesses?",
            "Why should we hire you for this role?"
        ],
        "intermediate": [
            "Describe a time you disagreed with a supervisor and how you handled it.",
            "How do you manage competing deadlines in a fast-paced environment?",
            "Tell me about a time you showed initiative at work."
        ],
        "advanced": [
            "Describe a time you drove organizational change.",
            "How do you build and lead high-performing teams?",
            "How do you align your team's goals with company objectives?"
        ]
    },
    "technical": {
        "beginner": [
            "Explain the difference between a stack and a queue.",
            "What is the time complexity of binary search?",
            "What is an API and how does it work?"
        ],
        "intermediate": [
            "Explain the SOLID principles.",
            "How would you design a URL shortener?",
            "What is the difference between SQL and NoSQL databases?"
        ],
        "advanced": [
            "How would you design a distributed system?",
            "Explain eventual consistency vs strong consistency.",
            "What are the trade-offs of different caching strategies?"
        ]
    },
    "behavioral": {
        "beginner": [
            "Tell me about a time you worked under pressure.",
            "Describe a situation where you had a conflict with a teammate.",
            "Tell me about a project you are proud of."
        ],
        "intermediate": [
            "Describe a time you had to manage competing priorities.",
            "Tell me about a time you gave difficult feedback to a colleague.",
            "How do you handle working with difficult people?"
        ],
        "advanced": [
            "Describe a time you led a team through a major transformation.",
            "Tell me about a time you had to make a high-stakes decision.",
            "How do you approach building a culture of accountability?"
        ]
    },
    "communication": {
        "beginner": [
            "Explain a technical concept to a non-technical person.",
            "How do you ensure clear communication within a team?",
            "Tell me about a time you presented to a group."
        ],
        "intermediate": [
            "How do you tailor your communication for different stakeholders?",
            "Describe a time you had to communicate a complex project status.",
            "Tell me about a time you presented to senior leadership."
        ],
        "advanced": [
            "How do you build a culture of open communication?",
            "Describe how you would communicate a major organizational change to a large team.",
            "Tell me about a time you had to build consensus through communication."
        ]
    },
    "general": {
        "beginner": [
            "Tell me about yourself.",
            "What are your career goals?",
            "How do you handle stress?"
        ],
        "intermediate": [
            "Tell me about your professional journey.",
            "Describe a time you exceeded expectations.",
            "How do you approach problem-solving?"
        ],
        "advanced": [
            "How do you drive innovation in your work?",
            "Describe a time you had to lead through uncertainty.",
            "How do you approach strategic planning?"
        ]
    }
}

FALLBACK_NEXT_QUESTIONS = [
    "Can you elaborate on the key points you just mentioned?",
    "Describe a specific example that illustrates what you explained.",
    "How would you approach this same situation differently with more resources?",
    "Can you walk me through the steps you would take to solve this?",
    "What was the most challenging part of what you described, and how did you handle it?",
    "Can you give me another example where you applied a similar approach?"
]


# ----------------------------------------------------------
# Small helpers
# ----------------------------------------------------------

DIFFICULTY_LABELS = {
    "easy": "Beginner",
    "beginner": "Beginner",
    "medium": "Intermediate",
    "intermediate": "Intermediate",
    "hard": "Advanced",
    "advanced": "Advanced",
}

INTERVIEW_TYPE_LABELS = {
    "hr": "HR / cultural fit interview",
    "technical": "technical interview",
    "behavioral": "behavioral (STAR method) interview",
    "communication": "communication skills interview",
    "general": "general interview",
    "mixed": "general interview",
}


def _normalize_type(interview_type):
    key = (interview_type or "general").strip().lower()
    return key if key in INTERVIEW_TYPE_LABELS else "general"


def _normalize_difficulty(difficulty):
    key = (difficulty or "beginner").strip().lower()
    if key in DIFFICULTY_LABELS:
        return DIFFICULTY_LABELS[key]
    return key.capitalize()


def _role_description(role):
    if not role:
        return "General / unspecified role"
    if role in ROLE_DESCRIPTIONS:
        return ROLE_DESCRIPTIONS[role]
    return str(role).replace("_", " ").title()


def _mask_secrets(text):
    """Never log the API key. Masks anything that looks like an OpenAI key."""
    return re.sub(r"sk-[A-Za-z0-9_-]{8,}", "sk-***", str(text))


def _log_question_event(feature, ok, detail=""):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(
        f"AI REQUEST: feature={feature} provider=openai time={ts} "
        f"success={'yes' if ok else 'no'}"
        f"{(' detail=' + _mask_secrets(detail)[:160]) if detail else ''}"
    )


# ----------------------------------------------------------
# Large-batch generation settings
# VERY large selections (50/100) are split into several smaller API
# requests instead of one giant prompt that could hit token limits.
# ----------------------------------------------------------

MAX_TOTAL_QUESTIONS = 200     # hard validation cap for any request
BATCH_SIZE = 20               # questions requested per single OpenAI call
MAX_BATCH_ATTEMPTS = 8        # extra top-up calls allowed to fill shortfalls


def _fallback_questions(interview_type, difficulty, count):
    count = max(1, min(int(count), MAX_TOTAL_QUESTIONS))
    interview_type = _normalize_type(interview_type)
    bank = FALLBACK_QUESTION_BANK

    pool = []
    seen = set()

    def add_type(type_key):
        for diff in ("beginner", "intermediate", "advanced"):
            for q in bank.get(type_key, {}).get(diff, []):
                if q not in seen:
                    seen.add(q)
                    pool.append(q)

    # Prefer the requested category, then general, then everything else.
    add_type(interview_type)
    if interview_type != "general":
        add_type("general")
    for other in bank:
        if other != interview_type and other != "general":
            add_type(other)

    if len(pool) >= count:
        return random.sample(pool, count)
    # Very large counts: pad with generic follow-ups (still no exact duplicates).
    result = list(pool)
    pad = [q for q in FALLBACK_NEXT_QUESTIONS if q not in seen]
    i = 0
    while len(result) < count and pad:
        result.append(pad[i % len(pad)])
        i += 1
    return result[:count]


def _fallback_next_question(interview_type, difficulty, role=None, history=None):
    if role and role in ROLE_DESCRIPTIONS:
        return f"As a {ROLE_DESCRIPTIONS[role].split(' with ')[0]}, tell me about a recent challenge you overcame and what you learned."
    if history:
        return "Can you tell me more about the example you just gave?"
    return random.choice(FALLBACK_NEXT_QUESTIONS)


# ----------------------------------------------------------
# OpenAI client (created lazily; key never leaves the server)
# ----------------------------------------------------------

_openai_client = None


def _get_openai_client():
    global _openai_client
    if not OPENAI_API_KEY:
        raise QuestionAPIError(
            "AI service is not configured. Add OPENAI_API_KEY to your .env file.",
            category="config",
        )
    if not _OPENAI_AVAILABLE:
        raise QuestionAPIError(
            "The 'openai' package is not installed. Run: pip install openai",
            category="config",
        )
    if _openai_client is None:
        _openai_client = openai.OpenAI(api_key=OPENAI_API_KEY, timeout=OPENAI_TIMEOUT)
    return _openai_client


def _error_category(e, msg):
    """Map an OpenAI SDK exception to a user-friendly error category."""
    etype = type(e).__name__
    low = str(msg).lower()
    if etype == "RateLimitError" or "rate limit" in low or "quota" in low:
        return "quota"
    if etype in ("AuthenticationError", "PermissionDeniedError") or "api key" in low:
        return "auth"
    if etype == "NotFoundError" or "model" in low:
        return "config"
    if etype in ("APIConnectionError", "APITimeoutError") or "connection" in low or "timed out" in low:
        return "network"
    if etype == "InternalServerError":
        return "server"
    return "server"


def _extract_json(raw):
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    return text


def _chat_json(system_prompt, user_prompt):
    """Call OpenAI chat completions and return parsed JSON. Raises QuestionAPIError."""
    client = _get_openai_client()
    max_attempts = 3
    last_error = None
    last_category = "server"

    for attempt in range(1, max_attempts + 1):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
            )
            content = response.choices[0].message.content or ""
            parsed = json.loads(_extract_json(content))
            _log_question_event("openai_chat", True, detail="ok")
            return parsed
        except QuestionAPIError:
            raise
        except json.JSONDecodeError as e:
            _log_question_event("openai_chat", False, detail=f"invalid json (attempt {attempt})")
            last_error = e
            last_category = "server"
            # Retrying rarely fixes malformed JSON, but a fresh call may differ.
            if attempt < max_attempts:
                time.sleep(1)
                continue
            raise QuestionAPIError(
                "OpenAI returned an unparseable response. Please try again.", category="server"
            ) from e
        except Exception as e:
            msg = _mask_secrets(str(e))
            category = _error_category(e, msg)
            _log_question_event("openai_chat", False, detail=f"{category} (attempt {attempt}) {msg[:120]}")
            last_error = e
            last_category = category
            # Transient errors (network / 5xx) get a couple of retries; others surface immediately.
            transient = category in ("network", "server")
            if transient and attempt < max_attempts:
                time.sleep(2 ** (attempt - 1))
                continue
            if category == "quota":
                raise QuestionAPIError(
                    "OpenAI API rate limit reached. Please check your API usage or try again later.",
                    category="quota",
                ) from e
            if category == "auth":
                raise QuestionAPIError(
                    "OpenAI API key is invalid or unavailable. Check OPENAI_API_KEY in .env.",
                    category="auth",
                ) from e
            if category == "config":
                raise QuestionAPIError(
                    f"OpenAI model '{OPENAI_MODEL}' is not available for this API account.",
                    category="config",
                ) from e
            if category == "network":
                raise QuestionAPIError(
                    "AI service connection was interrupted. Please try again in a moment.",
                    category="network",
                ) from e
            raise QuestionAPIError(
                "AI question generation failed. Please try again later.",
                category="server",
            ) from e

    raise QuestionAPIError(
        f"AI question generation failed after retries: {_mask_secrets(str(last_error))[:200]}",
        category=last_category,
    )


# ----------------------------------------------------------
# Public generation API (OpenAI-first, local fallback)
# ----------------------------------------------------------

_GEN_SYSTEM_PROMPT = (
    "You are an expert technical interviewer and hiring coach who writes realistic "
    "interview questions. You return ONLY a valid JSON array of question strings — "
    "never any explanations, hints, answers, or extra text."
)


def generate_questions_ai(
    interview_type,
    difficulty="beginner",
    count=10,
    role=None,
    experience=None,
    previous_questions=None,
):
    """Generate `count` unique interview questions via the OpenAI API.

    Large counts (e.g. 50 or 100) are generated in smaller batches
    (BATCH_SIZE per request) so no single API call becomes huge. Batches are
    combined and de-duplicated; if the API returns fewer questions than asked
    for, extra follow-up calls fill the remaining gap up to a retry limit.

    Raises QuestionAPIError on total failure. Callers fall back to the local bank.
    """
    count = max(1, min(int(count), MAX_TOTAL_QUESTIONS))
    type_key = _normalize_type(interview_type)
    type_label = INTERVIEW_TYPE_LABELS[type_key]
    skill_name = type_label.split(" (")[0]
    role_desc = _role_description(role)
    experience_label = (experience or "Any").replace("_", " ")
    diff_label = _normalize_difficulty(difficulty)

    # Previously asked questions are ONLY used as context (to avoid repeats);
    # they are never returned as part of the generated set.
    previous = []
    seen_lower = set()
    for q in previous_questions or []:
        text = q.get("question", "") if isinstance(q, dict) else str(q)
        text = text.strip()
        if text and text.lower() not in seen_lower:
            seen_lower.add(text.lower())
            previous.append(text)

    generated = []

    def add_questions(questions):
        added = 0
        for q in questions:
            if isinstance(q, str):
                clean = q.strip()
                key = clean.lower()
                if clean and len(clean) > 5 and key not in seen_lower:
                    seen_lower.add(key)
                    generated.append(clean)
                    added += 1
        return added

    total_calls = 0
    max_calls = (count + BATCH_SIZE - 1) // BATCH_SIZE + MAX_BATCH_ATTEMPTS

    while len(generated) < count and total_calls < max_calls:
        total_calls += 1
        want = min(BATCH_SIZE, count - len(generated))
        if want <= 0:
            break

        context_pool = previous + generated[-20:]
        if context_pool:
            previous_context = (
                "Questions already generated/asked (do NOT repeat or paraphrase ANY of them):\n"
                + "\n".join(f"- {q}" for q in context_pool)
                + "\n"
            )
        else:
            previous_context = ""

        user_prompt = f"""Generate exactly {want} unique interview questions.

Interview category: {type_label}
Difficulty: {diff_label}
Target job role: {role_desc}
Candidate experience: {experience_label}
{previous_context}
Requirements:
- Each question must genuinely test the candidate's {skill_name} ability for a {role_desc} at the {diff_label} difficulty level.
- Questions must be unique, specific, realistic and thought-provoking (no generic filler).
- Vary the wording; never repeat or paraphrase any question listed above.
- Do NOT include hints, answers, explanations or conversation.
- The entire response must be ONLY a JSON array of exactly {want} question strings, e.g.
["Question 1", "Question 2", "Question 3"]"""

        try:
            parsed = _chat_json(_GEN_SYSTEM_PROMPT, user_prompt)
        except QuestionAPIError:
            if generated:
                break        # keep whatever unique questions we already collected
            raise

        if not isinstance(parsed, list):
            if generated:
                break
            raise QuestionAPIError("OpenAI returned an invalid response format.", category="server")

        add_questions(parsed)

    if not generated:
        raise QuestionAPIError("OpenAI returned no usable questions.", category="server")
    return generated[:count]


def generate_next_question_ai(
    interview_type,
    difficulty="beginner",
    role=None,
    experience=None,
    history=None,
):
    """Generate a single follow-up question via the OpenAI API.

    Raises QuestionAPIError on failure.
    """
    type_key = _normalize_type(interview_type)
    type_label = INTERVIEW_TYPE_LABELS[type_key]
    skill_name = type_label.split(" (")[0]
    role_desc = _role_description(role)
    experience_label = (experience or "Any").replace("_", " ")
    diff_label = _normalize_difficulty(difficulty)

    history_text = ""
    if history:
        parts = []
        for item in history[-6:]:
            if isinstance(item, dict):
                q = (item.get("question") or "").strip()
                if not q:
                    continue
                a = (item.get("answer") or "").strip()
                score = item.get("score")
                parts.append(f"Q: {q}")
                if a:
                    parts.append(f"A: {a}" + (f" (score: {score}/100)" if score is not None else ""))
            else:
                q = str(item).strip()
                if q:
                    parts.append(f"Q: {q}")
        history_text = "\n".join(parts)

    conversation_block = (
        f"Conversation so far:\n{history_text}\n\n" if history_text else "This is the first question.\n\n"
    )

    user_prompt = f"""You are an interviewer conducting a {type_label}.

Target job role: {role_desc}
Candidate experience: {experience_label}
Difficulty: {diff_label}

{conversation_block}Generate exactly 1 follow-up interview question that:
- Tests the candidate's {skill_name} ability for a {role_desc} at the {diff_label} difficulty level.
- Builds naturally on the conversation above (if any).
- Does NOT repeat any question already asked.
- Is specific and requires a thoughtful answer.

Return ONLY a JSON object with a single "question" field:
{{"question": "Your question here"}}"""

    parsed = _chat_json(_GEN_SYSTEM_PROMPT, user_prompt)
    if isinstance(parsed, dict):
        question = parsed.get("question")
        if isinstance(question, str) and question.strip() and len(question.strip()) > 5:
            return question.strip()
    raise QuestionAPIError("OpenAI returned no valid question.", category="server")


def generate_resume_questions_ai(
    resume_data,
    role,
    experience,
    interview_type,
    difficulty,
    count,
):
    """Generate personalized questions grounded in the candidate's resume via OpenAI.

    Raises QuestionAPIError on failure.
    """
    count = max(1, min(int(count), 50))
    skills = ", ".join(resume_data.get("skills", [])[:10]) or "Not listed"
    langs = ", ".join(resume_data.get("programming_languages", [])[:5]) or "Not listed"
    frameworks = ", ".join(resume_data.get("frameworks", [])[:5]) or "Not listed"
    projects = "\n".join([
        f"- {p.get('name', 'Unknown')}: {p.get('description', '')[:100]} (Technologies: {', '.join(p.get('technologies', []))})"
        for p in resume_data.get("projects", [])[:5]
    ]) or "None listed"
    experience_text = "\n".join([
        f"- {e.get('title', '')} at {e.get('company', '')} ({e.get('duration', '')})"
        for e in resume_data.get("experience", [])[:3]
    ]) or "None listed - Fresher"
    education = ", ".join([
        f"{e.get('degree', '')} from {e.get('institution', '')}"
        for e in resume_data.get("education", [])[:3]
    ]) or "Not listed"

    type_key = _normalize_type(interview_type)
    type_label = INTERVIEW_TYPE_LABELS[type_key]
    diff_label = _normalize_difficulty(difficulty)
    experience_label = (experience or "Any").replace("_", " ")

    user_prompt = f"""Generate exactly {count} personalized interview questions based on this candidate's resume.

Candidate Resume Information:
Skills: {skills}
Programming Languages: {langs}
Frameworks: {frameworks}
Projects:
{projects}
Experience:
{experience_text}
Education: {education}

Interview Configuration:
- Target Role: {role}
- Experience Level: {experience_label}
- Interview Type: {type_label}
- Difficulty: {diff_label}

Requirements:
- Questions MUST reference specific skills, projects, or technologies from the resume.
- For projects, ask about architecture, challenges, technologies used, and improvements.
- For skills, ask about practical application and depth of knowledge.
- Include a mix of technical, behavioral, and project-specific questions.
- Questions should be unique and progressively increase in difficulty.
- Do NOT include hints, answers, explanations or conversation.
- Return ONLY a JSON array of exactly {count} question strings, e.g.
["Question 1", "Question 2", "Question 3"]"""

    parsed = _chat_json(_GEN_SYSTEM_PROMPT, user_prompt)
    if not isinstance(parsed, list):
        raise QuestionAPIError("OpenAI returned an invalid response format.", category="server")

    questions = []
    dedup = set()
    for item in parsed:
        if isinstance(item, str):
            clean = item.strip()
            key = clean.lower()
            if clean and len(clean) > 5 and key not in dedup:
                dedup.add(key)
                questions.append(clean)
    if not questions:
        raise QuestionAPIError("OpenAI returned no usable questions.", category="server")
    return questions[:count]


# ----------------------------------------------------------
# Convenience wrappers used by the Flask routes.
# These NEVER raise: they fall back to the local bank so the
# app keeps working (requirement: no crashes, friendly errors).
# ----------------------------------------------------------

def generate_questions_batch(
    interview_type,
    difficulty="beginner",
    count=10,
    role=None,
    experience=None,
    previous_questions=None,
):
    """AI-first batch generation with a local fallback.

    Returns {"questions": [...], "source": "ai"|"fallback", "warning": str|None}.
    """
    fallback = {
        "questions": _fallback_questions(interview_type, difficulty, count),
        "source": "fallback",
        "warning": "AI question generation is temporarily unavailable. Showing saved questions instead.",
    }
    if not OPENAI_API_KEY:
        return fallback
    try:
        questions = generate_questions_ai(
            interview_type, difficulty, count,
            role=role, experience=experience, previous_questions=previous_questions,
        )
        return {"questions": questions, "source": "ai", "warning": None}
    except QuestionAPIError as e:
        _log_question_event("question_batch", False, detail=str(e))
        fallback["warning"] = str(e)
        return fallback
    except Exception as e:
        _log_question_event("question_batch", False, detail=str(e))
        return fallback


def next_question_batch(
    interview_type,
    difficulty="beginner",
    role=None,
    experience=None,
    history=None,
):
    """AI-first single follow-up question generation with a local fallback.

    Returns {"question": str, "source": "ai"|"fallback", "warning": str|None}.
    """
    fallback = {
        "question": _fallback_next_question(interview_type, difficulty, role, history),
        "source": "fallback",
        "warning": "AI question generation is temporarily unavailable. Showing a saved follow-up question instead.",
    }
    if not OPENAI_API_KEY:
        return fallback
    try:
        question = generate_next_question_ai(
            interview_type, difficulty, role=role, experience=experience, history=history,
        )
        return {"question": question, "source": "ai", "warning": None}
    except QuestionAPIError as e:
        _log_question_event("next_question", False, detail=str(e))
        fallback["warning"] = str(e)
        return fallback
    except Exception as e:
        _log_question_event("next_question", False, detail=str(e))
        return fallback


# Backward-compatible helper: the old get_questions(interview_type,
# difficulty, count) signature still works (now AI-first with fallback).
def get_questions(
    interview_type,
    difficulty="beginner",
    count=10,
    role=None,
    experience=None,
    previous_questions=None,
):
    result = generate_questions_batch(
        interview_type, difficulty, count,
        role=role, experience=experience, previous_questions=previous_questions,
    )
    return result["questions"]