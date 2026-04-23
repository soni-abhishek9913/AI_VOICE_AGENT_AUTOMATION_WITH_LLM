import os
import json
from urllib.parse import quote
from twilio.rest import Client


ACCOUNT_SID    = ""
AUTH_TOKEN     = ""
TWILIO_NUMBER  = ""
PATIENT_NUMBER = ""

BASE_URL = ""

# %2B encodes the leading + so Flask doesn't decode it as a space
SERVER_URL = f"{BASE_URL}/voice?patient={quote(PATIENT_NUMBER)}"

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# Sidecar file: voice_server reads this as a guaranteed fallback
_SIDECAR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_pending_patient.json")


def make_call():
    # Write patient number to sidecar BEFORE placing the call
    with open(_SIDECAR, "w") as f:
        json.dump({"patient": PATIENT_NUMBER}, f)
    print(f"Sidecar written: {PATIENT_NUMBER}")

    call = client.calls.create(
        to=PATIENT_NUMBER,
        from_=TWILIO_NUMBER,
        url=SERVER_URL,
    )
    print("Call started")
    print("Call SID:", call.sid)


if __name__ == "__main__":
    make_call()