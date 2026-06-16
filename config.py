import os
from dotenv import load_dotenv

load_dotenv()


def get_config(key: str, default: str = "") -> str:
    value = os.getenv(key)
    if value:
        return value

    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass

    return default
