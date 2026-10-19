
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

DB_PATH = "./chroma_db"
COLLECTION_NAME = "research_pdf_chunks"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


# --------------------------------------------------
# LOAD MODEL AND DATABASE ONCE
# --------------------------------------------------

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


# --------------------------------------------------
# SPLIT TEXT INTO OVERLAPPING CHUNKS
# --------------------------------------------------

def split_text(text, chunk_size=1000, overlap=150):
    text = " ".join(text.split())

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        # Prefer splitting at a word boundary.
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


# --------------------------------------------------
# EXTRACT TEXT PAGE BY PAGE
# --------------------------------------------------

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


# --------------------------------------------------
# INDEX A PDF IN CHROMADB
# --------------------------------------------------

def index_pdf(filename, pdf_bytes):
    document_id = sha256(pdf_bytes).hexdigest()

    pages = extract_pdf_pages(pdf_bytes)

    documents = []
    metadatas = []
    ids = []

    for page_data in pages:
        page_number = page_data["page"]
        chunks = split_text(page_data["text"])

        for chunk_number, chunk in enumerate(chunks):
            chunk_id = (
                f"{document_id}_{page_number}_{chunk_number}"
            )

            ids.append(chunk_id)
            documents.append(chunk)

            metadatas.append({
                "document_id": document_id,
                "filename": Path(filename).name,
                "page": page_number,
            })

    if not documents:
        raise ValueError(
            "No readable text was found in this PDF. "
            "It may be a scanned PDF requiring OCR."
        )

    # Replace previous chunks for the same PDF content.
    collection = get_collection()

    collection.delete(
        where={"document_id": document_id}
    )

    model = get_embedding_model()

    embeddings = model.encode(
        documents,
        normalize_embeddings=True,
        show_progress_bar=False,
    ).tolist()

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )

    return {
        "filename": Path(filename).name,
        "chunks": len(documents),
        "document_id": document_id,
    }


# --------------------------------------------------
# LIST INDEXED DOCUMENTS
# --------------------------------------------------

def list_indexed_documents():
    collection = get_collection()

    result = collection.get(
        include=["metadatas"]
    )

    documents = {}

    for metadata in result.get("metadatas", []):
        if not metadata:
            continue

        document_id = metadata["document_id"]

        documents[document_id] = metadata["filename"]

    return sorted(documents.values())


# --------------------------------------------------
# RETRIEVE RELEVANT PASSAGES
# --------------------------------------------------

def retrieve_context(question, top_k=5):
    collection = get_collection()

    if collection.count() == 0:
        return []

    model = get_embedding_model()

    query_embedding = model.encode(
        [question],
        normalize_embeddings=True,
        show_progress_bar=False,
    ).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    retrieved = []

    for document, metadata, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        retrieved.append({
            "text": document,
            "filename": metadata["filename"],
            "page": metadata["page"],
            "distance": distance,
        })

    return retrieved


# --------------------------------------------------
# ANSWER QUESTIONS USING RETRIEVED PDF PASSAGES
# --------------------------------------------------

def answer_question(question, top_k=5):
    passages = retrieve_context(question, top_k=top_k)

    if not passages:
        return (
            "No indexed PDF passages were found. "
            "Upload and index a PDF first.",
            [],
        )

    context_parts = []

    for passage in passages:
        context_parts.append(
            f"Source: {passage['filename']}, "
            f"page {passage['page']}\n"
            f"{passage['text']}"
        )

    context = "\n\n---\n\n".join(context_parts)

    prompt = f"""
You are a document question-answering assistant.

Answer the user's question using the provided PDF passages.

Rules:
1. Base factual claims on the provided passages.
2. Cite sources inline using [filename, p. X].
3. If the passages do not contain enough information, say so.
4. Do not invent facts, quotations, page numbers, or sources.
5. You may explain the retrieved information in clear language.

PDF PASSAGES:
{context}

USER QUESTION:
{question}
"""

    # Reuse the Gemini model configured in agents.py.
    from agents import llm

    response = llm.invoke(prompt)
    answer = response.content

    # Handle text responses returned as a list of blocks.
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
        }
        for passage in passages
    ]

    return answer, sources
