import json
from alexandrie.hub import AlexandrieHub

def main():
    hub = AlexandrieHub()
    print("Catalog size:", len(hub._catalog))
    
    # Let's search keys or fields for various substrings case-insensitively
    keywords = ["conjecture", "frontier", "sorry", "galileo", "cc_"]
    
    for kw in keywords:
        print(f"\n--- Searching for '{kw}' ---")
        matches = []
        for entry in hub._catalog.values():
            entry_str = json.dumps(entry).lower()
            if kw in entry_str:
                matches.append(entry)
        print(f"Found {len(matches)} matches.")
        for m in matches[:15]:
            print(f"- {m['id']} ({m.get('room_type')}): {m.get('title')}")

if __name__ == "__main__":
    main()
