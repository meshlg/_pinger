#!/usr/bin/env python3
"""Simple test for localization without Unicode characters"""
from config import LANG

def test_localization_keys():
    ru_keys = set(LANG['ru'].keys())
    en_keys = set(LANG['en'].keys())
    
    only_ru = ru_keys - en_keys
    if only_ru:
        print("Keys only in Russian:", sorted(list(only_ru)))
    
    only_en = en_keys - ru_keys
    if only_en:
        print("Keys only in English:", sorted(list(only_en)))
    
    common = ru_keys & en_keys
    print("Common keys:", len(common))
    
    missing = only_ru | only_en
    
    if len(missing) == 0:
        print("\nAll localization keys match!")
        return True
    else:
        print("\nTotal missing keys:", len(missing))
        return False

def test_required_keys():
    required_ui_keys = [
        'p95', 'ping', 'loss', 'uptime', 'jitter',
        'dns', 'traceroute', 'network', 'title'
    ]
    
    all_passed = True
    for key in required_ui_keys:
        if key not in LANG['ru'] or key not in LANG['en']:
            print(f"Key '{key}' is missing")
            all_passed = False
    
    if all_passed:
        print("\nAll required UI keys are present")
    
    return all_passed

if __name__ == "__main__":
    print("=== LOCALIZATION VERIFICATION ===")
    print("=" * 50)
    
    test_localization_keys()
    test_required_keys()
    print("\n" + "=" * 50)
