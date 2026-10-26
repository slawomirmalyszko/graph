"""Local Streamlit chat shell backed by read-only AuraDB connectivity."""

from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from integration_catalogue.database import (
    AuraConfigurationError,
    AuraSettings,
    create_driver,
    verify_and_summarize,
)
from integration_catalogue.ui.chat import EXAMPLE_QUESTIONS, pending_query_response

load_dotenv()

st.set_page_config(page_title="Integration Catalogue", page_icon="🔗", layout="wide")


@st.cache_resource
def get_aura_connection() -> tuple[object, AuraSettings]:
    settings = AuraSettings.from_environment()
    return create_driver(settings), settings


def render_connection_status() -> bool:
    try:
        driver, settings = get_aura_connection()
        summary = verify_and_summarize(driver, settings.database)
    except AuraConfigurationError as error:
        st.warning(f"AuraDB is not configured. {error}")
        st.caption("Copy `.env.example` to `.env` and add your AuraDB credentials.")
        return False
    except Exception:
        st.error("AuraDB connection failed. Check the local settings and database availability.")
        return False

    st.success("Connected to AuraDB in read-only session mode.")
    first, second, third = st.columns(3)
    first.metric("Catalogue nodes", summary.nodes)
    second.metric("Relationships", summary.relationships)
    third.metric("Applications", summary.applications)
    with st.expander("Catalogue details"):
        st.write(
            {
                "interfaces": summary.interfaces,
                "integrations": summary.integrations,
                "information_objects": summary.information_objects,
            }
        )
    return True


def render_sidebar() -> bool:
    with st.sidebar:
        st.header("AuraDB")
        connected = render_connection_status()
        if st.button("Refresh connection", use_container_width=True):
            st.cache_resource.clear()
            st.rerun()

        st.divider()
        st.subheader("Example questions")
        for index, example in enumerate(EXAMPLE_QUESTIONS):
            if st.button(example, key=f"example-{index}", use_container_width=True):
                st.session_state.pending_question = example

        if st.button("Clear history", use_container_width=True):
            st.session_state.messages = []
            st.session_state.pop("pending_question", None)
            st.rerun()
    return connected


def main() -> None:
    st.title("Integration Catalogue")
    st.caption("Ask questions about applications, interfaces, integrations, and data flows.")

    st.session_state.setdefault("messages", [])
    connected = render_sidebar()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    typed_question = st.chat_input(
        "Ask a question about your integrations...",
        disabled=not connected,
    )
    question = typed_question or st.session_state.pop("pending_question", None)
    if question and connected:
        st.session_state.messages.append({"role": "user", "content": question})
        response = pending_query_response(question)
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()


main()
