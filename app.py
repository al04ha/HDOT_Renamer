import os
import json
import hashlib
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st
import google.genai as genai
from pydantic import BaseModel

# --- MANDATORY FIRST STREAMLIT ACTION ---
# This must run at the absolute start of execution before any other st. commands
st.set_page_config(page_title="Enterprise Document Pipeline", layout="wide")

# --- HYBRID ENVIRONMENT LOADERS ---
# 1. Local Fallback: Load .env if running on your machine
env_path = Path(__file__).resolve().parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# 2. Cloud Fallback: Pull from Streamlit Secrets store if running in production
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]

# 3. Enforcement Guardrail
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
        return json.load(f)

def save_json_file(file_path: Path, data: dict):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

# Load databases from local persistent disk space
doc_registry = load_json_file(REGISTRY_FILE, {"bid_tab": {"description": "Bid tabs.", "naming_convention": "projectname_date_bidtab"}})
user_db = load_json_file(USERS_FILE, {})

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
                        st.session_state.user_role = user_db[username_input]["role"]
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
                    st.error("That username identity is already claimed.")
                else:
                    user_db[reg_username] = {
                        "password_hash": hash_password(reg_password),
                        "role": "User Portal"
                    }
                    save_json_file(USERS_FILE, user_db)
                    st.success("🎉 Registration complete! You can now switch to the Sign In tab.")
    st.stop()

# =============================================================
# WORKSPACE CONTROL ENVIRONMENT
# =============================================================
is_master = (st.session_state.user_role == "Master Admin")
is_dev = (st.session_state.user_role == "Developer Admin")
