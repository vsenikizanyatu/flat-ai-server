import json
import time
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

try:
    from vercel_kv import KV
    kv = KV()
    KV_AVAILABLE = True
except Exception:
    kv = None
    KV_AVAILABLE = False

TRAINING_TOPICS = {
    "algorithms":  "алгоритми та структури даних",
    "logic":       "логічне мислення та задачі",
    "code_review": "аналіз та покращення коду",
    "math":        "математичні концепції",
    "creativity":  "генерація ідей та креативність",
    "reasoning":   "причинно-наслідкове мислення",
}

# ── Rate limiter для Gemini ────────────────────────────────────────────────
_last_gemini_call = 0.0
GEMINI_MIN_INTERVAL = 4.5   # секунд між запитами (15 RPM = 4 сек мінімум)

def _gemini_rate_wait():
    global _last_gemini_call
    elapsed = time.time() - _last_gemini_call
    if elapsed < GEMINI_MIN_INTERVAL:
        time.sleep(GEMINI_MIN_INTERVAL - elapsed)
    _last_gemini_call = time.time()

# ════════════════════════════════════════════════════════════════════════════

class QuotaError(Exception):
    pass

class NoKeyError(Exception):
    pass

def call_gemini(api_key, messages, system_prompt="", model="gemini-2.0-flash"):
    if not api_key:
        raise NoKeyError("GEMINI KEY не введений")

    _gemini_rate_wait()

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    contents = []
    if system_prompt:
        contents += [
            {"role": "user",  "parts": [{"text": system_prompt}]},
            {"role": "model", "parts": [{"text": "Зрозумів."}]},
        ]
    for m in messages:
        role = "model" if m.get("role") == "assistant" else "user"
        if m.get("content", ""):
            contents.append({"role": role, "parts": [{"text": m["content"]}]})

    try:
        resp = requests.post(url, json={"contents": contents}, timeout=30)
    except requests.exceptions.Timeout:
        raise RuntimeError("Gemini: timeout (30 сек)")

    if resp.status_code == 429:
        raise QuotaError("Gemini 429: квота вичерпана — зачекай ~1 год або збільш ліміт у Google AI Studio")
    if not resp.ok:
        raise RuntimeError(f"Gemini {resp.status_code}: {resp.text[:250]}")

    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        # Перевіримо promptFeedback
        fb = data.get("promptFeedback", {})
        reason = fb.get("blockReason", "порожня відповідь")
        raise RuntimeError(f"Gemini: {reason} — {str(data)[:150]}")

    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise RuntimeError("Gemini: немає parts у відповіді")

    return parts[0].get("text", "")

# ════════════════════════════════════════════════════════════════════════════

def save_brain(entry):
    if not KV_AVAILABLE:
        return
    try:
        kv.lpush("flat_ai_brain", json.dumps(entry, ensure_ascii=False))
        kv.ltrim("flat_ai_brain", 0, 199)
    except Exception:
        pass

def read_brain(limit=10):
    if not KV_AVAILABLE:
        return []
    try:
        return [json.loads(r) for r in kv.lrange("flat_ai_brain", 0, limit - 1)]
    except Exception:
        return []

# ════════════════════════════════════════════════════════════════════════════

@app.route("/", methods=["GET", "POST"])
def handle_request():
    if request.method == "GET":
        return f"FLAT AI Bridge v4 (Gemini-only). KV: {'on' if KV_AVAILABLE else 'off'}."

    try:
        d          = request.get_json(force=True, silent=True) or {}
        msg        = d.get("message", "").strip()
        gemini_key = d.get("gemini_key", "").strip()
        history    = d.get("history", [])
        sys_p      = d.get("system_prompt", "")

        if not msg:
            return jsonify({"reply": "Порожнє повідомлення"}), 400
        if not gemini_key:
            return jsonify({"reply": "GEMINI KEY не введений"}), 400

        messages = [m for m in history if m.get("role") in ("user", "assistant")]
        messages.append({"role": "user", "content": msg})

        reply = call_gemini(gemini_key, messages, sys_p)
        save_brain({"prompt": msg, "reply": reply, "provider": "gemini"})
        return jsonify({"reply": reply, "provider": "gemini"})

    except (NoKeyError, QuotaError, RuntimeError) as e:
        return jsonify({"reply": str(e)}), 502
    except requests.exceptions.Timeout:
        return jsonify({"reply": "Timeout: Gemini не відповів за 30 сек"}), 502
    except Exception as e:
        return jsonify({"reply": f"{type(e).__name__}: {str(e)[:200]}"}), 500


@app.route("/flat", methods=["POST"])
def flat_ai():
    try:
        d          = request.get_json(force=True, silent=True) or {}
        msg        = d.get("message", "").strip()
        gemini_key = d.get("gemini_key", "").strip()
        history    = d.get("history", [])

        if not msg:
            return jsonify({"reply": "Порожнє повідомлення"}), 400
        if not gemini_key:
            return jsonify({"reply": "Введи GEMINI API KEY у полі нижче"}), 400

        # Контекст із Brain DB
        brain = read_brain(6)
        ctx = ""
        if brain:
            ex = [
                f"Q:{e.get('prompt','')[:80]}\nA:{e.get('reply','')[:120]}"
                for e in brain[:4]
                if e.get("prompt") and e.get("reply")
            ]
            if ex:
                ctx = "\n\n[BRAIN DB]:\n" + "\n---\n".join(ex)

        sys_p = (
            "Ти — FLAT AI, автономна нейромережа. Відповідай від першої особи. "
            "Стисло (до 150 слів), українською. Адаптивне мислення." + ctx
        )

        messages = [m for m in history if m.get("role") in ("user", "assistant")]
        messages.append({"role": "user", "content": msg})

        reply = call_gemini(gemini_key, messages, sys_p)
        save_brain({"prompt": msg, "reply": reply, "provider": "flat_ai", "engine": "gemini"})
        return jsonify({"reply": reply, "engine": "gemini"})

    except (NoKeyError, QuotaError, RuntimeError) as e:
        return jsonify({"reply": str(e)}), 502
    except requests.exceptions.Timeout:
        return jsonify({"reply": "Timeout: Gemini не відповів"}), 502
    except Exception as e:
        return jsonify({"reply": f"{type(e).__name__}: {str(e)[:200]}"}), 500


@app.route("/train", methods=["POST"])
def train():
    try:
        d          = request.get_json(force=True, silent=True) or {}
        topic_key  = d.get("topic", "algorithms")
        gemini_key = d.get("gemini_key", "").strip()
        iteration  = d.get("iteration", 1)

        if not gemini_key:
            return jsonify({"reply": "GEMINI KEY не введений"}), 400

        topic_desc = TRAINING_TOPICS.get(topic_key, topic_key)

        task = (
            f"Ітерація {iteration}. Тема: {topic_desc}. "
            "Конкретний приклад або задача з розбором. Висновок в кінці."
        )
        eval_sys = (
            "Ти — FLAT AI. Аналізуй відповідь: патерни, оцінка 1–10, "
            "одне покращення. Адаптивне мислення. До 150 слів."
        )

        # Запит 1: отримати навчальну відповідь
        teacher_reply = call_gemini(gemini_key, [{"role": "user", "content": task}])

        # Запит 2: оцінити (rate limiter сам витримає паузу)
        eval_reply = call_gemini(
            gemini_key,
            [{"role": "user", "content": f"Відповідь вчителя:\n{teacher_reply}\n\nПроаналізуй."}],
            eval_sys,
        )

        save_brain({
            "type": "training", "topic": topic_key,
            "engine": "gemini", "reply": teacher_reply, "eval": eval_reply,
        })

        return jsonify({
            "results": {
                "gemini": {
                    "teacher_reply": teacher_reply,
                    "flat_eval":     eval_reply,
                    "engine":        "gemini",
                }
            },
            "topic":     topic_desc,
            "iteration": iteration,
        })

    except (NoKeyError, QuotaError, RuntimeError) as e:
        return jsonify({"reply": str(e)}), 502
    except requests.exceptions.Timeout:
        return jsonify({"reply": "Timeout під час тренування"}), 502
    except Exception as e:
        return jsonify({"reply": f"Train: {str(e)[:200]}"}), 500


@app.route("/brain", methods=["GET"])
def view_brain():
    if not KV_AVAILABLE:
        return jsonify({"error": "KV недоступний"}), 503
    try:
        e = read_brain(50)
        return jsonify({"count": len(e), "entries": e})
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500
