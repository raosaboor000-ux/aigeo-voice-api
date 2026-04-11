"""
Optional Supabase storage for per-session chat history. When session ends, rows are deleted.
Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (recommended for server) or SUPABASE_ANON_KEY.
"""
from __future__ import annotations

import os
from typing import Any, Optional

_TABLE = "conversation_messages"


def configured() -> bool:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.environ.get("SUPABASE_ANON_KEY", "").strip()
    )
    return bool(url and key)


def _client() -> Any:
    if not configured():
        return None
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL", "").strip()
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.environ.get("SUPABASE_ANON_KEY", "").strip()
    )
    return create_client(url, key)


def fetch_session_messages(session_id: str, limit: int = 24) -> list[dict[str, str]]:
    """Returns [{role, content}, ...] oldest first."""
    if not session_id or not configured():
        return []
    sb = _client()
    if not sb:
        return []
    try:
        res = (
            sb.table(_TABLE)
            .select("role,content,created_at")
            .eq("session_id", session_id)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        rows = res.data or []
        out: list[dict[str, str]] = []
        for r in rows:
            role = r.get("role")
            content = r.get("content")
            if role in ("user", "assistant") and content is not None:
                out.append({"role": role, "content": str(content)})
        return out
    except Exception:
        return []


def save_message(session_id: str, role: str, content: str) -> None:
    if not session_id or not configured() or role not in ("user", "assistant"):
        return
    sb = _client()
    if not sb:
        return
    try:
        sb.table(_TABLE).insert(
            {"session_id": session_id, "role": role, "content": content[:120000]}
        ).execute()
    except Exception:
        pass


def delete_session(session_id: str) -> int:
    """Deletes all messages for session. Returns 0 if unavailable."""
    if not session_id or not configured():
        return 0
    sb = _client()
    if not sb:
        return 0
    try:
        res = sb.table(_TABLE).delete().eq("session_id", session_id).execute()
        # supabase returns deleted rows count in some versions
        return len(res.data or []) if getattr(res, "data", None) is not None else 1
    except Exception:
        return 0
