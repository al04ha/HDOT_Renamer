import os
import json
import hashlib
import smtplib
import secrets
import time
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import streamlit as st
import google.genai as genai
from pydantic import BaseModel

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
        "email": "admin@example.com",
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

# --- PASSWORD RESET ENGINE ---
def send_reset_email(target_user: str, target_email: str) -> bool:
    """Generates a secure token and dispatches a verification link via SMTP."""
    reset_token = secrets.token_urlsafe(32)
    expiration_time = time.time() + 3600  # Token valid for 1 hour
    
    # Bind token metadata to the user in database memory
    user_db[target_user]["reset_token"] = reset_token
    user_db[target_user]["token_expires"] = expiration_time
    save_json_file(USERS_FILE, user_db)
    
    # Construct deep link URL
    base_url = os.getenv("APP_BASE_URL", st.secrets.get("APP_BASE_URL", "http://localhost:8501"))
    reset_link = f"{base_url}/?action=reset&token={reset_token}&user={target_user}"
    
    # Gather SMTP parameters safely
    sender = os.getenv("SMTP_SENDER_EMAIL", st.secrets.get("SMTP_SENDER_EMAIL"))
    password = os.getenv("SMTP_SENDER_PASSWORD", st.secrets.get("SMTP_SENDER_PASSWORD"))
    server_host = os.getenv("SMTP_SERVER", st.secrets.get("SMTP_SERVER", "smtp.gmail.com"))
    try:
        server_port = int(os.getenv("SMTP_PORT", st.secrets.get("SMTP_PORT", 587)))
    except (ValueError, TypeError):
        server_port = 587
    
    if not sender or not password:
        st.error("System SMTP email credentials missing from cloud configuration settings.")
        return False

    message = MIMEMultipart()
    message["From"] = sender
    message["To"] = target_email
    message["Subject"] = "🔐 HDOT Document Pipeline - Password Reset Request"
    
    body = f"""Hello,
    
A password reset request was initiated for your HDOT Pipeline profile account: '{target_user}'.
    
Click the secure authorization link below to establish a new password:
{reset_link}
    
This validation window will automatically expire in 60 minutes. If you did not request this modification, please disregard this transmission securely."""
    
    message.attach(MIMEText(body, "plain"))
    
    try:
        server = smtplib.SMTP(server_host, server_port)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, target_email, message.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Mail delivery pipeline failure: {e}")
        return False

# --- SESSION STATE INITIALIZATION ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "user_role" not in st.session_state:
    st.session_state.user_role = ""

# =============================================================
# THE ENTERPRISE GATEWAY (SIGN IN / SIGN UP / PASSWORD RESET)
# =============================================================
if not st.session_state.logged_in:
    # --- DEEP LINK URL PARAMETER INTERCEPTOR ---
    query_params = st.query_params
    
    if query_params.get("action") == "reset" and "token" in query_params and "user" in query_params:
        target_user = query_params["user"].lower()
        provided_token = query_params["token"]
        
        st.title("🔄 Establish New Account Password")
        
        if target_user in user_db and "reset_token" in user_db[target_user]:
            saved_token = user_db[target_user]["reset_token"]
            expiry = user_db[target_user].get("token_expires", 0)
            
            if provided_token == saved_token and time.time() < expiry:
                with st.form("reset_password_form"):
                    new_pass = st.text_input("Enter New Password", type="password").strip()
                    confirm_pass = st.text_input("Confirm New Password", type="password").strip()
                    submit_reset = st.form_submit_button("Update Password", type="primary")
                    
                    if submit_reset:
                        if len(new_pass) < 6:
                            st.error("Security enforcement: Password must contain at least 6 characters.")
                        elif new_pass != confirm_pass:
                            st.error("Verification match misaligned.")
                        else:
                            user_db[target_user]["password_hash"] = hash_password(new_pass)
                            user_db[target_user]["reset_token"] = ""
                            user_db[target_user]["token_expires"] = 0
                            save_json_file(USERS_FILE, user_db)
                            
                            st.success("🎉 Security credentials successfully modified!")
                            st.query_params.clear()
                            st.write("You may now sign in using your new password.")
                            st.stop()
            else:
                st.error("Authentication Error: The password token link is corrupted or has expired.")
        else:
            st.error("Authentication Error: Invalid profile link target identity.")
        
        if st.button("Return to Login Gateway"):
            st.query_params.clear()
            st.rerun()
        st.stop()

    # --- STANDARD GRAPHICAL GATEWAY PANELS ---
    st.title("🔐 Enterprise Document Gateway")
    tab_signin, tab_signup, tab_forgot = st.tabs(["🔒 Account Sign In", "📝 Create Account (Sign Up)", "❓ Forgot Password"])
    
    with tab_signin:
        with st.form("signin_form"):
            username_input = text_input_user = st.text_input("Username").strip().lower()
            password_input = st.text_input("Password", type="password").strip()
            submit_login = st.form_submit_button("Sign In", type="primary")
            
            if submit_login:
                if username_input in user_db:
                    if user_db[username_input]["password_hash"] == hash_password(password_input):
                        st.session_state.logged_in = True
                        st.session_state.username = username_input
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
            reg_email = st.text_input("Work Email Address (For Password Recovery)").strip().lower()
            reg_password = st.text_input("Choose Password", type="password").strip()
            reg_confirm = st.text_input("Confirm Password", type="password").strip()
            submit_signup = st.form_submit_button("Register Account", type="secondary")
            
            if submit_signup:
                if not reg_username or not reg_password or not reg_email:
                    st.error("All registration fields are required.")
                elif reg_password != reg_confirm:
                    st.error("Password verification fields do not match.")
                elif reg_username in user_db:
                    st.error("That username identity is already claimed.")
                else:
                    user_db[reg_username] = {
                        "email": reg_email,
                        "password_hash": hash_password(reg_password),
                        "role": "User Portal"
                    }
                    save_json_file(USERS_FILE, user_db)
                    st.success("🎉 Registration complete! You can now switch to the Sign In tab.")
                    
    with tab_forgot:
        st.write("Request a secure account verification link sent to your workspace system email.")
        with st.form("forgot_password_form"):
            forgot_user = st.text_input("Enter Account Username").strip().lower()
            submit_forgot = st.form_submit_button("Transmit Account Reset Request")
            
            if submit_forgot:
                if forgot_user in user_db:
                    user_email = user_db[forgot_user].get("email")
                    if user_email:
                        with st.spinner("Encrypting transmission handshake..."):
                            if send_reset_email(forgot_user, user_email):
                                split_email = user_email.split('@')
                                obfuscated = f"{user_email[:2]}***@{split_email[1]}"
                                st.success(f"📨 Verification request issued! Check your inbox at: `{obfuscated}`")
                            else:
                                st.error("Outbound mail relay error. Contact system administrators.")
                    else:
                        st.error("This user profile lacks a registered recovery email address. Contact an admin.")
                else:
                    st.info("If that account username matches active records, an authorization link has been queued.")
    st.stop()

# =============================================================
# WORKSPACE CONTROL ENVIRONMENT
# =============================================================
is_master = (st.session_state.user_role == "Master Admin")
is_dev = (st.session_state.user_role == "Developer Admin")

with st.sidebar:
    st.title("🛡️ Identity Access")
    st.markdown(f"**User ID:** `{st.session_state.username}`")
    st.markdown(f"**Security Profile:** `{st.session_state.user_role}`")
    
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
                "email": user_db.get(m_user, {}).get("email", f"{m_user}@example.com"),
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
                st.markdown(f"**Active Permission Bound:** `{data.get('role', 'User Portal')}`")
                st.markdown(f"**Recovery Destination:** `{data.get('email', 'None')}`")
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
# VIEW 3: USER PORTAL (Ingestion Pipeline Workspace Routing)
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
                        
                        prompt = f"""You are an automated administrative document processor. Process this transaction file:
                        
TASK 1: Categorize this record into exactly one of these enterprise keys:
{registry_context}
If it matches no descriptors, yield 'unknown_general'.
                        
TASK 2: Extract primary tracking parameters.
- project_name: Strip spaces/special characters, format lowercase.
- document_date: Map strictly to YYYY-MM-DD. If null, return 'no-date'."""

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
                        if temp_path.exists():
                            os.remove(temp_path)
                    except Exception as error:
                        status.update(label=f"❌ Transaction Failure: {uploaded_file.name}", state="error")
                        st.error(f"Error trace: {error}"
