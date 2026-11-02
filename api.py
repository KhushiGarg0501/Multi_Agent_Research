
from typing import Literal

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from graph import graph
from rag import index_pdf, answer_question, get_collection

from io import BytesIO
from fastapi.responses import StreamingResponse

from docx import Document

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable
)

from xml.sax.saxutils import escape
import re

app = FastAPI(title="Researchly API")

# Allow the local frontend to communicate with FastAPI.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    topic: str
    mode: Literal["web_search", "ask_pdfs", "combined"]
    selected_document_ids: list[str] = []

class ExportRequest(BaseModel):
    topic: str
    report: str

@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "message": "Researchly backend is running"
    }


@app.post("/api/upload-pdf")
def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported."
        )

    try:
        pdf_bytes = file.file.read()

        if not pdf_bytes:
            raise HTTPException(
                status_code=400,
                detail="The uploaded PDF is empty."
            )

        result = index_pdf(file.filename, pdf_bytes)

        return {
            "success": True,
            **result
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"PDF processing failed: {str(exc)}"
        )


@app.get("/api/documents")
def list_documents():
    collection = get_collection()

    result = collection.get(include=["metadatas"])

    documents = {}

    for metadata in result.get("metadatas", []):
        if not metadata:
            continue

        document_id = metadata.get("document_id")
        filename = metadata.get("filename")

        if document_id and filename:
            documents[document_id] = {
                "document_id": document_id,
                "filename": filename
            }

    return {
        "documents": list(documents.values())
    }


@app.post("/api/research")
def research(request: ResearchRequest):

    topic = request.topic.strip()

    if not topic:
        raise HTTPException(
            status_code=400,
            detail="Please enter a research question."
        )

    if request.mode in ["ask_pdfs", "combined"]:
        if not request.selected_document_ids:
            raise HTTPException(
                status_code=400,
                detail="Please upload or select at least one PDF."
            )

    try:

        # MODE 1: WEB SEARCH
        if request.mode == "web_search":

            result = graph.invoke({
                "topic": topic,
                "revision_count": 0,
                "use_uploaded_docs": False,
                "selected_document_ids": [],
            })

            return {
                "success": True,
                "mode": request.mode,
                "report": result.get("report", ""),
                "critique": result.get("critique", ""),
                "research_gaps": result.get("research_gaps", ""),
                "fact_check": result.get("fact_check", ""),
            }

        # MODE 2: ASK MY PDFs
        elif request.mode == "ask_pdfs":

            # The RAG function must accept document_ids;
            # see the small update below.
            answer, sources = answer_question(
                topic,
                document_ids=request.selected_document_ids,
            )

            return {
                "success": True,
                "mode": request.mode,
                "answer": answer,
                "sources": sources,
            }

        # MODE 3: WEB + PDFs
        elif request.mode == "combined":

            result = graph.invoke({
                "topic": topic,
                "revision_count": 0,
                "use_uploaded_docs": True,
                "selected_document_ids": request.selected_document_ids,
            })

            return {
                "success": True,
                "mode": request.mode,
                "report": result.get("report", ""),
                "critique": result.get("critique", ""),
                "research_gaps": result.get("research_gaps", ""),
                "fact_check": result.get("fact_check", ""),
            }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Research failed: {str(exc)}"
        )

def clean_markdown(text: str) -> str:
    """Clean Markdown formatting for Word export."""
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
    text = re.sub(r"(\*|_)(.*?)\1", r"\2", text)
    text = re.sub(r"`(.*?)`", r"\1", text)

    return text.strip()


@app.post("/api/export/docx")
async def export_docx(request: ExportRequest):

    document = Document()

    # Document title
    document.add_heading("Research Report", 0)
    document.add_heading(request.topic, level=1)

    # Process report content
    for line in request.report.splitlines():

        line = line.strip()

        if not line:
            continue

        if line.startswith("### "):
            document.add_heading(
                clean_markdown(line[4:]), level=3
            )

        elif line.startswith("## "):
            document.add_heading(
                clean_markdown(line[3:]), level=2
            )

        elif line.startswith("# "):
            document.add_heading(
                clean_markdown(line[2:]), level=1
            )

        elif line.startswith(("- ", "* ")):
            document.add_paragraph(
                clean_markdown(line[2:]),
                style="List Bullet"
            )

        elif re.match(r"^\d+\.\s", line):
            document.add_paragraph(
                clean_markdown(
                    re.sub(r"^\d+\.\s", "", line)
                ),
                style="List Number"
            )

        else:
            document.add_paragraph(clean_markdown(line))

    # Generate Word file in memory
    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": 'attachment; filename="researchly-report.docx"'
        }
    )

@app.post("/api/export/pdf")
async def export_pdf(request: ExportRequest):

    buffer = BytesIO()

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=22,
        leading=28,
        textColor=colors.HexColor("#17365D"),
        spaceAfter=18
    )

    heading_style = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        fontSize=14,
        leading=19,
        textColor=colors.HexColor("#24527A"),
        spaceBefore=14,
        spaceAfter=8
    )

    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        fontSize=10,
        leading=16,
        spaceAfter=8
    )

    story = [
        Paragraph("Research Report", title_style),
        Paragraph(escape(request.topic), heading_style),
        Spacer(1, 12)
    ]

    for line in request.report.splitlines():

        line = line.strip()

        if not line:
            continue

        if line.startswith("# "):
            story.append(
                Paragraph(
                    escape(clean_markdown(line[2:])),
                    heading_style
                )
            )

        elif line.startswith("## "):
            story.append(
                Paragraph(
                    escape(clean_markdown(line[3:])),
                    heading_style
                )
            )

        elif line.startswith("### "):
            story.append(
                Paragraph(
                    f"<b>{escape(clean_markdown(line[4:]))}</b>",
                    body_style
                )
            )

        elif line.startswith(("- ", "* ")):
            story.append(
                Paragraph(
                    f"&bull; {escape(clean_markdown(line[2:]))}",
                    body_style
                )
            )

        elif re.match(r"^\d+\.\s", line):
            story.append(
                Paragraph(
                    escape(clean_markdown(line)),
                    body_style
                )
            )

        else:
            story.append(
                Paragraph(
                    escape(clean_markdown(line)),
                    body_style
                )
            )

    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50
    )

    pdf.build(story)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="researchly-report.pdf"'
        }
    )
