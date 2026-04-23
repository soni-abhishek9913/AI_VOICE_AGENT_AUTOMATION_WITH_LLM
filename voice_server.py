# voice_server.py final

import json
import os
from datetime import datetime
from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather

from hospital_agent import HospitalAgent
import llm_interface as llm

app = Flask(__name__)


call_sessions: dict = {}   # call_sid → {"lang": "en"/"hi", "done": bool}
agents: dict        = {}   # call_sid → HospitalAgent instance


def get_agent(call_sid: str) -> HospitalAgent:
    if call_sid not in agents:
        agents[call_sid] = HospitalAgent(call_sid)
    return agents[call_sid]


def cleanup(call_sid: str):
    call_sessions.pop(call_sid, None)
    agents.pop(call_sid, None)


VOICE_EN = "Google.en-GB-Standard-B"
LANG_EN  = "en-GB"

VOICE_HI = "Google.hi-IN-Standard-B"
LANG_HI  = "hi-IN"


def say(twiml_obj, text: str, lang: str = "en"):
    if lang == "hi":
        twiml_obj.say(text, voice=VOICE_HI, language=LANG_HI)
    else:
        twiml_obj.say(text, voice=VOICE_EN, language=LANG_EN)


# ── Transcript helpers ────────────────────────────────────────────────────
TRANSCRIPT_FILE = "transcripts.txt"
_transcripts: dict = {}


def _log(call_sid: str, role: str, text: str):
    if call_sid not in _transcripts:
        _transcripts[call_sid] = []
    _transcripts[call_sid].append(f"[{role}] {text}")


def _save_transcript(call_sid: str):
    lines = _transcripts.pop(call_sid, [])
    if not lines:
        return
    with open(TRANSCRIPT_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"Call SID : {call_sid}\n")
        f.write(f"Date/Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lang = call_sessions.get(call_sid, {}).get("lang", "unknown")
        f.write(f"Language : {lang.upper()}\n")
        f.write(f"{'='*60}\n")
        for line in lines:
            f.write(line + "\n")
        f.write(f"{'='*60}\n")



HINTS_EN = (
    "Abhishek, Rahul, Priya, Amit, Pooja, Raj, Neha, Ravi, Sunita, Vikram, "
    "Anita, Suresh, Kavita, Mahesh, Rekha, Dinesh, Meena, Rajesh, Geeta, Anil, "
    "Sanjay, Deepa, Vijay, Asha, Ramesh, Usha, Prakash, Lata, Mohan, Shanti, "
    "Abhishek, Abhishek Soni, Soni, Patel, Shah, Sharma, Verma, Singh, Mehta, "
    "book appointment, cancel appointment, make an appointment, "
    "schedule appointment, get an appointment, book a slot, "
    "I want to book, I need a doctor, see a doctor, visit doctor, "
    "want to cancel, cancel my appointment, remove appointment, "
    "reschedule, change my appointment, change date, change time, "
    "move appointment, shift appointment, different date, new date, "
    "headache, head ache, head pain, migraine, "
    "fever, cold, flu, cough, sore throat, body pain, weakness, fatigue, "
    "bleeding, blood, injury, wound, chest pain, "
    "stomach pain, stomach ache, gas, nausea, vomiting, loose motion, "
    "indigestion, acidity, diarrhea, constipation, "
    "skin rash, itching, acne, pimples, skin problem, allergy, "
    "doctor one, doctor two, one, two, first, second, "
    "Dr Shah, Dr Reddy, Dr Mehta, Dr Singh, Dr Patel, Dr Verma, Dr Gupta, Dr Kapoor, "
    "A, B, C, D, E, F, G, H, I, J, K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Y, Z, "
    "eight AM, nine AM, ten AM, eleven AM, twelve PM, "
    "five PM, six PM, seven PM, eight PM, "
    "January, February, March, April, May, June, "
    "July, August, September, October, November, December, "
    "Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday, "
    "first, second, third, fourth, fifth, tenth, fifteenth, twentieth, "
    "twenty eighth, thirty first, "
    "yes, no, confirm, cancel, correct, go ahead, sure, okay, that is right"
)

HINTS_HI = (
    "Abhishek, Rahul, Priya, Amit, Pooja, Raj, Neha, Ravi, Sunita, Vikram, "
    "Anita, Suresh, Kavita, Mahesh, Rekha, Dinesh, Meena, Rajesh, Geeta, Anil, "
    "Sanjay, Deepa, Vijay, Asha, Ramesh, Usha, Prakash, Lata, Mohan, Shanti, "
    "appointment book karni hai, appointment chahiye, appointment leni hai, "
    "appointment karna hai, appointment karwani hai, appointment lena hai, "
    "doctor chahiye, doctor se milna hai, doctor ko dikhana hai, "
    "checkup karna hai, hospital aana hai, milna chahta hoon, "
    "appointment cancel karna, appointment cancel karni, band karna, "
    "nahi aana, hatao appointment, cancel karwana, "
    "reschedule karna, date badlo, time badlo, appointment badlo, "
    "doosri date chahiye, waqt badlo, phir se book karna, "
    "sar dard, sir dard, sir mein dard, migraine, "
    "bukhar, bukar, sardi, khansi, zukam, gale mein dard, "
    "body dard, kamzori, thakaan, khoon, chot lagi, zakhm, "
    "pet dard, pet mein dard, gas, ulti, dast, loose motion, "
    "acidity, kabz, khana nahi pachta, "
    "khujli, chamdi ki bimari, daane, pimple, allergy, skin problem, "
    "doctor ek, doctor do, ek, do, pehla, doosra, "
    "Dr Shah, Dr Reddy, Dr Mehta, Dr Singh, Dr Patel, Dr Verma, Dr Gupta, Dr Kapoor, "
    "A, B, C, D, E, F, G, H, I, J, K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Y, Z, "
    "eight AM, nine AM, ten AM, eleven AM, twelve PM, "
    "five PM, six PM, seven PM, eight PM, "
    "aath baje, nau baje, das baje, gyarah baje, barah baje, "
    "paanch baje, chhe baje, saat baje, aath baje sham, "
    "January, February, March, April, May, June, "
    "July, August, September, October, November, December, "
    "Somvar, Mangalvar, Budhvar, Guruvar, Shukravar, Shanivar, Ravivar, "
    "Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday, "
    "ek, do, teen, chaar, paanch, das, pandrah, bees, "
    "pachees, tees, ikattis, "
    "haan, nahi, confirm, cancel, bilkul, theek hai, aage badhein, sahi hai, "
    "haan ji, nahi ji, band karo"
)

HINTS_LANG = (
    "English, Hindi, one, two, 1, 2, "
    "angreji, hindi mein, hindi chahiye, english chahiye, "
    "angreji mein, hindi bolna chahta hoon, english mein baat karo"
)


HINTS_SPELL = (
    "A, B, C, D, E, F, G, H, I, J, K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Y, Z, "
    "a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p, q, r, s, t, u, v, w, x, y, z, "
    "Abhishek, Rahul, Priya, Amit, Pooja, Vikram, Sunita, Arjun, Ravi, Meena, "
    "Anjali, Deepak, Rohit, Suresh, Kavita, Arun, Manish, Ajay, Nikhil, Sanjay, "
    "Akash, Bhavna, Chirag, Dhruv, Esha, Faisal, Gaurav, Ishaan, Kartik, Lavanya, "
    "Mukesh, Namrata, Pankaj, Sachin, Tanvi, Umesh, Vandana, Yogesh, Zara, "
    "Soni, Shah, Patel, Sharma, Verma, Singh, Kumar, Gupta, Joshi, Mehta, Reddy, "
    "Kapoor, Malhotra, Agarwal, Bansal, Trivedi, Pandey, Rao, Nair, Iyer, "
    "Pillai, Desai, Chaudhary, Bose, Chatterjee, Mukherjee, Mishra, Tiwari, "
    "Dubey, Yadav, Patil, Naik, Kaur, Gill, Bhatia, Arora, Chopra, Mehra, "
    "Green, Brown, White, Black, Rose, "
    "alpha, bravo, charlie, delta, echo, foxtrot, golf, hotel, india, juliet, "
    "kilo, lima, mike, november, oscar, papa, quebec, romeo, sierra, tango, "
    "uniform, victor, whiskey, xray, yankee, zulu"
)


def _get_hints(agent, lang: str) -> str:
    """
    Return STT hints appropriate for the current agent state.
    Name-collection states get enriched letter-by-letter spelling hints.
    """
    base  = HINTS_HI if lang == "hi" else HINTS_EN
    state = getattr(agent, "state", "START") if agent else "START"
    # In any name-collection state, prepend rich spelling hints
    if state in ("ASK_FIRST", "SPELL_FIRST", "ASK_LAST", "SPELL_LAST",
                 "CANCEL_FIRST", "RESCHEDULE_FIRST",
                 "CANCEL_LAST", "RESCHEDULE_LAST"):
        return HINTS_SPELL + ", " + base
    return base


def _is_call_done(agent: HospitalAgent, reply: str, lang: str) -> bool:
    """Primary: agent.state == CHOOSE_LANG means reset() was called after booking/cancel."""
    if agent.state == "CHOOSE_LANG":
        return True
    r = reply.lower()
    if lang == "hi":
        phrases = [
            "confirm ho gayi", "cancel kar di gayi",
            "safaltapoorvak cancel", "anand hospital mein call karne ka shukriya",
        ]
    else:
        phrases = [
            "is confirmed", "has been cancelled",
            "successfully cancelled", "thank you for calling anand hospital",
        ]
    return any(p in r for p in phrases)




@app.route("/")
def home():
    return "ADAM Voice Agent Server is running. v4.0 — Profile + Reschedule + Emergency Triage enabled."


TWILIO_OWN_NUMBER = "+12182922989"
_SIDECAR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_pending_patient.json")


def _read_sidecar() -> str:
    try:
        with open(_SIDECAR) as f:
            return json.load(f).get("patient", "").strip()
    except Exception:
        return ""


@app.route("/voice", methods=["GET", "POST"])
def voice():
    call_sid = request.values.get("CallSid", "UNKNOWN")
    from_num = request.values.get("From", "").strip()
    to_num   = request.values.get("To",   "").strip()

    print(f"\n{'='*50}")
    print(f"NEW CALL — SID : {call_sid}")
    print(f"  From         : {from_num!r}")
    print(f"  To           : {to_num!r}")

    # Layer 1: ?patient= query param
    caller_number = request.args.get("patient", "").strip()

    # Layer 2: sidecar JSON
    if not caller_number or caller_number == TWILIO_OWN_NUMBER:
        caller_number = _read_sidecar()

    # Layer 3: From/To heuristic
    if not caller_number or caller_number == TWILIO_OWN_NUMBER:
        caller_number = to_num if from_num == TWILIO_OWN_NUMBER else from_num

    if caller_number == TWILIO_OWN_NUMBER:
        caller_number = ""

    print(f"  Final caller : {caller_number!r}")
    print(f"{'='*50}")

    # Fresh agent + session for every new call — pass call_sid so LLM state is keyed correctly
    agent = HospitalAgent(call_sid)
    agent.set_phone(caller_number)
    agents[call_sid]        = agent
    call_sessions[call_sid] = {"lang": None, "done": False, "from": caller_number}
    _transcripts[call_sid]  = []

    opening_en = (
        "Hello, welcome to Anand Hospital. This is ADAM. "
        "Would you prefer to speak in English or Hindi?"
    )
    opening_hi = "Kripya English ya Hindi chunein."

    _log(call_sid, "ADAM", opening_en + " " + opening_hi)
    print(f"ADAM : {opening_en} {opening_hi}")

    resp   = VoiceResponse()
    gather = Gather(
        input         = "speech dtmf",
        timeout       = 8,
        action        = f"/choose_language?call_sid={call_sid}",
        method        = "POST",
        speechModel   = "phone_call",
        hints         = HINTS_LANG,
        bargeIn       = True,
        numDigits     = 1,
        speechTimeout = "auto",
    )
    gather.say(opening_en, voice=VOICE_EN, language=LANG_EN)
    gather.say(opening_hi, voice=VOICE_HI, language=LANG_HI)
    resp.append(gather)
    resp.redirect("/voice")
    return str(resp)


@app.route("/choose_language", methods=["POST"])
def choose_language():
    call_sid = request.args.get("call_sid", "UNKNOWN")
    speech   = request.values.get("SpeechResult", "").strip().lower()
    digit    = request.values.get("Digits", "").strip()

    print(f"LANG CHOICE — speech: {speech!r}  digit: {digit!r}")

    lang = None
    if digit == "1" or any(w in speech for w in ["english", "one", "angreji"]):
        lang = "en"
    elif digit == "2" or any(w in speech for w in ["hindi", "two", "hindi mein", "hindi me"]):
        lang = "hi"

    resp = VoiceResponse()

    if lang is None:
        retry_en = "I am sorry, I did not catch that. Please say English or Hindi."
        retry_hi = "Ya 1 dabayein English ke liye, 2 dabayein Hindi ke liye."
        _log(call_sid, "ADAM", retry_en + " " + retry_hi)
        gather = Gather(
            input         = "speech dtmf",
            timeout       = 8,
            action        = f"/choose_language?call_sid={call_sid}",
            method        = "POST",
            hints         = HINTS_LANG,
            bargeIn       = True,
            numDigits     = 1,
            speechTimeout = "auto",
        )
        gather.say(retry_en, voice=VOICE_EN, language=LANG_EN)
        gather.say(retry_hi, voice=VOICE_HI, language=LANG_HI)
        resp.append(gather)
        resp.redirect(f"/choose_language?call_sid={call_sid}", method="POST")
        return str(resp)

    # Language chosen
    from_num_saved = call_sessions.get(call_sid, {}).get("from", "")
    call_sessions[call_sid] = {"lang": lang, "done": False, "from": from_num_saved}

    agent = get_agent(call_sid)
    agent.set_language(lang)
    hints = _get_hints(agent, lang)   # state-aware (START state at this point)

    llm.set_lang(lang)
    llm.set_context({})

    if lang == "hi":
        hint  = "Shukriya. Hum Hindi mein baat karenge. Main aapki kaise madad kar sakta hoon?"
    else:
        hint  = "Thank you for choosing English. How may I assist you today?"

    reply = llm.generate_response("language confirmed, greeting patient", hint)
    print(f"  [greeting] {reply}")

    _log(call_sid, "USER", f"[chose {lang.upper()}]")
    _log(call_sid, "ADAM", reply)
    print(f"USER : [chose {lang.upper()}]")
    print(f"ADAM : {reply}")

    gather = Gather(
        input         = "speech",
        timeout       = 8,
        action        = f"/process?call_sid={call_sid}",
        method        = "POST",
        speechModel   = "phone_call",
        hints         = hints,
        bargeIn       = True,
        speechTimeout = "auto",
    )
    say(gather, reply, lang=lang)
    resp.append(gather)
    return str(resp)


@app.route("/process", methods=["GET", "POST"])
def process():
    call_sid    = request.args.get("call_sid", "UNKNOWN")
    user_text   = request.values.get("SpeechResult", "").strip()
    call_status = request.values.get("CallStatus", "")

    lang  = call_sessions.get(call_sid, {}).get("lang", "en")
    agent = get_agent(call_sid)
    hints = _get_hints(agent, lang)   # state-aware hints

    resp = VoiceResponse()

    if call_status in ("completed", "busy", "no-answer", "failed"):
        _save_transcript(call_sid)
        cleanup(call_sid)
        return str(resp)

    if not user_text:
        reply = agent.get_repeat_prompt()
        print("USER : [silence]")
        print(f"ADAM : [silence→repeat] {reply}")
        _log(call_sid, "USER", "[silence]")
        _log(call_sid, "ADAM", reply)

        gather = Gather(
            input         = "speech",
            timeout       = 8,
            action        = f"/process?call_sid={call_sid}",
            method        = "POST",
            speechModel   = "phone_call",
            hints         = hints,
            bargeIn       = True,
            speechTimeout = "auto",
        )
        say(gather, reply, lang=lang)
        resp.append(gather)
        resp.redirect(f"/process?call_sid={call_sid}", method="POST")
        return str(resp)

    print(f"USER : {user_text}")
    _log(call_sid, "USER", user_text)

    try:
        reply = agent.handle(user_text)
    except Exception as e:
        print(f"  [agent.handle error]: {e}")
        import traceback
        traceback.print_exc()
        reply = (
            "Kshama karein, kuch galat ho gaya. Kripya dobara kahein."
            if lang == "hi" else
            "I am sorry, something went wrong. Could you please repeat?"
        )

    print(f"ADAM : {reply}")
    _log(call_sid, "ADAM", reply)

    is_done = _is_call_done(agent, reply, lang)

    if is_done:
        call_sessions[call_sid]["done"] = True
        resp = VoiceResponse()
        say(resp, reply, lang=lang)
        resp.redirect(f"/goodbye?call_sid={call_sid}", method="POST")
        return str(resp)

    if call_sessions.get(call_sid, {}).get("done"):
        resp = VoiceResponse()
        resp.redirect(f"/goodbye?call_sid={call_sid}", method="POST")
        return str(resp)

    # After handling, refresh hints because state may have changed
    hints = _get_hints(agent, lang)

    gather = Gather(
        input         = "speech",
        timeout       = 8,
        action        = f"/process?call_sid={call_sid}",
        method        = "POST",
        speechModel   = "phone_call",
        hints         = hints,
        bargeIn       = True,
        speechTimeout = "auto",
    )
    say(gather, reply, lang=lang)
    resp.append(gather)
    resp.redirect(f"/process?call_sid={call_sid}", method="POST")
    return str(resp)


@app.route("/goodbye", methods=["GET", "POST"])
def goodbye():
    call_sid = request.args.get("call_sid", "UNKNOWN")
    lang = call_sessions.get(call_sid, {}).get("lang", "en") or "en"

    if lang == "hi":
        hint = "Dhanyavaad. Anand Hospital mein aapka swagat rahega. Alvida aur apna dhyan rakhein!"
    else:
        hint = "Thank you for calling Anand Hospital. Goodbye and take care!"

    llm.set_lang(lang)
    farewell = llm.generate_response("call ending, saying farewell", hint)
    print(f"ADAM : [GOODBYE] {farewell}")
    _log(call_sid, "ADAM", farewell)
    _save_transcript(call_sid)
    cleanup(call_sid)

    resp = VoiceResponse()
    say(resp, farewell, lang=lang)
    resp.hangup()
    return str(resp)


@app.route("/status", methods=["POST"])
def call_status():
    call_sid = request.values.get("CallSid", "UNKNOWN")
    status   = request.values.get("CallStatus", "")
    print(f"Call {call_sid} status: {status}")
    if status in ("completed", "busy", "no-answer", "failed"):
        _save_transcript(call_sid)
        cleanup(call_sid)
    return "", 204


@app.route("/transcript", methods=["GET"])
def view_transcript():
    if not os.path.exists(TRANSCRIPT_FILE):
        return "<pre>No transcripts yet.</pre>"
    with open(TRANSCRIPT_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    return f"<pre style='font-family:monospace;font-size:14px'>{content}</pre>"


@app.route("/test-sms", methods=["GET"])
def test_sms():
    from hospital_agent import send_sms
    lang  = request.args.get("lang", "en")
    phone = _read_sidecar()
    if not phone:
        return "<pre>ERROR: No patient number found. Run make_call.py first.</pre>", 400

    test_data = {
        "first_name": "Test",
        "last_name":  "User",
        "doctor":     "Dr Mehta",
        "date":       "21 April",
        "time":       "10:00 AM",
    }
    print(f"[test-sms] Sending {lang.upper()} SMS to {phone!r}")
    try:
        send_sms(phone, test_data, lang=lang)
        return f"<pre>SMS sent!\nTo   : {phone}\nLang : {lang.upper()}</pre>"
    except Exception as e:
        import traceback
        return f"<pre>SMS FAILED:\n{e}\n\n{traceback.format_exc()}</pre>", 500


if __name__ == "__main__":
    print(f"Transcripts : {os.path.abspath(TRANSCRIPT_FILE)}")
    app.run(port=5000, debug=False)