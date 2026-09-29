"""
Knowledge base processor using LangChain and ChromaDB.
Processes PDF files and creates vector embeddings for RAG.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

# 使用国内镜像
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter


def load_metadata(knowledge_dir: str) -> dict:
    """Load knowledge base metadata from metadata.json."""
    metadata_path = Path(knowledge_dir) / "metadata.json"
    with open(metadata_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_embeddings(model_name: str = "BAAI/bge-large-zh-v1.5"):
    """Initialize HuggingFace embeddings model."""
    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def process_pdf(pdf_path: str, metadata: dict) -> list:
    """Load and split a PDF file into chunks."""
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=metadata.get("config", {}).get("chunk_size", 800),
        chunk_overlap=metadata.get("config", {}).get("chunk_overlap", 200),
        length_function=len,
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
    )

    return splitter.split_documents(documents)


def process_markdown(md_path: str, metadata: dict) -> list:
    """Load and split a Markdown file into chunks."""
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    documents = [Document(page_content=content, metadata={"source": md_path})]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=metadata.get("config", {}).get("chunk_size", 800),
        chunk_overlap=metadata.get("config", {}).get("chunk_overlap", 200),
        length_function=len,
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
    )

    return splitter.split_documents(documents)


def create_knowledge_base(
    knowledge_dir: str,
    persist_directory: Optional[str] = None,
) -> Chroma:
    """
    Create a vector knowledge base from PDF or Markdown files.

    Args:
        knowledge_dir: Path to knowledge base directory containing metadata.json
        persist_directory: Directory to persist ChromaDB. Defaults to knowledge_dir/vectordb

    Returns:
        Chroma vector store instance
    """
    knowledge_path = Path(knowledge_dir)
    metadata = load_metadata(knowledge_dir)

    # Set up persist directory
    if persist_directory is None:
        persist_directory = str(knowledge_path / "vectordb")

    # Get embedding model
    model_name = metadata.get("config", {}).get(
        "embedding_model", "BAAI/bge-large-zh-v1.5"
    )
    embeddings = get_embeddings(model_name)

    # Determine primary format from metadata
    primary_format = metadata.get("format", {}).get("primary", "pdf")

    all_chunks = []

    # Process files based on primary format
    if primary_format == "markdown":
        md_dir = knowledge_path / "raw" / "markdown"
        md_files = list(md_dir.glob("*.md"))

        if not md_files:
            raise ValueError(f"No Markdown files found in {md_dir}")

        print(f"Found {len(md_files)} Markdown file(s) to process")

        for md_file in md_files:
            print(f"Processing: {md_file.name}")
            chunks = process_markdown(str(md_file), metadata)
            for chunk in chunks:
                chunk.metadata["source"] = md_file.name
            all_chunks.extend(chunks)
            print(f"  -> {len(chunks)} chunks")

    elif primary_format == "pdf":  # Default to PDF
        pdf_dir = knowledge_path / "raw" / "pdf"
        pdf_files = list(pdf_dir.glob("*.pdf"))

        if not pdf_files:
            raise ValueError(f"No PDF files found in {pdf_dir}")

        print(f"Found {len(pdf_files)} PDF file(s) to process")

        for pdf_file in pdf_files:
            print(f"Processing: {pdf_file.name}")
            chunks = process_pdf(str(pdf_file), metadata)
            for chunk in chunks:
                chunk.metadata["source"] = pdf_file.name
            all_chunks.extend(chunks)
            print(f"  -> {len(chunks)} chunks")

    elif primary_format == "both":
        # Process both PDF and Markdown files
        md_dir = knowledge_path / "raw" / "markdown"
        if md_dir.exists():
            md_files = list(md_dir.glob("*.md"))
            print(f"Found {len(md_files)} Markdown file(s) to process")
            for md_file in md_files:
                print(f"Processing: {md_file.name}")
                chunks = process_markdown(str(md_file), metadata)
                for chunk in chunks:
                    chunk.metadata["source"] = md_file.name
                all_chunks.extend(chunks)
                print(f"  -> {len(chunks)} chunks")

        pdf_dir = knowledge_path / "raw" / "pdf"
        if pdf_dir.exists():
            pdf_files = list(pdf_dir.glob("*.pdf"))
            print(f"Found {len(pdf_files)} PDF file(s) to process")
            for pdf_file in pdf_files:
                print(f"Processing: {pdf_file.name}")
                chunks = process_pdf(str(pdf_file), metadata)
                for chunk in chunks:
                    chunk.metadata["source"] = pdf_file.name
                all_chunks.extend(chunks)
                print(f"  -> {len(chunks)} chunks")

    print(f"Total chunks: {len(all_chunks)}")

    # Create and persist vector store
    vectorstore = Chroma.from_documents(
        documents=all_chunks,
        embedding=embeddings,
        persist_directory=persist_directory,
    )

    print(f"Vector store created at: {persist_directory}")

    # Update metadata status
    metadata["status"] = "completed"
    metadata_path = knowledge_path / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return vectorstore


def load_knowledge_base(
    knowledge_dir: str,
) -> Chroma:
    """Load an existing knowledge base from disk."""
    knowledge_path = Path(knowledge_dir)
    metadata = load_metadata(knowledge_dir)
    persist_directory = str(knowledge_path / "vectordb")

    model_name = metadata.get("config", {}).get(
        "embedding_model", "BAAI/bge-large-zh-v1.5"
    )
    embeddings = get_embeddings(model_name)

    return Chroma(
        persist_directory=persist_directory,
        embedding_function=embeddings,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        knowledge_dir = "knowledge/KL001-my-knowledge"
    else:
        knowledge_dir = sys.argv[1]

    print(f"Creating knowledge base: {knowledge_dir}")
    create_knowledge_base(knowledge_dir)
    print("Done!")