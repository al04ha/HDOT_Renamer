import json
import hashlib
from pathlib import Path

users_file = Path(__file__).resolve().parent / 'users.json'

print("--- AUTH DIAGNOSTIC ---")
if not users_file.exists():
    print("❌ ERROR: Cannot find users.json in this directory!")
else:
    print("✅ Found users.json")
    with open(users_file, "r") as f:
        db = json.load(f)
    
    if "admin" not in db:
        print("❌ ERROR: 'admin' user is missing from the JSON file structure.")
    else:
        print("✅ 'admin' user exists in database.")
        
        # Test hash matching for 'admin123'
        input_password = "admin123"
        hashed_attempt = hashlib.sha256(input_password.encode()).hexdigest()
        stored_hash = db["admin"]["password_hash"]
        
        print(f"DEBUG - Generated Hash: {hashed_attempt}")
        print(f"DEBUG - Stored Hash:    {stored_hash}")
        
        if hashed_attempt == stored_hash:
            print("🎉 SUCCESS: The password hash matches perfectly!")
        else:
            print("❌ ERROR: Password hashes do not match. Your users.json might have a typo or hidden characters.")