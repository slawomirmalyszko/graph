"""Chat-shell content independent of Streamlit rendering."""

EXAMPLE_QUESTIONS = (
    "How many applications are there?",
    "Show all objects carried by integrations.",
    "Show all end-to-end flows that interface with SAP.",
    "Show the full path between Salesforce CRM and SAP S/4HANA.",
)


def pending_query_response(question: str) -> str:
    return (
        f"AuraDB is connected, but **{question}** was not executed. "
        "Controlled natural-language-to-Cypher generation is the next migration step."
    )
