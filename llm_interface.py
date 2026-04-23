#LLM_INTERFACE.PY FINAL

import os
import re
import torch
import tiktoken

from transformer import Transformer
from config import default_config as config


_V4 = 'models/transformer_v4_instruction.pt'
_V3 = 'models/transformer_v3_instruction.pt'
MODEL_PATH = _V4 if os.path.exists(_V4) else _V3

DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

enc = tiktoken.get_encoding('r50k_base')


_calls:   dict = {}
_call_id: str  = ''       # active call — set by reset_history()


def _state() -> dict:
    """Return the state dict for the currently active call, auto-creating it."""
    return _calls.setdefault(_call_id, {"conversation": [], "lang": "en", "context": {}})


def _get_conversation() -> list:
    return _state()["conversation"]

def _get_lang() -> str:
    return _state()["lang"]

def _get_context() -> dict:
    return _state()["context"]


# Build special tokens from char codes so XML parser cannot truncate them
_LT  = chr(60)   # <
_GT  = chr(62)   # >
_BAR = chr(124)  # |
U = _LT + _BAR + 'user'      + _BAR + _GT
A = _LT + _BAR + 'assistant' + _BAR + _GT
E = _LT + _BAR + 'endoftext' + _BAR + _GT

_STOP_STRINGS = [E, U, A, '\n\n', 'User:', 'Assistant:', 'REPHRASE_HINT:']

_DOCTOR_NAMES = {
    'Dr Shah', 'Dr Reddy', 'Dr Mehta', 'Dr Singh',
    'Dr Patel', 'Dr Verma', 'Dr Gupta', 'Dr Kapoor',
}

print('Loading instruction fine-tuned LLM model...')
print(f'  Model path: {MODEL_PATH}')
ckpt  = torch.load(MODEL_PATH, map_location=DEVICE, weights_only=False)
model = Transformer(
    n_head         = config['n_head'],
    n_embed        = config['n_embed'],
    context_length = config['context_length'],
    vocab_size     = config['vocab_size'],
    N_BLOCKS       = config['n_blocks'],
).to(DEVICE)
model.load_state_dict(ckpt['model_state_dict'])
model.eval()
print(
    f'Instruction LLM loaded on {DEVICE}. '
    f'Train loss: {ckpt.get("train_loss", 0):.4f}  '
    f'Dev loss: {ckpt.get("dev_loss", 0):.4f}'
)
print(f'Training type: {ckpt.get("training_type", "unknown")}\n')


def _compute_stop_ids() -> set:
    ids = set()
    for s in [E, U, A]:
        try:
            toks = enc.encode(s, allowed_special={U, A, E})
            if len(toks) == 1:
                ids.add(toks[0])
        except Exception:
            pass
    return ids

_STOP_IDS = _compute_stop_ids()


# ── Public state management ─────────────────────────────────────────────────

def set_lang(lang: str):
    _state()["lang"] = lang

def set_context(ctx: dict):
    _state()["context"] = ctx.copy()

def reset_history(call_id: str = ''):
    """
    Called once per incoming call (from HospitalAgent.reset).
    Creates a completely fresh, isolated state for this call_id.
    Any previous state for the same call_id is discarded.
    """
    global _call_id
    _call_id = call_id
    # Completely fresh slate — wipe any leftover state for this call_id
    _calls[_call_id] = {"conversation": [], "lang": "en", "context": {}}
    print(f'  [llm] conversation reset  call_id={call_id!r}')

def add_user_turn(text: str):
    _get_conversation().append({'role': 'user', 'content': text})


# ── Text cleaning helpers ───────────────────────────────────────────────────

def _clean_tokens(text: str) -> str:
    text = text.replace(U, '').replace(A, '').replace(E, '')
    text = re.sub(r'<\|[^|>]*\|?>?',  '', text)
    text = re.sub(r'<\|[^>]*',         '', text)
    text = re.sub(r'\|[a-z]+\s*\|?>?', '', text)
    text = re.sub(r'\s*\|\s*>?\s*',    ' ', text)
    text = re.sub(r'^\s*[<>|]+\s*',    '', text)
    text = re.sub(r'\s*[<>|]+\s*$',    '', text)
    text = re.sub(r'\bkand\b',          '', text)
    text = re.sub(r'REPHRASE_HINT:.*',  '', text)
    text = re.sub(r'LANG:.*',           '', text)
    text = re.sub(r'\s{2,}',           ' ', text)
    return text.strip()


def _has_token_leak(text: str) -> bool:
    bad = ['<|', '|>', '|user', '|assistant', 'kand', 'endoftext',
           'User:', 'Assistant:', 'REPHRASE_HINT', 'LANG:']
    return any(b in text for b in bad)


_HINDI_WORD_FIXES = {
    r'\bfirst naam\b':      'pehla naam',
    r'\blast naam\b':       'aakhiri naam',
    r'\bfirst name\b':      'pehla naam',
    r'\blast name\b':       'aakhiri naam',
    r'\bname batao\b':      'naam batayein',
    r'\bspell karo\b':      'spell karein',
    r'\bbatao\b':           'batayein',
    r'\bkaro\b':            'karein',
    r'\bbolein ge\b':       'bolenge',
    r'\bbolo\b':            'bolein',
    r'\bdekho\b':           'dekhein',
    r'\bsuno\b':            'sunein',
    r'\blao\b':             'laayein',
    r'\bjaao\b':            'jaayein',
    r'\bbolo na\b':         'batayein',
    r'\bchalo\b':           'chaliye',
    r'\bthero\b':           'ruk jaiye',
    r'^Ab\s+':              '',
    r'\bAb flat\b':         '',
    r'\bab flat\b':         '',
    r'\bSuno\b':            'Kripya sunein',
    r'\bSuno,\s*':          'Kripya sunein, ',
    r'\bHaan\s+toh\b':      'Ji haan,',
    r'\bHaan\b':            'Ji haan',
    r'\bthik hai\b':        'theek hai',
    r'\bkoi baat nahi\b':   'bilkul koi baat nahi',
    r'\bmaafi\b':           'kshama karein',
    r'\bsorry\b':           'kshama karein',
}

def _apply_hindi_fixes(text: str) -> str:
    if _get_lang() == 'hi':
        for pattern, replacement in _HINDI_WORD_FIXES.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _strip_trailing_partial_word(text: str) -> str:
    if not text:
        return text
    text = re.sub(r'\s+\w{1,4}\'\s*$', '', text).strip()
    text = re.sub(r'\'\s*$', '', text).strip()
    for _ in range(6):
        m = re.match(r'^(.*?)\s+([A-Za-z]{1,2})\s*([.?!]?)$', text)
        if m:
            before, short_tok, punct = m.group(1), m.group(2), m.group(3)
            _safe_short = {'dr', 'mr', 'ms', 'no', 'ok', 'pm', 'am'}
            if short_tok.lower() not in _safe_short and len(before.strip()) >= 3:
                text = before.strip()
                if punct:
                    text = text.rstrip('.?! ') + punct
        else:
            break
    return text.strip()


def _ensure_ending(text: str) -> str:
    text = re.sub(r'[,\s]+$', '', text).strip()
    if not text:
        return text
    if text[-1] not in '.?!':
        last_end = max(text.rfind('.'), text.rfind('?'), text.rfind('!'))
        if last_end > len(text) // 2:
            text = text[:last_end + 1]
        else:
            question_words = [
                'kya', 'kaun', 'kaise', 'kab', 'kahan',
                'which', 'what', 'who', 'how', 'when', 'would',
                'chahenge', 'batayein', 'bolein', 'karein',
                'chahiye', 'sakta', 'sakte', 'chunein',
            ]
            if any(w in text.lower() for w in question_words):
                text = text + '?'
            else:
                text = text + '.'
    return text.strip()


# -- Expanded bad-continuation patterns ---------------------------------------
_BAD_CONTINUATION_PATTERNS = [
    r'<\|',
    r'REPHRASE_HINT',
    r'\bUser\s*:',
    r'\bAssistant\s*:',
    # "Ab" hallucinations
    r'\bAb flat\b',
    r'\bab flat\b',
    r'^Ab[,\s]',
    r'\bAb\s+[A-Z]',
    r'\bab\s+[A-Z]',
    # LLM self-narration
    r'\bI have\b',
    r'\bI can\b',
    r'\bI will\b',
    r'\bI am\b',
    r'\bI see\b',
    r'\bPlease share\b',
    r'\bPlease note\b',
    r'\bPlease be\b',
    r'\bOf course\b',
    r'\bCertainly\b',
    r'\bLet me\b',
    r'\bSure,?\s',
    r'\bYour help\b',
    r'\bhelp karein\b',
    r'\bSee you\b',
    r'\bAb samay\b',
    r'\bAnand Ho\b',
    r'\bkand\b',
    r'\bZara\b',
    # Time range hallucination
    r'\d+:\d+\s*(?:AM|PM).*\d+:\d+\s*(?:AM|PM)',
    # Rude imperatives
    r'\bSuno\s',
    r'\bbolo\s',
    r'\bdekho\s',
    # Filler / meta
    r'\bbasically\b',
    r'\bactually\b',
    r'\bhowever\b',
    r'\bmoreover\b',
]


def _dedup_repetition(text: str) -> str:
    text = re.sub(r'\b((\w+\s+\w+)\s+\2)\b', r'\2', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\w+)\s+\1\b',          r'\1', text, flags=re.IGNORECASE)
    return text


def _has_unlisted_doctor(cont: str, hint: str) -> bool:
    for doc in _DOCTOR_NAMES:
        doc_last = doc.split()[-1]
        if doc_last.lower() in cont.lower() and doc_last.lower() not in hint.lower():
            return True
    return False


def _polish_response(text: str, lang: str) -> str:
    '''Final politeness pass. Strips Ab/Ab flat and rude imperatives.'''
    if not text:
        return text

    text = re.sub(r'^Ab[,\s]+',       '', text, flags=re.IGNORECASE).strip()
    text = re.sub(r'^ab[,\s]+',       '', text).strip()
    text = re.sub(r'\bAb flat\b',     '', text, flags=re.IGNORECASE).strip()
    text = re.sub(r'\bab flat\b',     '', text, flags=re.IGNORECASE).strip()
    text = re.sub(r'\bAb\s+',         '', text).strip()

    if lang == 'hi':
        text = re.sub(r'\bbolo\b',  'bolein',   text, flags=re.IGNORECASE)
        text = re.sub(r'\bbatao\b', 'batayein', text, flags=re.IGNORECASE)
        text = re.sub(r'\bkaro\b',  'karein',   text, flags=re.IGNORECASE)
        text = re.sub(r'\bsuno\b',  'sunein',   text, flags=re.IGNORECASE)
        text = re.sub(r'\bdekho\b', 'dekhein',  text, flags=re.IGNORECASE)
        text = re.sub(r'^Suno[,\s]+', 'Kripya sunein, ', text)
        text = re.sub(r'\bHaan\s+toh\b', 'Ji haan,', text, flags=re.IGNORECASE)

    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text


def _clean_continuation(cont: str, hint: str) -> str:
    if not cont or not cont.strip():
        return ''
    if _has_token_leak(cont):
        return ''
    for pattern in _BAD_CONTINUATION_PATTERNS:
        m = re.search(pattern, cont, flags=re.IGNORECASE)
        if m:
            cont = cont[:m.start()].strip()
            break
    if not cont.strip():
        return ''
    if '?' in cont:
        return ''
    hint_nums = re.findall(r'\b\d+\b', hint)
    cont_nums = re.findall(r'\b\d+\b', cont)
    if len(cont_nums) > len(hint_nums):
        return ''
    cont = _strip_trailing_partial_word(cont)
    cont = _dedup_repetition(cont)
    cont = re.sub(r'[.?!]{2,}', '.', cont)
    cont = re.sub(r'\s{2,}',    ' ', cont).strip()
    if len(cont.split()) < 3:
        return ''
    if _has_unlisted_doctor(cont, hint):
        return ''
    return cont


def _is_repetitive(cont: str, hint: str) -> bool:
    hint_words = set(hint.lower().split())
    cont_words  = cont.lower().split()
    if not cont_words:
        return True
    overlap = sum(1 for w in cont_words if w in hint_words)
    return (overlap / len(cont_words)) > 0.50


def _build_seeded_prompt(hint: str) -> str:
    parts        = []
    conversation = _get_conversation()
    history      = [t for t in conversation if not (
        t == conversation[-1] and t['role'] == 'user'
    )]
    recent = history[-4:] if len(history) > 4 else history
    for turn in recent:
        tok = U if turn['role'] == 'user' else A
        parts.append(f'{tok} {turn["content"]} ')
    if conversation and conversation[-1]['role'] == 'user':
        parts.append(f'{U} {conversation[-1]["content"]} ')
    parts.append(f'{A} {hint}')
    return ''.join(parts)


def _generate_continuation(prompt: str, max_tokens: int = 8) -> str:
    '''max_tokens is 8 by default to reduce hallucination drift.'''
    try:
        tokens  = enc.encode(prompt, allowed_special={U, A, E})
        max_ctx = config['context_length'] - max_tokens - 4
        if len(tokens) > max_ctx:
            tokens = tokens[-max_ctx:]
        idx = torch.tensor([tokens], dtype=torch.long, device=DEVICE)
        ids = []
        with torch.no_grad():
            for _ in range(max_tokens):
                cond      = idx[:, -config['context_length']:]
                logits, _ = model(cond)
                logits    = logits[:, -1, :] / 0.5
                for sid in _STOP_IDS:
                    logits[0, sid] = -1e9
                if ids:
                    for tid in set(ids[-20:]):
                        freq = ids[-20:].count(tid)
                        logits[0, tid] /= (1.2 + 0.3 * freq)
                topk, _ = torch.topk(logits, 20, dim=-1)
                logits   = logits.masked_fill(logits < topk[:, -1:], -1e9)
                probs    = torch.softmax(logits, dim=-1)
                next_tok = torch.multinomial(probs, 1)
                tok_id   = next_tok.item()
                if tok_id in _STOP_IDS:
                    break
                ids.append(tok_id)
                idx = torch.cat([idx, next_tok], dim=1)
                so_far = enc.decode(ids)
                for stop in _STOP_STRINGS:
                    if stop in so_far:
                        return _clean_tokens(so_far.split(stop)[0])
        return _clean_tokens(enc.decode(ids))
    except Exception as e:
        print(f'  [LLM error]: {e}')
        return ''


def extract_info(user_text: str) -> dict:
    text      = user_text.lower()
    en_book   = ['book','appointment','doctor','visit','schedule','consult',
                 'slot','sick','pain','unwell','feeling','see a doctor',
                 'need a doctor','check up','checkup']
    hi_book   = ['appointment','doctor','milna','visit','theek nahi','dard',
                 'bukhar','problem','madad','hospital aana','book karni',
                 'book karna','doctor chahiye','appointment chahiye',
                 'appointment leni','appointment lena','appointment karni',
                 'appointment karna','milna chahta','milna chahti','bimar',
                 'bimari','takleef','slot chahiye','help chahiye']
    en_cancel = ['cancel','remove','delete']
    hi_cancel = ['cancel','band','hatao','nahi aana','cancel karni',
                 'cancel karna','cancel karwani']
    en_reschedule = ['reschedule','change date','change time','move appointment']
    hi_reschedule = ['date badlo','time badlo','reschedule karna','appointment badlo']

    if any(w in text for w in en_reschedule + hi_reschedule):
        return {'intent': 'RESCHEDULE'}
    if any(w in text for w in en_cancel + hi_cancel):
        return {'intent': 'CANCEL'}
    if any(w in text for w in en_book + hi_book):
        return {'intent': 'BOOK'}
    return {}


# -- Tasks where we NEVER attempt LLM continuation (return hint verbatim) ----
_HINT_ONLY_TASKS = {
    'asking patient to choose language',
    'language confirmed english, greeting',
    'language confirmed hindi, greeting',
    'language confirmed, greeting patient',
    'patient wants to book, asking for first name',
    'patient wants to cancel, asking for first name',
    'reschedule intent, asking first name',
    'first name not understood, asking to spell',
    'spelling of first name unclear, asking again',
    'confirmed spelled first name',
    'got first name',
    'asking for last name',
    'confirmed last name',
    'spelling of last name unclear',
    'confirmed full name',
    'dob not understood',
    'dob confirmed',
    'asking symptom',
    'could not detect symptom',
    'doctor selection unclear',
    'date invalid',
    'time not understood',
    'slot already booked',
    'all details ready',
    'asking yes or no',
    'unclear response at confirmation',
    'patient said no',
    'appointment confirmed',
    'appointment not found',
    'appointment cancelled',
    'reschedule complete',
    'emergency detected',
    'call ending',
    'returning patient',
    'profile loaded',
    'name matches phone profile',
    'found profile by first name',
    'dob verified',
    'dob mismatch',
    # v4 additions
    'welcomed back from phone',
    'unrecognised symptom',
    'unrecognized symptom',
    'symptom not matched',
    'implicit booking intent',
    'stt noise detected',
    'multi-word stt with leading letter',
}


def _is_hint_only_task(task: str) -> bool:
    t = task.lower()
    for key in _HINT_ONLY_TASKS:
        if key in t:
            return True
    return False


def generate_response(task: str, coached_hint: str,
                      max_new_tokens: int = 40) -> str:
    lang = _get_lang()

    # 1. Clean and polish hint
    clean_hint = _clean_tokens(coached_hint)
    if not clean_hint:
        clean_hint = coached_hint.strip()
    clean_hint = _apply_hindi_fixes(clean_hint)
    clean_hint = _ensure_ending(clean_hint)
    clean_hint = _strip_trailing_partial_word(clean_hint)
    clean_hint = _ensure_ending(clean_hint)
    clean_hint = _polish_response(clean_hint, lang)

    print(f'  [LLM task ] {task}')
    print(f'  [LLM hint ] {clean_hint[:80]!r}')

    # 2. Hint-only cases: question hints, named tasks, or hints >= 20 words
    if (clean_hint.endswith('?')
            or _is_hint_only_task(task)
            or len(clean_hint.split()) >= 20):
        print(f'  [LLM reply] {clean_hint[:120]!r}  <- HINT ONLY')
        _get_conversation().append({'role': 'assistant', 'content': clean_hint})
        return clean_hint

    # 3. Build seeded prompt and generate continuation (max 8 tokens)
    prompt   = _build_seeded_prompt(clean_hint)
    raw_cont = _generate_continuation(prompt, max_tokens=8)

    # 4. Validate continuation
    cont = _clean_continuation(raw_cont, clean_hint)
    if cont and _is_repetitive(cont, clean_hint):
        cont = ''

    # 5. Merge
    if cont:
        base   = clean_hint.rstrip('.?! ')
        merged = f'{base} {cont}'
        merged = _strip_trailing_partial_word(merged)
        full   = _ensure_ending(merged)
    else:
        full = clean_hint

    if _has_token_leak(full) or not full:
        full = clean_hint

    full = _polish_response(full, lang)

    # Final guard against Ab/ab-flat leakage
    full = re.sub(r'\bAb flat\b', '', full, flags=re.IGNORECASE).strip()
    full = re.sub(r'\bab flat\b', '', full, flags=re.IGNORECASE).strip()
    full = re.sub(r'^Ab[,\s]+',   '', full, flags=re.IGNORECASE).strip()
    if not full:
        full = clean_hint

    print(f'  [LLM reply] {full[:120]!r}  <- LLM GENERATED')
    _get_conversation().append({'role': 'assistant', 'content': full})
    return full