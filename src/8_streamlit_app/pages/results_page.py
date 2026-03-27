"""
Results & Explanations Page

Features:
- Detailed recommendation results
- Score breakdowns with visualizations
- Knowledge graph path explanations
- Document metadata
- Comparison between recommendations
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd


def create_score_breakdown_chart(rec, weights):
    """Create interactive bar chart for score breakdown."""
    components = ['SimRank', "Horn's Index", 'Embedding']
    scores = [
        rec['component_scores']['simrank'],
        rec['component_scores']['horn'],
        rec['component_scores']['embedding']
    ]
    weighted_scores = [
        weights[0] * scores[0],
        weights[1] * scores[1],
        weights[2] * scores[2]
    ]

    fig = go.Figure(data=[
        go.Bar(name='Raw Score', x=components, y=scores, marker_color='#93c5fd'),
        go.Bar(name='Weighted Score', x=components, y=weighted_scores, marker_color='#2563eb')
    ])

    fig.update_layout(
        title=f"Score Breakdown: {rec['title']}",
        xaxis_title="Component",
        yaxis_title="Score",
        barmode='group',
        height=400,
        hovermode='x unified'
    )

    return fig


def create_comparison_chart(recommendations, top_n=10):
    """Create comparison chart for top-N recommendations."""
    df_data = []

    for rec in recommendations[:top_n]:
        df_data.append({
            'Document': rec['title'][:40] + '...' if len(rec['title']) > 40 else rec['title'],
            'SimRank': rec['component_scores']['simrank'],
            "Horn's Index": rec['component_scores']['horn'],
            'Embedding': rec['component_scores']['embedding'],
            'Hybrid Score': rec['hybrid_score']
        })

    df = pd.DataFrame(df_data)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='SimRank',
        x=df['Document'],
        y=df['SimRank'],
        marker_color='#2563eb'
    ))

    fig.add_trace(go.Bar(
        name="Horn's Index",
        x=df['Document'],
        y=df["Horn's Index"],
        marker_color='#0d9488'
    ))

    fig.add_trace(go.Bar(
        name='Embedding',
        x=df['Document'],
        y=df['Embedding'],
        marker_color='#475569'
    ))

    fig.update_layout(
        title=f"Top-{top_n} Recommendations Comparison",
        xaxis_title="Document",
        yaxis_title="Component Score",
        barmode='stack',
        height=500,
        hovermode='x unified',
        xaxis={'tickangle': -45}
    )

    return fig


def create_hybrid_score_distribution(recommendations):
    """Create histogram of hybrid scores."""
    scores = [rec['hybrid_score'] for rec in recommendations]

    fig = go.Figure(data=[go.Histogram(x=scores, nbinsx=20, marker_color='#2563eb')])

    fig.update_layout(
        title="Hybrid Score Distribution",
        xaxis_title="Hybrid Score",
        yaxis_title="Frequency",
        height=400
    )

    return fig


def render():
    """Render results and explanations page."""
    st.markdown('<h1 class="main-header">📊 Results & Explanations</h1>', unsafe_allow_html=True)

    # Check if results exist
    if 'recommendations' not in st.session_state:
        st.warning("No search results found. Please run a search first.")
        if st.button("Go to Search Page"):
            st.switch_page("pages/search_page.py")
        return

    recommendations = st.session_state['recommendations']
    query_text = st.session_state.get('query_text', 'Unknown Query')
    top_k = st.session_state.get('top_k', len(recommendations))

    # Query summary
    st.markdown(f"### 🔍 Query: \"{query_text}\"")
    st.markdown(f"**Found {len(recommendations)} results (Top-{top_k})**")

    st.markdown("---")

    # Overview visualizations
    st.markdown("### 📈 Overview")

    viz_col1, viz_col2 = st.columns(2)

    with viz_col1:
        # Comparison chart
        comparison_chart = create_comparison_chart(recommendations, min(10, len(recommendations)))
        st.plotly_chart(comparison_chart, use_container_width=True)

    with viz_col2:
        # Score distribution
        score_dist = create_hybrid_score_distribution(recommendations)
        st.plotly_chart(score_dist, use_container_width=True)

    # Summary statistics
    st.markdown("**Summary Statistics:**")

    stat_cols = st.columns(5)

    hybrid_scores = [rec['hybrid_score'] for rec in recommendations]
    simrank_scores = [rec['component_scores']['simrank'] for rec in recommendations]
    horn_scores = [rec['component_scores']['horn'] for rec in recommendations]
    embedding_scores = [rec['component_scores']['embedding'] for rec in recommendations]

    with stat_cols[0]:
        st.metric("Avg Hybrid Score", f"{sum(hybrid_scores) / len(hybrid_scores):.4f}")

    with stat_cols[1]:
        st.metric("Avg SimRank", f"{sum(simrank_scores) / len(simrank_scores):.4f}")

    with stat_cols[2]:
        st.metric("Avg Horn", f"{sum(horn_scores) / len(horn_scores):.4f}")

    with stat_cols[3]:
        st.metric("Avg Embedding", f"{sum(embedding_scores) / len(embedding_scores):.4f}")

    with stat_cols[4]:
        st.metric("Score Range", f"{min(hybrid_scores):.4f} - {max(hybrid_scores):.4f}")

    st.markdown("---")

    # Detailed results
    st.markdown("### 📄 Detailed Results")

    # Sorting options
    sort_col1, sort_col2 = st.columns([3, 1])

    with sort_col1:
        sort_by = st.selectbox(
            "Sort By",
            ["Hybrid Score", "SimRank", "Horn's Index", "Embedding", "Title"]
        )

    with sort_col2:
        sort_order = st.radio("Order", ["Descending", "Ascending"], horizontal=True)

    # Sort recommendations
    if sort_by == "Hybrid Score":
        sorted_recs = sorted(recommendations, key=lambda x: x['hybrid_score'],
                           reverse=(sort_order == "Descending"))
    elif sort_by == "SimRank":
        sorted_recs = sorted(recommendations, key=lambda x: x['component_scores']['simrank'],
                           reverse=(sort_order == "Descending"))
    elif sort_by == "Horn's Index":
        sorted_recs = sorted(recommendations, key=lambda x: x['component_scores']['horn'],
                           reverse=(sort_order == "Descending"))
    elif sort_by == "Embedding":
        sorted_recs = sorted(recommendations, key=lambda x: x['component_scores']['embedding'],
                           reverse=(sort_order == "Descending"))
    else:  # Title
        sorted_recs = sorted(recommendations, key=lambda x: x['title'],
                           reverse=(sort_order == "Descending"))

    # Display recommendations
    for i, rec in enumerate(sorted_recs, 1):
        with st.expander(
            f"#{rec['rank']} {rec['title']} — Hybrid Score: {rec['hybrid_score']:.4f}",
            expanded=(i <= 3)
        ):
            # Two columns: left for details, right for chart
            detail_col, chart_col = st.columns([2, 1])

            with detail_col:
                # Metadata
                st.markdown("**Metadata:**")
                meta_info = []

                if rec['metadata'].get('heritage_type'):
                    meta_info.append(f"**Heritage Type:** {rec['metadata']['heritage_type']}")
                if rec['metadata'].get('domain'):
                    meta_info.append(f"**Domain:** {rec['metadata']['domain']}")
                if rec['metadata'].get('time_period'):
                    meta_info.append(f"**Time Period:** {rec['metadata']['time_period']}")
                if rec['metadata'].get('region'):
                    meta_info.append(f"**Region:** {rec['metadata']['region']}")

                if meta_info:
                    st.markdown(" | ".join(meta_info))
                else:
                    st.info("No metadata available")

                # Score details
                st.markdown("**Score Components:**")

                score_df = pd.DataFrame({
                    'Component': ['SimRank', "Horn's Index", 'Embedding'],
                    'Raw Score': [
                        rec['component_scores']['simrank'],
                        rec['component_scores']['horn'],
                        rec['component_scores']['embedding']
                    ],
                    'Weight': [0.4, 0.3, 0.3],  # Default weights
                    'Contribution': [
                        0.4 * rec['component_scores']['simrank'],
                        0.3 * rec['component_scores']['horn'],
                        0.3 * rec['component_scores']['embedding']
                    ]
                })

                st.dataframe(score_df, use_container_width=True, hide_index=True)

                st.markdown(f"**Total Hybrid Score:** `{rec['hybrid_score']:.4f}`")

            with chart_col:
                # Score breakdown chart
                breakdown_fig = create_score_breakdown_chart(rec, [0.4, 0.3, 0.3])
                st.plotly_chart(breakdown_fig, use_container_width=True, key=f"breakdown_{i}")

            # KG Explanations
            if rec.get('kg_explanations'):
                st.markdown("---")
                st.markdown("**🕸️ Knowledge Graph Explanations:**")
                st.markdown("*Why this document was recommended (based on graph connections):*")

                for j, path in enumerate(rec['kg_explanations'][:5], 1):
                    st.markdown(
                        f'<div class="kg-path">{j}. {path}</div>',
                        unsafe_allow_html=True
                    )
            else:
                st.info("No knowledge graph paths available for this recommendation")

            # Document ID
            st.markdown(f"**Document ID:** `{rec['doc_id']}`")

    # Export options
    st.markdown("---")
    st.markdown("### 💾 Export Results")

    export_col1, export_col2, export_col3 = st.columns(3)

    with export_col1:
        if st.button("Export as CSV", use_container_width=True):
            # Prepare CSV data
            csv_data = []
            for rec in recommendations:
                csv_data.append({
                    'Rank': rec['rank'],
                    'Title': rec['title'],
                    'Hybrid Score': rec['hybrid_score'],
                    'SimRank': rec['component_scores']['simrank'],
                    "Horn's Index": rec['component_scores']['horn'],
                    'Embedding': rec['component_scores']['embedding'],
                    'Heritage Type': rec['metadata'].get('heritage_type', ''),
                    'Domain': rec['metadata'].get('domain', ''),
                    'Time Period': rec['metadata'].get('time_period', ''),
                    'Region': rec['metadata'].get('region', ''),
                    'Document ID': rec['doc_id']
                })

            df = pd.DataFrame(csv_data)
            csv = df.to_csv(index=False)

            st.download_button(
                "Download CSV",
                data=csv,
                file_name=f"heritage_recommendations_{query_text[:20]}.csv",
                mime="text/csv"
            )

    with export_col2:
        if st.button("Export as JSON", use_container_width=True):
            import json

            st.download_button(
                "Download JSON",
                data=json.dumps(recommendations, indent=2),
                file_name=f"heritage_recommendations_{query_text[:20]}.json",
                mime="application/json"
            )

    with export_col3:
        if st.button("Generate Report", use_container_width=True):
            # Generate markdown report
            report = f"# Heritage Recommendation Report\n\n"
            report += f"**Query:** {query_text}\n\n"
            report += f"**Date:** {pd.Timestamp.now()}\n\n"
            report += f"**Results:** {len(recommendations)} documents\n\n"
            report += "---\n\n"

            for rec in recommendations[:10]:
                report += f"## #{rec['rank']} {rec['title']}\n\n"
                report += f"**Hybrid Score:** {rec['hybrid_score']:.4f}\n\n"
                report += f"- SimRank: {rec['component_scores']['simrank']:.4f}\n"
                report += f"- Horn's Index: {rec['component_scores']['horn']:.4f}\n"
                report += f"- Embedding: {rec['component_scores']['embedding']:.4f}\n\n"

                if rec.get('kg_explanations'):
                    report += "**Explanations:**\n"
                    for path in rec['kg_explanations'][:3]:
                        report += f"- {path}\n"
                    report += "\n"

                report += "---\n\n"

            st.download_button(
                "Download Report (MD)",
                data=report,
                file_name=f"heritage_report_{query_text[:20]}.md",
                mime="text/markdown"
            )


if __name__ == "__main__":
    render()
