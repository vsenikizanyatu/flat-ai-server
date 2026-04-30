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

class QuotaError(Exception):
    pass

def call_gemini(api_key, messages, system_prompt=""):
    if not api_key:
        raise ValueError("GEMINI KEY не введений")
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           f"gemini-2.0-flash:generateContent?key={api_key}")
    contents = []
    if system_prompt:
        contents += [{"role":"user","parts":[{"text":system_prompt}]},
                     {"role":"model","parts":[{"text":"Зрозумів."}]}]
    for m in messages:
        role = "model" if m.get("role") == "assistant" else "user"
        if m.get("content",""):
            contents.append({"role":role,"parts":[{"text":m["content"]}]})
    resp = requests.post(url, json={"contents":contents}, timeout=25)
    if resp.status_code == 429:
        raise QuotaError("Gemini 429: квота вичерпана")
    if not resp.ok:
        raise RuntimeError(f"Gemini {resp.status_code}: {resp.text[:250]}")
    data = resp.json()
    if "candidates" not in data or not data["candidates"]:
        raise RuntimeError(f"Gemini: порожня відповідь — {str(data)[:150]}")
    return data["candidates"][0]["content"]["parts"][0]["text"]

def call_claude(api_key, messages, system_prompt=""):
    if not api_key:
        raise ValueError("CLAUDE KEY не введений")
    headers = {"x-api-key":api_key,"anthropic-version":"2023-06-01","content-type":"application/json"}
    filtered = [{"role":m["role"],"content":m["content"]}
                for m in messages if m.get("role") in ("user","assistant") and m.get("content","").strip()]
    if not filtered or filtered[0]["role"] != "user":
        filtered.insert(0,{"role":"user","content":"Привіт"})
    payload = {"model":"claude-opus-4-5","max_tokens":1024,"messages":filtered}
    if system_prompt:
        payload["system"] = system_prompt
    resp = requests.post("https://api.anthropic.com/v1/messages",
                         headers=headers, json=payload, timeout=25)
    if resp.status_code == 429:
        raise QuotaError("Claude 429: квота вичерпана")
    if not resp.ok:
        raise RuntimeError(f"Claude {resp.status_code}: {resp.text[:250]}")
    return resp.json()["content"][0]["text"]

def call_with_fallback(provider, gemini_key, claude_key, messages, system_prompt=""):
    """Повертає (reply, actual_provider). При 429 — автофallback."""
    secondary = "claude" if provider == "gemini" else "gemini"
    try:
        if provider == "gemini":
            return call_gemini(gemini_key, messages, system_prompt), "gemini"
        else:
            return call_claude(claude_key, messages, system_prompt), "claude"
    except QuotaError as q:
        # Спробуємо запасний провайдер
        try:
            if secondary == "claude":
                reply = call_claude(claude_key, messages, system_prompt)
            else:
                reply = call_gemini(gemini_key, messages, system_prompt)
            return f"[Fallback: {secondary.upper()}]\n{reply}", secondary
        except ValueError:
            # Запасний key не введений — чітке повідомлення
            raise RuntimeError(
                f"{q} | Fallback на {secondary.upper()} неможливий — "
                f"введи {secondary.upper()} KEY у полі нижче"
            )
        except Exception as e2:
            raise RuntimeError(f"{q} | {secondary.upper()} теж недоступний: {str(e2)[:150]}")

def save_brain(entry):
    if not KV_AVAILABLE: return
    try:
        kv.lpush("flat_ai_brain", json.dumps(entry, ensure_ascii=False))
        kv.ltrim("flat_ai_brain", 0, 199)
    except: pass

def read_brain(limit=10):
    if not KV_AVAILABLE: return []
    try:
        return [json.loads(r) for r in kv.lrange("flat_ai_brain", 0, limit-1)]
    except: return []

# ════════════════════════════════════════════════════════════════════════════

@app.route("/", methods=["GET","POST"])
def handle_request():
    if request.method == "GET":
        return f"FLAT AI Bridge v3. KV: {'on' if KV_AVAILABLE else 'off'}."
    try:
        d = request.get_json(force=True, silent=True) or {}
        msg        = d.get("message","").strip()
        provider   = d.get("provider","gemini").lower()
        gemini_key = d.get("gemini_key","").strip()
        claude_key = d.get("claude_key","").strip()
        history    = d.get("history",[])
        sys_p      = d.get("system_prompt","")
        if not msg: return jsonify({"reply":"Порожнє повідомлення"}),400
        if provider not in ("gemini","claude"):
            return jsonify({"reply":f"Невідомий провайдер: {provider}"}),400
        messages = [m for m in history if m.get("role") in ("user","assistant")]
        messages.append({"role":"user","content":msg})
        reply, actual = call_with_fallback(provider, gemini_key, claude_key, messages, sys_p)
        save_brain({"prompt":msg,"reply":reply,"provider":actual})
        return jsonify({"reply":reply,"provider":actual})
    except (ValueError, RuntimeError) as e:
        return jsonify({"reply": str(e)}), 502
    except requests.exceptions.Timeout:
        return jsonify({"reply":"Timeout: провайдер не відповів"}), 502
    except Exception as e:
        return jsonify({"reply":f"{type(e).__name__}: {str(e)[:200]}"}), 500

@app.route("/flat", methods=["POST"])
def flat_ai():
    try:
        d          = request.get_json(force=True, silent=True) or {}
        msg        = d.get("message","").strip()
        gemini_key = d.get("gemini_key","").strip()
        claude_key = d.get("claude_key","").strip()
        history    = d.get("history",[])
        if not msg: return jsonify({"reply":"Порожнє повідомлення"}),400
        # Вибір первинного провайдера
        if not claude_key and not gemini_key:
            return jsonify({"reply":"Введи хоча б один API key (Gemini або Claude)"}),400
        primary = "claude" if claude_key else "gemini"
        # Контекст із Brain DB
        brain = read_brain(6)
        ctx = ""
        if brain:
            ex = [f"Q:{e.get('prompt','')[:80]}\nA:{e.get('reply','')[:120]}"
                  for e in brain[:4] if e.get("prompt") and e.get("reply")]
            if ex: ctx = "\n\n[BRAIN DB]:\n" + "\n---\n".join(ex)
        sys_p = ("Ти — FLAT AI, автономна мережа. Відповідай від першої особи. "
                 "Стисло (до 150 слів), українською. Адаптивне мислення." + ctx)
        messages = [m for m in history if m.get("role") in ("user","assistant")]
        messages.append({"role":"user","content":msg})
        reply, actual = call_with_fallback(primary, gemini_key, claude_key, messages, sys_p)
        save_brain({"prompt":msg,"reply":reply,"provider":"flat_ai","engine":actual})
        return jsonify({"reply":reply,"engine":actual})
    except (ValueError, RuntimeError) as e:
        return jsonify({"reply": str(e)}), 502
    except Exception as e:
        return jsonify({"reply":f"{type(e).__name__}: {str(e)[:200]}"}), 500

@app.route("/train", methods=["POST"])
def train():
    try:
        d          = request.get_json(force=True, silent=True) or {}
        teacher    = d.get("teacher","gemini").lower()
        topic_key  = d.get("topic","algorithms")
        gemini_key = d.get("gemini_key","").strip()
        claude_key = d.get("claude_key","").strip()
        iteration  = d.get("iteration",1)
        topic_desc = TRAINING_TOPICS.get(topic_key, topic_key)
        task  = (f"Ітерація {iteration}. Тема: {topic_desc}. "
                 "Конкретний приклад або задача з розбором. Висновок в кінці.")
        esys  = ("Ти — FLAT AI. Аналізуй відповідь: патерни, оцінка 1–10, "
                 "одне покращення. Адаптивне мислення. До 150 слів.")
        results = {}
        for t in (["gemini","claude"] if teacher == "both" else [teacher]):
            try:
                tr, u1 = call_with_fallback(t, gemini_key, claude_key,
                                            [{"role":"user","content":task}])
                ev, u2 = call_with_fallback(t, gemini_key, claude_key,
                                            [{"role":"user","content":f"Відповідь вчителя:\n{tr}\n\nПроаналізуй."}],
                                            esys)
                results[t] = {"teacher_reply":tr,"flat_eval":ev,"engine":u1}
                save_brain({"type":"training","topic":topic_key,"teacher":t,
                            "engine":u1,"reply":tr,"eval":ev})
            except Exception as ex:
                results[t] = str(ex)[:200]
        return jsonify({"results":results,"topic":topic_desc,"iteration":iteration})
    except Exception as e:
        return jsonify({"reply":f"Train: {str(e)[:200]}"}), 500

@app.route("/brain", methods=["GET"])
def view_brain():
    if not KV_AVAILABLE: return jsonify({"error":"KV недоступний"}),503
    try:
        e = read_brain(50)
        return jsonify({"count":len(e),"entries":e})
    except Exception as ex:
        return jsonify({"error":str(ex)}),500
