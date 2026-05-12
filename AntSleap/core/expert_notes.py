import json
import os

try:
    from AntSleap.core.cascade_routes import parse_expert_id
except ImportError:
    from .cascade_routes import parse_expert_id


EXPERT_NOTES_FILENAME = "expert_notes.json"
MAX_EXPERT_NOTE_LENGTH = 96


def expert_notes_path(weights_dir):
    return os.path.join(os.path.abspath(str(weights_dir or "")), "experts", EXPERT_NOTES_FILENAME)


def sanitize_expert_note(value):
    text = str(value or "").strip()
    if not text:
        return ""
    text = " ".join(text.split())
    return text[:MAX_EXPERT_NOTE_LENGTH]


def load_expert_notes(weights_dir):
    path = expert_notes_path(weights_dir)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    raw_notes = payload.get("notes", payload)
    if not isinstance(raw_notes, dict):
        return {}

    notes = {}
    for expert_id, note in raw_notes.items():
        clean_part, clean_filename = parse_expert_id(expert_id)
        if not clean_part or not clean_filename:
            continue
        clean_id = f"{clean_part}/{clean_filename}"
        clean_note = sanitize_expert_note(note)
        if clean_note:
            notes[clean_id] = clean_note
    return notes


def save_expert_notes(weights_dir, notes):
    path = expert_notes_path(weights_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    clean_notes = {}
    if isinstance(notes, dict):
        for expert_id, note in notes.items():
            clean_part, clean_filename = parse_expert_id(expert_id)
            if not clean_part or not clean_filename:
                continue
            clean_note = sanitize_expert_note(note)
            if clean_note:
                clean_notes[f"{clean_part}/{clean_filename}"] = clean_note
    payload = {
        "version": 1,
        "notes": dict(sorted(clean_notes.items())),
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return clean_notes


def get_expert_note(weights_dir, expert_id):
    clean_part, clean_filename = parse_expert_id(expert_id)
    if not clean_part or not clean_filename:
        return ""
    return load_expert_notes(weights_dir).get(f"{clean_part}/{clean_filename}", "")


def set_expert_note(weights_dir, expert_id, note):
    clean_part, clean_filename = parse_expert_id(expert_id)
    if not clean_part or not clean_filename:
        return ""
    clean_id = f"{clean_part}/{clean_filename}"
    notes = load_expert_notes(weights_dir)
    clean_note = sanitize_expert_note(note)
    if clean_note:
        notes[clean_id] = clean_note
    else:
        notes.pop(clean_id, None)
    save_expert_notes(weights_dir, notes)
    return clean_note


def format_expert_display_name(expert_id, note=None, *, appointed=False):
    clean_part, clean_filename = parse_expert_id(expert_id)
    clean_id = f"{clean_part}/{clean_filename}" if clean_part and clean_filename else str(expert_id or "").strip()
    clean_note = sanitize_expert_note(note)
    prefix = "★ " if appointed else ""
    if clean_note:
        return f"{prefix}{clean_note} ({clean_id})"
    return f"{prefix}{clean_id}"
