import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
import subprocess
import tempfile
import wave
import re
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from groq import Groq

import memory
from rag import Chunk, SiteRAG

site_rag = SiteRAG()

# Default: edge (Microsoft Edge TTS) — no Groq Orpheus daily TPD cap. Set TTS_PROVIDER=groq for Groq Orpheus.
TTS_PROVIDER_DEFAULT = "edge"


def build_rag_system_prompt(
    context_blocks: list[str],
    session_history_block: Optional[str] = None,
) -> str:
    ctx = "\n\n---\n\n".join(context_blocks)
    hist = ""
    if session_history_block and session_history_block.strip():
        hist = f"""

## Prior conversation (this session only)
{session_history_block.strip()}
Use this only for follow-up context (e.g. "what about the phone number?"). Facts must still match WEBSITE CONTEXT below.
"""
    return f"""You are the voice assistant for AI Geo Navigators (website: aigeo360.com).

Answer using ONLY the website context below. Be clear and concise.
If the question is not answered by the context, say you could not find that on the website and suggest the Contact page or email info@aigeo360.com when contact details appear in the context; otherwise say to use the website contact page.
Do not invent products, services, addresses, or phone numbers that are not in the context.
{hist}
WEBSITE CONTEXT:
{ctx}
"""


def _format_session_history(msgs: list[dict]) -> str:
    lines: list[str] = []
    for m in msgs:
        r = m.get("role")
        c = m.get("content", "")
        if r == "user":
            lines.append(f"User: {c}")
        elif r == "assistant":
            lines.append(f"Assistant: {c}")
    return "\n".join(lines)


def _dedupe_hits(hits: list[Chunk], max_chunks: int = 8) -> list[Chunk]:
    seen: set[tuple[str, str]] = set()
    out: list[Chunk] = []
    for h in hits:
        key = (h.url, h.text[:320])
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
        if len(out) >= max_chunks:
            break
    return out


def _hybrid_retrieve(site_rag: SiteRAG, user_q: str, expanded_q: str, k: int = 6) -> list[Chunk]:
    a = site_rag.retrieve(user_q, top_k=k)
    b = site_rag.retrieve(expanded_q, top_k=k) if expanded_q.strip() != user_q.strip() else []
    return _dedupe_hits(a + b, max_chunks=k)


def expand_query_for_synonyms(user_query: str) -> str:
    """Adds synonyms / alternate terms so BM25 matches pages that use different wording."""
    if not client:
        return user_query
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            temperature=0.2,
            max_tokens=150,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You expand a user question for website keyword search. Output ONE line: "
                        "comma-separated synonyms, related industry terms, and alternate phrasings "
                        "(e.g. GIS, mapping, geospatial, remote sensing, climate, ESG, Islamabad, Pakistan). "
                        "No sentence, no quotes."
                    ),
                },
                {"role": "user", "content": user_query[:2000]},
            ],
        )
        extra = (completion.choices[0].message.content or "").strip()
        if not extra or len(extra) < 3:
            return user_query
        return f"{user_query}\n{extra}"
    except Exception:
        return user_query


DEFAULT_GREETING = (
    "Hello! I'm the AI Geo Navigators assistant. I answer from our website. "
    "After this message, please speak your question clearly."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(site_rag.crawl_and_index, 45, 2)
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


@app.get("/")
def root():
    return FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"))


@app.get("/widget.js")
def widget_js():
    return FileResponse(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "widget.js"),
        media_type="application/javascript",
    )


class AskRequest(BaseModel):
    text: str
    session_id: Optional[str] = None


class SessionEndBody(BaseModel):
    session_id: str


def _tts_provider() -> str:
    return (os.environ.get("TTS_PROVIDER") or TTS_PROVIDER_DEFAULT).strip().lower()


def _tts_http_status_groq(exc: Exception) -> tuple[int, str]:
    msg = str(exc)
    if "model_terms_required" in msg or "requires terms acceptance" in msg:
        return 403, f"TTS failed: {msg}"
    if "429" in msg or "rate_limit" in msg.lower() or "Rate limit" in msg:
        return (
            429,
            "Groq Orpheus TTS rate limit hit. Switch to Edge TTS (default): unset TTS_PROVIDER or set TTS_PROVIDER=edge. "
            "Or upgrade Groq: https://console.groq.com/settings/billing",
        )
    return 502, f"TTS failed: {msg}"


def _split_for_edge_tts(s: str, max_len: int = 3200) -> list[str]:
    """Edge reads long text reliably in segments; we concat MP3 with ffmpeg."""
    s = s.strip()
    if len(s) <= max_len:
        return [s]
    parts: list[str] = []
    start = 0
    while start < len(s):
        end = min(start + max_len, len(s))
        if end < len(s):
            cut = s.rfind(". ", start, end)
            if cut == -1 or cut < start + max_len // 2:
                cut = s.rfind(" ", start, end)
            if cut > start:
                end = cut + 1
        piece = s[start:end].strip()
        if piece:
            parts.append(piece)
        start = end
    return parts if parts else [s[:max_len]]


def _ffmpeg_concat_mp3(part_paths: list[str], out_path: str) -> None:
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    list_path = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    try:
        for p in part_paths:
            ap = os.path.abspath(p).replace("\\", "/").replace("'", "'\\''")
            list_path.write("file '" + ap + "'\n")
        list_path.close()
        r = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_path.name,
                "-c",
                "copy",
                out_path,
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if r.returncode != 0:
            raise RuntimeError(r.stderr or r.stdout or "ffmpeg concat failed")
    finally:
        try:
            os.unlink(list_path.name)
        except OSError:
            pass


def _speak_edge_tts(text: str) -> FileResponse:
    import edge_tts

    voice = os.environ.get("EDGE_TTS_VOICE", "en-US-AriaNeural")
    chunks = _split_for_edge_tts(text, 3200)
    part_paths: list[str] = []

    async def _save(chunk: str, path: str) -> None:
        await edge_tts.Communicate(chunk, voice).save(path)

    try:
        for i, ch in enumerate(chunks):
            fd, p = tempfile.mkstemp(suffix=f".{i}.mp3")
            os.close(fd)
            part_paths.append(p)
            asyncio.run(_save(ch, p))

        if len(part_paths) == 1:
            return FileResponse(part_paths[0], media_type="audio/mpeg", filename="reply.mp3")

        fd, out = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        _ffmpeg_concat_mp3(part_paths, out)
        for p in part_paths:
            try:
                os.remove(p)
            except OSError:
                pass
        part_paths.clear()
        return FileResponse(out, media_type="audio/mpeg", filename="reply.mp3")
    except Exception as e:
        for p in part_paths:
            try:
                os.remove(p)
            except OSError:
                pass
        raise HTTPException(status_code=502, detail=f"Edge TTS failed: {e}") from e


def _speak_groq_orpheus(text: str) -> FileResponse:
    if not client:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY is not set.")

    tts_model = "canopylabs/orpheus-v1-english"
    tts_voice = "troy"
    max_chars = 190

    def chunk_words(s: str, limit: int) -> list[str]:
        words = re.split(r"(\s+)", s)
        chunks: list[str] = []
        cur = ""
        for token in words:
            if not token:
                continue
            if len(cur) + len(token) > limit and cur.strip():
                chunks.append(cur.strip())
                cur = token.lstrip()
            else:
                cur += token
        if cur.strip():
            chunks.append(cur.strip())
        return chunks or [s[:limit]]

    chunks = chunk_words(text.strip(), max_chars)
    part_paths: list[str] = []
    speech_path = ""

    try:
        for i, chunk in enumerate(chunks):
            fd, part_path = tempfile.mkstemp(suffix=f".part{i}.wav")
            os.close(fd)
            part_paths.append(part_path)

            response = client.audio.speech.create(
                model=tts_model,
                voice=tts_voice,
                input=chunk,
                response_format="wav",
            )

            if hasattr(response, "write_to_file"):
                response.write_to_file(part_path)
            elif hasattr(response, "content"):
                with open(part_path, "wb") as f:
                    f.write(response.content)
            else:
                with open(part_path, "wb") as f:
                    f.write(bytes(response))

        fd, speech_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        merged_wav = wave.open(speech_path, "wb")
        first_params = None
        for part_path in part_paths:
            with wave.open(part_path, "rb") as w:
                if first_params is None:
                    first_params = (w.getnchannels(), w.getsampwidth(), w.getframerate())
                    merged_wav.setnchannels(first_params[0])
                    merged_wav.setsampwidth(first_params[1])
                    merged_wav.setframerate(first_params[2])
                if (
                    w.getnchannels() != first_params[0]
                    or w.getsampwidth() != first_params[1]
                    or w.getframerate() != first_params[2]
                ):
                    raise RuntimeError("TTS WAV parameters mismatch across chunks.")
                merged_wav.writeframes(w.readframes(w.getnframes()))

        merged_wav.close()
    except HTTPException:
        raise
    except Exception as e:
        status, detail = _tts_http_status_groq(e)
        raise HTTPException(status_code=status, detail=detail) from e
    finally:
        for p in part_paths:
            try:
                os.remove(p)
            except OSError:
                pass

    return FileResponse(speech_path, media_type="audio/wav", filename="reply.wav")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "tts_provider": _tts_provider(),
        "supabase_memory": memory.configured(),
    }


@app.get("/greeting")
def greeting():
    text = os.environ.get("GREETING_TEXT", DEFAULT_GREETING).strip() or DEFAULT_GREETING
    return {"text": text}


@app.post("/session/end")
def session_end(body: SessionEndBody):
    n = memory.delete_session(body.session_id.strip())
    return {"ok": True, "session_id": body.session_id.strip(), "deleted_rows": n}


@app.get("/rag/status")
def rag_status():
    return site_rag.status()


@app.post("/reindex")
async def reindex():
    n = await asyncio.to_thread(site_rag.crawl_and_index, 45, 2)
    return {"indexed_chunks": n, **site_rag.status()}


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    if not client:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY is not set.")

    filename = audio.filename or ""
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    suffix = ext if ext in {".webm", ".wav", ".ogg", ".mp4", ".m4a"} else ".webm"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    with open(tmp_path, "rb") as f:
        try:
            transcription = client.audio.transcriptions.create(
                file=f,
                model="whisper-large-v3",
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"STT failed: {e}")

    return {"text": transcription.text}


@app.post("/ask")
def ask(req: AskRequest):
    if not client:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY is not set.")

    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="No transcript text provided.")

    if not site_rag.is_ready():
        raise HTTPException(
            status_code=503,
            detail="Website index not ready. Check /rag/status or POST /reindex after startup.",
        )

    user_q = req.text.strip()
    expanded = expand_query_for_synonyms(user_q)
    hits = _hybrid_retrieve(site_rag, user_q, expanded, k=6)

    blocks = []
    sources: list[dict] = []
    seen_urls: set[str] = set()
    for h in hits:
        blocks.append(f"Page: {h.title}\nURL: {h.url}\n\n{h.text}")
        if h.url not in seen_urls:
            seen_urls.add(h.url)
            sources.append({"url": h.url, "title": h.title})

    session_id = (req.session_id or "").strip() or None
    history_msgs: list[dict] = []
    if session_id and memory.configured():
        history_msgs = memory.fetch_session_messages(session_id, limit=40)

    recent = history_msgs[-20:] if history_msgs else []
    history_block = _format_session_history(recent) if recent else None

    system = build_rag_system_prompt(
        blocks
        if blocks
        else ["(No matching passages; answer only that you could not find relevant information on the site.)"],
        session_history_block=history_block,
    )

    chat_messages: list[dict] = [{"role": "system", "content": system}]
    for m in recent:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            chat_messages.append({"role": m["role"], "content": m["content"]})
    chat_messages.append({"role": "user", "content": user_q})

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0.2,
        messages=chat_messages,
    )
    answer = completion.choices[0].message.content or ""

    if session_id and memory.configured():
        memory.save_message(session_id, "user", user_q)
        memory.save_message(session_id, "assistant", answer)

    return {"answer": answer, "sources": sources, "session_id": session_id}


@app.post("/speak")
def speak(req: AskRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="No text provided for TTS.")

    text = req.text.strip()
    provider = _tts_provider()

    if provider == "groq":
        return _speak_groq_orpheus(text)
    if provider in ("edge", "edge-tts", "microsoft"):
        return _speak_edge_tts(text)

    raise HTTPException(
        status_code=400,
        detail=f"Unknown TTS_PROVIDER={provider!r}. Use 'edge' (default) or 'groq'.",
    )


# ---------------------------------------------------------------------------
# Widget API — two endpoints a frontend needs for a voice-only widget
# ---------------------------------------------------------------------------

@app.post("/voice/greeting")
def voice_greeting():
    """Returns the greeting as audio directly. Call once when the widget opens."""
    text = os.environ.get("GREETING_TEXT", DEFAULT_GREETING).strip() or DEFAULT_GREETING
    provider = _tts_provider()
    if provider == "groq":
        return _speak_groq_orpheus(text)
    return _speak_edge_tts(text)


@app.post("/voice")
def voice(audio: UploadFile = File(...), session_id: Optional[str] = Form(None)):
    """
    Single round-trip for the widget: audio in → audio out.
    Transcribes, runs RAG + LLM, speaks the answer, returns the audio file.
    """
    if not client:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY is not set.")
    if not site_rag.is_ready():
        raise HTTPException(status_code=503, detail="Website index not ready yet.")

    # --- transcribe ---
    filename = audio.filename or ""
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    suffix = ext if ext in {".webm", ".wav", ".ogg", ".mp4", ".m4a"} else ".webm"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = audio.file.read()
        tmp.write(content)
        tmp_path = tmp.name

    with open(tmp_path, "rb") as f:
        try:
            transcription = client.audio.transcriptions.create(file=f, model="whisper-large-v3")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"STT failed: {e}")

    user_q = (transcription.text or "").strip()
    if not user_q:
        raise HTTPException(status_code=400, detail="Could not transcribe any speech.")

    # --- RAG + LLM ---
    sid = (session_id or "").strip() or None
    expanded = expand_query_for_synonyms(user_q)
    hits = _hybrid_retrieve(site_rag, user_q, expanded, k=6)

    blocks = [f"Page: {h.title}\nURL: {h.url}\n\n{h.text}" for h in hits]

    history_msgs: list[dict] = []
    if sid and memory.configured():
        history_msgs = memory.fetch_session_messages(sid, limit=40)

    recent = history_msgs[-20:] if history_msgs else []
    history_block = _format_session_history(recent) if recent else None

    system = build_rag_system_prompt(
        blocks or ["(No matching passages; answer only that you could not find relevant information on the site.)"],
        session_history_block=history_block,
    )

    chat_messages: list[dict] = [{"role": "system", "content": system}]
    for m in recent:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            chat_messages.append({"role": m["role"], "content": m["content"]})
    chat_messages.append({"role": "user", "content": user_q})

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile", temperature=0.2, messages=chat_messages,
    )
    answer = (completion.choices[0].message.content or "").strip()

    if sid and memory.configured():
        memory.save_message(sid, "user", user_q)
        memory.save_message(sid, "assistant", answer)

    if not answer:
        raise HTTPException(status_code=502, detail="LLM returned empty answer.")

    # --- TTS ---
    provider = _tts_provider()
    if provider == "groq":
        return _speak_groq_orpheus(answer)
    return _speak_edge_tts(answer)
