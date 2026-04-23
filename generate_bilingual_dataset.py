

import json
import random

# ── Data pools ────────────────────────────────────────────────────────────
FIRST_NAMES = [
    "Aarav","Aditi","Amit","Ananya","Arjun","Deepa","Divya","Gaurav",
    "Ishaan","Kavya","Kiran","Lakshmi","Manish","Meera","Mihir","Neha",
    "Nikhil","Pooja","Priya","Rahul","Raj","Riya","Rohan","Sanjay",
    "Sara","Shreya","Suresh","Tanvi","Vijay","Vikram","Vishal","Zara",
    "John","Mary","David","Lisa","Michael","Sarah","Robert","Emma",
]
LAST_NAMES = [
    "Shah","Patel","Mehta","Desai","Joshi","Sharma","Gupta","Singh",
    "Kumar","Verma","Mishra","Pandey","Yadav","Chopra","Malhotra",
    "Smith","Brown","Garcia","Johnson","Lee","Wilson","Taylor",
]

DOCTORS = {
    "neurology":   ["Dr Shah",  "Dr Reddy"],
    "general":     ["Dr Mehta", "Dr Singh"],
    "gastro":      ["Dr Patel", "Dr Verma"],
    "dermatology": ["Dr Gupta", "Dr Kapoor"],
}

SYMPTOM_TO_DEPT = {
    "headache":    "neurology",
    "migraine":    "neurology",
    "head pain":   "neurology",
    "sir dard":    "neurology",   # Hindi symptom
    "sar dard":    "neurology",   # Hindi symptom
    "fever":       "general",
    "cold":        "general",
    "flu":         "general",
    "cough":       "general",
    "bukhar":      "general",     # Hindi
    "sardi":       "general",     # Hindi
    "khansi":      "general",     # Hindi
    "stomach pain":"gastro",
    "nausea":      "gastro",
    "vomiting":    "gastro",
    "pet dard":    "gastro",      # Hindi
    "ulti":        "gastro",      # Hindi
    "skin rash":   "dermatology",
    "rash":        "dermatology",
    "itching":     "dermatology",
    "acne":        "dermatology",
    "chamdi":      "dermatology", # Hindi
    "khujli":      "dermatology", # Hindi
}

DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
TIMES = ["9:00 AM","10:00 AM","11:00 AM","12:00 PM",
         "5:00 PM","6:00 PM","7:00 PM","8:00 PM"]

# ── Language selection phrases 
LANG_CHOICES_EN = [
    "English", "one", "1", "I prefer English",
    "English please", "speak in English",
]
LANG_CHOICES_HI = [
    "Hindi", "two", "2", "Hindi mein baat karein",
    "mujhe Hindi chahiye", "Hindi please",
]

# ── English phrase pools 
EN = {
    "greet": [
        "Hello, thank you for calling Anand Hospital. This is ADAM. How may I assist you today?",
        "Good day, you have reached Anand Hospital. How can I help you?",
        "Welcome to Anand Hospital. This is ADAM speaking. What can I do for you today?",
    ],
    "lang_ask": [
        "Hello, welcome to Anand Hospital. This is ADAM. Would you prefer to speak in English or Hindi?",
        "Good day, Anand Hospital. This is ADAM. Shall we speak in English or Hindi?",
        "Welcome to Anand Hospital. I am ADAM. Do you prefer English or Hindi?",
    ],
    "lang_confirm": [
        "Great, we will continue in English. How may I assist you today?",
        "Perfect. How can I help you today?",
        "Alright, English it is. How may I help you?",
    ],
    "book_triggers": [
        "I want to book an appointment",
        "I need to see a doctor",
        "Can I make an appointment?",
        "I would like to schedule a visit",
        "I need a doctor",
        "Please book me an appointment",
        "I am not feeling well",
        "I want to visit the hospital",
        "Can I get an appointment please",
    ],
    "cancel_triggers": [
        "I want to cancel my appointment",
        "Please cancel my booking",
        "I need to cancel",
        "Cancel my appointment please",
        "I would like to cancel",
    ],
    "ask_first": [
        "Of course. What is your first name please?",
        "Sure, I can help with that. Could you tell me your first name?",
        "Certainly. May I have your first name?",
        "I would be happy to help. What is your first name?",
    ],
    "ask_spell_first": [
        "Thank you, {name}. Could you please spell your first name letter by letter?",
        "Got it, {name}. Just to confirm, could you spell your first name?",
        "I see, {name}. Could you spell that out for me please?",
    ],
    "confirm_first_ask_last": [
        "Thank you, {name}. May I have your last name please?",
        "Got it, {name}. And your last name?",
        "Perfect, {name}. What is your last name?",
    ],
    "ask_spell_last": [
        "Thank you. Could you please spell your last name?",
        "Got it. Could you spell your last name for me?",
        "Thank you. Just to confirm, please spell your last name.",
    ],
    "confirm_last_ask_symptom": [
        "Thank you, {last}. What symptoms are you experiencing?",
        "Got it, {last}. Could you describe your symptoms?",
        "Noted, {last}. What seems to be the problem today?",
    ],
    "recommend_doctors": [
        "For {symptom}, I can recommend {d1} or {d2}. Please say 1 for {d1} or 2 for {d2}.",
        "Based on your symptoms, you could see {d1} or {d2}. Which would you prefer, 1 or 2?",
        "I suggest {d1} or {d2} for {symptom}. Say 1 for {d1} or 2 for {d2}.",
    ],
    "confirm_doctor_ask_day": [
        "Noted, {doctor} it is. Which day would you like to visit?",
        "Great, I have noted {doctor}. What day works best for you?",
        "Alright, {doctor}. Which day would you prefer?",
    ],
    "ask_time": [
        "Sure, {date} is noted. Available times are {slots}. What time works for you?",
        "Alright, {date}. I have slots at {slots}. Which time do you prefer?",
        "Got it, {date}. Available times: {slots}. What time would you like?",
    ],
    "ask_confirm": [
        "Just to confirm, your appointment with {doctor} on {date} at {time}. Shall I go ahead?",
        "To recap: {doctor}, {date}, {time}. Would you like me to confirm this booking?",
        "I have {doctor} on {date} at {time}. Is that correct? Please say yes or no.",
    ],
    "booking_done": [
        "Your appointment with {doctor} on {date} at {time} is confirmed. We look forward to seeing you.",
        "All done! {doctor} on {date} at {time}. See you then.",
        "Booked successfully. {doctor} is expecting you on {date} at {time}.",
    ],
    "cancelled": [
        "Your appointment has been successfully cancelled. Thank you for letting us know.",
        "Done, your appointment has been cancelled. Please call us if you need to rebook.",
        "Cancelled successfully. Is there anything else I can help with?",
    ],
    "not_found": [
        "I am sorry, I could not find any appointment under that name. Please verify and call us again.",
        "No appointment was found under that name. Please double check and try again.",
    ],
    "ask_cancel_first": [
        "I can help with that. May I have your first name?",
        "Sure. Could you tell me your first name?",
        "Of course. What is your first name?",
    ],
    "ask_cancel_last": [
        "Thank you, {first}. And your last name?",
        "Got it, {first}. What is your last name?",
        "Thank you, {first}. Could I have your last name?",
    ],
}

# ── Hindi phrase pools 
HI = {
    "greet": [
        "Namaste, Anand Hospital mein aapka swagat hai. Main ADAM hoon. Main aapki kaise madad kar sakta hoon?",
        "Namaskar, aap Anand Hospital se baat kar rahe hain. Main aapki kya seva kar sakta hoon?",
        "Hello, Anand Hospital. Main ADAM bol raha hoon. Aapki kaise sahayata kar sakta hoon?",
    ],
    "lang_ask": [
        "Namaste, Anand Hospital mein aapka swagat hai. Main ADAM hoon. Aap English mein baat karenge ya Hindi mein?",
        "Namaskar, Anand Hospital. Main ADAM hoon. Kya aap English ya Hindi mein baat karna chahenge?",
        "Hello, main ADAM hoon. Aapko English pasand hai ya Hindi?",
    ],
    "lang_confirm": [
        "Shukriya. Hum Hindi mein baat karte hain. Main aapki kaise madad kar sakta hoon?",
        "Bilkul. Main aapki kya madad kar sakta hoon?",
        "Theek hai, Hindi mein baat karte hain. Aapki kya seva kar sakta hoon?",
    ],
    "book_triggers": [
        "Appointment book karni hai",
        "Mujhe doctor se milna hai",
        "Kya main appointment le sakta hoon",
        "Mujhe visit schedule karna hai",
        "Mujhe doctor chahiye",
        "Please meri appointment book karein",
        "Main theek nahi hoon",
        "Hospital aana chahta hoon",
    ],
    "cancel_triggers": [
        "Meri appointment cancel karni hai",
        "Please meri booking cancel karein",
        "Mujhe cancel karna hai",
        "Appointment cancel kar do please",
        "Main cancel karna chahta hoon",
    ],
    "ask_first": [
        "Bilkul. Kya aap apna pehla naam bata sakte hain?",
        "Zaroor, main madad karta hoon. Aapka pehla naam kya hai?",
        "Haan. Kripya apna pehla naam batayein.",
        "Main khushi se madad karoonga. Aapka pehla naam?",
    ],
    "ask_spell_first": [
        "Shukriya, {name}. Kya aap apna pehla naam ek ek akshar mein spell kar sakte hain?",
        "Theek hai, {name}. Confirm karne ke liye, kripya apna naam spell karein.",
        "Samajh gaya, {name}. Kya aap ek ek akshar mein bolenge?",
    ],
    "confirm_first_ask_last": [
        "Shukriya, {name}. Kya aap apna aakhiri naam bata sakte hain?",
        "Theek hai, {name}. Aur aapka aakhiri naam?",
        "Perfect, {name}. Aapka aakhiri naam kya hai?",
    ],
    "ask_spell_last": [
        "Shukriya. Kya aap apna aakhiri naam spell kar sakte hain?",
        "Theek hai. Kripya apna aakhiri naam spell karein.",
        "Shukriya. Confirm karne ke liye, apna aakhiri naam spell karein.",
    ],
    "confirm_last_ask_symptom": [
        "Shukriya, {last}. Aapko kya takleef ho rahi hai?",
        "Theek hai, {last}. Kya aap apne lakshan bata sakte hain?",
        "Noted, {last}. Aaj aapko kya problem hai?",
    ],
    "recommend_doctors": [
        "{symptom} ke liye main {d1} ya {d2} ki salah doonga. {d1} ke liye 1 kahein ya {d2} ke liye 2.",
        "Aapke lakshan ke hisaab se aap {d1} ya {d2} se mil sakte hain. Kaun sa chahiye, 1 ya 2?",
        "Main {d1} ya {d2} suggest karta hoon {symptom} ke liye. {d1} ke liye 1 ya {d2} ke liye 2 kahein.",
    ],
    "confirm_doctor_ask_day": [
        "Theek hai, {doctor} note kar liya. Aap kis din aana chahte hain?",
        "Bahut achha, {doctor} noted. Aapke liye kaunsa din theek rahega?",
        "Alright, {doctor}. Aap kaunse din aana pasand karenge?",
    ],
    "ask_time": [
        "Theek hai, {date} note kar liya. Upalabdh samay hain {slots}. Aap kaunsa samay chahenge?",
        "Samajh gaya, {date}. Mere paas {slots} ke slot hain. Kaunsa samay aapko pasand hai?",
        "Got it, {date}. Upalabdh samay: {slots}. Aap kab aana chahenge?",
    ],
    "ask_confirm": [
        "Confirm karne ke liye, aapki appointment {doctor} ke saath {date} ko {time} baje hai. Kya main aage badhoon?",
        "Summary: {doctor}, {date}, {time} baje. Kya aap is booking ki pushti karna chahte hain?",
        "Mere paas {doctor} ka {date} ko {time} baje ka slot hai. Kya yeh sahi hai? Haan ya nahi kahein.",
    ],
    "booking_done": [
        "Aapki appointment {doctor} ke saath {date} ko {time} baje confirm ho gayi. Aapka intezaar rahega.",
        "Ho gaya! {doctor} ke saath {date} ko {time} baje. Milte hain.",
        "Booking safal rahi. {doctor} aapka {date} ko {time} baje intezaar karenge.",
    ],
    "cancelled": [
        "Aapki appointment safaltapoorvak cancel kar di gayi. Shukriya.",
        "Ho gaya, aapki appointment cancel kar di gayi. Dobara book karna ho toh call karein.",
        "Booking remove kar di gayi. Kya main aur kuch madad kar sakta hoon?",
    ],
    "not_found": [
        "Maafi chahta hoon, us naam se koi appointment nahi mili. Kripya verify karke dobara call karein.",
        "Us naam se koi booking nahi mili. Kripya dobara check karein.",
    ],
    "ask_cancel_first": [
        "Main isme madad kar sakta hoon. Kya aap apna pehla naam bata sakte hain?",
        "Zaroor. Aapka pehla naam kya hai?",
        "Bilkul. Apna pehla naam batayein.",
    ],
    "ask_cancel_last": [
        "Shukriya, {first}. Aur aapka aakhiri naam?",
        "Theek hai, {first}. Aapka aakhiri naam kya hai?",
        "Shukriya, {first}. Kripya aakhiri naam batayein.",
    ],
}


# ── Helper 
def p(pool, lang, **kwargs):
    """Pick a random phrase from pool[lang][key] and format it."""
    text = random.choice(pool[lang])
    if kwargs:
        text = text.format(**kwargs)
    return text


def pick(pool_key, lang, **kwargs):
    pool = HI[pool_key] if lang == "hi" else EN[pool_key]
    text = random.choice(pool)
    if kwargs:
        text = text.format(**kwargs)
    return text


# ── Conversation builders 

def build_language_selection(lang):
    """
    Build the language selection opener.
    lang = "en" or "hi"
    """
    msgs = []
    # ADAM asks language preference
    lang_ask = random.choice(EN["lang_ask"])   # always English first
    msgs.append({"role": "assistant", "content": lang_ask})

    # User chooses
    if lang == "en":
        msgs.append({"role": "user", "content": random.choice(LANG_CHOICES_EN)})
        msgs.append({"role": "assistant", "content": pick("lang_confirm", "en")})
    else:
        msgs.append({"role": "user", "content": random.choice(LANG_CHOICES_HI)})
        msgs.append({"role": "assistant", "content": pick("lang_confirm", "hi")})

    return msgs


def build_booking(lang):
    msgs = []
    first   = random.choice(FIRST_NAMES)
    last    = random.choice(LAST_NAMES)

    # Pick a symptom appropriate for the language
    if lang == "hi":
        all_symptoms = list(SYMPTOM_TO_DEPT.keys())
    else:
        # English only symptoms (no Hinglish)
        all_symptoms = [s for s in SYMPTOM_TO_DEPT if not any(
            c in s for c in ["dard","sardi","khansi","bukhar","ulti","chamdi","khujli","pet"]
        )]
    symptom = random.choice(all_symptoms)
    dept    = SYMPTOM_TO_DEPT[symptom]
    doctors = DOCTORS[dept]
    doctor  = random.choice(doctors)
    d1, d2  = doctors[0], doctors[1]
    day     = random.choice(DAYS)
    time    = random.choice(TIMES)
    doc_num = "1" if doctor == d1 else "2"
    slots   = "9 AM, 10 AM, 11 AM, 12 PM, 5 PM, 6 PM, 7 PM, 8 PM"

    # Language selection header (70% of conversations)
    if random.random() < 0.7:
        msgs += build_language_selection(lang)

    # Booking intent
    msgs.append({"role": "user",      "content": pick("book_triggers", lang)})
    msgs.append({"role": "assistant", "content": pick("ask_first", lang)})

    # First name
    if lang == "hi":
        first_said = random.choice([first, f"Mera naam {first} hai", f"Main {first} hoon"])
    else:
        first_said = random.choice([first, f"My name is {first}", f"It's {first}", f"I am {first}"])
    msgs.append({"role": "user",      "content": first_said})
    msgs.append({"role": "assistant", "content": pick("ask_spell_first", lang, name=first)})

    # Spell first name
    msgs.append({"role": "user",      "content": " ".join(list(first.lower()))})
    msgs.append({"role": "assistant", "content": pick("confirm_first_ask_last", lang, name=first)})

    # Last name
    if lang == "hi":
        last_said = random.choice([last, f"Mera aakhiri naam {last} hai", last])
    else:
        last_said = random.choice([last, f"My last name is {last}", last])
    msgs.append({"role": "user",      "content": last_said})
    msgs.append({"role": "assistant", "content": pick("ask_spell_last", lang)})

    # Spell last name
    msgs.append({"role": "user",      "content": " ".join(list(last.lower()))})
    msgs.append({"role": "assistant", "content": pick("confirm_last_ask_symptom", lang, last=last)})

    # Symptom
    if lang == "hi":
        symptom_said = f"Mujhe {symptom} hai"
    else:
        symptom_said = f"I have {symptom}"
    msgs.append({"role": "user",      "content": symptom_said})
    msgs.append({"role": "assistant", "content": pick("recommend_doctors", lang, symptom=symptom, d1=d1, d2=d2)})

    # Doctor choice
    msgs.append({"role": "user",      "content": random.choice([doc_num, f"option {doc_num}", doctor])})
    msgs.append({"role": "assistant", "content": pick("confirm_doctor_ask_day", lang, doctor=doctor)})

    # Day
    msgs.append({"role": "user",      "content": day})
    msgs.append({"role": "assistant", "content": pick("ask_time", lang, date=day, slots=slots)})

    # Time
    time_said = random.choice([time, time.replace(":00",""), time.lower()])
    msgs.append({"role": "user",      "content": time_said})
    msgs.append({"role": "assistant", "content": pick("ask_confirm", lang, doctor=doctor, date=day, time=time)})

    # Confirm
    if lang == "hi":
        yes = random.choice(["Haan","Haan please","Confirm karein","Sahi hai","Aage badhein"])
    else:
        yes = random.choice(["Yes","Yes please","Confirm","That's correct","Go ahead"])
    msgs.append({"role": "user",      "content": yes})
    msgs.append({"role": "assistant", "content": pick("booking_done", lang, doctor=doctor, date=day, time=time)})

    return msgs


def build_cancellation(lang):
    msgs = []
    first = random.choice(FIRST_NAMES)
    last  = random.choice(LAST_NAMES)

    if random.random() < 0.6:
        msgs += build_language_selection(lang)

    msgs.append({"role": "user",      "content": pick("cancel_triggers", lang)})
    msgs.append({"role": "assistant", "content": pick("ask_cancel_first", lang)})
    msgs.append({"role": "user",      "content": first})
    msgs.append({"role": "assistant", "content": pick("ask_cancel_last", lang, first=first)})
    msgs.append({"role": "user",      "content": last})

    if random.random() < 0.8:
        msgs.append({"role": "assistant", "content": pick("cancelled", lang)})
    else:
        msgs.append({"role": "assistant", "content": pick("not_found", lang)})

    return msgs


def build_lang_selection_only(lang):
    """Just the language selection + first question, no full booking."""
    msgs = build_language_selection(lang)
    msgs.append({"role": "user",      "content": pick("book_triggers", lang)})
    msgs.append({"role": "assistant", "content": pick("ask_first", lang)})
    return msgs


# ── Generate ──────────────────────────────────────────────────────────────
def generate(n=40000, out="bilingual_hospital_dataset.jsonl"):
    counts = {"en_book": 0, "hi_book": 0, "en_cancel": 0,
              "hi_cancel": 0, "lang_only": 0}

    with open(out, "w", encoding="utf-8") as f:
        for _ in range(n):
            r = random.random()

            if r < 0.30:
                msgs = build_booking("en")
                counts["en_book"] += 1
            elif r < 0.60:
                msgs = build_booking("hi")
                counts["hi_book"] += 1
            elif r < 0.72:
                msgs = build_cancellation("en")
                counts["en_cancel"] += 1
            elif r < 0.84:
                msgs = build_cancellation("hi")
                counts["hi_cancel"] += 1
            else:
                lang = random.choice(["en", "hi"])
                msgs = build_lang_selection_only(lang)
                counts["lang_only"] += 1

            f.write(json.dumps({"messages": msgs}, ensure_ascii=False) + "\n")

    print(f"\nGenerated {n} conversations → {out}")
    print(f"  English booking  : {counts['en_book']:,}")
    print(f"  Hindi booking    : {counts['hi_book']:,}")
    print(f"  English cancel   : {counts['en_cancel']:,}")
    print(f"  Hindi cancel     : {counts['hi_cancel']:,}")
    print(f"  Lang select only : {counts['lang_only']:,}")

    # Show samples
    print("\n--- SAMPLE: English Booking ---")
    for m in build_booking("en")[:6]:
        print(f"  [{m['role'].upper():9}]: {m['content']}")

    print("\n--- SAMPLE: Hindi Booking ---")
    for m in build_booking("hi")[:6]:
        print(f"  [{m['role'].upper():9}]: {m['content']}")

    print("\n--- SAMPLE: Language Selection ---")
    for m in build_lang_selection_only("hi"):
        print(f"  [{m['role'].upper():9}]: {m['content']}")


if __name__ == "__main__":
    generate(40000, "bilingual_hospital_dataset.jsonl")
    