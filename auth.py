import streamlit as st

from backend.auth_sessions import login_user, revoke_session, validate_session_token


def login() -> None:
    st.sidebar.title("Login")
    with st.sidebar.form("login_form"):
        username = st.text_input("Username", value="admin")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", width="stretch")

    if submitted:
        identity = login_user(username, password)
        if identity:
            st.session_state.user = identity["user_id"]
            st.session_state.auth_session = identity
            st.session_state.user_identity = identity
            st.session_state.workspace_loaded = False
            st.success(f"Welcome {identity['display_name']}")
            st.rerun()
        else:
            st.error("Invalid credentials")


def logout() -> None:
    session = st.session_state.get("auth_session", {})
    revoke_session(session.get("session_token"))
    for key in ("user", "auth_session", "user_identity", "workspace_memory", "workspace_loaded", "workspace_session_id"):
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


def render_auth_controls() -> None:
    identity = st.session_state.get("auth_session") or st.session_state.get("user_identity")
    if not identity:
        return
    memory = st.session_state.get("workspace_memory", {})
    with st.sidebar.expander("Session", expanded=False):
        st.caption(f"{identity.get('display_name', identity.get('user_id', 'User'))}")
        st.caption(f"Workspace: {identity.get('workspace_id', '')}")
        st.caption(f"Saved SQL: {len(memory.get('query_history', []))}")
        st.caption(f"Investigations: {len(memory.get('investigations', []))}")
        st.caption(f"Recent activity: {len(memory.get('recent_activity', []))}")
        if st.button("Logout", width="stretch"):
            logout()


def require_login() -> dict:
    session = st.session_state.get("auth_session")
    if session and validate_session_token(session.get("session_token")):
        st.session_state.user_identity = session
        return session
    if session:
        st.warning("Session expired. Please log in again.")
        st.session_state.pop("auth_session", None)
    login()
    st.stop()
