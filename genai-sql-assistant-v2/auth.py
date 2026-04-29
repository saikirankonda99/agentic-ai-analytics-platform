import streamlit as st

USERS = {
    "admin": "admin123",
    "user": "user123"
}

def login():
    st.sidebar.title("🔐 Login")

    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")

    if st.sidebar.button("Login"):
        if username in USERS and USERS[username] == password:
            st.session_state.user = username
            st.success(f"Welcome {username}")
        else:
            st.error("Invalid credentials")


def require_login():
    if "user" not in st.session_state:
        login()
        st.stop()