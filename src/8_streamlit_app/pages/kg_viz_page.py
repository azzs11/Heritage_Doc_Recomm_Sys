"""
Knowledge Graph Visualization Page

Features:
- Interactive PyVis network visualization
- Subgraph extraction around query results
- Node filtering by type
- Edge filtering by relationship type
- Customizable layout and physics
"""

import streamlit as st
import streamlit.components.v1 as components
import pickle
import networkx as nx
from pathlib import Path
import tempfile


@st.cache_resource
def load_kg():
    """Load knowledge graph (cached)."""
    # Get project root (4 levels up from this file)
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
    kg_path = PROJECT_ROOT / 'knowledge_graph' / 'heritage_kg.gpickle'
    
    if not kg_path.exists():
        raise FileNotFoundError(
            f"Knowledge graph file not found at: {kg_path.absolute()}\n\n"
            f"To generate the knowledge graph, run:\n"
            f"  python src/4_knowledge_graph/5_build_knowledge_graph.py"
        )
    
    with open(kg_path, 'rb') as f:
        G = pickle.load(f)
    return G


def create_pyvis_network(G_sub, layout='spring', physics=True):
    """
    Create PyVis network from NetworkX graph.

    Args:
        G_sub: NetworkX subgraph
        layout: Layout algorithm ('spring', 'hierarchical', 'circular')
        physics: Enable physics simulation

    Returns:
        HTML string for PyVis visualization
    """
    try:
        from pyvis.network import Network
    except ImportError:
        st.error("PyVis not installed. Run: pip install pyvis")
        return None

    # Create PyVis network
    net = Network(
        height='700px',
        width='100%',
        bgcolor='#0f172a',
        font_color='#f1f5f9',
        notebook=False,
        directed=G_sub.is_directed()
    )

    # Color scheme by node type
    color_map = {
        'document': '#1f77b4',      # Blue
        'location': '#ff7f0e',      # Orange
        'person': '#2ca02c',        # Green
        'organization': '#d62728',  # Red
        'heritage_type': '#9467bd', # Purple
        'domain': '#8c564b',        # Brown
        'time_period': '#e377c2',   # Pink
        'region': '#7f7f7f'         # Gray
    }

    # Add nodes
    for node, data in G_sub.nodes(data=True):
        node_type = data.get('node_type', 'unknown')
        color = color_map.get(node_type, '#bcbd22')

        # Node size based on degree
        degree = G_sub.degree(node)
        size = 10 + degree * 2

        # Title (hover text)
        title = f"<b>{node}</b><br>Type: {node_type}<br>Degree: {degree}"

        # Label
        label = data.get('title', node) if node_type == 'document' else node

        # Add node
        net.add_node(
            node,
            label=label,
            title=title,
            color=color,
            size=size,
            shape='dot' if node_type != 'document' else 'box'
        )

    # Add edges
    for source, target, data in G_sub.edges(data=True):
        edge_type = data.get('relation', data.get('type', 'unknown'))
        net.add_edge(source, target, title=edge_type, label=edge_type)

    # Configure physics
    if physics:
        net.set_options("""
        {
          "physics": {
            "enabled": true,
            "barnesHut": {
              "gravitationalConstant": -8000,
              "centralGravity": 0.3,
              "springLength": 95,
              "springConstant": 0.04
            },
            "stabilization": {
              "iterations": 150
            }
          }
        }
        """)
    else:
        net.toggle_physics(False)

    # Generate HTML
    return net.generate_html()


def render():
    """Render KG visualization page."""
    st.markdown('<h1 class="main-header">🕸️ Knowledge Graph Visualization</h1>', unsafe_allow_html=True)

    st.markdown("""
    Explore the Heritage Knowledge Graph interactively. The graph contains documents,
    entities (locations, persons, organizations), and concepts (heritage types, domains, periods).
    """)

    # Load KG
    try:
        G = load_kg()
    except FileNotFoundError as e:
        st.error(f"""
        **🚨 Knowledge Graph File Not Found**
        
        The knowledge graph file is required for visualization.
        
        **To generate the knowledge graph:**
        1. Run: `python src/4_knowledge_graph/horn_index.py`
        2. This will create: `knowledge_graph/heritage_kg.gpickle`
        3. Refresh this page after generation
        
        **File expected at:** `knowledge_graph/heritage_kg.gpickle`
        """)
        return
    except Exception as e:
        st.error(f"**Failed to load knowledge graph:** {str(e)}")
        return

    # KG Statistics
    st.markdown("### 📊 Knowledge Graph Statistics")

    stat_cols = st.columns(4)

    with stat_cols[0]:
        st.metric("Total Nodes", G.number_of_nodes())

    with stat_cols[1]:
        st.metric("Total Edges", G.number_of_edges())

    with stat_cols[2]:
        st.metric("Graph Density", f"{nx.density(G):.4f}")

    with stat_cols[3]:
        st.metric("Components", nx.number_connected_components(G.to_undirected()))

    # Node type breakdown
    node_types = {}
    for node, data in G.nodes(data=True):
        node_type = data.get('node_type', 'unknown')
        node_types[node_type] = node_types.get(node_type, 0) + 1

    st.markdown("**Node Types:**")
    type_cols = st.columns(len(node_types))
    for i, (node_type, count) in enumerate(sorted(node_types.items())):
        type_cols[i].metric(node_type.replace('_', ' ').title(), count)

    st.markdown("---")

    # Visualization options
    st.markdown("### 🎨 Visualization Options")

    viz_col1, viz_col2 = st.columns(2)

    with viz_col1:
        # Subgraph extraction mode
        mode = st.radio(
            "Visualization Mode",
            ["Full Graph", "Subgraph from Search Results", "Subgraph Around Node", "Neighborhood"],
            help="Choose what to visualize"
        )

    with viz_col2:
        # Layout and physics
        layout = st.selectbox("Layout Algorithm", ["spring", "hierarchical", "circular"])
        physics = st.checkbox("Enable Physics Simulation", value=True)
        max_nodes = st.slider("Max Nodes to Display", 10, 3000, 2480, 100,
                             help="Limit number of nodes for performance")

    # Node and edge filters
    with st.expander("🔧 Filters"):
        filter_col1, filter_col2 = st.columns(2)

        with filter_col1:
            st.markdown("**Node Type Filters:**")
            include_node_types = st.multiselect(
                "Include Node Types",
                options=list(node_types.keys()),
                default=list(node_types.keys()),
                label_visibility="collapsed"
            )

        with filter_col2:
            st.markdown("**Edge Type Filters:**")

            # Get edge types
            edge_types = set()
            for _, _, data in G.edges(data=True):
                edge_types.add(data.get('relation', data.get('type', 'unknown')))

            include_edge_types = st.multiselect(
                "Include Edge Types",
                options=sorted(edge_types),
                default=sorted(edge_types),
                label_visibility="collapsed"
            )

    # Create subgraph based on mode
    G_sub = G.copy()

    if mode == "Subgraph from Search Results":
        if 'recommendations' not in st.session_state:
            st.warning("No search results found. Please run a search first on the Search page.")
            if st.button("Go to Search"):
                st.switch_page("pages/search_page.py")
            return

        # Extract subgraph around recommended documents
        recommendations = st.session_state['recommendations']
        top_k_viz = st.slider("Documents to Include", 1, len(recommendations), min(5, len(recommendations)))

        # Get document nodes
        doc_nodes = [rec['doc_id'] for rec in recommendations[:top_k_viz]]

        # Get 2-hop neighborhood
        subgraph_nodes = set(doc_nodes)
        for doc in doc_nodes:
            subgraph_nodes.update(G.neighbors(doc))
            for neighbor in G.neighbors(doc):
                subgraph_nodes.update(G.neighbors(neighbor))

        G_sub = G.subgraph(list(subgraph_nodes)[:max_nodes])

        st.info(f"Showing 2-hop neighborhood around top-{top_k_viz} recommended documents ({G_sub.number_of_nodes()} nodes)")

    elif mode == "Subgraph Around Node":
        # Select a node
        all_nodes = list(G.nodes())
        selected_node = st.selectbox("Select Node", all_nodes[:1000], help="First 1000 nodes shown")

        hops = st.slider("Number of Hops", 1, 3, 2)

        # Get k-hop neighborhood
        subgraph_nodes = set([selected_node])
        current_layer = {selected_node}

        for _ in range(hops):
            next_layer = set()
            for node in current_layer:
                neighbors = set(G.neighbors(node))
                next_layer.update(neighbors)
            subgraph_nodes.update(next_layer)
            current_layer = next_layer

        G_sub = G.subgraph(list(subgraph_nodes)[:max_nodes])

        st.info(f"Showing {hops}-hop neighborhood around '{selected_node}' ({G_sub.number_of_nodes()} nodes)")

    elif mode == "Neighborhood":
        # Random sample of nodes
        import random
        sample_size = min(max_nodes, G.number_of_nodes())
        sampled_nodes = random.sample(list(G.nodes()), sample_size)
        G_sub = G.subgraph(sampled_nodes)

        st.info(f"Showing random sample of {sample_size} nodes")

    else:  # Full Graph
        G_sub = G
        st.info(f"Showing full graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")

    # Apply filters
    nodes_to_keep = []
    for node, data in G_sub.nodes(data=True):
        node_type = data.get('node_type', 'unknown')
        if node_type in include_node_types:
            nodes_to_keep.append(node)

    G_sub = G_sub.subgraph(nodes_to_keep)

    # Filter edges
    edges_to_keep = []
    for u, v, data in G_sub.edges(data=True):
        edge_type = data.get('relation', data.get('type', 'unknown'))
        if edge_type in include_edge_types:
            edges_to_keep.append((u, v))

    G_sub = G_sub.edge_subgraph(edges_to_keep)

    st.markdown(f"**Filtered Graph:** {G_sub.number_of_nodes()} nodes, {G_sub.number_of_edges()} edges")

    # Generate visualization
    st.markdown("---")
    st.markdown("### 🎯 Interactive Visualization")

    with st.spinner("Generating visualization..."):
        html = create_pyvis_network(G_sub, layout=layout, physics=physics)

        if html:
            # Display PyVis network
            components.html(html, height=750, scrolling=True)

            # Legend
            st.markdown("**Legend:**")
            legend_cols = st.columns(4)

            legend_items = [
                ("Document", "#1f77b4", "box"),
                ("Location", "#ff7f0e", "dot"),
                ("Person", "#2ca02c", "dot"),
                ("Organization", "#d62728", "dot"),
                ("Heritage Type", "#9467bd", "dot"),
                ("Domain", "#8c564b", "dot"),
                ("Time Period", "#e377c2", "dot"),
                ("Region", "#7f7f7f", "dot")
            ]

            for i, (label, color, shape) in enumerate(legend_items):
                col_idx = i % 4
                shape_char = "■" if shape == "box" else "●"
                legend_cols[col_idx].markdown(
                    f'<span style="color: {color}; font-size: 1.5rem;">{shape_char}</span> {label}',
                    unsafe_allow_html=True
                )

    # Download options
    st.markdown("---")
    st.markdown("### 💾 Export Options")

    export_col1, export_col2 = st.columns(2)

    with export_col1:
        # Export as GraphML
        if st.button("Export as GraphML", use_container_width=True):
            import io
            buffer = io.BytesIO()
            nx.write_graphml(G_sub, buffer)
            st.download_button(
                "Download GraphML",
                data=buffer.getvalue(),
                file_name="heritage_kg_subgraph.graphml",
                mime="application/xml"
            )

    with export_col2:
        # Export statistics
        if st.button("Export Statistics", use_container_width=True):
            import json
            stats = {
                "nodes": G_sub.number_of_nodes(),
                "edges": G_sub.number_of_edges(),
                "density": nx.density(G_sub),
                "node_types": dict(node_types),
                "avg_degree": sum(dict(G_sub.degree()).values()) / G_sub.number_of_nodes()
            }

            st.download_button(
                "Download JSON",
                data=json.dumps(stats, indent=2),
                file_name="kg_statistics.json",
                mime="application/json"
            )


if __name__ == "__main__":
    render()
