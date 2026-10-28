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
from integration_catalogue.ui.chat import (
    SIDEBAR_QUESTION_GROUPS,
    ChatResponse,
    process_question,
    rows_to_csv,
)
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

    first, second, third = st.columns(3)
    first.metric("Catalogue nodes", summary.nodes)
    second.metric("Relationships", summary.relationships)
    third.metric("Apps", summary.applications)
    with st.expander("Catalogue details"):
        st.write(
            {
                "apps": summary.applications,
                "interfaces": summary.interfaces,
                "integrations": summary.integrations,
                "information_objects": summary.information_objects,
                "relationships": summary.relationships,
            }
        )
    return True


def render_sidebar() -> bool:
    with st.sidebar:
        mode = query_mode_from_environment()
        diagnostics = st.container()
        st.markdown(
            "<p style='color:#06B6D4; font-size:0.95rem; font-weight:500; "
            "text-align:center;'>Ask anything about your integrations in plain English</p>",
            unsafe_allow_html=True,
        )
        st.divider()

        connected = render_connection_status()
        connection = "AuraDB · connected (read-only)" if connected else "AuraDB · unavailable"
        with diagnostics:
            st.caption(f"Connection: `{connection}`")
            st.caption(f"Query mode: `{mode}`")

        st.divider()

        for group_index, group in enumerate(SIDEBAR_QUESTION_GROUPS):
            if group_index:
                st.divider()
            color = f" color:{group.title_color};" if group.title_color else ""
            st.markdown(
                f"<h3 style='text-align:center;{color}'>{group.title}</h3>",
                unsafe_allow_html=True,
            )
            for question_index, question in enumerate(group.questions):
                if st.button(
                    question.prompt,
                    key=f"sidebar-{group.key}-{question_index}",
                    width="stretch",
                ):
                    st.session_state.pending_question = question.prompt
                if question.caption:
                    st.markdown(
                        "<p style='text-align:center; color:#94A3B8; "
                        f"font-size:0.8rem;'>{question.caption}</p>",
                        unsafe_allow_html=True,
                    )

        st.divider()
        if st.button("Clear history", width="stretch"):
            st.session_state.messages = []
            st.session_state.pop("pending_question", None)
            st.rerun()
    return connected


def render_model_metadata(response: ChatResponse) -> None:
    if not response.model_id:
        return
    metadata = f"Model: `{response.model_id}`"
    if response.confidence is not None:
        metadata += f" · Confidence: {response.confidence:.0%}"
    if response.model_id != "mock:reviewed-examples":
        metadata += (
            f" · Tokens: {response.input_tokens} input + {response.output_tokens} output "
            f"= {response.total_tokens} total"
        )
        if response.latency_ms is not None:
            metadata += f" · Latency: {response.latency_ms} ms"
    st.caption(metadata)


def render_response(response: ChatResponse, *, key: str) -> None:
    if response.error:
        st.error(response.summary)
        st.caption(response.error)
        if response.cypher:
            (cypher_tab,) = st.tabs(["Generated Cypher"])
            with cypher_tab:
                st.code(response.cypher, language="cypher")
                st.write("Parameters", response.parameters or {})
            render_model_metadata(response)
        return
    if response.clarification:
        st.info(response.clarification)
        st.caption(response.summary)
        if response.confidence is not None:
            st.caption(f"Confidence: {response.confidence:.0%}")
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
            st.download_button(
                "Download CSV",
                data=rows_to_csv(response.rows),
                file_name="integration-catalogue-results.csv",
                mime="text/csv",
                key=f"{key}-download",
            )
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

    render_model_metadata(response)


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
