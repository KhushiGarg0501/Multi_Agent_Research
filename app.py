import streamlit as st
from graph import graph

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="AI Research System",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown("""
<style>

    /* Main page */
    .stApp {
        background-color: #f8fafc;
    }

    /* Hide Streamlit default menu */
    #MainMenu {
        visibility: hidden;
    }

    footer {
        visibility: hidden;
    }

    /* Header */
    .hero {
        padding: 10px 0 25px 0;
    }

    .hero-title {
        font-size: 42px;
        font-weight: 800;
        color: #172033;
        margin-bottom: 4px;
    }

    .hero-subtitle {
        font-size: 18px;
        color: #64748b;
    }

    /* Status badge */
    .status-badge {
        display: inline-block;
        padding: 7px 14px;
        border-radius: 20px;
        background-color: #dcfce7;
        color: #166534;
        font-size: 14px;
        font-weight: 600;
    }

    /* Section headings */
    .section-title {
        font-size: 25px;
        font-weight: 700;
        color: #172033;
        margin-top: 10px;
        margin-bottom: 15px;
    }

    /* Agent cards */
    .agent-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 18px;
        text-align: center;
        min-height: 125px;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
    }

    .agent-icon {
        font-size: 30px;
        margin-bottom: 8px;
    }

    .agent-name {
        font-size: 16px;
        font-weight: 700;
        color: #1e293b;
    }

    .agent-status {
        font-size: 13px;
        color: #16a34a;
        margin-top: 5px;
    }

    /* Research box */
    .research-box {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 25px;
        box-shadow: 0 3px 12px rgba(15, 23, 42, 0.05);
    }

    /* Report box */
    .report-box {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 28px;
        margin-top: 15px;
        min-height: 200px;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #eef2f7;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        min-height: 45px;
    }

    /* Divider */
    hr {
        border-color: #e2e8f0;
    }

</style>
""", unsafe_allow_html=True)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("## ⚙️ Research Settings")

    st.markdown(
        """
        <div style="
            background-color:white;
            padding:18px;
            border-radius:14px;
            border:1px solid #e2e8f0;
        ">
            <b>Multi-Agent Research</b><br><br>
            The system plans, searches, reads, writes,
            and critiques research automatically.
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("---")

    st.markdown("### 🤖 Research Agents")

    agents = [
        ("🧭", "Planner", "Breaks the topic into research questions"),
        ("🌐", "Search", "Finds relevant web sources"),
        ("📖", "Reader", "Extracts useful information"),
        ("✍️", "Writer", "Creates the research report"),
        ("🧐", "Critic", "Reviews report quality"),
    ]

    for icon, name, description in agents:
        st.markdown(
            f"""
            <div style="
                padding:10px 5px;
                margin-bottom:8px;
            ">
                <b>{icon} {name}</b><br>
                <span style="
                    font-size:12px;
                    color:#64748b;
                ">
                    {description}
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("---")

    st.markdown("### 🛠️ Technology")

    st.caption("LangGraph")
    st.caption("Google Gemini")
    st.caption("Tavily Search")
    st.caption("BeautifulSoup")
    st.caption("Streamlit")


# ============================================================
# HEADER
# ============================================================

col1, col2 = st.columns([5, 1])

with col1:
    st.markdown(
        """
        <div class="hero">
            <div class="hero-title">🧠 AI Research System</div>
            <div class="hero-subtitle">
                Multi-Agent Research Assistant
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col2:
    st.markdown(
        """
        <div style="text-align:right; margin-top:15px;">
            <span class="status-badge">● System Ready</span>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown(
    """
    <p style="color:#64748b; font-size:16px;">
        Generate structured research reports using AI agents,
        web research, source analysis, and critical review.
    </p>
    """,
    unsafe_allow_html=True
)

st.divider()


# ============================================================
# RESEARCH INPUT
# ============================================================

st.markdown(
    '<div class="section-title">🔍 Start Your Research</div>',
    unsafe_allow_html=True
)

st.markdown('<div class="research-box">', unsafe_allow_html=True)

topic = st.text_area(
    "Research Topic",
    placeholder="Example: Impact of Generative AI on Software Engineering",
    height=120,
    label_visibility="collapsed"
)

col1, col2, col3 = st.columns([1.3, 1.3, 3])

with col1:
    research_button = st.button(
        "🚀 Start Research",
        use_container_width=True
    )

with col2:
    clear_button = st.button(
        "🗑️ Clear",
        use_container_width=True
    )

st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# AGENT DASHBOARD
# ============================================================

st.markdown(
    '<div class="section-title">🤖 Research Pipeline</div>',
    unsafe_allow_html=True
)

agent_columns = st.columns(5)

agent_data = [
    ("🧭", "Planner"),
    ("🌐", "Search"),
    ("📖", "Reader"),
    ("✍️", "Writer"),
    ("🧐", "Critic")
]

for column, (icon, name) in zip(agent_columns, agent_data):

    with column:

        st.markdown(
            f"""
            <div class="agent-card">
                <div class="agent-icon">{icon}</div>
                <div class="agent-name">{name}</div>
                <div class="agent-status">● Ready</div>
            </div>
            """,
            unsafe_allow_html=True
        )


# ============================================================
# REAL RESEARCH WORKFLOW
# ============================================================

if research_button:

    if not topic.strip():

        st.warning("⚠️ Please enter a research topic first.")

    else:

        st.divider()

        st.markdown(
            f"""
            <div style="
                background:#eff6ff;
                border:1px solid #bfdbfe;
                border-radius:12px;
                padding:15px;
                color:#1e40af;
            ">
                🔎 Researching:
                <b>{topic}</b>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown("### ⚡ Research Progress")

        progress = st.progress(0)
        status = st.empty()

        try:

            status.markdown("**🧭 Running Planner Agent...**")
            progress.progress(15)

            result = graph.invoke({
                "topic": topic,
                "revision_count": 0
            })

            progress.progress(100)

            status.success("✅ Research workflow completed!")

            # --------------------------------------------
            # FINAL REPORT
            # --------------------------------------------

            st.divider()

            st.markdown(
                '<div class="section-title">📄 Final Research Report</div>',
                unsafe_allow_html=True
            )

            report = result.get("report", "")

            if report:

                st.markdown(
                    '<div class="report-box">',
                    unsafe_allow_html=True
                )

                st.markdown(report)

                st.markdown(
                    '</div>',
                    unsafe_allow_html=True
                )

                st.download_button(
                    label="📥 Download Report",
                    data=report,
                    file_name="research_report.txt",
                    mime="text/plain"
                )

            else:

                st.warning(
                    "The workflow completed, but no report was returned."
                )

        except Exception as e:

            progress.progress(0)

            st.error(
                "❌ The research workflow could not be completed."
            )

            st.warning(
                "This may be caused by a Gemini API quota or "
                "temporary service error."
            )

            st.code(str(e))


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.markdown(
    """
    <div style="
        text-align:center;
        color:#94a3b8;
        padding:10px;
        font-size:13px;
    ">
        🧠 AI Research System &nbsp;•&nbsp;
        LangGraph &nbsp;•&nbsp;
        Gemini &nbsp;•&nbsp;
        Tavily &nbsp;•&nbsp;
        Streamlit
    </div>
    """,
    unsafe_allow_html=True
)