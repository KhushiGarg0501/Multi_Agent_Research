
from typing import Literal

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from graph import graph
from rag import index_pdf, answer_question, get_collection


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
