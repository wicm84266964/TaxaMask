import json
import os


PARENT_MODEL_NOTES_FILENAME = "parent_model_notes.json"
MAX_PARENT_MODEL_NOTE_LENGTH = 96


def parent_model_notes_path(weights_dir):
    return os.path.join(os.path.abspath(str(weights_dir or "")), PARENT_MODEL_NOTES_FILENAME)


def sanitize_parent_model_filename(value):
    filename = os.path.basename(str(value or "").strip())
    if not filename.lower().endswith(".pth"):
        return ""
    if filename.startswith("locator_") or filename.startswith("sam_decoder_lora_"):
        return filename
    return ""


def sanitize_parent_model_note(value):
    text = str(value or "").strip()
    if not text:
        return ""
    text = " ".join(text.split())
    return text[:MAX_PARENT_MODEL_NOTE_LENGTH]


def load_parent_model_notes(weights_dir):
    path = parent_model_notes_path(weights_dir)
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
    for filename, note in raw_notes.items():
        clean_filename = sanitize_parent_model_filename(filename)
        clean_note = sanitize_parent_model_note(note)
        if clean_filename and clean_note:
            notes[clean_filename] = clean_note
    return notes


def save_parent_model_notes(weights_dir, notes):
    path = parent_model_notes_path(weights_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    clean_notes = {}
    if isinstance(notes, dict):
        for filename, note in notes.items():
            clean_filename = sanitize_parent_model_filename(filename)
            clean_note = sanitize_parent_model_note(note)
            if clean_filename and clean_note:
                clean_notes[clean_filename] = clean_note
    payload = {
        "version": 1,
        "notes": dict(sorted(clean_notes.items())),
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return clean_notes


def get_parent_model_note(weights_dir, filename):
    clean_filename = sanitize_parent_model_filename(filename)
    if not clean_filename:
        return ""
    return load_parent_model_notes(weights_dir).get(clean_filename, "")


def set_parent_model_note(weights_dir, filename, note):
    clean_filename = sanitize_parent_model_filename(filename)
    if not clean_filename:
        return ""
    notes = load_parent_model_notes(weights_dir)
    clean_note = sanitize_parent_model_note(note)
    if clean_note:
        notes[clean_filename] = clean_note
    else:
        notes.pop(clean_filename, None)
    save_parent_model_notes(weights_dir, notes)
    return clean_note


def format_parent_model_display_name(filename, note=None, *, details=None):
    clean_filename = sanitize_parent_model_filename(filename)
    base_name = clean_filename[:-4] if clean_filename.lower().endswith(".pth") else str(filename or "").strip()
    if base_name.startswith("locator_"):
        base_name = base_name[len("locator_"):]
    elif base_name.startswith("sam_decoder_lora_"):
        base_name = base_name[len("sam_decoder_lora_"):]
    detail_text = str(details or "").strip()
    if detail_text:
        base_name = f"{base_name} [{detail_text}]"
    clean_note = sanitize_parent_model_note(note)
    if clean_note:
        return f"{clean_note} ({base_name})"
    return base_name
