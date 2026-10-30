from functools import lru_cache
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "chroma_db")

COLLECTION_NAME = "research_pdf_chunks"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


# ============================================================
# DATABASE AND EMBEDDING MODEL
# ============================================================

@lru_cache(maxsize=1)
def get_embedding_model():
    return SentenceTransformer(EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def get_collection():
    client = chromadb.PersistentClient(path=DB_PATH)

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


# ============================================================
# SPLIT TEXT INTO CHUNKS
# ============================================================

def split_text(text, chunk_size=1000, overlap=150):
    text = " ".join(text.split())

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        if end < len(text):
            boundary = text.rfind(" ", start, end)

            if boundary > start + chunk_size // 2:
                end = boundary

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = max(start + 1, end - overlap)

    return chunks


# ============================================================
# EXTRACT PDF TEXT
# ============================================================

def extract_pdf_pages(pdf_bytes):
    reader = PdfReader(BytesIO(pdf_bytes))
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""

        if text.strip():
            pages.append({
                "page": page_number,
                "text": text,
            })

    return pages


# ============================================================
# INDEX PDF
# ============================================================

def index_pdf(filename, pdf_bytes):
    filename = Path(filename).name
    document_id = sha256(pdf_bytes).hexdigest()

    pages = extract_pdf_pages(pdf_bytes)

    documents = []
    metadatas = []
    ids = []

    for page_data in pages:
        page_number = page_data["page"]

        for chunk_number, chunk in enumerate(
            split_text(page_data["text"])
        ):
            ids.append(
                f"{document_id}_{page_number}_{chunk_number}"
            )

            documents.append(chunk)

            metadatas.append({
                "document_id": document_id,
                "filename": filename,
                "page": page_number,
            })

    if not documents:
        raise ValueError(
            "No readable text was extracted from this PDF. "
            "If the PDF contains scanned pages, OCR is required."
        )

    collection = get_collection()
    model = get_embedding_model()

    embeddings = model.encode(
        documents,
        normalize_embeddings=True,
        show_progress_bar=False,
    ).tolist()

    # Replace existing chunks for the same PDF content.
    collection.delete(
        where={"document_id": document_id}
    )

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )

    return {
        "filename": filename,
        "chunks": len(documents),
        "document_id": document_id,
        "total_chunks": collection.count(),
    }


# ============================================================
# LIST INDEXED DOCUMENTS
# ============================================================

def list_indexed_documents():
    collection = get_collection()

    result = collection.get(
        include=["metadatas"]
    )

    documents = {}

    for metadata in result.get("metadatas", []):
        if not metadata:
            continue

        document_id = metadata.get("document_id")
        filename = metadata.get("filename")

        if document_id and filename:
            documents[document_id] = filename

    return sorted(documents.values())


# ============================================================
# RETRIEVE PDF PASSAGES
# ============================================================

def retrieve_context(question, top_k=5):
    collection = get_collection()

    total_chunks = collection.count()

    if total_chunks == 0:
        return []

    model = get_embedding_model()

    query_embedding = model.encode(
        [question],
        normalize_embeddings=True,
        show_progress_bar=False,
    ).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k, total_chunks),
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )

    retrieved = []

    result_documents = results.get("documents") or [[]]
    result_metadatas = results.get("metadatas") or [[]]
    result_distances = results.get("distances") or [[]]

    for document, metadata, distance in zip(
        result_documents[0],
        result_metadatas[0],
        result_distances[0],
    ):
        if not document or not metadata:
            continue

        retrieved.append({
            "text": document,
            "filename": metadata.get(
                "filename", "Unknown PDF"
            ),
            "page": metadata.get("page", "?"),
            "document_id": metadata.get(
                "document_id", ""
            ),
            "distance": distance,
        })

    return retrieved


# ============================================================
# ANSWER QUESTIONS USING PDF CONTENT
# ============================================================

def answer_question(question, top_k=5):
    question = question.strip()

    if not question:
        return "Please enter a question.", []

    passages = retrieve_context(
        question,
        top_k=top_k,
    )

    if not passages:
        return (
            "No indexed PDF passages were found. "
            "Please upload and index a PDF first.",
            [],
        )

    context = "\n\n---\n\n".join(
        (
            f"Source: {passage['filename']}, "
            f"page {passage['page']}\n"
            f"{passage['text']}"
        )
        for passage in passages
    )

    prompt = f"""
You are a document question-answering assistant.

Answer the user's question using the provided PDF passages.

Rules:
1. Base factual claims on the provided passages.
2. Cite supporting claims as [filename, p. X].
3. If the passages do not contain enough information,
   clearly state that.
4. Do not invent facts, quotations, page numbers, or sources.
5. Explain the findings clearly and directly.

PDF PASSAGES:
{context}

USER QUESTION:
{question}
"""

    from agents import llm

    response = llm.invoke(prompt)
    answer = response.content

    if isinstance(answer, list):
        answer = "\n".join(
            block.get("text", "")
            for block in answer
            if isinstance(block, dict)
            and block.get("type") == "text"
        )

    sources = [
        {
            "filename": passage["filename"],
            "page": passage["page"],
            "text": passage["text"],
            "distance": passage["distance"],
        }
        for passage in passages
    ]

    return answer, sources
