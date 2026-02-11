"""
Script to check for missing localization keys.
Finds all t('key') calls in the codebase and verifies they exist in i18n.py
"""
import re
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, r'f:\Portable Applications\_pinger')

from config.i18n import LANG

def find_all_translation_keys():
    """Find all translation keys used in the codebase."""
    project_root = Path(r'f:\Portable Applications\_pinger')
    keys_used = set()
    
    # Find all Python files
    for py_file in project_root.rglob('*.py'):
        # Skip test files and this script
        if 'test_' in py_file.name or py_file.name == 'check_localization.py':
            continue
            
        try:
            content = py_file.read_text(encoding='utf-8')
            # Find all t('key') and t("key") patterns
            matches = re.findall(r't\(["\']([^"\']+)["\']\)', content)
            for match in matches:
                keys_used.add(match)
        except Exception as e:
            print(f"Error reading {py_file}: {e}")
    
    return keys_used

def check_missing_keys():
    """Check for missing translation keys."""
    keys_used = find_all_translation_keys()
    ru_keys = set(LANG['ru'].keys())
    en_keys = set(LANG['en'].keys())
    
    print("=" * 70)
    print("LOCALIZATION KEY VERIFICATION")
    print("=" * 70)
    print()
    
    print(f"Statistics:")
    print(f"  - Keys used in code: {len(keys_used)}")
    print(f"  - Keys in RU dict:   {len(ru_keys)}")
    print(f"  - Keys in EN dict:   {len(en_keys)}")
    print()
    
    # Check for missing translations
    missing_in_ru = keys_used - ru_keys
    missing_in_en = keys_used - en_keys
    
    if missing_in_ru or missing_in_en:
        print("[ERROR] MISSING TRANSLATIONS FOUND!")
        print()
        
        if missing_in_ru:
            print(f"Missing in RU ({len(missing_in_ru)} keys):")
            for key in sorted(missing_in_ru):
                print(f"  - {key}")
            print()
        
        if missing_in_en:
            print(f"Missing in EN ({len(missing_in_en)} keys):")
            for key in sorted(missing_in_en):
                print(f"  - {key}")
            print()
    else:
        print("[OK] ALL KEYS HAVE TRANSLATIONS!")
        print()
    
    # Check for unused keys
    unused_keys = (ru_keys & en_keys) - keys_used
    if unused_keys:
        print(f"[INFO] Unused keys in i18n.py ({len(unused_keys)} keys):")
        print("       (These are defined but not used in code)")
        for key in sorted(unused_keys)[:10]:  # Show first 10
            print(f"  - {key}")
        if len(unused_keys) > 10:
            print(f"  ... and {len(unused_keys) - 10} more")
        print()
    
    # Check for consistency between RU and EN
    only_in_ru = ru_keys - en_keys
    only_in_en = en_keys - ru_keys
    
    if only_in_ru or only_in_en:
        print("[WARNING] INCONSISTENCY BETWEEN RU AND EN!")
        if only_in_ru:
            print(f"Only in RU ({len(only_in_ru)} keys):")
            for key in sorted(only_in_ru):
                print(f"  - {key}")
        if only_in_en:
            print(f"Only in EN ({len(only_in_en)} keys):")
            for key in sorted(only_in_en):
                print(f"  - {key}")
        print()
    else:
        print("[OK] RU and EN dictionaries are consistent!")
        print()
    
    print("=" * 70)
    
    # Return status
    return len(missing_in_ru) == 0 and len(missing_in_en) == 0

if __name__ == '__main__':
    success = check_missing_keys()
    sys.exit(0 if success else 1)
