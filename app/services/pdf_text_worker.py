"""Bounded subprocess for extracting selectable text from public PDFs.

No OCR, remote requests, scripts, attachments or embedded links are executed.
"""
from io import BytesIO
import json
import logging
import sys

MAX_BYTES=5_000_000
MAX_PAGES=32
MAX_TEXT=200_000
MAX_PAGE_TEXT=24_000


def main():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,256*1024*1024))
        resource.setrlimit(resource.RLIMIT_CPU,(4,4))
    except ImportError:
        pass  # The parent still enforces a wall-clock timeout on Windows.
    logging.disable(logging.CRITICAL)
    try:
        import pypdf.filters
        from pypdf import PdfReader
        # Smaller than the library default; bound expanded stream allocations.
        pypdf.filters.ZLIB_MAX_OUTPUT_LENGTH=2_000_000
        raw=sys.stdin.buffer.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ValueError('pdf-size-limit')
        reader=PdfReader(BytesIO(raw),strict=False)
        if reader.is_encrypted:
            raise ValueError('encrypted-pdf')
        pages=[];size=0;truncated=len(reader.pages)>MAX_PAGES
        for number,page in enumerate(reader.pages[:MAX_PAGES],1):
            text=(page.extract_text() or '').strip()
            room=min(MAX_PAGE_TEXT,MAX_TEXT-size)
            if len(text)>room:truncated=True
            text=text[:room]
            if text:pages.append({'page':number,'text':text});size+=len(text)
            if size>=MAX_TEXT:break
        result={'pages':pages,'truncated':truncated,'page_count':len(reader.pages)}
    except Exception as exc:
        result={'pages':[],'error':type(exc).__name__}
    sys.stdout.write(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':main()
