import streamlit as st
import sys
from pathlib import Path
import plotly.graph_objects as go

# Get project root (4 levels up from this file)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.append(str(PROJECT_ROOT / 'src' / '6_query_system'))

from query_processor import QueryProcessor
from recommender import HeritageRecommender


@st.cache_resource
def load_system():
    """Load system (cached)."""
    try:
        # Change to project root temporarily for file access
        import os
        original_cwd = os.getcwd()
        
        try:
            # Try to change to project root if files not found in current dir
            if not Path('knowledge_graph/heritage_kg.gpickle').exists():
                os.chdir(PROJECT_ROOT)
            
            processor = QueryProcessor()
            recommender = HeritageRecommender()
            return processor, recommender, None
        finally:
            os.chdir(original_cwd)
    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        return None, None, error_msg


def create_score_gauge(score, title, color):
    """Create a gauge chart for scores."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={'text': title, 'font': {'size': 14, 'color': '#f1f5f9'}},
        number={'font': {'size': 20, 'color': '#f1f5f9'}},
        gauge={
            'axis': {'range': [0, 1], 'tickwidth': 1, 'tickcolor': '#94a3b8'},
            'bar': {'color': color},
            'bgcolor': "#1e293b",
            'borderwidth': 2,
            'bordercolor': "#334155",
            'steps': [
                {'range': [0, 0.33], 'color': 'rgba(239, 68, 68, 0.2)'},
                {'range': [0.33, 0.67], 'color': 'rgba(245, 158, 11, 0.2)'},
                {'range': [0.67, 1], 'color': 'rgba(16, 185, 129, 0.2)'}
            ],
            'threshold': {
                'line': {'color': color, 'width': 4},
                'thickness': 0.75,
                'value': 0.9
            }
        }
    ))
    
    fig.update_layout(
        height=200,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'family': 'Inter', 'color': '#f1f5f9'}
    )
    
    return fig


def render():
    """Render enhanced search page."""
    
    # Header
    st.markdown('<h1 class="main-header">🔍 Heritage Document Search</h1>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class='info-box'>
        <strong>🎯 How It Works:</strong> Enter a natural language query about heritage documents. 
        Our AI system will understand your intent, extract relevant attributes, and recommend 
        documents using a hybrid approach combining <strong>graph structure</strong>, 
        <strong>entity importance</strong>, and <strong>semantic similarity</strong>.
    </div>
    """, unsafe_allow_html=True)
    
    # Load system
    processor, recommender, error = load_system()
    
    if error or processor is None or recommender is None:
        st.error(f"""
        **🚨 System Error: Cannot Load Components**
        
        {error if error else "Failed to initialize system components"}
        
        **Required Setup:**
        1. Ensure knowledge graph exists: `knowledge_graph/heritage_kg.gpickle`
        2. Run Horn's Index: `python src/4_knowledge_graph/horn_index.py`
        3. Verify all required files are present
        
        **Please check the error message above and ensure all dependencies are installed.**
        """)
        return
    
    # ========== SEARCH INPUT SECTION ==========
    st.markdown("## 📝 Enter Your Search Query")
    
    col1, col2 = st.columns([4, 1])
    
    with col1:
        query_text = st.text_input(
            "Search Query",
            placeholder="e.g., 'Buddhist monasteries in ancient India', 'Mughal palaces', 'Temples in South India'...",
            label_visibility="collapsed",
            key="main_query"
        )
    
    with col2:
        top_k = st.number_input(
            "Results", 
            min_value=5, 
            max_value=50, 
            value=10, 
            step=5,
            help="Number of recommendations to return"
        )
    
    # ========== EXAMPLE QUERIES ==========
    st.markdown("### 💡 Try These Examples")
    
    example_cols = st.columns(4)
    
    examples = [
        "🕌 Mughal architecture",
        "🏯 Ancient Buddhist monasteries",
        "⛰️ Forts in Rajasthan",
        "🛕 Dravidian temples"
    ]
    
    for i, example in enumerate(examples):
        if example_cols[i].button(example, key=f"ex_{i}", use_container_width=True):
            query_text = example.split(" ", 1)[1]  # Remove emoji
            st.rerun()
    
    st.markdown("---")
    
    # ========== ADVANCED OPTIONS ==========
    simrank_weight = 0.4
    horn_weight = 0.3
    embedding_weight = 0.3
    
    with st.expander("⚙️ Advanced Options", expanded=False):
        tab1, tab2 = st.tabs(["🎚️ Score Weights", "🔍 Filters"])
        
        with tab1:
            st.markdown("**Customize Hybrid Scoring:**")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                simrank_weight = st.slider(
                    "🕸️ SimRank (Graph)",
                    0.0, 1.0, 0.4, 0.05,
                    help="Weight for graph structure similarity"
                )
            
            with col2:
                horn_weight = st.slider(
                    "⭐ Horn's Index (Importance)",
                    0.0, 1.0, 0.3, 0.05,
                    help="Weight for entity importance"
                )
            
            with col3:
                embedding_weight = st.slider(
                    "🧠 Embeddings (Semantic)",
                    0.0, 1.0, 0.3, 0.05,
                    help="Weight for semantic similarity"
                )
            
            total = simrank_weight + horn_weight + embedding_weight
            if abs(total - 1.0) > 0.01:
                st.warning(f"⚠️ Weights sum to {total:.2f}, will normalize to 1.0")
        
        with tab2:
            st.markdown("**Filter Results:**")
            
            fcol1, fcol2 = st.columns(2)
            
            with fcol1:
                filter_period = st.multiselect(
                    "Time Period",
                    ["ancient", "medieval", "modern"]
                )
                
                filter_region = st.multiselect(
                    "Region",
                    ["north", "south", "east", "west", "central"]
                )
            
            with fcol2:
                filter_heritage = st.multiselect(
                    "Heritage Type",
                    ["temple", "fort", "palace", "monastery", "mosque", "stupa"]
                )
                
                filter_domain = st.multiselect(
                    "Domain",
                    ["religious", "military", "royal", "cultural"]
                )
    
    # ========== SEARCH BUTTON ==========
    search_clicked = st.button("🔍 Search Now", type="primary", use_container_width=True)
    
    if not search_clicked and not query_text:
        st.info("👆 Enter a query above to start searching")
        return
    
    if query_text:
        # ========== QUERY PARSING ==========
        try:
            with st.spinner("🔍 Parsing your query..."):
                parsed_query = processor.parse_query(query_text)
        except Exception as e:
            st.error(f"❌ Error parsing query: {str(e)}")
            return
        
        # Display parsed attributes
        st.markdown("---")
        st.markdown("## 🔎 Query Understanding")

        attr_col1, attr_col2, attr_col3, attr_col4 = st.columns(4)

        # Extract and convert sets to display strings
        heritage_types = parsed_query.get('heritage_types', set())
        heritage_display = ', '.join(sorted(heritage_types)) if heritage_types else 'None detected'

        domains = parsed_query.get('domains', set())
        domain_display = ', '.join(sorted(domains)) if domains else 'None detected'

        time_period = parsed_query.get('time_period')
        period_display = time_period.title() if time_period else 'Not specified'

        region = parsed_query.get('region')
        region_display = region.title() if region else 'Not specified'

        with attr_col1:
            st.markdown(f"""
            <div class='result-card animated-card'>
                <strong>🏛️ Heritage Types</strong><br>
                {heritage_display}
            </div>
            """, unsafe_allow_html=True)

        with attr_col2:
            st.markdown(f"""
            <div class='result-card animated-card'>
                <strong>🎯 Domains</strong><br>
                {domain_display}
            </div>
            """, unsafe_allow_html=True)

        with attr_col3:
            st.markdown(f"""
            <div class='result-card animated-card'>
                <strong>⏳ Period</strong><br>
                {period_display}
            </div>
            """, unsafe_allow_html=True)

        with attr_col4:
            st.markdown(f"""
            <div class='result-card animated-card'>
                <strong>📍 Region</strong><br>
                {region_display}
            </div>
            """, unsafe_allow_html=True)
        
        # ========== RECOMMENDATIONS ==========
        st.markdown("---")
        
        try:
            with st.spinner(f"🤖 Finding top-{top_k} recommendations..."):
                # Update weights if customized
                total = simrank_weight + horn_weight + embedding_weight
                if total > 0:
                    recommender.simrank_weight = simrank_weight / total
                    recommender.horn_weight = horn_weight / total
                    recommender.embedding_weight = embedding_weight / total

                # Pass filters to recommender (empty lists are treated as no filter)
                recommendations = recommender.recommend(
                    parsed_query,
                    top_k=top_k,
                    explain=True,
                    filter_period=filter_period if filter_period else None,
                    filter_region=filter_region if filter_region else None,
                    filter_heritage=filter_heritage if filter_heritage else None,
                    filter_domain=filter_domain if filter_domain else None
                )
        except Exception as e:
            st.error(f"❌ Error getting recommendations: {str(e)}")
            return
        
        # Store in session
        st.session_state.update({
            'query_text': query_text,
            'parsed_query': parsed_query,
            'recommendations': recommendations,
            'top_k': top_k
        })
        
        if not recommendations or len(recommendations) == 0:
            st.warning("⚠️ No recommendations found for this query. Try a different search term.")
            return
        
        # Success message
        st.success(f"✅ Found {len(recommendations)} relevant documents!")

        # ========== RESULTS PREVIEW ==========
        st.markdown("## 📚 Top Recommendations")

        for i, rec in enumerate(recommendations, 1):  # Show ALL results
            title = rec.get('title', 'Untitled Document')
            score = rec.get('hybrid_score', 0.0)
            
            with st.expander(
                f"**#{i}** {title[:80]}{'...' if len(title) > 80 else ''} — Score: {score:.4f}",
                expanded=(i <= 2)
            ):
                # Metadata row
                meta_cols = st.columns(4)
                
                with meta_cols[0]:
                    heritage_type = rec.get('metadata', {}).get('heritage_type', '')
                    if heritage_type:
                        st.markdown(f"🏛️ **Type:** {heritage_type}")
                    else:
                        st.markdown("🏛️ **Type:** N/A")
                
                with meta_cols[1]:
                    domain = rec.get('metadata', {}).get('domain', '')
                    if domain:
                        st.markdown(f"🎯 **Domain:** {domain}")
                    else:
                        st.markdown("🎯 **Domain:** N/A")
                
                with meta_cols[2]:
                    time_period = rec.get('metadata', {}).get('time_period', '')
                    if time_period:
                        st.markdown(f"⏳ **Period:** {time_period}")
                    else:
                        st.markdown("⏳ **Period:** N/A")
                
                with meta_cols[3]:
                    region = rec.get('metadata', {}).get('region', '')
                    if region:
                        st.markdown(f"📍 **Region:** {region}")
                    else:
                        st.markdown("📍 **Region:** N/A")
                
                # Score breakdown with gauges
                st.markdown("**Score Components:**")
                
                component_scores = rec.get('component_scores', {})
                
                gauge_cols = st.columns(3)
                
                with gauge_cols[0]:
                    simrank_score = component_scores.get('simrank', 0.0)
                    fig1 = create_score_gauge(
                        simrank_score,
                        "SimRank",
                        "#2563eb"
                    )
                    st.plotly_chart(fig1, use_container_width=True, key=f"simrank_{i}")

                with gauge_cols[1]:
                    horn_score = component_scores.get('horn', 0.0)
                    fig2 = create_score_gauge(
                        horn_score,
                        "Horn's Index",
                        "#0d9488"
                    )
                    st.plotly_chart(fig2, use_container_width=True, key=f"horn_{i}")

                with gauge_cols[2]:
                    embedding_score = component_scores.get('embedding', 0.0)
                    fig3 = create_score_gauge(
                        embedding_score,
                        "Embedding",
                        "#475569"
                    )
                    st.plotly_chart(fig3, use_container_width=True, key=f"embedding_{i}")
                
                # KG explanations
                kg_explanations = rec.get('kg_explanations', [])
                if kg_explanations:
                    st.markdown("**🕸️ Why Recommended (Knowledge Graph):**")
                    for path in kg_explanations[:3]:
                        st.markdown(f'<div class="kg-path">{path}</div>', unsafe_allow_html=True)
                else:
                    st.info("No knowledge graph explanations available for this recommendation.")
        
        # ========== NAVIGATION ==========
        st.markdown("---")
        
        nav_col1, nav_col2, nav_col3 = st.columns(3)
        
        with nav_col1:
            if st.button("📊 View All Results", use_container_width=True):
                st.switch_page("pages/results_page.py")
        
        with nav_col2:
            if st.button("🕸️ Explore Graph", use_container_width=True):
                st.switch_page("pages/kg_viz_page.py")
        
        with nav_col3:
            if st.button("📈 Check Performance", use_container_width=True):
                st.switch_page("pages/evaluation_page.py")


if __name__ == "__main__":
    render()