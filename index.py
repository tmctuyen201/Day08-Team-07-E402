"""
index.py — Sprint 1: Build RAG Index
====================================
Mục tiêu Sprint 1 (60 phút):
  - Đọc và preprocess tài liệu từ data/docs/
  - Chunk tài liệu theo cấu trúc tự nhiên (heading/section)
  - Gắn metadata: source, section, department, effective_date, access
  - Embed và lưu vào vector store (ChromaDB)

Definition of Done Sprint 1:
  ✓ Script chạy được và index đủ docs
  ✓ Có ít nhất 3 metadata fields hữu ích cho retrieval
  ✓ Có thể kiểm tra chunk bằng list_chunks()
"""

import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# Disable TensorFlow to avoid Keras 3 / torchvision conflicts in this environment
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_TORCH", "1")

# =============================================================================
# CẤU HÌNH
# =============================================================================

DOCS_DIR = Path(__file__).parent / "data" / "docs"
CHROMA_DB_DIR = Path(__file__).parent / "chroma_db"

CHUNK_SIZE = 400       # tokens (ước lượng bằng số ký tự / 4)
CHUNK_OVERLAP = 80     # tokens overlap giữa các chunk

# Embedding provider: "openai" hoặc "local"
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
API_KEY = os.getenv("OPENAI_API_KEY", "")


# =============================================================================
# STEP 1: PREPROCESS
# =============================================================================

def preprocess_document(raw_text: str, filepath: str) -> Dict[str, Any]:
    """
    Preprocess một tài liệu: extract metadata từ header và làm sạch nội dung.
    """
    lines = raw_text.strip().split("\n")
    metadata = {
        "source": filepath,
        "section": "",
        "department": "unknown",
        "effective_date": "unknown",
        "access": "internal",
    }
    content_lines = []
    header_done = False
    
    # Dùng list để giữ title nếu nó là dòng đầu tiên
    for i, line in enumerate(lines):
        clean_line = line.strip()
        if not clean_line:
            if header_done:
                content_lines.append(line)
            continue

        if not header_done:
            # Luôn giữ dòng đầu tiên nếu nó có vẻ là tiêu đề (viết hoa hoặc không phải metadata)
            if i == 0 and not clean_line.startswith(("Source:", "Department:", "Effective Date:", "Access:")):
                content_lines.append(line)
                continue

            if clean_line.startswith("Source:"):
                metadata["source"] = clean_line.replace("Source:", "").strip()
            elif clean_line.startswith("Department:"):
                metadata["department"] = clean_line.replace("Department:", "").strip()
            elif clean_line.startswith("Effective Date:"):
                metadata["effective_date"] = clean_line.replace("Effective Date:", "").strip()
            elif clean_line.startswith("Access:"):
                metadata["access"] = clean_line.replace("Access:", "").strip()
            elif clean_line.startswith("==="):
                header_done = True
                content_lines.append(line)
            else:
                # Nếu gặp dòng không phải metadata và chưa có ===, coi như bắt đầu nội dung
                # trừ khi nó là dòng trống (đã check ở trên)
                header_done = True
                content_lines.append(line)
        else:
            content_lines.append(line)

    cleaned_text = "\n".join(content_lines)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)

    return {
        "text": cleaned_text,
        "metadata": metadata,
    }


# =============================================================================
# STEP 2: CHUNK
# =============================================================================

def chunk_document(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Chunk một tài liệu đã preprocess thành danh sách các chunk nhỏ.
    Split theo heading "=== ... ===" trước, rồi split theo paragraph nếu quá dài.
    """
    text = doc["text"]
    base_metadata = doc["metadata"].copy()
    chunks = []

    # Split theo heading pattern "=== ... ==="
    sections = re.split(r"(===.*?===)", text)

    current_section = "General"
    current_section_text = ""

    for part in sections:
        if re.match(r"===.*?===", part):
            if current_section_text.strip():
                section_chunks = _split_by_paragraph(
                    current_section_text.strip(),
                    base_metadata=base_metadata,
                    section=current_section,
                )
                chunks.extend(section_chunks)
            current_section = part.strip("= ").strip()
            current_section_text = ""
        else:
            current_section_text += part

    # Lưu section cuối cùng
    if current_section_text.strip():
        section_chunks = _split_by_paragraph(
            current_section_text.strip(),
            base_metadata=base_metadata,
            section=current_section,
        )
        chunks.extend(section_chunks)

    return chunks


def _split_by_paragraph(
    text: str,
    base_metadata: Dict,
    section: str,
    chunk_chars: int = CHUNK_SIZE * 4,
    overlap_chars: int = CHUNK_OVERLAP * 4,
) -> List[Dict[str, Any]]:
    """
    Split text theo paragraph với overlap. Ưu tiên cắt tại ranh giới paragraph.
    Nếu một paragraph vẫn quá dài, sẽ cắt nhỏ tiếp theo độ dài ký tự.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    
    # Nếu không có paragraph nào, xử lý text như một khối
    if not paragraphs and text.strip():
        paragraphs = [text.strip()]

    chunks = []
    current_chunk_text = ""
    
    def add_chunk(content):
        nonlocal current_chunk_text
        # Lấy overlap từ chunk cuối cùng đã thêm
        prev_text = chunks[-1]["text"] if chunks else ""
        overlap = prev_text[-overlap_chars:] if len(prev_text) > overlap_chars else prev_text
        
        full_text = (overlap.strip() + "\n\n" + content).strip() if overlap else content
        chunks.append({
            "text": full_text,
            "metadata": {**base_metadata, "section": section},
        })

    for para in paragraphs:
        # Nếu một paragraph đơn lẻ quá dài, cắt nhỏ nó ra
        if len(para) > chunk_chars:
            # Add current_chunk_text if not empty
            if current_chunk_text:
                add_chunk(current_chunk_text)
                current_chunk_text = ""
            
            # Chia nhỏ paragraph dài
            for i in range(0, len(para), chunk_chars - overlap_chars):
                sub_para = para[i:i + chunk_chars]
                add_chunk(sub_para)
            continue

        if len(current_chunk_text) + len(para) + 2 <= chunk_chars:
            current_chunk_text = (current_chunk_text + "\n\n" + para).strip() if current_chunk_text else para
        else:
            add_chunk(current_chunk_text)
            current_chunk_text = para

    if current_chunk_text:
        add_chunk(current_chunk_text)

    return chunks if chunks else [{
        "text": text,
        "metadata": {**base_metadata, "section": section},
    }]


# =============================================================================
# STEP 3: EMBED + STORE
# =============================================================================

# Cache model để không load lại nhiều lần
_embedding_model = None

def get_embedding(text: str) -> List[float]:
    """
    Tạo embedding vector cho một đoạn text.
    Dùng Sentence Transformers (local) hoặc OpenAI tùy EMBEDDING_PROVIDER.
    """
    global _embedding_model

    if EMBEDDING_PROVIDER == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=API_KEY)
        response = client.embeddings.create(
            input=text,
            model=EMBEDDING_MODEL
        )
        return response.data[0].embedding
    else:
        # Local: dùng torch + transformers trực tiếp để tránh xung đột TF/torchvision
        import torch
        from transformers import AutoTokenizer, AutoModel
        if _embedding_model is None:
            print(f"  [Embedding] Loading model {EMBEDDING_MODEL} (pytorch only)...")
            model_name = EMBEDDING_MODEL if EMBEDDING_PROVIDER != "openai" else "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModel.from_pretrained(model_name)
            model.eval()
            _embedding_model = (tokenizer, model)

        tokenizer, model = _embedding_model
        with torch.no_grad():
            inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding=True)
            outputs = model(**inputs)
            # Mean pooling
            token_embeddings = outputs.last_hidden_state
            attention_mask = inputs["attention_mask"]
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            embedding = torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)
            # Normalize
            embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)
        return embedding[0].tolist()

# Hỗ trợ đọc nhiều định dạng file (txt, pdf, docx) nếu cần mở rộng sau này    

def read_file(filepath: Path) -> str:
    if filepath.suffix == ".txt":
        return filepath.read_text(encoding="utf-8")

    elif filepath.suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(filepath)
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    elif filepath.suffix == ".docx":
        import docx
        doc = docx.Document(filepath)
        return "\n".join(p.text for p in doc.paragraphs)

    else:
        raise ValueError(f"Unsupported file type: {filepath}")


def build_index(docs_dir: Path = DOCS_DIR, db_dir: Path = CHROMA_DB_DIR) -> None:
    """
    Pipeline hoàn chỉnh: đọc docs → preprocess → chunk → embed → store.
    """
    import chromadb

    print(f"Đang build index từ: {docs_dir}")
    db_dir.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(db_dir))
    # Xóa collection cũ nếu có để re-index sạch
    try:
        client.delete_collection("rag_lab")
    except Exception:
        pass
    collection = client.get_or_create_collection(
        name="rag_lab",
        metadata={"hnsw:space": "cosine"}
    )

    total_chunks = 0
    # Tìm kiếm tất cả các file hỗ trợ
    doc_files = []
    for ext in ["*.txt", "*.pdf", "*.docx"]:
        doc_files.extend(list(docs_dir.glob(ext)))

    if not doc_files:
        print(f"Không tìm thấy file .txt trong {docs_dir}")
        return

    for filepath in doc_files:
        print(f"  Processing: {filepath.name}")
        raw_text = read_file(filepath)

        doc = preprocess_document(raw_text, str(filepath))
        chunks = chunk_document(doc)

        print(f"    → {len(chunks)} chunks, source={doc['metadata']['source']}, date={doc['metadata']['effective_date']}")

        ids = []
        embeddings = []
        documents = []
        metadatas = []

        for i, chunk in enumerate(chunks):
            chunk_id = f"{filepath.stem}_{i}"
            embedding = get_embedding(chunk["text"])
            ids.append(chunk_id)
            embeddings.append(embedding)
            documents.append(chunk["text"])
            metadatas.append(chunk["metadata"])

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        total_chunks += len(chunks)

    print(f"\nHoàn thành! Tổng số chunks đã index: {total_chunks}")


# =============================================================================
# STEP 4: INSPECT / KIỂM TRA
# =============================================================================

def list_chunks(db_dir: Path = CHROMA_DB_DIR, n: int = 5) -> None:
    """In ra n chunk đầu tiên trong ChromaDB để kiểm tra chất lượng index."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(db_dir))
        collection = client.get_collection("rag_lab")
        results = collection.get(limit=n, include=["documents", "metadatas"])

        print(f"\n=== Top {n} chunks trong index ===\n")
        for i, (doc, meta) in enumerate(zip(results["documents"], results["metadatas"])):
            print(f"[Chunk {i+1}]")
            print(f"  Source: {meta.get('source', 'N/A')}")
            print(f"  Section: {meta.get('section', 'N/A')}")
            print(f"  Effective Date: {meta.get('effective_date', 'N/A')}")
            print(f"  Department: {meta.get('department', 'N/A')}")
            print(f"  Text preview: {doc[:120]}...")
            print()
    except Exception as e:
        print(f"Lỗi khi đọc index: {e}")
        print("Hãy chạy build_index() trước.")


def inspect_metadata_coverage(db_dir: Path = CHROMA_DB_DIR) -> None:
    """Kiểm tra phân phối metadata trong toàn bộ index."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(db_dir))
        collection = client.get_collection("rag_lab")
        results = collection.get(include=["metadatas"])

        print(f"\nTổng chunks: {len(results['metadatas'])}")

        departments = {}
        missing_date = 0
        for meta in results["metadatas"]:
            dept = meta.get("department", "unknown")
            departments[dept] = departments.get(dept, 0) + 1
            if meta.get("effective_date") in ("unknown", "", None):
                missing_date += 1

        print("Phân bố theo department:")
        for dept, count in departments.items():
            print(f"  {dept}: {count} chunks")
        print(f"Chunks thiếu effective_date: {missing_date}")

    except Exception as e:
        print(f"Lỗi: {e}. Hãy chạy build_index() trước.")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Sprint 1: Build RAG Index")
    print("=" * 60)

    doc_files = list(DOCS_DIR.glob("*.txt"))
    print(f"\nTìm thấy {len(doc_files)} tài liệu:")
    for f in doc_files:
        print(f"  - {f.name}")

    # Test preprocess + chunking
    print("\n--- Test preprocess + chunking ---")
    for filepath in doc_files[:1]:
        raw = filepath.read_text(encoding="utf-8")
        doc = preprocess_document(raw, str(filepath))
        chunks = chunk_document(doc)
        print(f"\nFile: {filepath.name}")
        print(f"  Metadata: {doc['metadata']}")
        print(f"  Số chunks: {len(chunks)}")
        for i, chunk in enumerate(chunks[:3]):
            print(f"\n  [Chunk {i+1}] Section: {chunk['metadata']['section']}")
            print(f"  Text: {chunk['text'][:150]}...")

    # Build full index
    print("\n--- Build Full Index ---")
    build_index()

    # Kiểm tra index
    list_chunks()
    inspect_metadata_coverage()

    print("\nSprint 1 hoàn thành!")
