import os
import json
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ─── СПРОБА ПІДКЛЮЧИТИ KV (не критично якщо відсутнє) ───────────────────────
try:
    from vercel_kv import KV
    kv = KV()
    KV_AVAILABLE = True
except Exception:
    kv = None
    KV_AVAILABLE = False

# ─── ТЕМИ ДЛЯ ТРЕНУВАННЯ ────────────────────────────────────────────────────
TRAINING_TOPICS = {
    "algorithms":   "алгоритми та структури даних",
    "logic":        "логічне мислення та задачі",
    "code_review":  "аналіз та покращення коду",
    "math":         "математичні концепції",
    "creativity":   "генерація ідей та креативність",
    "reasoning":    "причинно-наслідкове мислення",
}

# ─── ДОПОМІЖНІ ФУНКЦІЇ ──────────────────────────────────────────────────────
def call_gemini(api_key: str, messages: list, system_prompt: str = "") -> str:
    """Викликає Gemini 1.5 Flash з підтримкою history."""
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"

    contents = []
    # Системний промпт — перше user-повідомлення
    if system_prompt:
        contents.append({"role": "user",  "parts": [{"text": system_prompt}]})
        contents.append({"role": "model", "parts": [{"text": "Зрозумів. Слідую інструкціям."}]})

    for m in messages:
        role = "model" if m.get("role") == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})

    payload = {"contents": contents}
    res = requests.post(url, json=payload, timeout=25)
    res.raise_for_status()
    data = res.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def call_claude(api_key: str, messages: list, system_prompt: str = "") -> str:
    """Викликає Claude claude-opus-4-5 з підтримкою history."""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    # Фільтруємо системні повідомлення з history — вони йдуть окремо
    filtered = [m for m in messages if m.get("role") in ("user", "assistant")]

    payload = {
        "model": "claude-opus-4-5",
        "max_tokens": 1024,
        "messages": filtered,
    }
    if system_prompt:
        payload["system"] = system_prompt

    res = requests.post(url, headers=headers, json=payload, timeout=25)
    res.raise_for_status()
    data = res.json()
    return data["content"][0]["text"]


def save_to_brain(entry: dict):
    """Зберігає знання в KV (якщо доступно)."""
    if not KV_AVAILABLE:
        return
    try:
        kv.lpush("flat_ai_brain", json.dumps(entry, ensure_ascii=False))
        kv.ltrim("flat_ai_brain", 0, 199)   # зберігаємо до 200 записів
    except Exception:
        pass


# ─── ГОЛОВНИЙ МАРШРУТ ───────────────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def handle_request():
    if request.method == "GET":
        status = "Connected" if KV_AVAILABLE else "Offline (no KV)"
        return f"FLAT AI Bridge: Active. Storage: {status}."

    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"reply": "No JSON received"}), 400

        user_msg     = data.get("message", "").strip()
        provider     = data.get("provider", "gemini").lower()
        gemini_key   = data.get("gemini_key", "").strip()
        claude_key   = data.get("claude_key", "").strip()
        history      = data.get("history", [])
        system_prompt = data.get("system_prompt", "")

        # ── Будуємо messages з history + поточним запитом ───────────────────
        messages = [m for m in history if m.get("role") != "system"]
        messages.append({"role": "user", "content": user_msg})

        # ── Виклик провайдера ────────────────────────────────────────────────
        if provider == "claude":
            if not claude_key:
                return jsonify({"reply": "❌ Claude API Key відсутній"}), 400
            reply = call_claude(claude_key, messages, system_prompt)

        elif provider == "gemini":
            if not gemini_key:
                return jsonify({"reply": "❌ Gemini API Key відсутній"}), 400
            reply = call_gemini(gemini_key, messages, system_prompt)

        else:
            return jsonify({"reply": f"❌ Невідомий провайдер: {provider}"}), 400

        # ── Збереження в Brain DB ────────────────────────────────────────────
        save_to_brain({
            "prompt":   user_msg,
            "reply":    reply,
            "provider": provider,
        })

        return jsonify({"reply": reply})

    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response else "?"
        body = e.response.text[:300] if e.response else ""
        return jsonify({"reply": f"API HTTP {code}: {body}"}), 502
    except Exception as e:
        return jsonify({"reply": f"System Error: {str(e)}"}), 500


# ─── МАРШРУТ ТРЕНУВАННЯ ─────────────────────────────────────────────────────
@app.route("/train", methods=["POST"])
def train():
    """
    Один крок тренування: Teacher відповідає на тему,
    потім FLAT AI аналізує відповідь.
    Повертає обидві відповіді.
    """
    try:
        data = request.get_json(force=True)
        teacher      = data.get("teacher", "gemini").lower()    # gemini | claude | both
        topic_key    = data.get("topic", "algorithms")
        gemini_key   = data.get("gemini_key", "").strip()
        claude_key   = data.get("claude_key", "").strip()
        iteration    = data.get("iteration", 1)

        topic_desc = TRAINING_TOPICS.get(topic_key, topic_key)

        # ── Формуємо завдання ────────────────────────────────────────────────
        task_prompt = (
            f"Ітерація {iteration}. Тема: {topic_desc}. "
            f"Дай розгорнутий приклад або задачу з цієї теми. "
            f"Завершуй чітким висновком."
        )
        eval_system = (
            "Ти — FLAT AI. Аналізуй отриману відповідь, виділи ключові патерни, "
            "оціни якість та запропонуй покращення. Використовуй 'Адаптивне мислення'."
        )

        results = {}

        # ── Teacher: Gemini ──────────────────────────────────────────────────
        if teacher in ("gemini", "both"):
            if not gemini_key:
                results["gemini"] = "❌ Gemini Key відсутній"
            else:
                g_reply = call_gemini(gemini_key, [{"role": "user", "content": task_prompt}])
                eval_msg = f"Відповідь вчителя:\n{g_reply}\n\nПроаналізуй."
                flat_eval = call_gemini(gemini_key, [{"role": "user", "content": eval_msg}], eval_system)
                results["gemini"] = {"teacher_reply": g_reply, "flat_eval": flat_eval}
                save_to_brain({"type": "training", "topic": topic_key,
                               "teacher": "gemini", "reply": g_reply, "eval": flat_eval})

        # ── Teacher: Claude ──────────────────────────────────────────────────
        if teacher in ("claude", "both"):
            if not claude_key:
                results["claude"] = "❌ Claude Key відсутній"
            else:
                c_reply = call_claude(claude_key, [{"role": "user", "content": task_prompt}])
                eval_msg = f"Відповідь вчителя:\n{c_reply}\n\nПроаналізуй."
                flat_eval = call_claude(claude_key, [{"role": "user", "content": eval_msg}], eval_system)
                results["claude"] = {"teacher_reply": c_reply, "flat_eval": flat_eval}
                save_to_brain({"type": "training", "topic": topic_key,
                               "teacher": "claude", "reply": c_reply, "eval": flat_eval})

        return jsonify({"results": results, "topic": topic_desc, "iteration": iteration})

    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response else "?"
        body = e.response.text[:300] if e.response else ""
        return jsonify({"reply": f"API HTTP {code}: {body}"}), 502
    except Exception as e:
        return jsonify({"reply": f"Train Error: {str(e)}"}), 500


# ─── ПЕРЕГЛЯД BRAIN DB ───────────────────────────────────────────────────────
@app.route("/brain", methods=["GET"])
def view_brain():
    if not KV_AVAILABLE:
        return jsonify({"error": "KV недоступний"}), 503
    try:
        raw = kv.lrange("flat_ai_brain", 0, 49)
        entries = [json.loads(r) for r in raw]
        return jsonify({"count": len(entries), "entries": entries})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
