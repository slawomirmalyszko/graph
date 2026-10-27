"""Local Streamlit chat UI backed by controlled NL-to-Cypher execution."""

from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from integration_catalogue.database import (
    AuraConfigurationError,
    AuraSettings,
    create_driver,
    verify_and_summarize,
)
from integration_catalogue.query.pipeline import create_query_generator, query_mode_from_environment
from integration_catalogue.ui.chat import EXAMPLE_QUESTIONS, ChatResponse, process_question
from integration_catalogue.ui.graph import render_graph

load_dotenv()

st.set_page_config(page_title="Integration Catalogue", page_icon="🔗", layout="wide")


@st.cache_resource
def get_aura_connection() -> tuple[object, AuraSettings]:
    settings = AuraSettings.from_environment()
    return create_driver(settings), settings


@st.cache_resource
def get_query_generator():
    return create_query_generator(query_mode_from_environment())


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
        mode = query_mode_from_environment()
        st.caption(f"Query mode: `{mode}`")
        if st.button("Refresh connection", width="stretch"):
            st.cache_resource.clear()
            st.rerun()

        st.divider()
        st.subheader("Example questions")
        for index, example in enumerate(EXAMPLE_QUESTIONS):
            if st.button(example, key=f"example-{index}", width="stretch"):
                st.session_state.pending_question = example

        if st.button("Clear history", width="stretch"):
            st.session_state.messages = []
            st.session_state.pop("pending_question", None)
            st.rerun()
    return connected


def render_response(response: ChatResponse, *, key: str) -> None:
    if response.error:
        st.error(response.summary)
        st.caption(response.error)
        return
    if response.clarification:
        st.info(response.clarification)
        st.caption(response.summary)
        return

    st.markdown(response.summary)
    tab_names = ["Results", "Generated Cypher"]
    if response.graph:
        tab_names.insert(1, "Graph")
    tabs = st.tabs(tab_names)
    results_tab = tabs[0]
    cypher_tab = tabs[-1]
    with results_tab:
        if response.rows:
            st.dataframe(response.rows, width="stretch")
        else:
            st.info("The query returned no rows.")
    if response.graph:
        with tabs[1]:
            st.caption(
                f"{len(response.graph.nodes)} nodes · {len(response.graph.edges)} relationships"
            )
            render_graph(response.graph, key=key)
    with cypher_tab:
        st.code(response.cypher or "", language="cypher")
        st.write("Parameters", response.parameters or {})

    if response.model_id:
        metadata = f"Model: `{response.model_id}`"
        if response.model_id != "mock:reviewed-examples":
            metadata += (
                f" · Tokens: {response.input_tokens} input + {response.output_tokens} output "
                f"= {response.total_tokens} total"
            )
            if response.latency_ms is not None:
                metadata += f" · Latency: {response.latency_ms} ms"
        st.caption(metadata)


def main() -> None:
    st.title("Integration Catalogue")
    st.caption("Ask questions about applications, interfaces, integrations, and data flows.")

    st.session_state.setdefault("messages", [])
    connected = render_sidebar()

    for index, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.markdown(message["content"])
            else:
                render_response(message["response"], key=f"result-graph-{index}")

    typed_question = st.chat_input(
        "Ask a question about your integrations...",
        disabled=not connected,
    )
    question = typed_question or st.session_state.pop("pending_question", None)
    if question and connected:
        st.session_state.messages.append({"role": "user", "content": question})
        driver, settings = get_aura_connection()
        response = process_question(
            get_query_generator(),
            driver,
            question,
            database=settings.database,
        )
        st.session_state.messages.append({"role": "assistant", "response": response})
        st.rerun()


main()
