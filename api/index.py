import json
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

# ════════════════════════════════════════════════════════════════════════════
# ПРОВАЙДЕРИ
# ════════════════════════════════════════════════════════════════════════════

class QuotaError(Exception):
    """429 від провайдера — потрібен fallback."""
    pass

def call_gemini(api_key: str, messages: list, system_prompt: str = "") -> str:
    if not api_key:
        raise ValueError("Gemini API key порожній")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={api_key}"
    )
    contents = []
    if system_prompt:
        contents.append({"role": "user",  "parts": [{"text": system_prompt}]})
        contents.append({"role": "model", "parts": [{"text": "Зрозумів."}]})
    for m in messages:
        role = "model" if m.get("role") == "assistant" else "user"
        text = m.get("content", "")
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})

    resp = requests.post(url, json={"contents": contents}, timeout=25)

    if resp.status_code == 429:
        raise QuotaError("Gemini: квота вичерпана (429). Перемикаюсь на Claude...")
    if not resp.ok:
        raise RuntimeError(f"Gemini HTTP {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    if "candidates" not in data or not data["candidates"]:
        raise RuntimeError(f"Gemini: порожня відповідь. Raw: {str(data)[:200]}")
    return data["candidates"][0]["content"]["parts"][0]["text"]


def call_claude(api_key: str, messages: list, system_prompt: str = "") -> str:
    if not api_key:
        raise ValueError("Claude API key порожній")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    filtered = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m.get("role") in ("user", "assistant") and m.get("content", "").strip()
    ]
    if not filtered or filtered[0]["role"] != "user":
        filtered.insert(0, {"role": "user", "content": "Привіт"})

    payload = {"model": "claude-opus-4-5", "max_tokens": 1024, "messages": filtered}
    if system_prompt:
        payload["system"] = system_prompt

    resp = requests.post("https://api.anthropic.com/v1/messages",
                         headers=headers, json=payload, timeout=25)

    if resp.status_code == 429:
        raise QuotaError("Claude: квота вичерпана (429).")
    if not resp.ok:
        raise RuntimeError(f"Claude HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()["content"][0]["text"]


def call_with_fallback(provider: str, gemini_key: str, claude_key: str,
                       messages: list, system_prompt: str = "") -> tuple[str, str]:
    """
    Викликає провайдера. Якщо 429 — автоматично перемикається на інший.
    Повертає (reply, actual_provider).
    """
    primary   = provider
    secondary = "claude" if provider == "gemini" else "gemini"

    try:
        if primary == "gemini":
            return call_gemini(gemini_key, messages, system_prompt), "gemini"
        else:
            return call_claude(claude_key, messages, system_prompt), "claude"

    except QuotaError as qe:
        # Fallback на інший провайдер
        fallback_note = str(qe)
        try:
            if secondary == "claude":
                reply = call_claude(claude_key, messages, system_prompt)
            else:
                reply = call_gemini(gemini_key, messages, system_prompt)
            # Додаємо примітку про переключення
            return f"[⚡ Fallback на {secondary.upper()}]\n{reply}", secondary
        except Exception as e2:
            raise RuntimeError(f"{fallback_note} | {secondary} також недоступний: {str(e2)[:150]}")


def save_to_brain(entry: dict):
    if not KV_AVAILABLE:
        return
    try:
        kv.lpush("flat_ai_brain", json.dumps(entry, ensure_ascii=False))
        kv.ltrim("flat_ai_brain", 0, 199)
    except Exception:
        pass


def read_brain(limit: int = 10) -> list:
    if not KV_AVAILABLE:
        return []
    try:
        raw = kv.lrange("flat_ai_brain", 0, limit - 1)
        return [json.loads(r) for r in raw]
    except Exception:
        return []


# ════════════════════════════════════════════════════════════════════════════
# МАРШРУТИ
# ════════════════════════════════════════════════════════════════════════════

@app.route("/", methods=["GET", "POST"])
def handle_request():
    if request.method == "GET":
        return f"FLAT AI Bridge: Active. KV: {'on' if KV_AVAILABLE else 'off'}."

    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"reply": "Не отримано JSON"}), 400

        user_msg      = data.get("message", "").strip()
        provider      = data.get("provider", "gemini").lower()
        gemini_key    = data.get("gemini_key", "").strip()
        claude_key    = data.get("claude_key", "").strip()
        history       = data.get("history", [])
        system_prompt = data.get("system_prompt", "")

        if not user_msg:
            return jsonify({"reply": "Порожнє повідомлення"}), 400

        messages = [m for m in history if m.get("role") in ("user", "assistant")]
        messages.append({"role": "user", "content": user_msg})

        if provider not in ("gemini", "claude"):
            return jsonify({"reply": f"Невідомий провайдер: {provider}"}), 400

        reply, actual = call_with_fallback(provider, gemini_key, claude_key, messages, system_prompt)

        save_to_brain({"prompt": user_msg, "reply": reply,
                       "provider": actual, "requested": provider})
        return jsonify({"reply": reply, "provider": actual})

    except ValueError as e:
        return jsonify({"reply": f"Конфіг: {str(e)}"}), 400
    except RuntimeError as e:
        return jsonify({"reply": str(e)}), 502
    except requests.exceptions.Timeout:
        return jsonify({"reply": "Timeout: провайдер не відповів за 25 сек"}), 502
    except Exception as e:
        return jsonify({"reply": f"{type(e).__name__}: {str(e)[:200]}"}), 500


@app.route("/flat", methods=["POST"])
def flat_ai():
    try:
        data       = request.get_json(force=True, silent=True) or {}
        user_msg   = data.get("message", "").strip()
        gemini_key = data.get("gemini_key", "").strip()
        claude_key = data.get("claude_key", "").strip()
        history    = data.get("history", [])

        if not user_msg:
            return jsonify({"reply": "Порожнє повідомлення"}), 400

        brain_entries = read_brain(limit=8)
        brain_context = ""
        if brain_entries:
            examples = []
            for e in brain_entries[:5]:
                p = e.get("prompt", "")[:100]
                r = e.get("reply",  "")[:150]
                if p and r:
                    examples.append(f"Q: {p}\nA: {r}")
            if examples:
                brain_context = (
                    "\n\n[ЗНАННЯ З BRAIN DB]:\n" + "\n---\n".join(examples)
                )

        flat_system = (
            "Ти — FLAT AI, автономна нейронна мережа. "
            "Твої риси: аналітичність, стислість, адаптивне мислення. "
            "Відповідай від першої особи як FLAT AI, українською, до 150 слів."
            + brain_context
        )

        messages = [m for m in history if m.get("role") in ("user", "assistant")]
        messages.append({"role": "user", "content": user_msg})

        # Пріоритет: Claude > Gemini (Claude стабільніший)
        if claude_key:
            primary = "claude"
        elif gemini_key:
            primary = "gemini"
        else:
            return jsonify({"reply": "Немає жодного API ключа."}), 400

        reply, actual = call_with_fallback(primary, gemini_key, claude_key, messages, flat_system)

        save_to_brain({"prompt": user_msg, "reply": reply, "provider": "flat_ai", "engine": actual})
        return jsonify({"reply": reply, "engine": actual})

    except ValueError as e:
        return jsonify({"reply": f"Конфіг: {str(e)}"}), 400
    except RuntimeError as e:
        return jsonify({"reply": str(e)}), 502
    except Exception as e:
        return jsonify({"reply": f"{type(e).__name__}: {str(e)[:200]}"}), 500


@app.route("/train", methods=["POST"])
def train():
    try:
        data       = request.get_json(force=True, silent=True) or {}
        teacher    = data.get("teacher", "gemini").lower()
        topic_key  = data.get("topic", "algorithms")
        gemini_key = data.get("gemini_key", "").strip()
        claude_key = data.get("claude_key", "").strip()
        iteration  = data.get("iteration", 1)

        topic_desc  = TRAINING_TOPICS.get(topic_key, topic_key)
        task_prompt = (
            f"Ітерація {iteration}. Тема: {topic_desc}. "
            "Дай конкретний приклад або задачу з розбором. Висновок в кінці."
        )
        eval_system = (
            "Ти — FLAT AI. Аналізуй відповідь вчителя: ключові патерни, "
            "оцінка 1–10, одне покращення. Адаптивне мислення. До 150 слів."
        )

        results = {}

        teachers = ["gemini", "claude"] if teacher == "both" else [teacher]

        for t in teachers:
            try:
                task_reply, used = call_with_fallback(
                    t, gemini_key, claude_key,
                    [{"role": "user", "content": task_prompt}])

                eval_reply, _ = call_with_fallback(
                    t, gemini_key, claude_key,
                    [{"role": "user",
                      "content": f"Відповідь вчителя:\n{task_reply}\n\nПроаналізуй."}],
                    eval_system)

                results[t] = {"teacher_reply": task_reply,
                               "flat_eval": eval_reply,
                               "engine": used}
                save_to_brain({"type": "training", "topic": topic_key,
                               "teacher": t, "engine": used,
                               "reply": task_reply, "eval": eval_reply})
            except Exception as ex:
                results[t] = str(ex)[:200]

        return jsonify({"results": results, "topic": topic_desc, "iteration": iteration})

    except Exception as e:
        return jsonify({"reply": f"Train error: {str(e)[:200]}"}), 500


@app.route("/brain", methods=["GET"])
def view_brain():
    if not KV_AVAILABLE:
        return jsonify({"error": "KV недоступний"}), 503
    try:
        entries = read_brain(50)
        return jsonify({"count": len(entries), "entries": entries})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
