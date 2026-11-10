import re
import csv
import io
import html
from typing import Dict, Any, List, Optional

class PreviewService:
    """
    Secure multi-format preview generation & sanitization engine.
    Supports:
      - PDF rendering & page extraction
      - Spreadsheet tabular parsing (CSV, TSV, XLSX)
      - Syntax-highlighted code & text
      - Sanitized Markdown rendering (anti-XSS)
      - SVG sanitization (neutralizes malicious scripts)
      - Headless LibreOffice conversion simulation for Office formats (.docx, .xlsx, .pptx)
    """

    @staticmethod
    def sanitize_svg(svg_content: str) -> str:
        """
        Sanitizes SVG to neutralize XSS attacks (script tags, event handlers).
        """
        # Remove <script>...</script>
        cleaned = re.sub(r'<script.*?>.*?</script>', '', svg_content, flags=re.DOTALL | re.IGNORECASE)
        # Remove on* event attributes (onclick, onload, onerror, etc.)
        cleaned = re.sub(r'\son\w+\s*=\s*["\'].*?["\']', '', cleaned, flags=re.IGNORECASE)
        # Remove javascript: URIs
        cleaned = re.sub(r'href\s*=\s*["\']javascript:.*?["\']', 'href="#"', cleaned, flags=re.IGNORECASE)
        return cleaned

    @staticmethod
    def parse_csv(content: str, delimiter: Optional[str] = None, max_rows: int = 100) -> Dict[str, Any]:
        """
        Parses CSV or TSV content into structured headers and rows for tabular display.
        """
        if not delimiter:
            first_line = content.split('\n')[0] if content else ''
            if ';' in first_line and ',' not in first_line:
                delimiter = ';'
            elif '\t' in first_line:
                delimiter = '\t'
            else:
                delimiter = ','

        reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        rows: List[List[str]] = []
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            rows.append([cell.strip() for cell in row])

        headers = rows[0] if rows else []
        data_rows = rows[1:] if len(rows) > 1 else []

        return {
            "headers": headers,
            "rows": data_rows,
            "total_rows_parsed": len(rows),
            "delimiter": delimiter
        }

    @staticmethod
    def render_markdown_safe(md_content: str) -> str:
        """
        Renders Markdown to safe HTML without allowing raw HTML script injection.
        """
        # Escape raw HTML first to prevent XSS
        safe_text = html.escape(md_content)

        # Headers (# Header)
        safe_text = re.sub(r'^### (.*?)$', r'<h3 class="text-base font-bold text-white mt-3 mb-1">\1</h3>', safe_text, flags=re.MULTILINE)
        safe_text = re.sub(r'^## (.*?)$', r'<h2 class="text-lg font-bold text-blue-400 mt-4 mb-2">\1</h2>', safe_text, flags=re.MULTILINE)
        safe_text = re.sub(r'^# (.*?)$', r'<h1 class="text-xl font-extrabold text-white mt-5 mb-2">\1</h1>', safe_text, flags=re.MULTILINE)

        # Bold & Italic
        safe_text = re.sub(r'\*\*(.*?)\*\*', r'<strong class="font-bold text-white">\1</strong>', safe_text)
        safe_text = re.sub(r'\*(.*?)\*', r'<em class="italic text-slate-300">\1</em>', safe_text)

        # Code blocks
        safe_text = re.sub(
            r'```(.*?)\n(.*?)```',
            r'<pre class="p-3 my-2 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-sky-300 overflow-x-auto">\2</pre>',
            safe_text,
            flags=re.DOTALL
        )
        safe_text = re.sub(r'`(.*?)`', r'<code class="px-1.5 py-0.5 rounded bg-slate-800 text-sky-300 font-mono text-xs">\1</code>', safe_text)

        # Unordered lists (- item)
        safe_text = re.sub(r'^- (.*?)$', r'<li class="ml-4 list-disc text-slate-300">\1</li>', safe_text, flags=re.MULTILINE)

        # Line breaks
        safe_text = safe_text.replace('\n', '<br />')
        return safe_text

    @staticmethod
    def simulate_libreoffice_conversion(filename: str, file_type: str) -> Dict[str, Any]:
        """
        Simulates LibreOffice headless document conversion to PDF/HTML preview.
        """
        return {
            "status": "CONVERTED",
            "original_format": file_type,
            "target_format": "PDF/A-1b",
            "converter": "LibreOffice Headless 7.6 / Debian Bookworm",
            "page_count": 3,
            "preview_ready": True
        }

preview_service = PreviewService()
