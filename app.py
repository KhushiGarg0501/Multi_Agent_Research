import re
from io import BytesIO
from xml.sax.saxutils import escape

import streamlit as st
from docx import Document
from docx.shared import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem

from graph import graph
from rag import index_pdf, answer_question, list_indexed_documents, retrieve_context


# -----------------------------
# Report export helpers
# -----------------------------
def create_report_pdf(report: str) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=0.7 * inch, leftMargin=0.7 * inch,
        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
        title="Research Report", author="AI Research System",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"], fontSize=20, leading=26,
        alignment=TA_CENTER, spaceAfter=20, textColor=colors.HexColor("#243B53"),
    )
    heading_style = ParagraphStyle(
        "ReportHeading", parent=styles["Heading1"], fontSize=15, leading=19,
        spaceBefore=14, spaceAfter=8, keepWithNext=True,
        textColor=colors.HexColor("#243B53"),
    )
    subheading_style = ParagraphStyle(
        "ReportSubheading", parent=styles["Heading2"], fontSize=12,
        leading=16, spaceBefore=10, spaceAfter=5, keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "ReportBody", parent=styles["BodyText"], fontSize=9.5,
        leading=14, spaceAfter=7, splitLongWords=True,
    )
    story, first_heading = [], True
    for raw_line in report.splitlines():
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 4))
        elif line.startswith("### "):
            story.append(Paragraph(escape(line[4:]), subheading_style))
        elif line.startswith("## "):
            story.append(Paragraph(escape(line[3:]), heading_style))
        elif line.startswith("# "):
            style = title_style if first_heading else heading_style
            story.append(Paragraph(escape(line[2:]), style))
            first_heading = False
        elif line.startswith(("- ", "* ")):
            story.append(ListFlowable(
                [ListItem(Paragraph(escape(line[2:]), body_style))],
                bulletType="bullet", leftIndent=18,
            ))
            story.append(Spacer(1, 4))
        elif re.match(r"^\d+[.)]\s+(.+)$", line):
            match = re.match(r"^\d+[.)]\s+(.+)$", line)
            story.append(Paragraph(escape(match.group(1)), body_style, bulletText="•"))
        else:
            text = escape(line)
            text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
            text = re.sub(r"(?<!\*)\*(.+?)\*(?!\*)", r"<i>\1</i>", text)
            story.append(Paragraph(text, body_style))
    if not story:
        story.append(Paragraph("No report content available.", body_style))

    def add_page_number(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(A4[0] / 2, 0.35 * inch, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return buffer.getvalue()


def create_report_docx(report: str) -> bytes:
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.85)
    section.right_margin = Inches(0.85)
    doc.styles["Normal"].font.name = "Arial"
    doc.styles["Normal"].font.size = Pt(10)
    for line in report.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("### "):
            doc.add_heading(line[4:].strip(), level=2)
        elif line.startswith("## "):
            doc.add_heading(line[3:].strip(), level=1)
        elif line.startswith("# "):
            doc.add_heading(line[2:].strip(), level=0)
        elif line.startswith(("- ", "* ")):
            doc.add_paragraph(line[2:].strip(), style="List Bullet")
        elif re.match(r"^\d+[.)]\s+", line):
            doc.add_paragraph(re.sub(r"^\d+[.)]\s+", "", line), style="List Number")
        else:
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            text = re.sub(r"(?<!\*)\*(.+?)\*(?!\*)", r"\1", text)
            doc.add_paragraph(text)
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def combined_answer(question: str, web_report: str = ""):
    """Synthesize an answer from retrieved PDF passages and optional web research."""
    from agents import llm
    passages = retrieve_context(question, top_k=6)
    pdf_context = "\n\n---\n\n".join(
        f"Source: {p['filename']}, page {p['page']}\n{p['text']}" for p in passages
    ) or "No relevant PDF passages were retrieved."
    prompt = f"""You are an evidence-focused research assistant. Answer the user's question in detail.
Use the web research and PDF passages when available. Distinguish what each source supports,
point out agreement or disagreement, and clearly state when evidence is missing. Cite PDF claims
as [filename, p. X]. Do not invent sources or citations. Use a clear, structured answer.

WEB RESEARCH REPORT:
{web_report or 'No web research report supplied.'}

PDF PASSAGES:
{pdf_context}

USER QUESTION:
{question}
"""
    response = llm.invoke(prompt)
    answer = response.content
    if isinstance(answer, list):
        answer = "\n".join(
            block.get("text", "") for block in answer
            if isinstance(block, dict) and block.get("type") == "text"
        )
    sources = [{"filename": p["filename"], "page": p["page"], "text": p["text"]} for p in passages]
    return str(answer), sources


# -----------------------------
# Streamlit configuration + styling
# -----------------------------
st.set_page_config(page_title="AI Research System", page_icon="🧠", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
:root {
    --ink: #172033;
    --muted: #64748b;
    --line: #e2e8f0;
    --surface: #ffffff;
    --brand: #635bff;
    --brand-dark: #4f46e5;
}
.stApp {
    background: linear-gradient(180deg, #f8faff 0%, #f5f7fb 55%, #f8fafc 100%);
    color: var(--ink);
    overflow-x: hidden;
}
#MainMenu, footer,  { visibility: hidden; }
.block-container {
    width: 100%;
    max-width: 1180px;
    padding: 1.6rem 2rem 2.5rem 2rem;
    margin: 0 auto;
}
.hero {
    background: linear-gradient(125deg, #ffffff 0%, #f0f4ff 62%, #eef2ff 100%);
    border: 1px solid #e3e8f5;
    border-radius: 24px;
    padding: 28px 32px 25px;
    margin: 0 0 18px 0;
    box-shadow: 0 10px 32px rgba(30, 41, 59, .05);
}
.hero-title {
    font-size: clamp(2rem, 4vw, 2.8rem);
    line-height: 1.12;
    font-weight: 850;
    letter-spacing: -1.2px;
    color: #172033;
    margin: 0 0 10px 0;
}
.hero-subtitle { font-size: 1.08rem; color: #5c6b82; line-height: 1.6; }
.status-badge {
    display: inline-block; padding: 7px 13px; border-radius: 999px;
    background: #dcfce7; color: #166534; font-size: .86rem; font-weight: 700;
    border: 1px solid #bbf7d0;
}
.section-title {
    font-size: 1.55rem; font-weight: 800; letter-spacing: -.35px;
    color: #172033; margin: 12px 0 12px 0;
}
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 18px !important;
}
div[data-testid="stExpander"] {
    border: 1px solid #dce3ee;
    border-radius: 13px;
    background: rgba(255,255,255,.8);
}
div[data-testid="stRadio"] > label,
div[data-testid="stTextArea"] > label,
div[data-testid="stTextInput"] > label,
div[data-testid="stFileUploader"] > label {
    color: #334155;
    font-weight: 650;
}
div[role="radiogroup"] {
    gap: 10px;
    flex-wrap: wrap;
}
div[role="radiogroup"] label {
    background: #fff;
    border: 1px solid #dbe2ed;
    border-radius: 12px;
    padding: 10px 14px;
    margin: 0;
    transition: border-color .15s ease, box-shadow .15s ease;
}
div[role="radiogroup"] label:hover {
    border-color: #a5b4fc;
    box-shadow: 0 3px 12px rgba(79,70,229,.08);
}
.stTextArea textarea, .stTextInput input {
    background: #fff !important;
    color: #172033 !important;
    border: 1px solid #d5deeb !important;
    border-radius: 12px !important;
    box-shadow: 0 2px 5px rgba(15,23,42,.025);
}
.stTextArea textarea:focus, .stTextInput input:focus {
    border-color: #818cf8 !important;
    box-shadow: 0 0 0 3px rgba(99,91,255,.12) !important;
}
.stTextArea textarea { min-height: 115px; }
.stButton > button, .stDownloadButton > button {
    border-radius: 12px;
    min-height: 45px;
    font-weight: 700;
    border: 1px solid #d7deea;
    transition: transform .12s ease, box-shadow .12s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 5px 14px rgba(15,23,42,.08);
    border-color: #a5b4fc;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #635bff, #4f46e5);
    border: 0;
    color: white;
}
.agent-card {
    background: #fff; border: 1px solid #e2e8f0; border-radius: 16px;
    padding: 16px 10px; text-align: center; min-height: 112px;
    box-shadow: 0 4px 14px rgba(15,23,42,.035);
}
.agent-icon { font-size: 27px; margin-bottom: 7px; }
.agent-name { font-size: 15px; font-weight: 750; color: #1e293b; }
.agent-status { font-size: 12px; color: #16a34a; margin-top: 5px; }
section[data-testid="stSidebar"] {
    background: #f0f3f9;
    border-right: 1px solid #e1e7f0;
}
section[data-testid="stSidebar"] .block-container { padding: 1.4rem 1.1rem; }
div[data-testid="stAlert"] { border-radius: 12px; }
hr { border-color: #e2e8f0; margin: 1.3rem 0; }
[data-testid="stMarkdownContainer"] p { line-height: 1.65; }
@media (max-width: 768px) {
    .block-container { padding: 1rem 1rem 2rem; }
    .hero { padding: 22px 20px; border-radius: 18px; }
    .hero-subtitle { font-size: .98rem; }
    .section-title { font-size: 1.35rem; }
    div[role="radiogroup"] label { width: 100%; }
}
</style>
""", unsafe_allow_html=True)


# ================= GOOGLE AUTHENTICATION =================

if not st.user.is_logged_in:
    st.title("🧠 MultiAgent Research System")
    st.markdown("### Welcome!")
    st.write("Sign in with your Google account to access the research system.")

    st.button(
        "Continue with Google",
        on_click=st.login,
        type="primary",
        use_container_width=True,
    )

    st.stop()



# ================= EXISTING RESEARCH SIDEBAR =================


with st.sidebar:
    st.markdown("### 👤 Your Account")
    st.write(f"**Name:** {st.user.name}")
    st.caption(st.user.email)

    if st.button("🚪 Logout", use_container_width=True):
        st.logout()

    st.divider()

    st.markdown("## ⚙️ Research Settings")
    st.markdown("""<div style="background:white;padding:18px;border-radius:14px;border:1px solid #e2e8f0;">
    <b>Multi-Agent Research</b><br><br>Plan, search, read, synthesize and critique research, or ask questions about your own PDFs.
    </div>""", unsafe_allow_html=True)
    st.markdown("---\n### 🤖 Research Agents")
    for icon, name, description in [
        ("🧭", "Planner", "Breaks the topic into research questions"),
        ("🌐", "Search", "Finds relevant web sources"),
        ("📖", "Reader", "Extracts useful information"),
        ("✍️", "Writer", "Creates the research report"),
        ("🧐", "Critic", "Reviews report quality"),
    ]:
        st.markdown(f"<div style='padding:8px 5px'><b>{icon} {name}</b><br><span style='font-size:12px;color:#64748b'>{description}</span></div>", unsafe_allow_html=True)
    st.markdown("---\n### 🛠️ Technology")
    for tech in ["LangGraph", "Google Gemini", "Tavily Search", "BeautifulSoup", "Streamlit", "ChromaDB + RAG"]:
        st.caption(tech)

st.markdown("""<div class="hero">
<div class="hero-title">🧠 AI Research System</div>
<div class="hero-subtitle">Your intelligent workspace for web research, document Q&A, and evidence synthesis.</div>
</div>""", unsafe_allow_html=True)
st.markdown("<span class='status-badge'>● System ready</span>", unsafe_allow_html=True)
st.markdown("<p style='color:#64748b;margin-top:12px;margin-bottom:4px'>Choose a workflow below. PDF uploads are optional for web research.</p>", unsafe_allow_html=True)
st.divider()

# Persistent state
for key, default in {
    "research_result": None, "research_topic": "", "research_answer": "",
    "answer_sources": [], "answer_question": "", "chat_history": [],
    "generated_report": "", "generated_report_topic": "",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

st.markdown('<div class="section-title">🔎 Your Research Workspace</div>', unsafe_allow_html=True)
st.caption("Select a mode, add your topic or question, and let the research assistant do the rest.")
mode = st.radio(
    "Choose a mode",
    ["🌐 Web Research", "📚 Ask My PDFs", "🔬 Combined Research"],
    horizontal=True,
    key="research_mode",
    help="Web Research uses the multi-agent web workflow. Ask My PDFs answers from indexed PDFs. Combined Research compares web research with your PDFs.",
)

# -----------------------------
# PDF Upload Section
# -----------------------------

st.markdown("### 📎 Upload PDFs")

uploaded_pdfs = st.file_uploader(
    "Upload one or more PDF documents",
    type=["pdf"],
    accept_multiple_files=True,
    key="workspace_pdf_uploader",
)

if st.button(
    "📥 Index uploaded PDFs",
    use_container_width=True,
    key="workspace_index_pdfs",
):
    if not uploaded_pdfs:
        st.warning("Please upload at least one PDF first.")
    else:
        successful = 0
        progress = st.progress(0)

        for i, pdf in enumerate(uploaded_pdfs, start=1):
            try:
                with st.spinner(f"Indexing {pdf.name}..."):
                    indexed = index_pdf(pdf.name, pdf.getvalue())

                successful += 1
                st.success(
                    f"Indexed **{indexed['filename']}** — "
                    f"{indexed['chunks']} text chunks."
                )

            except Exception as exc:
                st.error(f"Could not index {pdf.name}: {exc}")

            progress.progress(i / len(uploaded_pdfs))

        if successful:
            st.success(f"Finished indexing {successful} PDF(s).")

# -----------------------------
# Indexed PDF Library Dropdown
# -----------------------------

try:
    indexed_documents = list_indexed_documents()
except Exception as exc:
    indexed_documents = []
    st.warning(f"Could not load the indexed PDF library: {exc}")

with st.expander("📚 View Indexed PDF Library", expanded=False):
    if indexed_documents:
        for filename in indexed_documents:
            st.markdown(f"📄 {filename}")
    else:
        st.info("No PDFs indexed yet. Upload and index a PDF to get started.")



if mode == "🌐 Web Research":
    st.caption("The multi-agent pipeline searches the web and creates a structured research report.")
elif mode == "📚 Ask My PDFs":
    st.caption("Ask a question about your indexed PDFs. Answers include PDF filename and page citations where available.")
else:
    st.caption("Get a detailed answer that combines web research with relevant passages from your indexed PDFs. You can generate a full report afterward.")

prompt_label = "Research topic" if mode == "🌐 Web Research" else "Question or research topic"
placeholder = "Example: Impact of Generative AI on Software Engineering" if mode != "📚 Ask My PDFs" else "Example: What are the main findings of these papers?"
user_prompt = st.text_area(prompt_label, placeholder=placeholder, height=100, key="workspace_prompt")

button_label = {"🌐 Web Research": "🚀 Start Web Research", "📚 Ask My PDFs": "🔎 Answer from PDFs", "🔬 Combined Research": "🔬 Research Across Web + PDFs"}[mode]
col_run, col_clear, col_spacer = st.columns([1.5, 1, 4])
with col_run:
    run_clicked = st.button(button_label, type="primary", use_container_width=True)
with col_clear:
    clear_clicked = st.button("🗑️ Clear results", use_container_width=True)

if clear_clicked:
    for key in ["research_result", "research_topic", "research_answer", "answer_sources", "answer_question", "chat_history", "generated_report", "generated_report_topic"]:
        st.session_state[key] = {"answer_sources": [], "chat_history": []}.get(key, None if key in ["research_result"] else "")
    st.rerun()

if run_clicked:
    if not user_prompt.strip():
        st.warning("Please enter a topic or question first.")
    elif mode == "📚 Ask My PDFs" and not indexed_documents:
        st.warning("Upload and index at least one PDF before asking a document question.")
    elif mode == "🔬 Combined Research" and not indexed_documents:
        st.warning("Combined Research needs at least one indexed PDF. You can switch to Web Research if you do not want to use PDFs.")
    else:
        try:
            if mode == "🌐 Web Research":
                with st.spinner("The research agents are planning, searching, reading and writing..."):
                    result = graph.invoke({"topic": user_prompt.strip(), "revision_count": 0})
                report = result.get("report", "")
                if not isinstance(report, str):
                    report = str(report or "")
                if not report.strip():
                    st.error("The workflow finished but returned an empty report.")
                else:
                    st.session_state.research_result = result
                    st.session_state.research_topic = user_prompt.strip()
                    st.session_state.generated_report = report
                    st.session_state.generated_report_topic = user_prompt.strip()
                    st.session_state.research_answer = ""
                    st.session_state.answer_sources = []
                    st.session_state.answer_question = ""
            elif mode == "📚 Ask My PDFs":
                contextual_question = user_prompt.strip()
                history = st.session_state.chat_history[-6:]
                if history:
                    history_text = "\n".join(f"{item['role']}: {item['content']}" for item in history)
                    contextual_question = f"Conversation so far:\n{history_text}\n\nFollow-up question: {contextual_question}"
                with st.spinner("Searching indexed PDF passages and generating an answer..."):
                    answer, sources = answer_question(contextual_question, top_k=6)
                st.session_state.research_answer = answer
                st.session_state.answer_sources = sources
                st.session_state.answer_question = user_prompt.strip()
                st.session_state.chat_history.append({"role": "user", "content": user_prompt.strip()})
                st.session_state.chat_history.append({"role": "assistant", "content": answer})
            else:
                with st.spinner("Running web research first..."):
                    result = graph.invoke({"topic": user_prompt.strip(), "revision_count": 0})
                web_report = result.get("report", "")
                web_report = web_report if isinstance(web_report, str) else str(web_report or "")
                with st.spinner("Comparing web findings with your PDF evidence..."):
                    answer, sources = combined_answer(user_prompt.strip(), web_report)
                st.session_state.research_result = result
                st.session_state.research_topic = user_prompt.strip()
                st.session_state.research_answer = answer
                st.session_state.answer_sources = sources
                st.session_state.answer_question = user_prompt.strip()
                st.session_state.generated_report = ""
                st.session_state.generated_report_topic = user_prompt.strip()
        except Exception as exc:
            st.error("The request could not be completed.")
            st.exception(exc)

# -----------------------------
# Results
# -----------------------------
if mode == "📚 Ask My PDFs" and st.session_state.research_answer:
    st.divider()
    st.markdown("## 📝 Answer from your PDFs")
    st.caption(f"Question: {st.session_state.answer_question}")
    st.markdown(st.session_state.research_answer)

    if st.session_state.answer_sources:
        with st.expander("📖 Retrieved source passages", expanded=False):
            for source in st.session_state.answer_sources:
                st.markdown(
                    f"**{source['filename']} — page {source['page']}**"
                )
                st.write(source.get("text", ""))

    st.markdown("### 💬 Ask a follow-up")

    with st.form("pdf_followup_form", clear_on_submit=True):
        followup_question = st.text_input(
            "Your follow-up question",
            placeholder="Ask another question about your PDFs...",
        )

        followup_submitted = st.form_submit_button(
            "🔎 Answer from PDFs",
            type="primary",
            use_container_width=True,
        )

    if followup_submitted:
        if not followup_question.strip():
            st.warning("Please enter a follow-up question.")
        else:
            try:
                history = st.session_state.chat_history[-6:]

                contextual_question = followup_question.strip()

                if history:
                    history_text = "\n".join(
                        f"{item['role']}: {item['content']}"
                        for item in history
                    )
                    contextual_question = (
                        f"Conversation so far:\n{history_text}\n\n"
                        f"Follow-up question: {followup_question.strip()}"
                    )

                with st.spinner("Searching your PDFs for an answer..."):
                    answer, sources = answer_question(
                        contextual_question,
                        top_k=6,
                    )

                st.session_state.research_answer = answer
                st.session_state.answer_sources = sources
                st.session_state.answer_question = followup_question.strip()

                st.session_state.chat_history.append(
                    {
                        "role": "user",
                        "content": followup_question.strip(),
                    }
                )
                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": answer,
                    }
                )

                st.rerun()

            except Exception as exc:
                st.error("Could not answer your follow-up question.")
                st.exception(exc)

    if st.button("🧹 Clear PDF conversation", key="clear_pdf_chat"):
        st.session_state.chat_history = []
        st.session_state.research_answer = ""
        st.session_state.answer_sources = []
        st.session_state.answer_question = ""
        st.rerun()


if mode == "🔬 Combined Research" and st.session_state.research_answer:
    st.divider()
    st.markdown("## 🔬 Combined Research Answer")
    st.caption(f"Question: {st.session_state.answer_question}")
    st.markdown(st.session_state.research_answer)
    if st.session_state.answer_sources:
        with st.expander("📖 PDF evidence used", expanded=False):
            for source in st.session_state.answer_sources:
                st.markdown(f"**{source['filename']} — page {source['page']}**")
                st.write(source.get("text", ""))
    if st.button("📝 Generate Full Research Report", type="primary", key="generate_combined_report"):
        with st.spinner("Preparing the full report from the completed web research..."):
            result = st.session_state.research_result or {}
            report = result.get("report", "")
            report = report if isinstance(report, str) else str(report or "")
            # Include the evidence-synthesized answer so the downloadable report reflects both sources.
            full_report = f"# Combined Research Report\n\n## Research Question\n{st.session_state.answer_question}\n\n## Evidence-Synthesized Answer\n{st.session_state.research_answer}\n\n## Web Research Report\n{report}"
            st.session_state.generated_report = full_report
            st.session_state.generated_report_topic = st.session_state.answer_question

if mode == "🌐 Web Research" and st.session_state.research_result:
    result = st.session_state.research_result
    report = result.get("report", "")
    report = report if isinstance(report, str) else str(report or "")

    if report.strip():
        st.divider()
        st.markdown("## 📄 Final Research Report")
        st.caption(f"Topic: {st.session_state.research_topic}")

        # Display the research report only once.
        st.markdown(report)

        # Keep download buttons with the report.
        st.markdown("### 📥 Download Your Report")

        col_pdf, col_docx = st.columns(2)

        with col_pdf:
            st.download_button(
                "Download PDF",
                data=create_report_pdf(report),
                file_name="research_report.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="web_download_pdf",
            )

        with col_docx:
            st.download_button(
                "Download Word document (.docx)",
                data=create_report_docx(report),
                file_name="research_report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key="web_download_docx",
            )

        with st.expander(
            "🔍 Research Questions and Quality Review",
            expanded=False,
        ):
            st.markdown("### Research Questions")

            for i, question in enumerate(
                result.get("research_questions", []), 1
            ):
                st.markdown(f"{i}. {question}")

            st.markdown("### Critic Feedback")
            st.write(result.get("critique", "No critique returned."))

            if result.get("research_gaps"):
                st.markdown("### Research Gaps")
                st.write(result["research_gaps"])

            if result.get("fact_check"):
                st.markdown("### Fact-Check Findings")
                st.write(result["fact_check"])

if mode == "🔬 Combined Research" and st.session_state.generated_report:
    st.divider()
    st.markdown("## 📄 Full Research Report")
    st.caption(f"Topic: {st.session_state.generated_report_topic}")
    st.markdown(st.session_state.generated_report)
    st.markdown("### 📥 Download your report")
    col_pdf, col_docx = st.columns(2)
    with col_pdf:
        st.download_button("Download PDF", data=create_report_pdf(st.session_state.generated_report), file_name="research_report.pdf", mime="application/pdf", use_container_width=True, key="workspace_download_pdf")
    with col_docx:
        st.download_button("Download Word document (.docx)", data=create_report_docx(st.session_state.generated_report), file_name="research_report.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True, key="workspace_download_docx")

st.divider()
st.markdown("<div style='text-align:center;color:#94a3b8;padding:10px;font-size:13px'>🧠 AI Research System &nbsp;•&nbsp; LangGraph &nbsp;•&nbsp; Gemini &nbsp;•&nbsp; Tavily &nbsp;•&nbsp; Streamlit</div>", unsafe_allow_html=True)
