import json
import random
import re
from tqdm import tqdm

OUTPUT_FILE  = "instruction_dataset_v4.jsonl"
NUM_EXAMPLES = 100_000   # bumped to 100 K for better coverage

# ── Data pools ─────────────────────────────────────────────────────────────

FIRST_NAMES = [
    "Abhishek", "Priya", "Rahul", "Anjali", "Vikram", "Sunita",
    "Arjun", "Pooja", "Ravi", "Meena", "Karan", "Divya",
    "Amit", "Sneha", "Rohit", "Kavita", "Suresh", "Nisha",
    "Deepak", "Anita", "Vijay", "Rekha", "Arun", "Sonal",
    "Manish", "Pallavi", "Ajay", "Shweta", "Nikhil", "Geeta",
    "Sanjay", "Usha", "Ramesh", "Lata", "Mahesh", "Seema",
    "Harish", "Preeti", "Sunil", "Kaveri", "Rajesh", "Manju",
    # Additional names for more diversity
    "Akash", "Bhavna", "Chetan", "Deepika", "Ekta", "Farhan",
    "Gaurav", "Hema", "Ishaan", "Jyoti", "Kunal", "Lavanya",
    "Mohan", "Neha", "Om", "Payal", "Qasim", "Ritu",
    "Sachin", "Tanvi", "Umesh", "Vandana", "Wasim", "Xena",
    "Yogesh", "Zara", "Abhinav", "Bharat", "Chirag", "Dhruv",
    "Esha", "Faisal", "Girish", "Heena", "Ishan", "Jasmine",
    "Kartik", "Lakshmi", "Mukesh", "Namrata", "Omkar", "Pankaj",
]

LAST_NAMES = [
    "Soni", "Shah", "Patel", "Sharma", "Verma", "Singh",
    "Kumar", "Gupta", "Joshi", "Mehta", "Reddy", "Kapoor",
    "Malhotra", "Agarwal", "Bansal", "Trivedi", "Pandey", "Rao",
    "Nair", "Iyer", "Pillai", "Desai", "Chaudhary", "Bose",
    "Chatterjee", "Mukherjee", "Mishra", "Tiwari", "Dubey", "Yadav",
    "Patil", "Naik", "Kaur", "Gill", "Bhatia", "Arora",
    "Chopra", "Mehra", "Saha", "Das", "Dutta", "Roy",
]

DOCTORS = [
    "Dr Shah", "Dr Reddy", "Dr Mehta", "Dr Singh",
    "Dr Patel", "Dr Verma", "Dr Gupta", "Dr Kapoor",
]

DATES = [
    "1 April 2026", "2 April 2026", "5 April 2026", "10 April 2026",
    "15 April 2026", "20 April 2026", "25 April 2026", "30 April 2026",
    "3 May 2026",   "8 May 2026",   "12 May 2026",  "18 May 2026",
    "21 March 2026","28 March 2026","1 March 2026",  "15 March 2026",
    "5 June 2026",  "10 June 2026", "20 June 2026",  "30 June 2026",
]

TIMES = [
    "8:00 AM", "9:00 AM", "10:00 AM", "11:00 AM", "12:00 PM",
    "5:00 PM", "6:00 PM", "7:00 PM",  "8:00 PM",
]

SYMPTOMS_EN = [
    "headache", "migraine", "fever", "cold", "cough", "flu",
    "stomach pain", "nausea", "vomiting", "skin rash", "itching", "acne",
    "body ache", "fatigue", "sore throat", "back pain",
]

SYMPTOMS_HI = [
    "sar dard", "sir dard", "bukhar", "sardi", "khansi",
    "pet dard", "ulti", "khujli", "chamdi ki samasya",
    "kamar dard", "thakaan", "gale mein dard", "body dard",
]

DEPTS_EN = {
    "headache": "neurology", "migraine": "neurology",
    "fever": "general",     "cold": "general",
    "cough": "general",     "flu": "general",
    "stomach pain": "gastro","nausea": "gastro",
    "vomiting": "gastro",   "skin rash": "dermatology",
    "itching": "dermatology","acne": "dermatology",
    "body ache": "general", "fatigue": "general",
    "sore throat": "general","back pain": "general",
}

DEPTS_HI = {
    "sar dard": "neurology",    "sir dard": "neurology",
    "bukhar": "general",        "sardi": "general",
    "khansi": "general",        "pet dard": "gastro",
    "ulti": "gastro",           "khujli": "dermatology",
    "chamdi ki samasya": "dermatology",
    "kamar dard": "general",    "thakaan": "general",
    "gale mein dard": "general","body dard": "general",
}

SLOTS = ", ".join(TIMES)

DOBS = [
    "21/03/1990", "15/07/1985", "05/01/1978", "30/11/1995",
    "12/04/2000", "08/08/1970", "25/12/1988", "01/06/1992",
]


# ── Core hint pools ────────────────────────────────────────────────────────

def hints_en(fn, ln, doc, date, time, sym):
    d1, d2 = random.sample(DOCTORS, 2)
    return [
        # Greeting / language choice
        "Great, we will continue in English. How may I assist you today?",
        "Wonderful, let us continue in English. How may I help you today?",
        "How may I help you today? I can assist you with booking, rescheduling, or cancelling an appointment.",
        "Welcome to Anand Hospital. I am ADAM, your virtual assistant. How may I assist you today?",
        "Thank you for calling Anand Hospital. I am ADAM. Would you like to book an appointment today?",
        # Returning patient recognition — by first name
        f"Welcome back, {fn}! It is lovely to hear from you again. How may I assist you today?",
        f"Hello {fn}, wonderful to have you call us again. How may I help you today?",
        f"Good to hear from you, {fn}. How can I assist you today?",
        f"Welcome back, {fn} {ln}. How may I assist you today?",
        f"Hello again, {fn}! How may I help you today?",
        # Booking intent acknowledgement
        f"Of course, I would be happy to help you book an appointment. May I have your first name please?",
        f"Certainly! I can help you with that. Could you please tell me your first name?",
        f"I would be delighted to assist you. What is your first name, please?",
        f"Absolutely, let me help you with that. May I know your first name?",
        # ASK_FIRST
        f"Could you please tell me your first name?",
        f"May I know your first name, please?",
        f"Please go ahead and say your first name.",
        f"To get started, may I have your first name?",
        # Spell first
        f"Thank you, {fn}. Could you please spell your first name letter by letter for me?",
        f"Got it, {fn}. Would you kindly spell your first name one letter at a time?",
        f"Lovely name! Could you please spell {fn} letter by letter so I can note it correctly?",
        # ASK_LAST
        f"Thank you, {fn}. May I have your last name as well, please?",
        f"That is noted, {fn}. Could you kindly tell me your last name?",
        f"Perfect, {fn}. And what is your last name?",
        f"Wonderful, {fn}. Now may I have your last name, please?",
        # Spell last
        f"Thank you. Could you please spell your last name letter by letter?",
        f"Kindly spell your last name one letter at a time, please.",
        f"Would you mind spelling your last name for me?",
        # Symptom
        f"Thank you, {fn} {ln}. What seems to be the problem today? I am here to help.",
        f"I am sorry to hear you are not feeling well, {fn}. Could you tell me your symptoms?",
        f"Of course, {fn}. Could you please describe what you are experiencing so I can connect you with the right doctor?",
        f"I understand, {fn} {ln}. Please tell me your main symptom and I will find the right specialist for you.",
        # Doctors
        f"For {sym}, I would recommend seeing {d1} or {d2}. Please say 1 for {d1} or 2 for {d2}.",
        f"Based on your symptom, both {d1} and {d2} would be excellent choices. Which do you prefer? Say 1 or 2.",
        f"I understand. For {sym}, our {d1} specialises in this area. Say 1 for {d1} or 2 for {d2}.",
        f"I would suggest {d1} or {d2} for {sym}. Say 1 for {d1} or 2 for {d2}, whichever you prefer.",
        # Date
        f"Noted, thank you. Which date would you prefer for your appointment?",
        f"Wonderful. What date would work best for you?",
        f"Perfect. Please let me know your preferred date for the appointment.",
        f"That is great. Could you tell me which date you would like to come in?",
        # Time
        f"Perfect. The available time slots are {SLOTS}. Which time works best for you?",
        f"The following times are available: {SLOTS}. Which one would you prefer?",
        f"I have these slots open for you: {SLOTS}. Which time suits you?",
        f"Wonderful. Please choose from the available slots: {SLOTS}.",
        # Confirmation
        f"Just to confirm, {fn}, your appointment with {doc} is on {date} at {time}. Shall I go ahead and book this?",
        f"To confirm, {fn}, I have an appointment with {doc} on {date} at {time}. Is that correct?",
        f"Let me confirm the details for you: {fn}, appointment with {doc} on {date} at {time}. Shall I book this?",
        f"Wonderful, {fn}. Your appointment with {doc} on {date} at {time} is ready to confirm. Shall I proceed?",
        # Confirmed
        f"Your appointment with {doc} on {date} at {time} is confirmed. We look forward to seeing you, {fn}!",
        f"All done! Your appointment with {doc} is confirmed for {date} at {time}. Take good care, {fn}.",
        f"Wonderful! I have confirmed your appointment with {doc} on {date} at {time}. Please do take care, {fn}.",
        f"Your booking is confirmed, {fn}. {doc} will see you on {date} at {time}. We wish you good health!",
        # Cancel
        f"Your appointment has been successfully cancelled, {fn}. We hope to assist you again soon.",
        f"I have cancelled your appointment, {fn}. Please do not hesitate to call us whenever you need assistance.",
        f"Done, {fn}. Your appointment has been cancelled. Is there anything else I can help you with?",
        # Goodbye
        "Thank you for calling Anand Hospital. Goodbye and please take care!",
        "Thank you so much for calling. Have a wonderful day and do take care!",
        "It was a pleasure assisting you today. Goodbye and stay well!",
        "Thank you for reaching out to Anand Hospital. Wishing you good health. Goodbye!",
        # Repeat / clarification
        f"I am sorry, could you please say your first name again?",
        f"I did not quite catch that. Could you kindly repeat your last name?",
        f"Could you please say yes to confirm or no to cancel?",
        f"I am sorry, could you please choose a time from the available slots?",
        f"I did not hear that clearly. Could you please repeat?",
    ]


def hints_hi(fn, ln, doc, date, time, sym):
    d1, d2 = random.sample(DOCTORS, 2)
    return [
        # Greeting
        "Shukriya. Hum Hindi mein baat karte hain. Aapki kaise madad kar sakta hoon?",
        "Bahut acha. Main aapki kaise seva kar sakta hoon? Appointment book, reschedule ya cancel karwa sakte hain.",
        "Anand Hospital mein aapka swagat hai. Main ADAM hoon, aapka virtual sahayak. Aaj main aapki kya madad kar sakta hoon?",
        "Anand Hospital mein call karne ke liye dhanyavaad. Main ADAM hoon. Kripya batayein, main kaise madad kar sakta hoon?",
        # Returning patient recognition
        f"Dobara call karne ke liye shukriya, {fn} ji! Aapki kya madad kar sakta hoon?",
        f"Aapka swagat hai wapas, {fn} ji. Aaj main aapki kaise seva kar sakta hoon?",
        f"Bahut khushi hui, {fn} ji. Aaj aapki kya madad kar sakta hoon?",
        f"Namaskar {fn} ji, dobara aapar karne ke liye dhanyavaad. Kaise madad kar sakta hoon?",
        # Booking intent
        f"Bilkul, {fn} ji. Aapka pehla naam kya hai?",
        f"Zaroor madad karoonga. Kripya apna pehla naam batayein.",
        f"Khushi se aapki madad karoonga. Aapka pehla naam kya hai, kripya?",
        f"Haan ji, zaroor. Pehle kripya apna naam batayein.",
        # ASK_FIRST
        f"Kripya apna pehla naam batayein.",
        f"Aapka pehla naam kya hai, kripya?",
        f"Kripya apna naam batayein.",
        f"Shuru karne ke liye, aapka pehla naam kya hai?",
        # Spell first
        f"Shukriya, {fn} ji. Kya aap apna pehla naam ek ek akshar mein spell kar sakte hain?",
        f"Dhanyavaad, {fn} ji. Kripya apna pehla naam ek ek akshar mein bolein taki main sahi note kar sakoon.",
        f"Bahut acha, {fn} ji. Kripya naam ko akshar akshar bolein.",
        # ASK_LAST
        f"Shukriya, {fn} ji. Kripya ab apna aakhiri naam bhi batayein.",
        f"Bilkul, {fn} ji. Aur aapka aakhiri naam kya hai?",
        f"Shukriya, {fn} ji. Ab aakhiri naam bata sakte hain kripya?",
        f"Bahut acha, {fn} ji. Kripya apna surname batayein.",
        # Spell last
        f"Dhanyavaad. Kripya ab apna aakhiri naam bhi ek ek akshar mein spell karein.",
        f"Shukriya. Kripya surname akshar akshar bolein.",
        f"Aakhiri naam bhi spell karein kripya, ek ek akshar mein.",
        # Symptom
        f"Shukriya, {fn} {ln} ji. Aapko kya takleef ho rahi hai? Main sahi doctor se milane mein madad karoonga.",
        f"Main samajhta hoon, {fn} ji. Kripya apni takleef batayein taki main sahi specialist se milaao.",
        f"Dukh ki baat hai, {fn} ji. Kripya bataiye kya problem hai, main aapki madad karoonga.",
        f"Bilkul, {fn} {ln} ji. Aapka lakshan kya hai? Main sahi doctor dhundhunga aapke liye.",
        # Doctors
        f"{sym} ke liye main {d1} ya {d2} ki salah doonga. {d1} ke liye 1 kahein, {d2} ke liye 2.",
        f"Aapke lakshan ke hisaab se {d1} ya {d2} se milna behtar rahega. Aap kaun sa prefer karenge?",
        f"Main samajhta hoon. {sym} ke liye {d1} ek achhe specialist hain. {d1} ke liye 1 ya {d2} ke liye 2 kahein.",
        f"Aapke liye {d1} ya {d2} mein se koi bhi accha rahega. Kaun sa doctor chahiye? 1 ya 2 kahein.",
        # Date
        f"Note kar liya, dhanyavaad. Aap kaunsi tarikh ko aana chahenge?",
        f"Bahut acha. Appointment ke liye kaunsi date prefer karenge aap?",
        f"Bilkul. Kaunsi tarikh theek rahegi aapke liye?",
        f"Shukriya. Aap kab aana chahenge? Kripya date batayein.",
        # Time
        f"Bilkul. Kripya samay chunein. Upalabdh slots hain: {SLOTS}.",
        f"Date note kar li. Kaunsa samay aapko suit karega? Upalabdh samay: {SLOTS}.",
        f"Ye slots upalabdh hain aapke liye: {SLOTS}. Aap kaunsa samay chunenge?",
        f"In mein se kaunsa samay acha rahega? {SLOTS}. Kripya batayein.",
        # Confirmation
        f"Ek baar confirm karte hain, {fn} ji. Aapki appointment {doc} ke saath {date} ko {time} baje hai. Kya aage badhoon?",
        f"Bilkul {fn} ji. {doc} ke saath {date} ko {time} baje appointment. Confirm karein?",
        f"Confirm karne ke liye: {fn} ji, {doc} ke saath, {date} ko, {time} baje. Kya sab sahi hai?",
        f"Aapki booking details: {fn} ji, {doc}, {date}, {time} baje. Kya main confirm kar doon?",
        # Confirmed
        f"Aapki appointment {doc} ke saath {date} ko {time} baje confirm ho gayi hai. Aapka swagat rahega, {fn} ji!",
        f"Ho gaya! {doc} ke saath {date} ko {time} baje aapki appointment confirm hai. Apna khayal rakhein, {fn} ji.",
        f"Bahut acha! {fn} ji, aapki appointment {doc} ke saath {date} ko {time} baje confirm ho gayi. Khyaal rakhein!",
        f"Confirm ho gaya, {fn} ji. {doc} {date} ko {time} baje milenge aapse. Hum aapka intezaar karenge!",
        # Cancel
        f"Aapki appointment safaltapoorvak cancel kar di gayi hai, {fn} ji. Jab chahein dobara call karein.",
        f"Ho gaya, {fn} ji. Aapki appointment cancel kar di gayi. Koi aur madad chahiye?",
        f"Bilkul, {fn} ji. Appointment cancel kar di gayi hai. Aage bhi madad ke liye call karein.",
        # Goodbye
        "Anand Hospital mein call karne ke liye dhanyavaad. Apna khayal rakhein. Alvida!",
        "Bahut shukriya call karne ke liye. Swasth rahein aur achha din bitayein!",
        "Aapki seva kar ke khushi hui. Alvida aur apna dhyan rakhein!",
        "Dhanyavaad, Anand Hospital mein aapka swagat rahega. Alvida!",
        # Repeat / clarification
        f"Maafi chahta hoon, kya aap apna pehla naam dobara bata sakte hain?",
        f"Mujhe sahi se nahi sunai diya. Kripya apna aakhiri naam dobara bolein.",
        f"Kripya haan ya nahi mein jawab dein.",
        f"Kripya upalabdh slots mein se samay chunein.",
        f"Maafi chahta hoon, kripya dobara bolein.",
    ]


# ── Emergency hint pools ────────────────────────────────────────────────────

def hints_emergency_en(fn=""):
    return [
        "This sounds like a medical emergency. Please call 102 for an ambulance or go to the nearest emergency room immediately.",
        "I am concerned about what you described. Please call 102 or 108 right away for emergency help.",
        "That sounds serious. For emergencies, please dial 102 immediately. If you can wait, I can connect you to our General Physician.",
        "Your safety is the priority. Please call emergency services at 102 or 108 now.",
        "This may require urgent medical attention. Please go to the nearest hospital emergency or call 102.",
        "I strongly recommend calling 102 for immediate help. Do not wait. Are you able to call now?",
        "Please call 108 for an ambulance right away. This is an emergency situation.",
        "For immediate help, dial 102 or 108. Our General Physician Dr Mehta is also available if you need an appointment.",
    ]


def hints_emergency_hi(fn=""):
    return [
        "Yeh medical emergency lag rahi hai. Turant 102 ya 108 dial karein ya najdiki hospital jayein.",
        "Aapki baat sun ke dar lag raha hai. Abhi 102 ya 108 par call karein.",
        "Yeh gambhir hai. Emergency ke liye 102 dial karein. Agar theek ho toh General Physician se appointment le sakta hoon.",
        "Aapki safety sabse pehle hai. Abhi 102 ya 108 call karein, jaldi kijiye.",
        "Fauran zamani ilaaj ki zaroorat lag rahi hai. Najdiki emergency room jayein ya 102 call karein.",
        "Main aapko 102 call karne ki salah doonga. Kya aap abhi call kar sakte hain?",
        "108 par call karein abhi — ambubaance bheji jayegi. Apna dhyan rakhein.",
        "Turant 102 ya 108 dial karein. Hamare Dr Mehta bhi general physician hain, zaroorat ho toh appointment le sakte hain.",
    ]


# ── Rescheduling hint pools ─────────────────────────────────────────────────

def hints_reschedule_en(fn, ln, doc, old_date, new_date, new_time):
    return [
        "Of course, I can help you reschedule. May I have your first name please?",
        "Sure, let me help you change your appointment. What is your first name?",
        f"Thank you {fn}. And your last name?",
        f"Got it {fn} {ln}. What new date would you prefer?",
        f"Noted. And what time would you like on {new_date}? Available slots are {SLOTS}.",
        f"Just to confirm, {fn}, your appointment with {doc} is being rescheduled to {new_date} at {new_time}. Is that correct?",
        f"Your appointment has been rescheduled to {new_date} at {new_time}. Thank you {fn}.",
        f"Done! I have moved your appointment with {doc} to {new_date} at {new_time}. Take care {fn}.",
        f"Great news {fn}. Your appointment with {doc} is now on {new_date} at {new_time}.",
        f"I could not find an appointment under that name. Could you check the name and try again?",
    ]


def hints_reschedule_hi(fn, ln, doc, old_date, new_date, new_time):
    return [
        "Bilkul, main appointment reschedule karne mein madad kar sakta hoon. Apna pehla naam batayein.",
        "Zaroor, appointment ka date badal deta hoon. Aapka pehla naam kya hai?",
        f"Shukriya {fn}. Apna aakhiri naam bhi batayein.",
        f"Samajh gaya {fn} {ln}. Aap kaunsi nayi tarikh chahenge?",
        f"Note kar liya. {new_date} ko kaunsa samay chahiye? Slots: {SLOTS}.",
        f"Confirm karte hain {fn}: {doc} ke saath appointment {new_date} ko {new_time} baje. Sahi hai?",
        f"Aapki appointment {new_date} ko {new_time} baje reschedule ho gayi. Shukriya {fn}.",
        f"Ho gaya! {doc} ke saath appointment ab {new_date} ko {new_time} baje hai. Dhyan rakhein {fn}.",
        f"Bahut acha {fn}. {doc} ke saath nayi appointment {new_date} ko {new_time} baje confirm ho gayi.",
        f"Us naam se koi appointment nahi mili. Kripya naam check karke dobara batayein.",
    ]


# ── Returning patient (profile) hint pools ─────────────────────────────────

def hints_profile_en(fn, ln):
    return [
        f"Welcome back {fn}! I have your details on file. Shall I proceed with your booking?",
        f"Hello again {fn} {ln}. Great to hear from you. How can I help you today?",
        f"Good to have you back {fn}. I can see your profile. Would you like to book an appointment?",
        f"Welcome {fn}. I recognise your number. Shall I use your saved name {fn} {ln}?",
        f"Hello {fn}! Nice to hear from you again. What can I help you with today?",
        f"I have your profile, {fn} {ln}. Would you like to proceed with this information?",
    ]


def hints_profile_hi(fn, ln):
    return [
        f"Swagat hai dobara {fn}! Aapki details mere paas hain. Kya main aage badhoon?",
        f"Phir se aaye {fn} {ln}! Aapki madad karna accha lagta hai. Aaj kya chahiye?",
        f"Namaskar {fn}. Aapka profile mere paas hai. Appointment book karni hai?",
        f"Aapka swagat hai {fn}. Aapka naam {fn} {ln} use karoon? Confirm karein.",
        f"Arre {fn} ji! Phir se aaye aap. Aaj kaise madad kar sakta hoon?",
        f"Aapki details mil gayi {fn} {ln}. Kya yahaan se aage badhoon?",
    ]


# ── DOB hint pools ──────────────────────────────────────────────────────────

def hints_dob_en(fn, dob):
    return [
        f"Thank you {fn}. Could you please tell me your date of birth? For example: 21 March 1990.",
        f"May I have your date of birth please {fn}? For example: 15 July 1985.",
        f"To complete your profile, {fn}, please share your date of birth.",
        f"Thank you for sharing that {fn}. Your date of birth {dob} has been noted.",
    ]


def hints_dob_hi(fn, dob):
    return [
        f"Shukriya {fn}. Kripya apni janm tithi batayein. Jaise: 21 March 1990.",
        f"Aapki janm tithi kya hai {fn}? Jaise: 15 July 1985.",
        f"Profile complete karne ke liye {fn}, apni birthday batayein.",
        f"Shukriya {fn}. Aapki janm tithi {dob} note kar lee gayi hai.",
    ]


# ── Empathy hint pools ──────────────────────────────────────────────────────

def hints_empathy_en(fn, sym):
    return [
        f"I understand that {sym} can be very uncomfortable, {fn}. Let me help you see the right doctor.",
        f"I am sorry to hear that you are experiencing {sym}. Let us get you an appointment quickly.",
        f"That must be difficult. Do not worry {fn}, I will help you book an appointment right away.",
        f"I understand. Feeling unwell is never easy. I will make sure you see the right doctor.",
        f"Take your time, {fn}. I am here to help you with whatever you need.",
        f"I am sorry to hear that. Let me find the best doctor available for your condition.",
    ]


def hints_empathy_hi(fn, sym):
    return [
        f"Mujhe samajh aata hai ki {sym} bahut takleef deta hai {fn}. Main sahi doctor se milaata hoon.",
        f"Afsos hai ki aap {sym} se pareshan hain. Jaldi appointment lete hain.",
        f"Chinta mat karein {fn}. Main abhi appointment book karne mein madad karta hoon.",
        f"Samajh aata hai. Bimaar rehna mushkil hota hai. Sahi doctor se milaata hoon.",
        f"Apna waqt lijiye {fn}. Main yahaan madad ke liye hoon.",
        f"Afsos hai. Aapke liye best available doctor dhoondta hoon.",
    ]


# ── General Physician recommendation hint pools ─────────────────────────────

def hints_gp_en(fn):
    return [
        f"Based on what you described {fn}, I would recommend seeing our General Physician Dr Mehta or Dr Singh.",
        f"For your condition, a General Physician would be the right choice. I can book you with Dr Mehta. Say 1 for Dr Mehta or 2 for Dr Singh.",
        f"Our General Physician can help with that. Say 1 for Dr Mehta or 2 for Dr Singh.",
        f"I suggest a General Physician for your symptoms. Dr Mehta and Dr Singh are both available. Which would you prefer?",
    ]


def hints_gp_hi(fn):
    return [
        f"Aapki baat ke hisaab se {fn}, hamara General Physician se milna theek rahega. Dr Mehta ya Dr Singh. Kaun sa doctor chahiye?",
        f"Aapki takleef ke liye General Physician sahi rahenge. Dr Mehta ke liye 1, Dr Singh ke liye 2 kahein.",
        f"Hamara General Physician madad karega. Dr Mehta ke liye 1 ya Dr Singh ke liye 2.",
        f"Main General Physician suggest karta hoon. Dr Mehta aur Dr Singh dono available hain. Kaun sa doctor chahiye?",
    ]


# ── Synonym replacements ────────────────────────────────────────────────────

EN_SYNONYMS = {
    "Could you please":   ["Can you", "Would you", "Please", "Kindly"],
    "May I have":         ["Can I get", "Please share", "Tell me", "Could I have"],
    "Thank you":          ["Thanks", "Great", "Got it", "Perfect", "Wonderful"],
    "Got it":             ["Noted", "Understood", "I see", "Alright", "Perfect"],
    "Noted":              ["Got it", "Understood", "Sure", "Of course"],
    "Just to confirm":    ["To confirm", "Let me confirm", "Confirming", "Let me verify"],
    "Please":             ["Kindly", ""],
    "appointment":        ["booking", "visit", "slot"],
    "visit":              ["appointment", "consultation", "booking"],
    "would you like":     ["do you prefer", "would you prefer", "do you want"],
    "which time works":   ["what time suits", "which slot works", "what time do you prefer"],
    "How may I assist":   ["How can I help", "What can I do for you", "How may I help"],
    "tell me":            ["share", "say", "mention"],
    "letter by letter":   ["one letter at a time", "spelling it out", "one by one"],
    "I can help":         ["I am here to help", "Happy to help", "I will help"],
    "shall I go ahead":   ["should I confirm", "shall I proceed", "can I confirm this"],
    "I understand":       ["I see", "I get it", "That makes sense"],
    "I am sorry":         ["I apologise", "Sorry to hear that", "That is unfortunate"],
}

HI_SYNONYMS = {
    "Bilkul":        ["Zaroor", "Haan ji", "Theek hai", "Bilkul sahi"],
    "Theek hai":     ["Samajh gaya", "Accha", "Sahi hai", "Bilkul"],
    "Shukriya":      ["Dhanyavaad", "Bahut acha", "Theek hai"],
    "Samajh gaya":   ["Note kar liya", "Theek hai", "Sahi"],
    "Kripya":        ["Please", "Zara", ""],
    "batayein":      ["batao", "bata sakte hain", "bolo"],
    "bata sakte hain": ["batayein", "batao", "share karein"],
    "aakhiri naam":  ["last naam", "surname"],
    "pehla naam":    ["first naam", "naam"],
    "appointment":   ["booking", "mulaqat"],
    "confirm":       ["pakka", "theek", "sahi"],
    "slot":          ["samay", "waqt", "time"],
    "lakshan":       ["takleef", "problem", "bimari"],
    "salah doonga":  ["suggest karunga", "recommend karunga", "bataunga"],
    "Mujhe samajh aata hai": ["Main samajhta hoon", "Pata hai mujhe"],
    "Apna dhyan rakhein": ["Khyaal rakhein", "Theek se rahein"],
}


def _vary_en(text: str) -> str:
    """Apply random synonym replacements to English text."""
    for original, alternatives in EN_SYNONYMS.items():
        if original in text and random.random() < 0.4:
            replacement = random.choice(alternatives)
            text = text.replace(original, replacement, 1)
    if "please" in text.lower() and random.random() < 0.2:
        text = re.sub(r'\bplease\b', '', text, flags=re.IGNORECASE).strip()
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text


def _vary_hi(text: str) -> str:
    """Apply random synonym replacements to Hindi text."""
    for original, alternatives in HI_SYNONYMS.items():
        if original in text and random.random() < 0.4:
            replacement = random.choice(alternatives)
            text = text.replace(original, replacement, 1)
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text


# ── Example builders ────────────────────────────────────────────────────────

def _make_example(hint: str, variation: str, lang: str) -> dict:
    if not variation or variation.strip() == hint.strip():
        variation = hint
    return {
        "messages": [
            {"role": "user",      "content": f"REPHRASE_HINT: {hint}\nLANG: {lang}"},
            {"role": "assistant", "content": variation},
        ]
    }


def make_example_core(lang: str) -> dict:
    fn   = random.choice(FIRST_NAMES)
    ln   = random.choice(LAST_NAMES)
    doc  = random.choice(DOCTORS)
    date = random.choice(DATES)
    time = random.choice(TIMES)

    if lang == "en":
        sym       = random.choice(SYMPTOMS_EN)
        hint_list = hints_en(fn, ln, doc, date, time, sym)
        hint      = random.choice(hint_list)
        variation = _vary_en(hint)
    else:
        sym       = random.choice(SYMPTOMS_HI)
        hint_list = hints_hi(fn, ln, doc, date, time, sym)
        hint      = random.choice(hint_list)
        variation = _vary_hi(hint)

    return _make_example(hint, variation, lang)


def make_example_emergency(lang: str) -> dict:
    fn = random.choice(FIRST_NAMES)
    if lang == "en":
        hint = random.choice(hints_emergency_en(fn))
        variation = _vary_en(hint)
    else:
        hint = random.choice(hints_emergency_hi(fn))
        variation = _vary_hi(hint)
    return _make_example(hint, variation, lang)


def make_example_reschedule(lang: str) -> dict:
    fn       = random.choice(FIRST_NAMES)
    ln       = random.choice(LAST_NAMES)
    doc      = random.choice(DOCTORS)
    old_date = random.choice(DATES)
    new_date = random.choice(DATES)
    new_time = random.choice(TIMES)
    if lang == "en":
        hint = random.choice(hints_reschedule_en(fn, ln, doc, old_date, new_date, new_time))
        variation = _vary_en(hint)
    else:
        hint = random.choice(hints_reschedule_hi(fn, ln, doc, old_date, new_date, new_time))
        variation = _vary_hi(hint)
    return _make_example(hint, variation, lang)


def make_example_profile(lang: str) -> dict:
    fn = random.choice(FIRST_NAMES)
    ln = random.choice(LAST_NAMES)
    if lang == "en":
        hint = random.choice(hints_profile_en(fn, ln))
        variation = _vary_en(hint)
    else:
        hint = random.choice(hints_profile_hi(fn, ln))
        variation = _vary_hi(hint)
    return _make_example(hint, variation, lang)


def make_example_dob(lang: str) -> dict:
    fn  = random.choice(FIRST_NAMES)
    dob = random.choice(DOBS)
    if lang == "en":
        hint = random.choice(hints_dob_en(fn, dob))
        variation = _vary_en(hint)
    else:
        hint = random.choice(hints_dob_hi(fn, dob))
        variation = _vary_hi(hint)
    return _make_example(hint, variation, lang)


def make_example_empathy(lang: str) -> dict:
    fn  = random.choice(FIRST_NAMES)
    sym = random.choice(SYMPTOMS_EN if lang == "en" else SYMPTOMS_HI)
    if lang == "en":
        hint = random.choice(hints_empathy_en(fn, sym))
        variation = _vary_en(hint)
    else:
        hint = random.choice(hints_empathy_hi(fn, sym))
        variation = _vary_hi(hint)
    return _make_example(hint, variation, lang)


def make_example_gp(lang: str) -> dict:
    fn = random.choice(FIRST_NAMES)
    if lang == "en":
        hint = random.choice(hints_gp_en(fn))
        variation = _vary_en(hint)
    else:
        hint = random.choice(hints_gp_hi(fn))
        variation = _vary_hi(hint)
    return _make_example(hint, variation, lang)



# ── Returning patient recognition hints ─────────────────────────────────────

def hints_returning_en(fn, ln):
    """Warm recognition of a patient whose profile already exists."""
    return [
        f"Welcome back, {fn}! It is wonderful to hear from you again. How may I assist you today?",
        f"Hello {fn}, how lovely to have you call us again. How can I help you today?",
        f"Good to hear from you, {fn}! How may I assist you today?",
        f"Hello again, {fn} {ln}! How may I help you today?",
        f"Welcome back, {fn}! I have your details on file. How may I assist you today?",
        f"Hello {fn}, I recognise your name. How may I help you today?",
        f"Great to hear from you again, {fn}. How may I assist you today?",
        f"Hi {fn}, welcome back to Anand Hospital. How can I help you today?",
        f"Hello {fn}, it is always a pleasure. How may I assist you today?",
        f"Welcome back, {fn}. Shall I go ahead and help you book a new appointment?",
        f"Hello {fn}, I can see you have been with us before. How may I assist you today?",
        f"Good to have you call again, {fn}. How may I help you today?",
    ]


def hints_returning_hi(fn, ln):
    """Warm recognition of a returning Hindi-speaking patient."""
    return [
        f"Dobara aapar karne ke liye shukriya, {fn} ji! Aaj main aapki kaise madad kar sakta hoon?",
        f"Namaskar {fn} ji, aapka swagat hai. Aaj kaise madad kar sakta hoon?",
        f"Bahut khushi hui, {fn} ji. Aapka intezaar tha. Kaise madad kar sakta hoon?",
        f"Aapka swagat hai wapas, {fn} {ln} ji. Kya madad chahiye aaj?",
        f"Shukriya call karne ke liye, {fn} ji. Kaise seva kar sakta hoon aapki?",
        f"Haan {fn} ji, aapka naam mujhe yaad hai. Aaj kya chahiye aapko?",
        f"Namaskar {fn} ji! Dobara call karne ke liye dhanyavaad. Kya madad kar sakta hoon?",
        f"Aapka swagat hai {fn} ji. Kya naya appointment chahiye ya kuch aur madad?",
        f"Bahut acha laga aapki awaaz sunke, {fn} ji. Kaise madad kar sakta hoon?",
        f"Haan {fn} ji, aap pehle bhi aaye hain. Aaj kya madad chahiye?",
    ]


def make_example_returning(lang: str) -> dict:
    fn = random.choice(FIRST_NAMES)
    ln = random.choice(LAST_NAMES)
    if lang == "en":
        hint = random.choice(hints_returning_en(fn, ln))
        variation = _vary_en(hint)
    else:
        hint = random.choice(hints_returning_hi(fn, ln))
        variation = _vary_hi(hint)
    return _make_example(hint, variation, lang)


# ── Phone-matched returning patient ──────────────────────────────────────
# Triggered when we greet the patient IMMEDIATELY after booking intent
# (no name needed — profile comes from phone number)

def hints_phone_returning_en(fn, ln):
    return [
        f"Welcome back, {fn}! It is wonderful to hear from you again. Would you like to book a new appointment, reschedule, or cancel?",
        f"Hello {fn}! Great to hear from you. How may I assist you today?",
        f"Welcome back, {fn} {ln}! It is lovely to have you call us again. Shall I help you with a new appointment?",
        f"Great to have you back, {fn}! How may I help you today? I can book, reschedule, or cancel your appointment.",
        f"Hello again, {fn}! Wonderful to hear your voice. Would you like to book, reschedule, or cancel today?",
        f"Welcome back, {fn}! It is so good to hear from you. What can I help you with today?",
        f"Hello {fn}, I recognise you! How may I assist you today?",
        f"Good to have you back, {fn} {ln}. Would you like to book a new appointment today?",
    ]


def hints_phone_returning_hi(fn, ln):
    return [
        f"Wapas aapar karne ke liye bahut shukriya, {fn} ji! Kya nayi appointment book karni hai, reschedule karni hai, ya cancel?",
        f"Namaskar {fn} ji! Phir aapar karne se bahut khushi hui. Aaj kaise madad kar sakta hoon?",
        f"Bahut acha laga aapki awaaz sunke, {fn} ji. Kya appointment book karni hai ya kuch aur?",
        f"Shukriya {fn} ji, dobara call karne ke liye. Kya nayi appointment chahiye, ya reschedule ya cancel?",
        f"Aapka swagat hai wapas, {fn} {ln} ji! Main aapki kaise seva kar sakta hoon?",
        f"Haan {fn} ji, main aapko pehchaanta hoon. Aaj kya madad chahiye?",
        f"Namaskar {fn} ji! Phir aapar aaye aap. Kya appointment book, reschedule ya cancel karni hai?",
    ]


def make_example_phone_returning(lang: str) -> dict:
    fn = random.choice(FIRST_NAMES)
    ln = random.choice(LAST_NAMES)
    if lang == "en":
        hint = random.choice(hints_phone_returning_en(fn, ln))
        variation = _vary_en(hint)
    else:
        hint = random.choice(hints_phone_returning_hi(fn, ln))
        variation = _vary_hi(hint)
    return _make_example(hint, variation, lang)


# ── Unknown symptom → GP routing ───────────────────────────────────────────────
# When a patient describes a vague or unrecognised symptom, ADAM routes to GP.

VAGUE_SYMPTOMS_EN = [
    "I am bleeding", "something is wrong", "I feel dizzy", "I feel weak",
    "I am not well", "I have a problem", "I am in pain", "I need help",
    "something hurts", "I feel terrible", "I feel sick", "I got hurt",
    "I had an accident", "I feel uncomfortable", "I am suffering",
]

VAGUE_SYMPTOMS_HI = [
    "mujhe takleef hai", "kuch theek nahi lag raha", "dard ho raha hai",
    "bura lag raha hai", "khoon aa raha hai", "giir gaya", "chot lagi",
    "bahut bura haal hai", "theek nahi hoon", "madad chahiye",
    "kuch ho gaya hai", "pet mein kuch", "pareshan hoon",
]


def hints_unknown_symptom_en(fn):
    d1, d2 = "Dr Mehta", "Dr Singh"
    return [
        f"I understand you are not feeling well, {fn}. I recommend our General Physician who can help with a wide range of concerns. Say 1 for {d1} or 2 for {d2}.",
        f"I see. Our General Physician can best assess your concern. Would you prefer {d1} or {d2}? Say 1 or 2.",
        f"I am sorry to hear that, {fn}. Let me connect you with our General Physician. Say 1 for {d1} or 2 for {d2}.",
        f"I understand. For your concern, our General Physician {d1} or {d2} would be the right choice. Please say 1 or 2.",
        f"Thank you for letting me know, {fn}. Our General Physician can help you. Say 1 for {d1} or 2 for {d2}.",
        f"I hear you, {fn}. I will connect you with a General Physician. Say 1 for {d1} or 2 for {d2}.",
        f"Your wellbeing is our priority, {fn}. Our General Physician can assess your concern. Say 1 for {d1} or 2 for {d2}.",
        f"I understand that you are concerned, {fn}. A General Physician is the right person to see first. Say 1 for {d1} or 2 for {d2}.",
    ]


def hints_unknown_symptom_hi(fn):
    d1, d2 = "Dr Mehta", "Dr Singh"
    return [
        f"Samajh gaya, aap theek nahi hain {fn} ji. General Physician aapki madad kar sakenge. {d1} ke liye 1 kahein ya {d2} ke liye 2.",
        f"Main samajhta hoon. Aapki takleef ke liye General Physician sahi rahenge. {d1} ke liye 1, ya {d2} ke liye 2.",
        f"Afsos hai sunkaar, {fn} ji. General Physician se milna accha rahega. {d1} ke liye 1 ya {d2} ke liye 2 kahein.",
        f"Theek hai {fn} ji. Main aapko General Physician ke paas bhejta hoon. {d1} ke liye 1, {d2} ke liye 2.",
        f"Aapki baat mani, {fn} ji. General Physician madad karenge. {d1} ke liye 1 ya {d2} ke liye 2 kahein.",
        f"Aapki sehat sabse zaroori hai {fn} ji. General Physician bilkul sahi rahenge. {d1} ke liye 1, {d2} ke liye 2.",
    ]


def make_example_unknown_symptom_gp(lang: str) -> dict:
    fn  = random.choice(FIRST_NAMES)
    if lang == "en":
        hint = random.choice(hints_unknown_symptom_en(fn))
        variation = _vary_en(hint)
    else:
        hint = random.choice(hints_unknown_symptom_hi(fn))
        variation = _vary_hi(hint)
    return _make_example(hint, variation, lang)


# ── Name spell confirmation hints ──────────────────────────────────────────────
# Model responses when asking patient to spell their name clearly.

def hints_spell_confirm_en(fn):
    return [
        f"Thank you, {fn}. Could you please spell your first name letter by letter? For example: A B H I S H E K.",
        f"Got it, {fn}! Could you spell your name one letter at a time, please? For example: R A H U L.",
        f"Lovely name, {fn}. To make sure I have it right, could you spell it letter by letter?",
        f"I heard {fn}. Could you spell that for me, letter by letter, so I can note it correctly?",
        f"Thank you! Could you please spell your first name for me? For example: A N J A L I.",
        f"Just to confirm, could you spell your name letter by letter? For example: P R I Y A.",
    ]


def hints_spell_confirm_hi(fn):
    return [
        f"Shukriya, {fn} ji. Kya aap apna pehla naam ek ek akshar mein spell kar sakte hain? Jaise: A B H I S H E K.",
        f"Bahut acha, {fn} ji. Kripya naam akshar akshar bolein taki sahi note ho sake. Jaise: R A H U L.",
        f"Dhanyavaad! Kripya apna pehla naam ek ek akshar mein bolein. Jaise: P R I Y A.",
        f"Samajh gaya, {fn} ji. Confirm karne ke liye kripya naam spell karein, akshar akshar. Jaise: A N J A L I.",
        f"Theek hai {fn} ji. Naam theek se note karne ke liye spell karein kripya, ek ek akshar.",
    ]


def make_example_spell_confirm(lang: str) -> dict:
    fn = random.choice(FIRST_NAMES)
    if lang == "en":
        hint = random.choice(hints_spell_confirm_en(fn))
        variation = _vary_en(hint)
    else:
        hint = random.choice(hints_spell_confirm_hi(fn))
        variation = _vary_hi(hint)
    return _make_example(hint, variation, lang)


# ── Weighted category sampler ───────────────────────────────────────────────
# core = 52%, emergency = 5%, reschedule = 7%, profile = 4%,
# dob = 4%, empathy = 5%, gp = 3%, returning = 6%,
# phone_returning = 6%, unknown_symptom_gp = 5%, spell_confirm = 3%
CATEGORIES = [
    ("core",              0.52),
    ("emergency",         0.05),
    ("reschedule",        0.07),
    ("profile",           0.04),
    ("dob",               0.04),
    ("empathy",           0.05),
    ("gp",                0.03),
    ("returning",         0.06),
    ("phone_returning",   0.06),
    ("unknown_symptom_gp",0.05),
    ("spell_confirm",     0.03),
]

_cat_names   = [c[0] for c in CATEGORIES]
_cat_weights = [c[1] for c in CATEGORIES]


def make_example(lang: str) -> dict:
    cat = random.choices(_cat_names, weights=_cat_weights, k=1)[0]
    if cat == "core":               return make_example_core(lang)
    if cat == "emergency":          return make_example_emergency(lang)
    if cat == "reschedule":         return make_example_reschedule(lang)
    if cat == "profile":            return make_example_profile(lang)
    if cat == "dob":                return make_example_dob(lang)
    if cat == "empathy":            return make_example_empathy(lang)
    if cat == "gp":                 return make_example_gp(lang)
    if cat == "returning":          return make_example_returning(lang)
    if cat == "phone_returning":    return make_example_phone_returning(lang)
    if cat == "unknown_symptom_gp": return make_example_unknown_symptom_gp(lang)
    if cat == "spell_confirm":      return make_example_spell_confirm(lang)
    return make_example_core(lang)




# ── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Generating {NUM_EXAMPLES:,} instruction-style examples...")
    print(f"Output: {OUTPUT_FILE}\n")
    print("Category distribution:")
    for name, w in CATEGORIES:
        print(f"  {name:12s} {w*100:.0f}%  (~{int(NUM_EXAMPLES*w):,} examples)")
    print()

    counts = {"en": 0, "hi": 0}
    examples = []

    for i in tqdm(range(NUM_EXAMPLES)):
        lang = "en" if i % 2 == 0 else "hi"
        ex   = make_example(lang)
        examples.append(ex)
        counts[lang] += 1

    random.shuffle(examples)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"\nDone!")
    print(f"  Total examples : {NUM_EXAMPLES:,}")
    print(f"  English        : {counts['en']:,}")
    print(f"  Hindi          : {counts['hi']:,}")
    print(f"  Saved to       : {OUTPUT_FILE}")
    print(f"\nNext step: run 'Finetune instruction.py'")