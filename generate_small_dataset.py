

import json
import random

FIRST = ["John","Mary","David","Lisa","Michael","Sarah","Robert","Emma"]
LAST = ["Smith","Brown","Garcia","Johnson","Lee","Wilson"]

SYMPTOMS = [
"headache",
"fever",
"stomach pain",
"skin rash",
"back pain"
]

DOCTORS = {
"headache":"Dr Shah",
"fever":"Dr Mehta",
"stomach pain":"Dr Patel",
"skin rash":"Dr Gupta",
"back pain":"Dr Singh"
}

DATES = ["Monday","Tuesday","Wednesday","Thursday","Friday"]

TIMES = [
"9:00 AM","9:30 AM","10:00 AM","10:30 AM",
"11:00 AM","5:00 PM","5:30 PM","6:00 PM"
]


def booking():

    first=random.choice(FIRST)
    last=random.choice(LAST)

    symptom=random.choice(SYMPTOMS)
    doctor=DOCTORS[symptom]

    date=random.choice(DATES)
    time=random.choice(TIMES)

    return [
    {"role":"user","content":"I want to book an appointment"},
    {"role":"assistant","content":"Sure. May I have your first name?"},
    {"role":"user","content":first},
    {"role":"assistant","content":"Thank you. What is your last name?"},
    {"role":"user","content":last},
    {"role":"assistant","content":"What symptoms are you experiencing?"},
    {"role":"user","content":symptom},
    {"role":"assistant","content":f"I recommend {doctor}. What day would you like to visit?"},
    {"role":"user","content":date},
    {"role":"assistant","content":"What time works best for you?"},
    {"role":"user","content":time},
    {"role":"assistant","content":f"Your appointment with {doctor} is booked for {date} at {time}."}
    ]


def cancel():

    first=random.choice(FIRST)
    last=random.choice(LAST)

    return [
    {"role":"user","content":"I want to cancel my appointment"},
    {"role":"assistant","content":"Sure. May I have your first name?"},
    {"role":"user","content":first},
    {"role":"assistant","content":"What is your last name?"},
    {"role":"user","content":last},
    {"role":"assistant","content":"Your appointment has been cancelled."}
    ]


def generate(n=20000):

    with open("hospital_dataset_small.jsonl","w") as f:

        for i in range(n):

            if random.random()<0.7:
                msgs=booking()
            else:
                msgs=cancel()

            row={"messages":msgs}

            f.write(json.dumps(row)+"\n")


generate()

print("dataset created")