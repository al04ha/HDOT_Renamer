import os
import json
import hashlib
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st
import google.genai as genai
from pydantic import BaseModelimport smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets  # For generating secure, un-guessable reset tokens
import time     # For token expiration checks

# --- MANDATORY FIRST STREAMLIT ACTION ---
st.set_page_config(page_title="Enterprise Document Pipeline", layout="wide")

# --- HYBRID ENVIRONMENT LOADERS ---
env_path = Path(__file__).resolve().parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

if "GEMINI_API_KEY" in st.secrets:
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]

if not os.getenv("GEMINI_API_KEY"):
    st.error("Error: GEMINI_API_KEY configuration token not detected in system memory. Check your cloud Secrets or local .env file.")
    st.stop()

client = genai.Client()
REGISTRY_FILE = Path(__file__).resolve().parent / 'registry.json'
USERS_FILE = Path(__file__).resolve().parent / 'users.json'

# --- SECURITY & DATABASE HELPERS ---
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def load_json_file(file_path: Path, fallback_data: dict) -> dict:
    if not file_path.exists():
        return fallback_data
    with open(file_path, "r") as f:
        try:
            data = json.load(f)
            return data if data else fallback_data
        except json.JSONDecodeError:
            return fallback_data

def save_json_file(file_path: Path, data: dict):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

# Load databases with structural fail-safes
doc_registry = load_json_file(REGISTRY_FILE, {"bid_tab": {"description": "Bid tabs.", "naming_convention": "projectname_date_bidtab"}})

# Pre-seeded directory fallback to protect admin elevation paths
DEFAULT_USERS = {
    "admin": {
        "password_hash": hash_password("hdotadmin2026"),  # Change these defaults anytime
        "role": "Master Admin"
    }
}
user_db = load_json_file(USERS_FILE, DEFAULT_USERS)
if not user_db:
    user_db = DEFAULT_USERS

class DocumentClassifier(BaseModel):
    identified_category: str  
    project_name: str         
    document_date: str        
    confidence_explanation: str

# --- SESSION STATE INITIALIZATION ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "user_role" not in st.session_state:
    st.session_state.user_role = ""

# =============================================================
# THE ENTERPRISE GATEWAY (SIGN IN / SIGN UP)
# =============================================================
if not st.session_state.logged_in:
    st.title("🔐 Enterprise Document Gateway")
    
    tab_signin, tab_signup = st.tabs(["🔒 Account Sign In", "📝 Create Account (Sign Up)"])
    
    with tab_signin:
        with st.form("signin_form"):
            username_input = st.text_input("Username").strip().lower()
            password_input = st.text_input("Password", type="password").strip()
            submit_login = st.form_submit_button("Sign In", type="primary")
            
            if submit_login:
                if username_input in user_db:
                    if user_db[username_input]["password_hash"] == hash_password(password_input):
                        st.session_state.logged_in = True
                        st.session_state.username = username_input
                        # Fallback mapping if database role field reads empty or corrupt
                        stored_role = user_db[username_input].get("role", "User Portal")
                        st.session_state.user_role = stored_role if stored_role else "User Portal"
                        st.success("Access Granted. Redirecting...")
                        st.rerun()
                    else:
                        st.error("Invalid password authentication signature.")
                else:
                    st.error("Account identity username not found.")
                    
    with tab_signup:
        st.write("Register a new individual profile. All self-registered accounts default to standard user privileges.")
        with st.form("signup_form"):
            reg_username = st.text_input("Choose Username", placeholder="e.g., john_d").strip().lower()
            reg_password = st.text_input("Choose Password", type="password").strip()
            reg_confirm = st.text_input("Confirm Password", type="password").strip()
            submit_signup = st.form_submit_button("Register Account", type="secondary")
            
            if submit_signup:
                if not reg_username or not reg_password:
                    st.error("All credential fields are required.")
                elif reg_password != reg_confirm:
                    st.error("Password verification fields do not match.")
                elif reg_username in user_db:
                    st.error
