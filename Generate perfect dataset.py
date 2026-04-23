import json
import random

# ── Data pools ─────────────────────────────────────────────────────────────
FIRST_NAMES = [
    "Aarav","Aditi","Amit","Ananya","Arjun","Deepa","Divya","Gaurav",
    "Ishaan","Kavya","Kiran","Lakshmi","Manish","Meera","Mihir","Neha",
    "Nikhil","Pooja","Priya","Rahul","Raj","Riya","Rohan","Sanjay",
    "Sara","Shreya","Suresh","Tanvi","Vijay","Vikram","Vishal","Zara",
    "John","Mary","David","Lisa","Michael","Sarah","Robert","Emma",
    "James","Jennifer","William","Patricia","Charles","Linda","Thomas"
]
LAST_NAMES = [
    "Shah","Patel","Mehta","Desai","Joshi","Sharma","Gupta","Singh",
    "Kumar","Verma","Mishra","Pandey","Yadav","Chopra","Malhotra",
    "Smith","Brown","Garcia","Johnson","Lee","Wilson","Taylor","Anderson"
]

DOCTORS = {
    "neurology":   ["Dr Shah", "Dr Reddy"],
    "general":     ["Dr Mehta", "Dr Singh"],
    "gastro":      ["Dr Patel", "Dr Verma"],
    "dermatology": ["Dr Gupta", "Dr Kapoor"],
}
SYMPTOM_TO_DEPT = {
    "headache": "neurology", "migraine": "neurology", "head pain": "neurology",
    "fever": "general", "cold": "general", "flu": "general", "cough": "general",
    "stomach pain": "gastro", "stomach ache": "gastro", "gas trouble": "gastro", "nausea": "gastro",
    "skin rash": "dermatology", "rash": "dermatology", "itching": "dermatology", "acne": "dermatology",
}
DAYS   = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
TIMES  = ["9:00 AM","10:00 AM","11:00 AM","12:00 PM","5:00 PM","6:00 PM","7:00 PM","8:00 PM"]

# ── Varied phrasings ───────────────────────────────────────────────────────
BOOK_TRIGGERS = [
    "I want to book an appointment",
    "I need to see a doctor",
    "Can I make an appointment?",
    "I'd like to schedule a visit",
    "I want to fix an appointment",
    "Please book me an appointment",
    "I need a doctor's appointment",
    "Can you help me book a slot?",
    "I am not feeling well, I need to see a doctor",
    "Hello, I need medical help",
    "I want to visit the hospital",
    "Can I get an appointment please",
    "I need to consult a doctor",
]
CANCEL_TRIGGERS = [
    "I want to cancel my appointment",
    "Please cancel my booking",
    "I need to cancel my appointment",
    "Cancel my appointment please",
    "I would like to cancel",
    "Can you cancel my slot?",
    "I won't be able to come, please cancel",
    "Please remove my appointment",
]
GREETINGS = [
    "Hello", "Hi", "Good morning", "Good afternoon",
    "Hello, is this the hospital?", "Hi there",
]

# ── Natural reply variants ─────────────────────────────────────────────────
def greet_and_offer():
    return random.choice([
        "Hello, thank you for calling Anand Hospital. This is ADAM. How may I assist you today?",
        "Good day, you have reached Anand Hospital. How can I help you?",
        "Welcome to Anand Hospital. This is ADAM speaking. What can I do for you today?",
        "Hello, Anand Hospital, ADAM speaking. How may I help you?",
    ])

def ask_first_name():
    return random.choice([
        "Of course, I'd be happy to help. May I have your first name please?",
        "Sure, I can help with that. Could you please tell me your first name?",
        "Certainly. May I start with your first name?",
        "Of course. What is your first name please?",
        "I'll be glad to help. Could I have your first name?",
    ])

def ask_spell_first(name):
    return random.choice([
        f"Thank you, {name}. Could you please spell your first name letter by letter?",
        f"Got it, {name}. Just to confirm, could you spell your first name for me?",
        f"I see, {name}. Could you spell that out for me please?",
        f"Thank you. To confirm, could you spell your first name?",
    ])

def confirm_first_ask_last(name):
    return random.choice([
        f"Thank you, {name}. May I have your last name please?",
        f"Got it, {name}. And your last name?",
        f"Perfect, {name}. What is your last name?",
        f"Thank you, {name}. Could you tell me your last name?",
    ])

def ask_spell_last(name):
    return random.choice([
        f"Thank you, {name}. Could you please spell your last name?",
        f"Got it. Could you spell your last name for me?",
        f"Thank you. Just to confirm, please spell your last name.",
    ])

def confirm_last_ask_symptom(last):
    return random.choice([
        f"Thank you, {last}. What symptoms are you experiencing?",
        f"Got it, {last}. Could you describe your symptoms?",
        f"Noted, {last}. What seems to be the problem today?",
        f"Thank you. What are your symptoms?",
    ])

def recommend_doctors(symptom, d1, d2):
    return random.choice([
        f"For {symptom}, I can recommend Dr {d1.split()[1]} or Dr {d2.split()[1]}. Please say 1 for {d1} or 2 for {d2}.",
        f"Based on your symptoms, you could see {d1} or {d2}. Which would you prefer, 1 or 2?",
        f"I suggest {d1} or {d2} for {symptom}. Say 1 for {d1} or 2 for {d2}.",
    ])

def confirm_doctor_ask_day(doctor):
    return random.choice([
        f"Noted, {doctor} it is. Which day would you like to visit?",
        f"Great, I have noted {doctor}. What day works best for you?",
        f"Alright, {doctor}. Which day would you prefer?",
    ])

def ask_time(date):
    slots = "9 AM, 10 AM, 11 AM, 12 PM, 5 PM, 6 PM, 7 PM, or 8 PM"
    return random.choice([
        f"Sure, {date} is noted. Available times are {slots}. What time works for you?",
        f"Alright, {date}. I have slots at {slots}. Which time do you prefer?",
        f"Got it, {date}. Available times: {slots}. What time would you like?",
    ])

def ask_confirm(doctor, date, time):
    return random.choice([
        f"Just to confirm, your appointment with {doctor} on {date} at {time}. Shall I go ahead?",
        f"To recap: {doctor}, {date}, {time}. Would you like me to confirm this booking?",
        f"I have {doctor} on {date} at {time}. Is that correct? Please say yes or no.",
        f"Your appointment: {doctor}, {date} at {time}. Shall I confirm?",
    ])

def booking_done(doctor, date, time):
    return random.choice([
        f"Your appointment with {doctor} on {date} at {time} is confirmed. We look forward to seeing you.",
        f"All done! {doctor} on {date} at {time}. See you then.",
        f"Booked successfully. {doctor} is expecting you on {date} at {time}.",
        f"Your appointment is confirmed with {doctor} on {date} at {time}. Thank you for calling.",
    ])

def cancelled():
    return random.choice([
        "Your appointment has been successfully cancelled. Thank you for letting us know.",
        "Done, your appointment has been cancelled. Please call us if you need to rebook.",
        "Your booking has been removed. Have a good day.",
        "Cancelled successfully. Is there anything else I can help with?",
    ])

def not_found():
    return random.choice([
        "I'm sorry, I couldn't find any appointment under that name. Could you double-check?",
        "I don't see a booking for that name. Please verify and call us again.",
        "No appointment was found. You may not have a booking with us.",
    ])

def ask_cancel_first():
    return random.choice([
        "I can help with that. May I have your first name?",
        "Sure, to locate your booking, could you tell me your first name?",
        "Of course. What is your first name?",
    ])

def ask_cancel_last(first):
    return random.choice([
        f"Thank you, {first}. And your last name?",
        f"Got it, {first}. What is your last name?",
    ])

# ── Conversation builders ──────────────────────────────────────────────────

def build_booking():
    msgs = []
    first = random.choice(FIRST_NAMES)
    last  = random.choice(LAST_NAMES)
    symptom = random.choice(list(SYMPTOM_TO_DEPT.keys()))
    dept    = SYMPTOM_TO_DEPT[symptom]
    doctors = DOCTORS[dept]
    doctor  = random.choice(doctors)
    d1, d2  = doctors[0], doctors[1]
    day     = random.choice(DAYS)
    time    = random.choice(TIMES)
    doc_num = "1" if doctor == d1 else "2"

    # Optional greeting before booking intent
    if random.random() < 0.3:
        msgs.append({"role": "user",      "content": random.choice(GREETINGS)})
        msgs.append({"role": "assistant", "content": greet_and_offer()})

    # Booking intent
    msgs.append({"role": "user",      "content": random.choice(BOOK_TRIGGERS)})
    msgs.append({"role": "assistant", "content": ask_first_name()})

    # First name (sometimes patient says full sentence)
    first_said = random.choice([
        first,
        f"My name is {first}",
        f"It's {first}",
        f"I am {first}",
    ])
    msgs.append({"role": "user",      "content": first_said})
    msgs.append({"role": "assistant", "content": ask_spell_first(first)})

    # Spell first name
    spelled_first = " ".join(list(first.lower()))
    msgs.append({"role": "user",      "content": spelled_first})
    msgs.append({"role": "assistant", "content": confirm_first_ask_last(first)})

    # Last name
    last_said = random.choice([last, f"My last name is {last}", last])
    msgs.append({"role": "user",      "content": last_said})
    msgs.append({"role": "assistant", "content": ask_spell_last(last)})

    spelled_last = " ".join(list(last.lower()))
    msgs.append({"role": "user",      "content": spelled_last})
    msgs.append({"role": "assistant", "content": confirm_last_ask_symptom(last)})

    # Symptom
    msgs.append({"role": "user",      "content": f"I have {symptom}"})
    msgs.append({"role": "assistant", "content": recommend_doctors(symptom, d1, d2)})

    # Doctor choice
    msgs.append({"role": "user",      "content": random.choice([doc_num, f"option {doc_num}", f"doctor {doc_num}"])})
    msgs.append({"role": "assistant", "content": confirm_doctor_ask_day(doctor)})

    # Day
    msgs.append({"role": "user",      "content": day})
    msgs.append({"role": "assistant", "content": ask_time(day)})

    # Time
    time_said = random.choice([time, time.replace(":00",""), time.lower()])
    msgs.append({"role": "user",      "content": time_said})
    msgs.append({"role": "assistant", "content": ask_confirm(doctor, day, time)})

    # Confirmation
    msgs.append({"role": "user",      "content": random.choice(["Yes","Yes please","Confirm","That's correct","Go ahead"])})
    msgs.append({"role": "assistant", "content": booking_done(doctor, day, time)})

    return msgs


def build_cancellation():
    msgs = []
    first = random.choice(FIRST_NAMES)
    last  = random.choice(LAST_NAMES)

    if random.random() < 0.2:
        msgs.append({"role": "user",      "content": random.choice(GREETINGS)})
        msgs.append({"role": "assistant", "content": greet_and_offer()})

    msgs.append({"role": "user",      "content": random.choice(CANCEL_TRIGGERS)})
    msgs.append({"role": "assistant", "content": ask_cancel_first()})

    msgs.append({"role": "user",      "content": first})
    msgs.append({"role": "assistant", "content": ask_cancel_last(first)})

    msgs.append({"role": "user",      "content": last})

    if random.random() < 0.8:
        msgs.append({"role": "assistant", "content": cancelled()})
    else:
        msgs.append({"role": "assistant", "content": not_found()})

    return msgs


def build_greeting_only():
    """Short greeting → offer to help conversation."""
    msgs = []
    msgs.append({"role": "user",      "content": random.choice(GREETINGS)})
    msgs.append({"role": "assistant", "content": greet_and_offer()})
    msgs.append({"role": "user",      "content": random.choice(BOOK_TRIGGERS)})
    msgs.append({"role": "assistant", "content": ask_first_name()})
    return msgs


def build_confused_user():
    """User says something unclear → agent redirects politely."""
    confused = [
        "What?", "Huh?", "I don't know", "Can you repeat?",
        "What did you say?", "Hello?", "Is anyone there?",
    ]
    redirect = [
        "I'm sorry, I didn't catch that. Could you please repeat?",
        "I apologise, could you say that again?",
        "Sorry, I couldn't understand. Could you please speak clearly?",
        "I beg your pardon, could you repeat that?",
    ]
    return [
        {"role": "user",      "content": random.choice(confused)},
        {"role": "assistant", "content": random.choice(redirect)},
    ]


# ── Generate dataset ───────────────────────────────────────────────────────

def generate(n=30000, out="perfect_hospital_dataset.jsonl"):
    with open(out, "w") as f:
        for i in range(n):
            r = random.random()
            if r < 0.60:
                msgs = build_booking()
            elif r < 0.85:
                msgs = build_cancellation()
            elif r < 0.95:
                msgs = build_greeting_only()
            else:
                msgs = build_confused_user()

            f.write(json.dumps({"messages": msgs}) + "\n")

    print(f"Generated {n} conversations → {out}")

    # Show 3 sample conversations
    print("\n--- SAMPLE 1: Booking ---")
    sample = build_booking()
    for m in sample[:8]:
        print(f"  [{m['role'].upper()}]: {m['content']}")

    print("\n--- SAMPLE 2: Cancellation ---")
    sample = build_cancellation()
    for m in sample:
        print(f"  [{m['role'].upper()}]: {m['content']}")

    print("\n--- SAMPLE 3: Greeting ---")
    sample = build_greeting_only()
    for m in sample:
        print(f"  [{m['role'].upper()}]: {m['content']}")


generate(30000, "perfect_hospital_dataset.jsonl")