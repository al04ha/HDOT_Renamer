import os
import json
import hashlib
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st
import google.genai as genai
from pydantic import BaseModel

# Load environment variables
env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=env_path)

if not os.getenv("GEMINI_API_KEY"):
    st.error("Error: GEMINI_API_KEY not found in your .env file.")
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

# Load databases
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
    st.set_page_config(page_title="Gateway - Document Pipeline", layout="centered")
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
            reg_username = st.text_input("Choose Username", placeholder="e.g., wendell_h").strip().lower()
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
                    # Self-registrations always drop to standard User Portal bounds safely
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
st.set_page_config(page_title="Enterprise Document Pipeline", layout="wide")

# Determine maximum scope capabilities based on roles
is_master = (st.session_state.user_role == "Master Admin")
is_dev = (st.session_state.user_role == "Developer Admin")

with st.sidebar:
    st.title("🛡️ Identity Access")
    st.markdown(f"**User ID:** `{st.session_state.username}`")
    st.markdown(f"**Security Profile:** `{st.session_state.user_role}`")
    
    # Dynamic workspace view filtering based on credentials
    available_views = ["User Portal"]
    if is_master or is_dev:
        available_views.insert(0, "Developer Control Console")
    if is_master:
        available_views.insert(0, "Master Administration")
        
    view_mode = st.selectbox("Switch Workspace View:", available_views)
    st.markdown("---")
    if st.button("Log Out / Terminate Session", type="secondary"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.user_role = ""
        st.rerun()

# =============================================================
# VIEW 1: MASTER ADMINISTRATION (User Governance Engine)
# =============================================================
if view_mode == "Master Administration":
    st.title("👑 Master Identity & Governance Panel")
    st.write("Modify organizational system access and elevate standard accounts to administrative tiers.")
    
    st.subheader("➕ Provision/Elevate Privileged Staff Account")
    col_u, col_p, col_r = st.columns(3)
    with col_u:
        m_user = st.text_input("Username", placeholder="e.g., manager_dev").strip().lower()
    with col_p:
        m_pass = st.text_input("Password", type="password").strip()
    with col_r:
        m_role = st.selectbox("Target Security Privilege Level", ["User Portal", "Developer Admin", "Master Admin"])
        
    if st.button("Commit Identity Configuration", type="primary"):
        if not m_user or not m_pass:
            st.error("Valid authentication parameters required.")
        else:
            user_db[m_user] = {
                "password_hash": hash_password(m_pass),
                "role": m_role
            }
            save_json_file(USERS_FILE, user_db)
            st.success(f"Identity system updated: registered `{m_user}` with `{m_role}` permissions.")
            st.rerun()

    st.markdown("---")
    st.subheader("👥 System Account Directory Control")
    
    for username, data in list(user_db.items()):
        is_self = (username == st.session_state.username)
        with st.container(border=True):
            u_info, u_action = st.columns([4, 1])
            with u_info:
                st.markdown(f"**Account ID:** `{username}`")
                st.markdown(f"**Active Permission Bound:** `{data['role']}`")
            with u_action:
                if st.button(f"Revoke: {username}", key=f"m_del_{username}", type="secondary", disabled=is_self):
                    del user_db[username]
                    save_json_file(USERS_FILE, user_db)
                    st.warning(f"Identity `{username}` deleted from system tables.")
                    st.rerun()

# =============================================================
# VIEW 2: DEVELOPER CONTROL CONSOLE (Taxonomy Configuration)
# =============================================================
elif view_mode == "Developer Control Console":
    st.title("🛠️ Developer Administrative Dashboard")
    st.write("Modify the live pipeline classification rules and system taxonomy matrices.")

    st.subheader("➕ Register New Document Target")
    col_key, col_rule = st.columns(2)
    with col_key:
        new_key = st.text_input("Unique System Key", placeholder="e.g., environmental_report").strip().lower()
    with col_rule:
        new_convention = st.text_input("Naming Convention Rule", value="projectname_date_suffix")
        
    new_description = st.text_area("Prompt Engineering Context / AI Instructions", placeholder="Describe document properties...")
    
    if st.button("Save New Specification", type="primary"):
        if not new_key or not new_description:
            st.error("Validation Error: System Key and Instructions are mandatory fields.")
        elif "projectname" not in new_convention or "date" not in new_convention:
            st.error("Validation Error: Format rule must contain 'projectname' and 'date' tokens.")
        else:
            doc_registry[new_key] = {"description": new_description, "naming_convention": new_convention}
            save_json_file(REGISTRY_FILE, doc_registry)
            st.success(f"System key `{new_key}` compiled to disk storage.")
            st.rerun()

    st.markdown("---")
    st.subheader("🗑️ Active Pipeline Registry")
    for key, config in list(doc_registry.items()):
        with st.container(border=True):
            c_data, c_action = st.columns([4, 1])
            with c_data:
                st.markdown(f"### System Registry Key: `{key}`")
                st.markdown(f"**Naming Convention:** `{config['naming_convention']}`")
                st.markdown(f"**AI Guidance:** *{config['description']}*")
            with c_action:
                if st.button(f"Purge Key: {key}", key=f"del_{key}", type="secondary"):
                    del doc_registry[key]
                    save_json_file(REGISTRY_FILE, doc_registry)
                    st.warning(f"Purged `{key}`.")
                    st.rerun()

# =============================================================
# VIEW 3: USER PORTAL (Execution Pipeline)
# =============================================================
else:
    st.title("📂 Automated Document Ingestion Workspace")
    st.write("Drop files below to automatically audit, map, and rename records to compliance schemas.")

    uploaded_files = st.file_uploader(
        "Upload files for parsing (Max 5 documents concurrently)", 
        type=["pdf", "png", "jpg", "jpeg", "txt", "docx"],
        accept_multiple_files=True
    )

    if uploaded_files:
        if len(uploaded_files) > 5:
            st.error("Exceeded maximum batch handling volume. Please filter down to 5 records.")
            st.stop()
            
        if st.button("Execute Ingestion Pipeline", type="primary"):
            for uploaded_file in uploaded_files:
                with st.status(f"Parsing: {uploaded_file.name}...", expanded=False) as status:
                    try:
                        temp_path = Path(uploaded_file.name)
                        with open(temp_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())

                        gemini_file = client.files.upload(file=temp_path)
                        registry_context = "\n".join([f"- {k}: {v['description']}" for k, v in doc_registry.items()])
                        
                        prompt = f"""
                        You are an automated administrative document processor. Process this transaction file:
                        
                        TASK 1: Categorize this record into exactly one of these enterprise keys:
                        {registry_context}
                        If it matches no descriptors, yield 'unknown_general'.
                        
                        TASK 2: Extract primary tracking parameters.
                        - project_name: Strip spaces/special characters, format lowercase.
                        - document_date: Map strictly to YYYY-MM-DD. If null, return 'no-date'.
                        """

                        response = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=[gemini_file, prompt],
                            config={
                                "response_mime_type": "application/json",
                                "response_schema": DocumentClassifier,
                            }
                        )

                        result = json.loads(response.text)
                        cat = result.get("identified_category", "unknown_general")
                        proj = result.get("project_name", "unknown-project").replace(" ", "-").lower()
                        dt = result.get("document_date", "no-date")
                        
                        if cat not in doc_registry:
                            convention = "projectname_date_general"
                            cat_label = "UNKNOWN_GENERAL"
                        else:
                            convention = doc_registry[cat]["naming_convention"]
                            cat_label = cat.upper()
                            
                        final_name = convention.replace("projectname", proj).replace("date", dt)
                        final_filename = f"{final_name}{temp_path.suffix}"
                        
                        status.update(label=f"✅ Finished Processing: {uploaded_file.name}", state="complete")
                        
                        with st.container(border=True):
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.markdown(f"**Source File Name:** `{uploaded_file.name}`")
                                st.markdown(f"**Enterprise Taxonomy Category:** :green[[{cat_label}]]")
                                st.markdown(f"**Standardized Target Output:** `{final_filename}`")
                                st.caption(f"*System Logging Metadata:* {result.get('confidence_explanation')}")
                            with col2:
                                with open(temp_path, "rb") as f:
                                    file_bytes = f.read()
                                st.download_button(
                                    label="Download Normal Record",
                                    data=file_bytes,
                                    file_name=final_filename,
                                    mime=uploaded_file.type,
                                    key=f"dl_{uploaded_file.name}"
                                )

                        if temp_path.exists():
                            os.remove(temp_path)

                    except Exception as error:
                        status.update(label=f"❌ Transaction Failure: {uploaded_file.name}", state="error")
                        st.error(f"Error trace: {error}")