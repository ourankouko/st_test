import streamlit as st
import pandas as pd
from pyvis.network import Network
import streamlit.components.v1 as components
import tempfile

st.set_page_config(page_title="Graph Network App", layout="wide")

st.title("Google Sheets Graph Network App")

# ----------------------------------------------------
# Google Sheet settings
# ----------------------------------------------------
SHEET_ID = "10TvWjCVU9xzqmggJeKQI50BzsdYPucuTfbboQTLtpb0"

# Replace these with the actual gid values of your tabs
EDGES_GID = "0"
NODES_GID = "1026224586"

edges_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={EDGES_GID}"
nodes_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={NODES_GID}"


@st.cache_data(ttl=600)
def load_data():
    edges = pd.read_csv(edges_url)
    nodes = pd.read_csv(nodes_url)
    return edges, nodes


edges, nodes = load_data()

# ----------------------------------------------------
# Basic cleanup
# ----------------------------------------------------
edges.columns = edges.columns.str.strip()
nodes.columns = nodes.columns.str.strip()

for col in ["From Name", "To Name", "From Type", "To Type", "Edge Type"]:
    if col in edges.columns:
        edges[col] = edges[col].astype("string").str.strip()

if "Name" in nodes.columns:
    nodes["Name"] = nodes["Name"].astype("string").str.strip()

if "Type" in nodes.columns:
    nodes["Type"] = nodes["Type"].astype("string").str.strip()

if "Weight" in edges.columns:
    edges["Weight"] = pd.to_numeric(edges["Weight"], errors="coerce").fillna(1)
else:
    edges["Weight"] = 1

# Remove empty edges
edges = edges[
    edges["From Name"].notna()
    & edges["To Name"].notna()
    & (edges["From Name"] != "")
    & (edges["To Name"] != "")
].copy()

# ----------------------------------------------------
# Sidebar filters
# ----------------------------------------------------
st.sidebar.header("Filters")

edge_types = sorted(edges["Edge Type"].dropna().unique().tolist())
selected_edge_types = st.sidebar.multiselect(
    "Edge Type",
    edge_types,
    default=edge_types
)

from_types = sorted(edges["From Type"].dropna().unique().tolist())
selected_from_types = st.sidebar.multiselect(
    "From Type",
    from_types,
    default=from_types
)

to_types = sorted(edges["To Type"].dropna().unique().tolist())
selected_to_types = st.sidebar.multiselect(
    "To Type",
    to_types,
    default=to_types
)

min_weight = st.sidebar.slider(
    "Minimum Weight",
    min_value=int(edges["Weight"].min()),
    max_value=int(edges["Weight"].max()),
    value=int(edges["Weight"].min())
)

search_name = st.sidebar.text_input("Search person / organisation name")

filtered_edges = edges[
    edges["Edge Type"].isin(selected_edge_types)
    & edges["From Type"].isin(selected_from_types)
    & edges["To Type"].isin(selected_to_types)
    & (edges["Weight"] >= min_weight)
].copy()

if search_name:
    search_name_lower = search_name.lower()
    filtered_edges = filtered_edges[
        filtered_edges["From Name"].str.lower().str.contains(search_name_lower, na=False)
        | filtered_edges["To Name"].str.lower().str.contains(search_name_lower, na=False)
    ]

if filtered_edges.empty:
    st.warning("No edges match the current filters.")
    st.stop()

# ----------------------------------------------------
# Summary
# ----------------------------------------------------
unique_nodes = pd.unique(
    pd.concat([
        filtered_edges["From Name"],
        filtered_edges["To Name"]
    ], ignore_index=True)
)

col1, col2, col3 = st.columns(3)

col1.metric("Nodes", len(unique_nodes))
col2.metric("Edges", len(filtered_edges))
col3.metric("Total Weight", int(filtered_edges["Weight"].sum()))

# ----------------------------------------------------
# Build graph
# ----------------------------------------------------
def get_node_type(name):
    match_from = filtered_edges.loc[filtered_edges["From Name"] == name, "From Type"]
    if len(match_from) > 0:
        return match_from.iloc[0]

    match_to = filtered_edges.loc[filtered_edges["To Name"] == name, "To Type"]
    if len(match_to) > 0:
        return match_to.iloc[0]

    return "Unknown"


def get_node_color(node_type):
    color_map = {
        "Hololive": "#99e6ff",
        "Crazy Raccoon": "#ffd966",
        "DEV_IS": "#c9daf8",
        "Unknown": "#dddddd",
    }
    return color_map.get(node_type, "#dddddd")


net = Network(
    height="750px",
    width="100%",
    bgcolor="#111111",
    font_color="white",
    directed=False
)

net.barnes_hut(
    gravity=-30000,
    central_gravity=0.3,
    spring_length=150,
    spring_strength=0.05,
    damping=0.09,
    overlap=0
)

# Add nodes
for node in unique_nodes:
    node_type = get_node_type(node)

    net.add_node(
        node,
        label=node,
        title=f"{node}<br>Type: {node_type}",
        color=get_node_color(node_type),
        size=18
    )

# Add edges
for _, row in filtered_edges.iterrows():
    from_name = row["From Name"]
    to_name = row["To Name"]
    edge_type = row["Edge Type"]
    weight = row["Weight"]

    date = row["Date"] if "Date" in row and pd.notna(row["Date"]) else ""

    net.add_edge(
        from_name,
        to_name,
        value=float(weight),
        title=f"Type: {edge_type}<br>Weight: {weight}<br>Date: {date}",
        label=edge_type
    )

# ----------------------------------------------------
# Display graph
# ----------------------------------------------------
st.subheader("Network Graph")

with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp_file:
    net.save_graph(tmp_file.name)
    html = open(tmp_file.name, "r", encoding="utf-8").read()

components.html(html, height=780, scrolling=True)

# ----------------------------------------------------
# Data tables
# ----------------------------------------------------
with st.expander("View filtered edge data"):
    st.dataframe(filtered_edges)

with st.expander("View node data"):
    st.dataframe(nodes)

# ----------------------------------------------------
# Chatbot
# ----------------------------------------------------

st.subheader("Ask about the graph")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Display previous chat messages
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

question = st.chat_input("Ask a question about the graph")

if question:
    # Show the user's question immediately
    with st.chat_message("user"):
        st.write(question)

    st.session_state.chat_history.append({
        "role": "user",
        "content": question
    })

    q = question.lower()
    table_to_show = None
    chart_to_show = None

    if "how many node" in q:
        answer = f"There are {len(unique_nodes)} nodes in the current filtered graph."

    elif "how many edge" in q or "how many connection" in q:
        answer = f"There are {len(filtered_edges)} edges in the current filtered graph."

    elif "top" in q or "most connected" in q:
        top_nodes = (
            pd.concat([
                filtered_edges["From Name"],
                filtered_edges["To Name"]
            ])
            .value_counts()
            .head(10)
        )

        answer = "Top connected nodes:\n\n"
        for name, count in top_nodes.items():
            answer += f"- {name}: {count} connections\n"

    elif "show" in q or "find" in q or "involving" in q or "connected to" in q:
        stop_words = {
            "show", "find", "involving", "connections", "connection",
            "connected", "to", "with", "the", "a", "an", "and", "of",
            "edges", "edge", "links", "link"
        }

        keywords = [
            word for word in q.split()
            if word not in stop_words and len(word) > 1
        ]

        if keywords:
            matches = filtered_edges[
                filtered_edges["From Name"].str.lower().apply(
                    lambda x: any(word in x for word in keywords)
                )
                | filtered_edges["To Name"].str.lower().apply(
                    lambda x: any(word in x for word in keywords)
                )
            ]
        else:
            matches = pd.DataFrame()

        if len(matches) > 0:
            answer = f"I found {len(matches)} matching edges. Showing them below."
            table_to_show = matches
        else:
            answer = "I could not find matching edges in the current filtered graph."

    else:
        answer = "I can currently answer simple questions about node count, edge count, and top connected nodes."

    # Show assistant response first, then table inside the same assistant message
    with st.chat_message("assistant"):
        st.write(answer)

        if table_to_show is not None:
            st.dataframe(table_to_show)

    st.session_state.chat_history.append({
        "role": "assistant",
        "content": answer
    })
