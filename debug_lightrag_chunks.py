"""
Debug LightRAG retrieval: print the actual retrieved chunks.

Usage examples:
  python debug_lightrag_chunks.py --query "Tell me about EBL Utkorsho" --kb ebl_products
  python debug_lightrag_chunks.py --query "Tell me about EBL Utkorsho" --kb ebl_website --top-k 8 --chunk-top-k 10

This calls LightRAG's /query/data endpoint and prints:
- Response keys
- References (if any)
- Retrieved chunks (best-effort extraction across possible response shapes)
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

from connect_lightrag import LightRAGClient


def _ensure_utf8_stdout() -> None:
    """
    Windows consoles often default to cp1252, which can crash on arrows/emdashes, etc.
    This mirrors the UTF-8 setup used in other test scripts in this repo.
    """
    try:
        if getattr(sys.stdout, "encoding", None) and sys.stdout.encoding.lower() != "utf-8":
            try:
                sys.stdout.reconfigure(encoding="utf-8")
            except Exception:
                import codecs
                sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    except Exception:
        # If we can't reconfigure stdout, continue; printing may still fail for some chars.
        pass


def _as_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return str(v)


def _guess_source(obj: Dict[str, Any]) -> str:
    for k in ("source", "file_source", "file_name", "document", "doc", "path"):
        v = obj.get(k)
        if v:
            return _as_str(v)
    return ""


def _guess_score(obj: Dict[str, Any]) -> Optional[float]:
    for k in ("score", "similarity", "cosine", "rerank_score", "distance"):
        v = obj.get(k)
        if v is None:
            continue
        try:
            return float(v)
        except Exception:
            continue
    return None


def _guess_text(obj: Dict[str, Any]) -> str:
    for k in ("text", "chunk", "content", "page_content", "context"):
        v = obj.get(k)
        if v:
            return _as_str(v)
    return ""


def _iter_possible_chunk_dicts(data: Any) -> Iterable[Dict[str, Any]]:
    """
    LightRAG /query/data response shapes vary.
    We defensively scan known container keys for chunk-like dicts.
    """
    if isinstance(data, dict):
        # direct chunk list
        for key in ("chunks", "chunk", "vector_chunks", "retrieved_chunks", "contexts"):
            v = data.get(key)
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        yield item
                    elif isinstance(item, str):
                        yield {"text": item}
        # sometimes chunks are nested under "data"
        if "data" in data:
            yield from _iter_possible_chunk_dicts(data["data"])
        # fallback: scan dict values for lists of dicts with text-like keys
        for v in data.values():
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and any(k in item for k in ("text", "chunk", "content", "page_content", "context")):
                        yield item


def _extract_chunks(resp: Dict[str, Any]) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str]] = set()
    for c in _iter_possible_chunk_dicts(resp):
        text = _guess_text(c).strip()
        source = _guess_source(c).strip()
        if not text and not source:
            continue
        key = (source, text[:200])
        if key in seen:
            continue
        seen.add(key)
        chunks.append(c)
    return chunks


def _print_refs(resp: Dict[str, Any], limit: int) -> None:
    refs = resp.get("references")
    if not refs:
        return
    print("\n" + "=" * 90)
    print(f"REFERENCES ({len(refs)})")
    print("=" * 90)
    for i, r in enumerate(refs[:limit], start=1):
        if isinstance(r, str):
            print(f"[{i}] {r}")
            continue
        if not isinstance(r, dict):
            print(f"[{i}] {r}")
            continue
        src = _guess_source(r)
        txt = _guess_text(r).replace("\n", " ").strip()
        if txt:
            txt = (txt[:220] + "...") if len(txt) > 220 else txt
        print(f"[{i}] source={src or '(unknown)'}")
        if txt:
            print(f"    {txt}")


def _print_chunks(chunks: List[Dict[str, Any]], limit: int) -> None:
    print("\n" + "=" * 90)
    print(f"CHUNKS (extracted {len(chunks)})")
    print("=" * 90)
    for i, c in enumerate(chunks[:limit], start=1):
        src = _guess_source(c) or "(unknown)"
        score = _guess_score(c)
        txt = _guess_text(c).strip()
        if txt:
            txt = txt.replace("\r\n", "\n")
            preview = txt[:900] + ("..." if len(txt) > 900 else "")
        else:
            preview = "(no text field found on chunk object)"
        score_part = f" score={score:.4f}" if isinstance(score, float) else ""
        print(f"\n[{i}] source={src}{score_part}")
        print(preview)


def main() -> None:
    _ensure_utf8_stdout()
    p = argparse.ArgumentParser(description="Print retrieved chunks for a LightRAG query (/query/data).")
    p.add_argument("--query", required=True, help="User query to send to LightRAG")
    p.add_argument("--kb", default="ebl_website", help="Knowledge base name (e.g., ebl_website, ebl_products)")
    p.add_argument("--base-url", default="http://localhost:9262", help="LightRAG base URL (default: http://localhost:9262)")
    p.add_argument("--api-key", default="MyCustomLightRagKey456", help="LightRAG API key")
    p.add_argument("--mode", default="mix", help="LightRAG mode (mix/kg/chunk)")
    p.add_argument("--top-k", type=int, default=8, help="top_k (KG)")
    p.add_argument("--chunk-top-k", type=int, default=10, help="chunk_top_k (vector chunks)")
    p.add_argument("--only-need-context", action="store_true", help="Set only_need_context=true (default false)")
    p.add_argument("--include-references", action="store_true", help="Set include_references=true (default false)")
    p.add_argument("--print-raw", action="store_true", help="Print raw JSON response (careful: can be large)")
    p.add_argument("--limit", type=int, default=10, help="Max chunks/references to print")
    args = p.parse_args()

    client = LightRAGClient(base_url=args.base_url, api_key=args.api_key)
    resp = client.query_data(
        args.query,
        knowledge_base=args.kb,
        mode=args.mode,
        top_k=args.top_k,
        chunk_top_k=args.chunk_top_k,
        include_references=bool(args.include_references),
        only_need_context=bool(args.only_need_context),
    )

    print("=" * 90)
    print("LightRAG /query/data response received")
    print("=" * 90)
    print(f"query: {args.query}")
    print(f"kb: {args.kb}")
    print(f"mode: {args.mode}  top_k: {args.top_k}  chunk_top_k: {args.chunk_top_k}")
    print(f"keys: {sorted(list(resp.keys()))}")

    if args.print_raw:
        print("\n" + "=" * 90)
        print("RAW JSON")
        print("=" * 90)
        print(json.dumps(resp, ensure_ascii=False, indent=2)[:20000])

    _print_refs(resp, limit=args.limit)
    chunks = _extract_chunks(resp)
    _print_chunks(chunks, limit=args.limit)


if __name__ == "__main__":
    main()

