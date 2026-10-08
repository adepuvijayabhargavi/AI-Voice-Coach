/* ==========================================
   AI Interview & Communication Coach
   Main JavaScript
   ========================================== */

// ==========================================
// SPEECH RECOGNITION
// ==========================================

let recognition = null;
let isListening = false;
let finalText = "";
let speechStartTime = null;

const SpeechRecognition =
    window.SpeechRecognition ||
    window.webkitSpeechRecognition;

function initSpeechRecognition() {
    const startBtn = document.getElementById("startBtn");
    const status = document.getElementById("status");
    const transcript = document.getElementById("transcript");

    if (!SpeechRecognition) {
        if (status) {
            status.innerText = "Speech recognition is not supported. Please use Google Chrome.";
        }
        if (startBtn) {
            startBtn.disabled = true;
        }
        return null;
    }

    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onstart = function () {
        isListening = true;
        speechStartTime = Date.now();
        if (startBtn) {
            startBtn.innerText = "Stop Speaking";
            startBtn.classList.remove("btn-primary");
            startBtn.classList.add("btn-danger");
        }
        if (status) {
            status.innerText = "Listening... Speak now!";
        }
    };

    recognition.onresult = function (event) {
        let currentText = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const text = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
                finalText += text + " ";
            } else {
                currentText += text;
            }
        }
        if (transcript) {
            transcript.innerText = finalText + currentText;
            transcript.classList.remove("empty");
        }
    };

    recognition.onerror = function (event) {
        console.error("Speech error:", event.error);
        isListening = false;
        if (startBtn) {
            startBtn.innerText = "Start Speaking";
            startBtn.classList.remove("btn-danger");
            startBtn.classList.add("btn-primary");
        }
        if (status) {
            if (event.error === "not-allowed") {
                status.innerText = "Microphone permission denied. Please allow microphone access.";
            } else {
                status.innerText = "Speech error: " + event.error;
            }
        }
    };

    recognition.onend = function () {
        isListening = false;
        if (startBtn) {
            startBtn.innerText = "Start Speaking";
            startBtn.classList.remove("btn-danger");
            startBtn.classList.add("btn-primary");
        }
        if (status) {
            status.innerText = "Recording stopped.";
        }
    };

    return recognition;
}

function toggleSpeech() {
    if (!recognition) {
        alert("Speech recognition is not available. Please use Google Chrome.");
        return;
    }

    if (isListening) {
        recognition.stop();
    } else {
        finalText = "";
        speechStartTime = Date.now();
        const transcript = document.getElementById("transcript");
        if (transcript) {
            transcript.innerText = "Listening...";
            transcript.classList.remove("empty");
        }
        try {
            recognition.start();
        } catch (error) {
            console.error("Speech start error:", error);
        }
    }
}

// ==========================================
// TEXT TO SPEECH (QUESTION VOICE)
// ==========================================

let ttsSupported = ("speechSynthesis" in window);
let ttsSpeakTimer = null;

function stopSpeechTTS() {
    if (ttsSpeakTimer !== null) {
        clearTimeout(ttsSpeakTimer);
        ttsSpeakTimer = null;
    }
    if (!ttsSupported) return;
    window.speechSynthesis.cancel();
}

function speakQuestion(questionText, handlers) {
    console.log("TTS requested:", questionText);
    const text = (questionText === undefined || questionText === null) ? "" : String(questionText).trim();
    const cb = handlers || {};

    if (!text) {
        console.error("TTS ERROR: Question text is empty");
        if (cb.onerror) cb.onerror({ error: "empty" });
        return;
    }
    if (!ttsSupported) {
        console.error("TTS ERROR: Browser does not support speechSynthesis");
        if (cb.onerror) cb.onerror({ error: "unsupported" });
        return;
    }

    // Stop any existing speech so questions never overlap.
    window.speechSynthesis.cancel();
    if (ttsSpeakTimer !== null) clearTimeout(ttsSpeakTimer);
    ttsSpeakTimer = null;

    // Small delay so cancel completes before speaking. Chrome silently drops
    // an utterance when speak() runs in the same tick as cancel().
    ttsSpeakTimer = window.setTimeout(function () {
        ttsSpeakTimer = null;
        try {
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = "en-US";
            utterance.rate = 0.9;
            utterance.pitch = 1;
            utterance.volume = 1;
            utterance.onstart = function () {
                console.log("TTS onstart: question aloud");
                if (cb.onstart) cb.onstart();
            };
            utterance.onend = function () {
                console.log("TTS onend: question finished");
                if (cb.onend) cb.onend();
            };
            utterance.onerror = function (event) {
                console.error("TTS error:", event);
                if (cb.onerror) cb.onerror(event);
            };
            window.speechSynthesis.speak(utterance);
            console.log("speechSynthesis.speaking after speak():", window.speechSynthesis.speaking);
        } catch (err) {
            console.error("TTS exception:", err);
            if (cb.onerror) cb.onerror(err);
        }
    }, 100);
}

window.addEventListener("beforeunload", function () {
    if (ttsSupported && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
    }
});

// ==========================================
// FILLER WORD DETECTION
// ==========================================

function detectFillerWords(text) {
    const fillerPatterns = [
        /\bum+\b/gi,
        /\buh+\b/gi,
        /\blike\b/gi,
        /\bbasically\b/gi,
        /\bactually\b/gi,
        /\byou know\b/gi,
        /\bso\b/gi,
        /\bI mean\b/gi,
        /\bkind of\b/gi,
        /\bsort of\b/gi
    ];

    const fillerWords = {};
    let totalFillers = 0;
    const lowerText = text.toLowerCase();

    fillerPatterns.forEach(function (pattern) {
        const matches = lowerText.match(pattern);
        if (matches) {
            const key = matches[0].trim();
            fillerWords[key] = (fillerWords[key] || 0) + matches.length;
            totalFillers += matches.length;
        }
    });

    const wordCount = text.split(/\s+/).filter(function (w) {
        return w.length > 0;
    }).length;

    return {
        total: totalFillers,
        rate: wordCount > 0 ? ((totalFillers / wordCount) * 100).toFixed(1) : "0.0",
        words: fillerWords,
        wordCount: wordCount
    };
}

// ==========================================
// SPEAKING METRICS
// ==========================================

function calculateSpeakingMetrics(text) {
    const wordCount = text.split(/\s+/).filter(function (w) {
        return w.length > 0;
    }).length;

    let duration = 0;
    if (speechStartTime) {
        duration = Math.round((Date.now() - speechStartTime) / 1000);
    }

    const minutes = duration / 60;
    const wpm = minutes > 0 ? Math.round(wordCount / minutes) : 0;

    return {
        wordCount: wordCount,
        duration: duration,
        durationFormatted: formatDuration(duration),
        wpm: wpm
    };
}

function formatDuration(seconds) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return m + "m " + s + "s";
}

// ==========================================
// ANALYZE ANSWER
// ==========================================

function friendlyApiError(data) {
    if (!data || typeof data !== "object") return "Analysis failed. Please try again.";
    if (data.error_type === "quota") return "Gemini API rate limit reached. Please wait a moment and try again.";
    if (data.error_type === "auth") return "AI API key is invalid or unavailable.";
    if (data.error_type === "config") return "AI service configuration error.";
    return data.error || "Analysis failed. Please try again.";
}

async function analyzeAnswer() {
    const transcript = document.getElementById("transcript");
    const loading = document.getElementById("loading");
    const analyzeBtn = document.getElementById("analyzeBtn");
    const resultDiv = document.getElementById("analysisResult");

    if (!transcript) return;

    const answer = transcript.innerText.trim();

    if (!answer || answer === "Your speech will appear here..." || answer === "Listening...") {
        showAlert("Please provide an answer before submitting.", "warning");
        return;
    }

    if (loading) loading.classList.add("active");
    if (analyzeBtn) analyzeBtn.disabled = true;
    if (resultDiv) resultDiv.innerHTML = "";

    const metrics = calculateSpeakingMetrics(answer);
    const fillerData = detectFillerWords(answer);

    try {
        const question = (typeof getCurrentQuestion === "function") ? getCurrentQuestion() : "";
        const roleEl = document.getElementById("targetRole");
        const response = await fetch("/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                text: answer,
                question: question,
                interview_role: roleEl ? roleEl.value : "",
                word_count: metrics.wordCount,
                duration: metrics.duration,
                wpm: metrics.wpm,
                filler_words: fillerData
            })
        });

        const data = await response.json();

        if (loading) loading.classList.remove("active");
        if (analyzeBtn) analyzeBtn.disabled = false;

        if (!response.ok) {
            showAlert(friendlyApiError(data), "error");
            return;
        }

        data.speaking_metrics = metrics;
        data.filler_data = fillerData;

        displayAnalysis(data);

        if (typeof scores !== "undefined" && typeof currentIndex !== "undefined") {
            scores[currentIndex] = {
                overall: data.overall_score,
                scores: data.scores,
                strengths: data.strengths || [],
                improvements: data.areas_to_improve || data.improvements || [],
                suggestions: data.suggestions || [],
                detailed_analysis: data.detailed_analysis || {},
                corrected_answer: data.corrected_answer || "",
                improved_sample_answer: data.improved_sample_answer || data.better_answer || "",
                ai_feedback: data.ai_feedback || "",
                better_answer: data.better_answer || ""
            };
        }

    } catch (error) {
        console.error("Analysis error:", error);
        if (loading) loading.classList.remove("active");
        if (analyzeBtn) analyzeBtn.disabled = false;
        showAlert("Could not connect to the server. Please try again.", "error");
    }
}

// ==========================================
// DISPLAY ANALYSIS RESULT
// ==========================================

function displayAnalysis(data) {
    const resultDiv = document.getElementById("analysisResult");
    if (!resultDiv) return;

    let html = '<div class="analysis-result">';

    if (data.ai_available === false && (data.feedback_note || data.ai_error)) {
        html += '<div class="alert alert-warning">' + escapeHtml(data.feedback_note || data.ai_error) + '</div>';
    }

    html += '<div class="card">';
    html += '<div class="card-header">AI Evaluation</div>';

    if (data.overall_score !== undefined) {
        html += '<div class="text-center mb-3">';
        html += '<div class="stat-marks" style="font-size:2.5rem;">' + data.overall_score + ' / 100</div>';
        html += '<div class="stat-pct" style="font-size:1.2rem;">' + data.overall_score + '%</div>';
        html += '<div class="text-muted">Overall Score</div>';
        html += '</div>';
    }

    if (data.scores) {
        html += '<div class="score-overview">';
        const labels = {
            communication: "Communication",
            confidence: "Confidence",
            clarity: "Clarity",
            grammar: "Grammar",
            relevance: "Relevance",
            structure: "Structure",
            technical_knowledge: "Technical"
        };
        for (const key in labels) {
            if (data.scores[key] !== undefined) {
                const val = data.scores[key];
                const cls = val >= 80 ? "high" : val >= 60 ? "medium" : "low";
                html += '<div class="score-item">';
                html += '<div class="score-label">' + labels[key] + '</div>';
                html += '<div class="score-marks ' + cls + '">' + val + ' / 100</div>';
                html += '<div class="score-pct">' + val + '%</div>';
                html += '</div>';
            }
        }
        html += '</div>';
    }
    html += '</div>';

    const da = data.detailed_analysis || {};
    if (typeof da === "string") {
        if (da.trim()) {
            html += '<div class="card mt-2">';
            html += '<div class="card-header">Detailed Answer Analysis</div>';
            html += '<div class="card-body" style="padding:0.75rem 1rem;line-height:1.7;">' + escapeHtml(da) + '</div>';
            html += '</div>';
        }
    } else {
        const daParts = [
            ["Summary", da.summary || ""],
            ["Content Analysis", da.content_analysis || ""],
            ["Technical Accuracy", da.technical_accuracy || ""],
            ["Communication Analysis", da.communication_analysis || ""]
        ];
        const hasDa = daParts.some(function (p) { return !!p[1]; });
        if (hasDa) {
            html += '<div class="card mt-2">';
            html += '<div class="card-header">Detailed Answer Analysis</div>';
            html += '<div class="card-body" style="padding:0.75rem 1rem;line-height:1.7;">';
            daParts.forEach(function (p) {
                if (p[1]) {
                    html += '<div style="margin-bottom:0.5rem;"><strong>' + p[0] + ':</strong><span style="white-space:pre-line;"> ' + escapeHtml(p[1]) + '</span></div>';
                }
            });
            html += '</div></div>';
        }
    }

    if (data.strengths && data.strengths.length > 0) {
        html += '<div class="card mt-2">';
        html += '<div class="card-header">Strengths</div>';
        html += '<ul class="strengths-list">';
        data.strengths.forEach(function (s) {
            html += '<li>' + escapeHtml(s) + '</li>';
        });
        html += '</ul></div>';
    }

    const evalAreas = (data.areas_to_improve && data.areas_to_improve.length) ? data.areas_to_improve : (data.improvements || []);
    if (evalAreas.length > 0) {
        html += '<div class="card mt-2">';
        html += '<div class="card-header">Areas to Improve</div>';
        html += '<ul class="improvements-list">';
        evalAreas.forEach(function (s) {
            html += '<li>' + escapeHtml(s) + '</li>';
        });
        html += '</ul></div>';
    }

    if (data.suggestions && data.suggestions.length > 0) {
        html += '<div class="card mt-2">';
        html += '<div class="card-header">Suggestions</div>';
        html += '<ul class="improvements-list">';
        data.suggestions.forEach(function (s) {
            html += '<li>' + escapeHtml(s) + '</li>';
        });
        html += '</ul></div>';
    }

    if (data.corrected_answer) {
        html += '<div class="card mt-2">';
        html += '<div class="card-header">Corrected Answer</div>';
        html += '<div class="better-answer">' + escapeHtml(data.corrected_answer) + '</div>';
        html += '</div>';
    }

    const evalImprovedSample = data.improved_sample_answer || data.better_answer || "";
    if (evalImprovedSample) {
        html += '<div class="card mt-2">';
        html += '<div class="card-header">Improved Sample Answer</div>';
        html += '<div class="better-answer">' + escapeHtml(evalImprovedSample) + '</div>';
        html += '</div>';
    }

    if (data.interview_tip) {
        html += '<div class="card mt-2">';
        html += '<div class="card-header">Interview Tip</div>';
        html += '<div class="interview-tip">' + escapeHtml(data.interview_tip) + '</div>';
        html += '</div>';
    }

    const evalFeedback = data.ai_feedback || data.feedback || "";
    if (evalFeedback) {
        html += '<div class="card mt-2">';
        html += '<div class="card-header">Detailed AI Feedback</div>';
        html += '<div style="white-space:pre-line;line-height:1.7;">' + escapeHtml(evalFeedback) + '</div>';
        html += '</div>';
    }

    if (data.speaking_metrics) {
        html += '<div class="card mt-2">';
        html += '<div class="card-header">Speaking Analysis</div>';
        html += '<div class="filler-stats">';
        html += '<div class="filler-stat"><div class="filler-value">' + data.speaking_metrics.wordCount + '</div><div class="filler-label">Words Spoken</div></div>';
        html += '<div class="filler-stat"><div class="filler-value">' + data.speaking_metrics.durationFormatted + '</div><div class="filler-label">Speaking Time</div></div>';
        html += '<div class="filler-stat"><div class="filler-value">' + data.speaking_metrics.wpm + '</div><div class="filler-label">Words/Min</div></div>';
        html += '</div>';
        if (data.speaking_analysis && (data.speaking_analysis.pace_feedback || data.speaking_analysis.confidence_feedback)) {
            if (data.speaking_analysis.pace_feedback) {
                html += '<div style="margin-top:0.6rem;line-height:1.6;"><strong>Pace:</strong> <span>' + escapeHtml(data.speaking_analysis.pace_feedback) + '</span></div>';
            }
            if (data.speaking_analysis.confidence_feedback) {
                html += '<div style="margin-top:0.4rem;line-height:1.6;"><strong>Confidence:</strong> <span>' + escapeHtml(data.speaking_analysis.confidence_feedback) + '</span></div>';
            }
        }
        html += '</div>';
    }

    if (data.filler_data && data.filler_data.total > 0) {
        html += '<div class="card mt-2">';
        html += '<div class="card-header">Filler Words</div>';
        html += '<div class="filler-stats">';
        html += '<div class="filler-stat"><div class="filler-value">' + data.filler_data.total + '</div><div class="filler-label">Total Fillers</div></div>';
        html += '<div class="filler-stat"><div class="filler-value">' + data.filler_data.rate + '%</div><div class="filler-label">Filler Rate</div></div>';
        html += '</div>';
        html += '<div class="filler-words-list mt-1">';
        for (const word in data.filler_data.words) {
            html += '<span class="filler-tag">"' + escapeHtml(word) + '" - ' + data.filler_data.words[word] + '</span>';
        }
        html += '</div></div>';
    }

    if (data.star_analysis) {
        html += '<div class="card mt-2">';
        html += '<div class="card-header">STAR Analysis</div>';
        html += '<div class="star-grid">';
        const starLabels = { S: "Situation", T: "Task", A: "Action", R: "Result" };
        for (const key in starLabels) {
            const present = data.star_analysis[key.toLowerCase()];
            const cls = present ? "present" : "missing";
            const status = present ? "Present" : "Missing";
            html += '<div class="star-item ' + cls + '">';
            html += '<div class="star-letter">' + key + '</div>';
            html += '<div class="star-label">' + starLabels[key] + '</div>';
            html += '<div class="star-status">' + status + '</div>';
            html += '</div>';
        }
        html += '</div>';
        if (data.star_score !== undefined) {
            html += '<div class="text-center mt-2"><strong>STAR Score: ' + data.star_score + '%</strong></div>';
        }
        html += '</div>';
    }

    html += '</div>';

    resultDiv.innerHTML = html;

    if (typeof saveAnalysisForCurrentQuestion === "function") {
        saveAnalysisForCurrentQuestion(html);
    }
}

// ==========================================
// UTILITY FUNCTIONS
// ==========================================

// ==========================================
// UTILITY FUNCTIONS
// ==========================================

function escapeHtml(text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}

function showAlert(message, type) {
    const existing = document.querySelector(".alert");
    if (existing) existing.remove();

    const alert = document.createElement("div");
    alert.className = "alert alert-" + (type || "info");
    alert.innerText = message;

    const content = document.querySelector(".page-content") || document.querySelector(".container");
    if (content) {
        content.insertBefore(alert, content.firstChild);
    }

    setTimeout(function () {
        alert.remove();
    }, 5000);
}

// ==========================================
// NAVIGATION TOGGLE (MOBILE)
// ==========================================

function toggleNav() {
    const nav = document.querySelector(".navbar-nav");
    if (nav) {
        nav.classList.toggle("open");
    }
}

// ==========================================
// INITIALIZATION
// ==========================================

document.addEventListener("DOMContentLoaded", function () {
    initSpeechRecognition();
});
