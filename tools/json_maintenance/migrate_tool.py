import json
import os
import sys
from typing import Any

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from AntSleap.core.taxonomy_defaults import DEFAULT_LOCATOR_SCOPE, DEFAULT_PROJECT_TAXONOMY

RECOVERED_DIR = os.path.join(ROOT_DIR, "json_projects", "recovered")

def migrate_project(old_json_path: str, new_json_path: str) -> None:
    print(f"Migrating from {old_json_path} to {new_json_path}...")
    
    if not os.path.exists(old_json_path):
        print("Old project file not found.")
        return

    try:
        with open(old_json_path, 'r', encoding='utf-8') as f:
            old_data: dict[str, Any] = json.load(f)
    except Exception as e:
        print(f"Failed to load old project: {e}")
        return

    new_data: dict[str, Any] = {
        "name": old_data.get("name", "Migrated_Project") + "_Clean",
        "taxonomy": old_data.get("taxonomy", list(DEFAULT_PROJECT_TAXONOMY)),
        "locator_scope": old_data.get("locator_scope", old_data.get("taxonomy", list(DEFAULT_LOCATOR_SCOPE))),
        "images": [],
        "labels": {},
        "scales": old_data.get("scales", {})
    }
    
    migrated_count = 0
    bad_count = 0
    
    # Resolve old paths
    old_dir = os.path.dirname(os.path.abspath(old_json_path))
    
    for img_rel in old_data.get("images", []):
        # 1. Resolve Path
        img_abs = os.path.normpath(os.path.join(old_dir, img_rel))
        if not os.path.exists(img_abs):
            # Try finding it relative to current dir?
            if os.path.exists(img_rel):
                img_abs = os.path.abspath(img_rel)
            else:
                print(f"Skipping missing image: {img_rel}")
                continue
                
        # 2. Get Labels
        label_data = old_data.get("labels", {}).get(img_rel)
        if not label_data:
            # Maybe path key format mismatch? Try to find by basename match
            # But let's stick to exact match first.
            pass
            
        clean_parts = {}
        if label_data and "parts" in label_data:
            for part, points in label_data["parts"].items():
                # 3. Validate Points
                if not isinstance(points, list): continue
                if len(points) < 3: continue # Triangle at least
                
                valid_poly = True
                clean_points = []
                for pt in points:
                    if not isinstance(pt, list) or len(pt) < 2:
                        valid_poly = False; break
                    x, y = pt[0], pt[1]
                    # Check for NaN, Inf, or extreme values
                    if not (isinstance(x, (int, float)) and isinstance(y, (int, float))):
                        valid_poly = False; break
                    if x < -5000 or y < -5000 or x > 50000 or y > 50000:
                        valid_poly = False; break
                    clean_points.append([float(x), float(y)])
                
                if valid_poly:
                    clean_parts[part] = clean_points
                else:
                    bad_count += 1
                    print(f"Dropping bad polygon for {part} in {os.path.basename(img_abs)}")

        # 4. Add to New Project
        # Convert absolute back to relative for new project
        new_dir = os.path.dirname(os.path.abspath(new_json_path))
        try:
            new_rel = os.path.relpath(img_abs, new_dir)
        except:
            new_rel = img_abs # Fallback
            
        new_data["images"].append(new_rel)
        new_data["labels"][new_rel] = {
            "status": "labeled" if clean_parts else "unlabeled",
            "genus": label_data.get("genus", "Unknown") if label_data else "Unknown",
            "parts": clean_parts,
            "descriptions": label_data.get("descriptions", {}) if label_data else {}
        }
        migrated_count += 1

    # Save
    os.makedirs(os.path.dirname(new_json_path), exist_ok=True)
    with open(new_json_path, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, indent=4, ensure_ascii=False)
        
    print(f"Migration Complete. {migrated_count} images migrated. {bad_count} bad polygons dropped.")
    print(f"New project saved to: {new_json_path}")

if __name__ == "__main__":
    # Source: The fixed (but still glitchy) project
    src = os.path.join(RECOVERED_DIR, "test-head_fixed.json")
    # Dest: A fresh start
    dst = os.path.join(RECOVERED_DIR, "test-head_clean.json")
    
    if os.path.exists(src):
        migrate_project(src, dst)
    else:
        print(f"Source file not found: {src}")
