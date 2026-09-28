import hashlib
import html
import math
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from .models import RagChatEvent, RagChunk, RagDocument, utc_now


SUPPORTED_EXTENSIONS = {".html", ".htm", ".md", ".txt", ".pdf"}
TOKEN_RE = re.compile(r"[a-záéíóúüñ0-9]{3,}", re.IGNORECASE)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
INJECTION_PATTERNS = (
    "ignora las instrucciones",
    "ignora todas las instrucciones",
    "olvida las instrucciones",
    "actua como",
    "actúa como",
    "system prompt",
    "developer message",
    "mensaje del sistema",
    "instrucciones del sistema",
    "jailbreak",
    "api key",
    "contraseña",
    "secreto",
    "token",
)


@dataclass(frozen=True)
class SourceDocument:
    source_key: str
    title: str
    path: Path
    text: str


class _VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "svg", "noscript"}:
            self._skip_depth += 1
        if tag in {"p", "br", "li", "h1", "h2", "h3", "h4", "section", "article"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "svg", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "li", "h1", "h2", "h3", "h4", "section", "article"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip_depth:
            self.parts.append(data)

    def text(self):
        return clean_text(" ".join(self.parts))


def clean_text(value):
    value = html.unescape(value or "")
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s+([,.;:])", r"\1", value)
    return value.strip()


def tokenize(value):
    return [match.group(0).lower() for match in TOKEN_RE.finditer(value or "")]


def embed_text(value, dimensions):
    vector = [0.0] * dimensions
    for token in tokenize(value):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(item * item for item in vector))
    if norm == 0:
        return vector
    return [round(item / norm, 6) for item in vector]


def cosine(left, right):
    return sum(float(a) * float(b) for a, b in zip(left, right))


def resolve_source_files(source_paths, base_dir=None):
    base_dir = Path(base_dir or Path.cwd())
    files = []
    for configured in source_paths:
        path = Path(configured)
        candidates = [path] if path.is_absolute() else [base_dir / path, base_dir.parent / path]
        existing = next((candidate for candidate in candidates if candidate.exists()), None)
        if existing is None:
            continue
        if existing.is_dir():
            files.extend(
                sorted(
                    item
                    for item in existing.rglob("*")
                    if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS
                )
            )
        elif existing.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(existing)
    return list(dict.fromkeys(files))


def extract_text(path):
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return clean_text(path.read_text(encoding="utf-8", errors="ignore"))
    if suffix in {".html", ".htm"}:
        parser = _VisibleTextParser()
        parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
        return parser.text()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            return ""
        reader = PdfReader(str(path))
        return clean_text("\n".join(page.extract_text() or "" for page in reader.pages))
    return ""


def load_sources(settings, base_dir=None):
    sources = []
    for path in resolve_source_files(settings.rag_source_paths, base_dir=base_dir):
        text = extract_text(path)
        if len(text) < 80:
            continue
        title = path.stem.replace("_", " ").replace("-", " ").strip()
        sources.append(
            SourceDocument(
                source_key=hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:24],
                title=title,
                path=path,
                text=text,
            )
        )
    return sources


def chunk_text(text, chunk_chars, overlap):
    paragraphs = [part.strip() for part in re.split(r"\n+|(?<=\.)\s{2,}", text) if part.strip()]
    chunks = []
    current = ""
    for paragraph in paragraphs:
        if not current:
            current = paragraph
        elif len(current) + 1 + len(paragraph) <= chunk_chars:
            current = current + " " + paragraph
        else:
            chunks.append(current[:chunk_chars].strip())
            current = (current[-overlap:] + " " + paragraph).strip() if overlap else paragraph
            while len(current) > chunk_chars:
                chunks.append(current[:chunk_chars].strip())
                current = current[chunk_chars - overlap :].strip() if overlap else current[chunk_chars:].strip()
    if current:
        chunks.append(current[:chunk_chars].strip())
    return [chunk for chunk in chunks if len(chunk) >= 60]


def ingest_sources(db: Session, settings, base_dir=None):
    documents = load_sources(settings, base_dir=base_dir)
    db.execute(delete(RagChunk))
    db.execute(delete(RagDocument))
    total_chunks = 0
    source_names = []
    for source in documents:
        chunks = chunk_text(source.text, settings.rag_chunk_chars, settings.rag_chunk_overlap)
        document = RagDocument(
            source_key=source.source_key,
            title=source.title[:256],
            source_path=str(source.path),
            content_hash=hashlib.sha256(source.text.encode("utf-8")).hexdigest(),
            chunk_count=len(chunks),
            ingested_at=utc_now(),
        )
        db.add(document)
        db.flush()
        for index, chunk in enumerate(chunks, start=1):
            db.add(
                RagChunk(
                    document_id=document.id,
                    chunk_index=index,
                    locator="fragmento {0}".format(index),
                    text=chunk,
                    embedding=embed_text(chunk, settings.rag_embedding_dimensions),
                    token_count=len(tokenize(chunk)),
                )
            )
        total_chunks += len(chunks)
        source_names.append(source.path.name)
    db.commit()
    return {"documents": len(documents), "chunks": total_chunks, "sources": source_names}


def rag_status(db: Session):
    return {
        "documents": db.scalar(select(func.count(RagDocument.id))) or 0,
        "chunks": db.scalar(select(func.count(RagChunk.id))) or 0,
    }


def looks_like_prompt_injection(question):
    lowered = (question or "").lower()
    return any(pattern in lowered for pattern in INJECTION_PATTERNS)


def retrieve_chunks(db: Session, question, settings):
    query_embedding = embed_text(question, settings.rag_embedding_dimensions)
    chunks = db.scalars(select(RagChunk).options(selectinload(RagChunk.document))).all()
    ranked = sorted(
        ((cosine(query_embedding, chunk.embedding), chunk) for chunk in chunks),
        key=lambda item: item[0],
        reverse=True,
    )
    return ranked[: settings.rag_top_k]


def _best_sentences(question, chunks):
    question_terms = set(tokenize(question))
    scored = []
    for citation_number, (_, chunk) in enumerate(chunks, start=1):
        for sentence in SENTENCE_RE.split(chunk.text):
            sentence = clean_text(sentence)
            if len(sentence) < 40:
                continue
            terms = set(tokenize(sentence))
            score = len(question_terms & terms) / max(len(question_terms), 1)
            scored.append((score, citation_number, sentence))
    scored.sort(key=lambda item: item[0], reverse=True)
    selected = []
    seen = set()
    for score, citation_number, sentence in scored:
        key = sentence[:80].lower()
        if key in seen:
            continue
        seen.add(key)
        selected.append((citation_number, sentence))
        if len(selected) == 3:
            break
    return selected


def build_answer(question, ranked_chunks):
    relevant = [(score, chunk) for score, chunk in ranked_chunks if score > 0.04]
    if not relevant:
        citations = [_citation(score, chunk) for score, chunk in ranked_chunks[:2]]
        return (
            "No encontré una fuente suficientemente relacionada en los documentos ingeridos del OVA. "
            "Reformula la pregunta o revisa si falta ingerir material fuente.",
            citations,
        )
    citations = [_citation(score, chunk) for score, chunk in relevant]
    sentences = _best_sentences(question, relevant)
    if not sentences:
        answer = (
            "Con base en las fuentes del OVA, el tema aparece tratado en los fragmentos citados. "
            "Revisa las citas para confirmar el alcance exacto de la respuesta."
        )
    else:
        answer = " ".join("{0} [{1}]".format(sentence, number) for number, sentence in sentences)
    return answer, citations


def _citation(score, chunk):
    snippet = clean_text(chunk.text)
    if len(snippet) > 360:
        snippet = snippet[:357].rstrip() + "..."
    return {
        "source_id": chunk.document.source_key,
        "title": chunk.document.title,
        "locator": chunk.locator,
        "snippet": snippet,
        "score": round(float(score), 4),
    }


def answer_question(db: Session, settings, subject_id, question):
    question = clean_text(question)
    if len(question) > settings.rag_max_question_chars:
        raise ValueError("La pregunta supera el límite permitido para el piloto")
    if looks_like_prompt_injection(question):
        answer = (
            "No puedo seguir instrucciones que intenten cambiar las reglas del asistente, revelar secretos "
            "o ignorar las fuentes del OVA. Formula una pregunta sobre el Modelo de las Tres Líneas."
        )
        ranked_chunks = retrieve_chunks(
            db,
            "uso seguro del asistente fuentes del OVA secretos tokens instrucciones internas",
            settings,
        )
        citations = [_citation(score, chunk) for score, chunk in ranked_chunks[:2]]
        event = RagChatEvent(subject_id=subject_id, question=question, answer=answer, citations=citations)
        db.add(event)
        db.commit()
        return {"answer": answer, "citations": citations, "blocked": True}
    ranked_chunks = retrieve_chunks(db, question, settings)
    if not ranked_chunks:
        raise LookupError("RAG no tiene documentos ingeridos")
    answer, citations = build_answer(question, ranked_chunks)
    event = RagChatEvent(subject_id=subject_id, question=question, answer=answer, citations=citations)
    db.add(event)
    db.commit()
    return {"answer": answer, "citations": citations, "blocked": False}
