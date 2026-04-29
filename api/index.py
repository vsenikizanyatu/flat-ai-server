import os
import json
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ── KV (не критично) ─────────────────────────────────────────────────────────
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
def call_gemini(api_key: str, messages: list, system_prompt: str = "") -> str:
    if not api_key:
        raise ValueError("Gemini API key порожній")

    # v1beta — актуальний endpoint
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-1.5-flash:generateContent?key={api_key}"
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

    if not resp.ok:
        raise RuntimeError(f"Gemini HTTP {resp.status_code}: {resp.text[:400]}")

    data = resp.json()
    if "candidates" not in data or not data["candidates"]:
        raise RuntimeError(f"Gemini: порожня відповідь. Raw: {str(data)[:300]}")

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
    # Claude вимагає перше повідомлення — user
    if not filtered or filtered[0]["role"] != "user":
        filtered.insert(0, {"role": "user", "content": "Привіт"})

    payload = {"model": "claude-opus-4-5", "max_tokens": 1024, "messages": filtered}
    if system_prompt:
        payload["system"] = system_prompt

    resp = requests.post("https://api.anthropic.com/v1/messages",
                         headers=headers, json=payload, timeout=25)

    if not resp.ok:
        raise RuntimeError(f"Claude HTTP {resp.status_code}: {resp.text[:400]}")

    return resp.json()["content"][0]["text"]


def save_to_brain(entry: dict):
    if not KV_AVAILABLE:
        return
    try:
        kv.lpush("flat_ai_brain", json.dumps(entry, ensure_ascii=False))
        kv.ltrim("flat_ai_brain", 0, 199)
    except Exception:
        pass


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

        if provider == "gemini":
            reply = call_gemini(gemini_key, messages, system_prompt)
        elif provider == "claude":
            reply = call_claude(claude_key, messages, system_prompt)
        else:
            return jsonify({"reply": f"Невідомий провайдер: {provider}"}), 400

        save_to_brain({"prompt": user_msg, "reply": reply, "provider": provider})
        return jsonify({"reply": reply})

    except ValueError as e:
        return jsonify({"reply": f"Конфіг: {str(e)}"}), 400
    except RuntimeError as e:
        # Містить HTTP код та тіло відповіді від провайдера
        return jsonify({"reply": str(e)}), 502
    except requests.exceptions.ConnectionError as e:
        return jsonify({"reply": f"Помилка з'єднання з провайдером: {str(e)[:150]}"}), 502
    except requests.exceptions.Timeout:
        return jsonify({"reply": "Timeout: провайдер не відповів за 25 сек"}), 502
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
            "Дай конкретний приклад або задачу з розбором. Чіткий висновок в кінці."
        )
        eval_system = (
            "Ти — FLAT AI. Аналізуй відповідь вчителя: виділи ключові патерни, "
            "оціни якість (1-10), запропонуй одне покращення. "
            "Використовуй 'Адаптивне мислення'. Відповідь до 200 слів."
        )

        results = {}

        if teacher in ("gemini", "both"):
            try:
                t = call_gemini(gemini_key, [{"role": "user", "content": task_prompt}])
                e = call_gemini(gemini_key,
                                [{"role": "user", "content": f"Відповідь вчителя:\n{t}\n\nПроаналізуй."}],
                                eval_system)
                results["gemini"] = {"teacher_reply": t, "flat_eval": e}
                save_to_brain({"type": "training", "topic": topic_key, "teacher": "gemini",
                               "reply": t, "eval": e})
            except Exception as e:
                results["gemini"] = str(e)[:200]

        if teacher in ("claude", "both"):
            try:
                t = call_claude(claude_key, [{"role": "user", "content": task_prompt}])
                e = call_claude(claude_key,
                                [{"role": "user", "content": f"Відповідь вчителя:\n{t}\n\nПроаналізуй."}],
                                eval_system)
                results["claude"] = {"teacher_reply": t, "flat_eval": e}
                save_to_brain({"type": "training", "topic": topic_key, "teacher": "claude",
                               "reply": t, "eval": e})
            except Exception as e:
                results["claude"] = str(e)[:200]

        return jsonify({"results": results, "topic": topic_desc, "iteration": iteration})

    except Exception as e:
        return jsonify({"reply": f"Train error: {str(e)[:200]}"}), 500


@app.route("/brain", methods=["GET"])
def view_brain():
    if not KV_AVAILABLE:
        return jsonify({"error": "KV недоступний"}), 503
    try:
        raw     = kv.lrange("flat_ai_brain", 0, 49)
        entries = [json.loads(r) for r in raw]
        return jsonify({"count": len(entries), "entries": entries})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
