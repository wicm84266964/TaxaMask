import json
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def fix_json(file_path):
    print(f"Attempting to fix: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    print(f"Original Length: {len(content)}")
    
    # 1. Try to find the last valid "labels" entry
    # The structure is usually: { ..., "labels": { "path": {...}, "path": {...} <BROKEN>
    
    # Let's try to find the last closing brace '}' that looks like end of an object
    # We work backwards
    
    # A safer heuristic: 
    # The file probably ends abruptly.
    # We can try to truncate to the last ',' and then add "}}" (close labels, close root)
    # Or last '}' and add "}}"
    
    # Let's simple truncate to the last '},' or '}'
    last_brace = content.rfind('}')
    if last_brace == -1:
        print("Fatal: No braces found.")
        return

    # Keep content up to the last brace
    fixed_content = content[:last_brace+1]
    
    # Now we need to close the open brackets.
    # Count open/close braces
    open_count = fixed_content.count('{')
    close_count = fixed_content.count('}')
    
    missing_closes = open_count - close_count
    print(f"Open: {open_count}, Close: {close_count}, Missing: {missing_closes}")
    
    if missing_closes > 0:
        fixed_content += '}' * missing_closes
        
    out_path = file_path.replace(".json", "_fixed.json")
    
    try:
        json.loads(fixed_content)
        print("Success! JSON is valid.")
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        print(f"Saved fixed project to: {out_path}")
    except json.JSONDecodeError as e:
        print(f"Failed to fix simply: {e}")
        # Plan B: Truncate more aggressively (remove the last partial label)
        # Find the last "image_path": { ... } pattern
        pass

if __name__ == "__main__":
    files = [
        os.path.join(ROOT_DIR, "test-head.json"),
        os.path.join(ROOT_DIR, "Formica_Seg.json"),
    ]
    for f in files:
        if os.path.exists(f):
            fix_json(f)
