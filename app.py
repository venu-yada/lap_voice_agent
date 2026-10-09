"""A small, local browser demo for the LAP qualification conversation.

Run with: py app.py
Uses only Python's standard library. It does not place calls or need API keys.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import uuid

HOST = "127.0.0.1"
PORT = 8000
OFFER_LIMIT_LAKH = 75
SESSIONS = {}  # Demo conversations stay in memory and clear when the app stops.

DATA_FIELDS = [
    "property_type",
    "ownership",
    "documents_available",
    "loan_amount_lakh",
    "occupation",
    "income_mode",
    "market_value_lakh",
    "tenure_years",
]

CHECKLIST_STEPS = [
    "property_type",
    "ownership",
    "documents_available",
    "loan_amount_lakh",
    "occupation_income",
    "market_value_lakh",
    "tenure_years",
]

QUESTIONS = {
    "en": {
        "property_type": "What kind of property is it: residential, commercial, or industrial?",
        "ownership": "Is the property solely owned, or jointly owned?",
        "documents_available": "Are the original property documents available for verification?",
        "loan_amount_lakh": "Roughly how much would you like to borrow, in lakhs?",
        "occupation_income": "Are you salaried or self-employed, and do you receive income through a bank account or in cash?",
        "market_value_lakh": "What do you estimate the property's current market value to be, in lakhs? A rough estimate is fine.",
        "tenure_years": "What repayment tenure would you prefer, in years? The range for this offer is 3 to 15 years.",
    },
    "hi": {
        "property_type": "आपकी प्रॉपर्टी किस तरह की है—रिहायशी, कमर्शियल या इंडस्ट्रियल?",
        "ownership": "प्रॉपर्टी आपके अकेले के नाम पर है या संयुक्त रूप से?",
        "documents_available": "क्या प्रॉपर्टी के मूल दस्तावेज़ जाँच के लिए उपलब्ध हैं?",
        "loan_amount_lakh": "आपको लगभग कितने लाख रुपये का लोन चाहिए?",
        "occupation_income": "आप नौकरी करते हैं या अपना व्यवसाय? आपकी आमदनी बैंक खाते में आती है या नकद मिलती है?",
        "market_value_lakh": "आपके हिसाब से प्रॉपर्टी की मौजूदा बाज़ार कीमत लगभग कितनी है? लाख में बता सकते हैं।",
        "tenure_years": "आप कितने साल की अवधि रखना चाहेंगे? इस ऑफ़र में अवधि 3 से 15 साल तक है।",
    },
}


def yes_no(text):
    text = text.casefold()
    if re.search(r"\b(yes|yeah|yep|correct|speaking|that's me|haan|हाँ|हां|जी)\b", text):
        return True
    if re.search(r"\b(no|nope|wrong|nahin|nahi|नहीं)\b", text):
        return False
    return None


def amount_in_lakhs(text, current_step):
    text = text.casefold().replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)\s*(crore|crores|cr|करोड़|करोड़)", text)
    if match:
        return float(match.group(1)) * 100
    match = re.search(r"(\d+(?:\.\d+)?)\s*(lakh|lakhs|lac|lacs|लाख)", text)
    if match:
        return float(match.group(1))
    if current_step in ("loan_amount_lakh", "market_value_lakh"):
        match = re.search(r"\b(\d+(?:\.\d+)?)\b", text)
        if match:
            return float(match.group(1))
    return None


def collect_answers(session, text, current_step=None):
    """Read common, explicit answers; ambiguous values stay unanswered."""
    data = session["answers"]
    value = text.casefold()
    step = current_step

    if any(word in value for word in ("agricultural", "farm land", "farmland", "कृषि", "खेती")):
        data["property_type"] = "agricultural"
    elif any(word in value for word in ("residential", "house", "flat", "apartment", "रिहायशी", "घर", "फ्लैट")):
        data["property_type"] = "residential"
    elif any(word in value for word in ("commercial", "shop", "office", "कमर्शियल", "दुकान", "ऑफिस")):
        data["property_type"] = "commercial"
    elif any(word in value for word in ("industrial", "factory", "इंडस्ट्रियल", "फैक्ट्री")):
        data["property_type"] = "industrial"

    if any(word in value for word in ("joint", "jointly", "with my wife", "with my husband", "संयुक्त")):
        data["ownership"] = "joint"
    elif any(word in value for word in ("sole", "only mine", "single owner", "मेरे नाम", "अकेले")):
        data["ownership"] = "sole"
    elif step == "ownership" and yes_no(text) is True:
        data["ownership"] = "sole"

    if step == "documents_available" and yes_no(text) is not None:
        data["documents_available"] = yes_no(text)
    elif any(word in value for word in ("original documents", "original papers", "दस्तावेज़", "कागज़")):
        if re.search(r"\b(not available|unavailable|don't have|do not have|नहीं हैं|नहीं)\b", value):
            data["documents_available"] = False
        elif re.search(r"\b(available|have them|yes|हैं|उपलब्ध)\b", value):
            data["documents_available"] = True

    if any(word in value for word in ("cash", "कैश", "नकद")):
        data["income_mode"] = "cash"
    elif any(word in value for word in ("bank", "cheque", "check", "बैंक", "चेक", "खाते")):
        data["income_mode"] = "bank"

    if any(word in value for word in ("self-employed", "self employed", "business owner", "own business", "व्यवसाय", "अपना बिज़नेस")):
        data["occupation"] = "self_employed"
    elif any(word in value for word in ("salaried", "salary", "नौकरी")):
        data["occupation"] = "salaried"

    amount = amount_in_lakhs(text, step)
    if amount is not None:
        if step == "market_value_lakh" or any(word in value for word in ("market value", "worth", "मूल्य", "कीमत")):
            data["market_value_lakh"] = amount
        elif step == "loan_amount_lakh" or any(word in value for word in ("loan", "borrow", "लोन", "ऋण")):
            data["loan_amount_lakh"] = amount

    years = re.search(r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?|साल|वर्ष)", value)
    if years:
        data["tenure_years"] = float(years.group(1))
    elif step == "tenure_years":
        number = re.search(r"\b(\d+(?:\.\d+)?)\b", value)
        if number:
            data["tenure_years"] = float(number.group(1))


def missing_question(session):
    answers = session["answers"]
    for step in CHECKLIST_STEPS:
        if step == "occupation_income":
            occupation_missing = answers["occupation"] is None
            income_missing = answers["income_mode"] is None
            if occupation_missing or income_missing:
                session["current_step"] = step
                if occupation_missing and income_missing:
                    return QUESTIONS[session["language"]][step]
                if occupation_missing:
                    return "Are you salaried or self-employed?" if session["language"] == "en" else "आप नौकरी करते हैं या अपना व्यवसाय?"
                return "Does your income come through a bank account or in cash?" if session["language"] == "en" else "आपकी आमदनी बैंक खाते में आती है या नकद मिलती है?"
            continue
        if answers.get(step) is None:
            session["current_step"] = step
            return QUESTIONS[session["language"]][step]
    session["current_step"] = None
    return None


def disqualified(session):
    answers = session["answers"]
    tenure = answers["tenure_years"]
    return (
        answers["property_type"] == "agricultural"
        or answers["documents_available"] is False
        or answers["income_mode"] == "cash"
        or (tenure is not None and not 3 <= tenure <= 15)
    )


def finish(session, status, message):
    session["status"] = status
    return message, True


def reply(session, text):
    name = session["customer_name"]
    lang = session["language"]
    text = text.strip()
    value = text.casefold()
    stage = session["stage"]

    if not text:
        return "Sorry, I didn't quite catch that. Could you say it another way?", False
    if re.search(r"\b(don't call|do not call|stop calling|remove my number|opt out)\b|\bफोन मत करो|कॉल मत करो\b", value):
        return finish(session, "do_not_call", "Understood. I’ve noted that you don’t want further calls. Have a good day.")

    if stage == "identity":
        identity_answer = yes_no(text)
        wrong_person = identity_answer is False or bool(
            re.search(r"\b(wrong number|not me|गलत नंबर)\b", value)
        )
        if wrong_person:
            return finish(session, "wrong_person", "Thanks for letting me know. I’ll end the demo call now.")
        confirmed = identity_answer is True or bool(
            re.search(r"\b(this is|speaking|हाँ|हां|जी)\b", value)
        ) or name.casefold() in value
        if not confirmed:
            retry = f"माफ़ कीजिए, क्या मेरी बात {name} जी से हो रही है?" if lang == "hi" else f"Sorry, may I confirm I’m speaking with {name}?"
            return retry, False
        session["stage"] = "availability"
        if lang == "hi":
            return f"धन्यवाद {name} जी। मैं Home Credit की automated voice assistant हूँ। हमारे रिकॉर्ड में ₹75 लाख तक का संभावित Loan Against Property ऑफ़र दिख रहा है। क्या अभी कुछ बुनियादी सवालों के लिए एक मिनट है?", False
        return f"Thanks, {name}. I’m Asha, an automated voice assistant calling for Home Credit. Our records show a potential Loan Against Property offer of up to 75 lakh rupees. Would you have a minute for a few basic questions?", False

    if stage == "availability":
        if re.search(r"not interested|no thanks|don't want|do not want|रुचि नहीं|नहीं चाहिए", value):
            return finish(session, "declined", "Understood. I won’t take more of your time. Have a good day.")
        if any(word in value for word in ("busy", "later", "not now", "call back", "बाद में", "व्यस्त")) or yes_no(text) is False:
            session["stage"] = "callback"
            return ("कोई बात नहीं। किस तारीख़ और समय पर वापस कॉल करना ठीक रहेगा?" if lang == "hi" else "Of course. What date and time would suit you for a callback?"), False
        if yes_no(text) is not True:
            return "Would now be a convenient time to continue?", False
        session["stage"] = "qualification"
        collect_answers(session, text, session.get("current_step"))
        question = missing_question(session)
        return (question or "Thanks. Let's continue with the basic eligibility details."), False

    if stage == "callback":
        session["answers"]["callback_time"] = text[:160]
        return finish(session, "callback_requested", "Thanks, I’ve noted your callback request. Have a good day.")

    if stage == "loan_cap_confirm":
        if yes_no(text) is not True:
            return finish(session, "declined", "Understood. This offer is capped at 75 lakh rupees. Thanks for your time.")
        session["answers"]["loan_amount_lakh"] = OFFER_LIMIT_LAKH
        session["stage"] = "qualification"
        question = missing_question(session)
        if question:
            return question, False
        return finish(session, "qualified", f"Thanks, {name}. You appear to meet the preliminary criteria. A senior loan expert will contact you to confirm the details.")

    if stage == "qualification":
        no_existing_loan = re.search(r"\b(no|don't have|do not have|without)\b.{0,35}\bloan\b", value)
        existing_loan = re.search(r"\b(existing|current|home|property) loan\b|\bloan on (?:the )?(?:property|home)\b", value)
        lower_emi = re.search(r"\b(lower|reduce|decrease|cut)\w*\b.{0,15}\bemi\b|\bemi\b.{0,15}\b(lower|reduce|decrease|cut)\w*", value)
        if (existing_loan and not no_existing_loan) or lower_emi:
            return finish(session, "transfer_referral", "Thanks for letting me know. A loan transfer specialist will contact you about your existing loan options.")

        collect_answers(session, text, session.get("current_step"))
        if disqualified(session):
            return finish(session, "disqualified", "Thanks for sharing that. Under the current criteria for this offer, we can’t take the application forward. I appreciate your time.")

        amount = session["answers"]["loan_amount_lakh"]
        if amount is not None and amount > OFFER_LIMIT_LAKH:
            session["answers"]["requested_loan_amount_lakh"] = amount
            session["answers"]["loan_amount_lakh"] = None
            session["stage"] = "loan_cap_confirm"
            return "This offer is capped at 75 lakh rupees. Would you like to continue with 75 lakh rupees?", False

        question = missing_question(session)
        if question:
            return question, False
        return finish(session, "qualified", f"Thanks for sharing those details, {name}. Based on these initial checks, you appear to meet the preliminary criteria. A senior loan expert will contact you to confirm rates and next steps.")

    return finish(session, "ended", "Thanks for your time. Goodbye.")


PAGE = r"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LAP Qualification Demo</title>
<style>
body{margin:0;background:#edf2f7;color:#172536;font:16px/1.5 system-ui,sans-serif}main{max-width:720px;margin:36px auto;padding:0 16px}.card{background:white;border:1px solid #dce4ed;border-radius:16px;overflow:hidden;box-shadow:0 12px 36px #19385a12}header{padding:22px 26px;border-bottom:1px solid #dce4ed}h1{font-size:22px;margin:0}.muted{color:#637386;font-size:14px;margin:4px 0 0}.setup,.composer{display:flex;gap:9px;padding:16px 24px;background:#f5f8fb}.setup{border-bottom:1px solid #dce4ed}input,select,button{font:inherit;border-radius:9px;padding:10px;border:1px solid #dce4ed}input{flex:1;min-width:0}button{background:#155eef;color:white;border:0;font-weight:650;cursor:pointer}button:disabled,input:disabled{opacity:.55}.messages{height:390px;overflow:auto;padding:20px 24px;display:flex;flex-direction:column;gap:10px}.bubble{max-width:84%;padding:10px 13px;border-radius:13px;white-space:pre-wrap}.agent{align-self:flex-start;background:#f2f6fa;border:1px solid #dce4ed}.caller{align-self:flex-end;background:#e8efff}.composer{border-top:1px solid #dce4ed;background:white}.foot{padding:0 24px 18px;color:#637386;font-size:12px}@media(max-width:520px){main{margin:14px auto}.messages{height:55vh}.setup,.composer,header{padding-left:16px;padding-right:16px}}
</style>
<main><section class="card"><header><h1>Loan Against Property · Demo</h1><p class="muted">A simple local conversation demo. It does not place calls.</p></header>
<form class="setup" id="setup"><input id="name" maxlength="100" value="Alex" placeholder="Customer name"><select id="language"><option value="en">English</option><option value="hi">Hindi</option></select><button>Start</button></form>
<div id="messages" class="messages" aria-live="polite"></div><form class="composer" id="composer"><input id="text" maxlength="1000" placeholder="Type the customer's answer…" disabled><button id="send" disabled>Send</button></form>
<div class="foot">Demo conversations stay in memory and clear when you stop the app. No API keys or extra packages are needed.</div></section></main>
<script>
let id=null;const messages=document.querySelector('#messages'),input=document.querySelector('#text'),send=document.querySelector('#send');
function bubble(text,who){const el=document.createElement('div');el.className='bubble '+who;el.textContent=text;messages.append(el);messages.scrollTop=messages.scrollHeight}
async function post(url,body){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.error||'Something went wrong');return d}
document.querySelector('#setup').onsubmit=async e=>{e.preventDefault();try{const d=await post('/demo/start',{customer_name:document.querySelector('#name').value,language:document.querySelector('#language').value});id=d.session_id;messages.replaceChildren();bubble(d.say,'agent');input.disabled=false;send.disabled=false;input.focus()}catch(err){bubble(err.message,'agent')}};
document.querySelector('#composer').onsubmit=async e=>{e.preventDefault();const text=input.value.trim();if(!id||!text)return;bubble(text,'caller');input.value='';send.disabled=true;try{const d=await post('/demo/turn',{session_id:id,text});bubble(d.say,'agent');if(d.terminal)input.disabled=true}catch(err){bubble(err.message,'agent')}finally{send.disabled=input.disabled;input.focus()}};
</script>"""


class Handler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            return self.send_json({"status": "ok"})
        if self.path != "/":
            return self.send_json({"error": "Not found"}, 404)
        body = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 10000:
                return self.send_json({"error": "Request is too large"}, 413)
            payload = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/demo/start":
                language = payload.get("language", "en")
                if language not in QUESTIONS:
                    language = "en"
                name = str(payload.get("customer_name", "Alex")).strip()[:100] or "there"
                session_id = str(uuid.uuid4())
                SESSIONS[session_id] = {
                    "customer_name": name,
                    "language": language,
                    "stage": "identity",
                    "status": "in_progress",
                    "answers": {step: None for step in DATA_FIELDS},
                    "current_step": None,
                }
                greeting = f"नमस्ते, क्या मैं {name} जी से बात कर रहा हूँ?" if language == "hi" else f"Hello, may I speak with {name}?"
                return self.send_json({"session_id": session_id, "say": greeting, "status": "in_progress"})

            if self.path == "/demo/turn":
                session = SESSIONS.get(str(payload.get("session_id", "")))
                if session is None:
                    return self.send_json({"error": "Conversation not found. Start a new demo."}, 404)
                if session["status"] != "in_progress":
                    return self.send_json({"error": "This conversation has ended. Start a new demo."}, 409)
                spoken, terminal = reply(session, str(payload.get("text", ""))[:1000])
                return self.send_json({"say": spoken, "status": session["status"], "terminal": terminal})

            return self.send_json({"error": "Not found"}, 404)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self.send_json({"error": "Send valid JSON"}, 400)
        except Exception:
            return self.send_json({"error": "The demo could not process that answer"}, 500)

    def log_message(self, format_string, *args):
        # Keep the demo's console output quiet; caller answers are not logged.
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"LAP qualification demo is ready: http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDemo stopped.")
    finally:
        server.server_close()
