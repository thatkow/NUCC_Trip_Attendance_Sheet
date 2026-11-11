"""
A small, dependency-free Markdown-to-HTML renderer for admin-editable
content pages (see content_pages / handle_content_page in app.py). Not a
full CommonMark implementation -- just enough for the kind of reference
page this app needs: headings, paragraphs, bold/italic, links, images,
and simple bullet lists. User input is HTML-escaped before any markdown
syntax is turned into tags, so stray '<'/'>' in the source can't inject
markup.
"""

import html
import re

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_RE = re.compile(r"^[-*]\s+(.*)$")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_ITALIC_RE = re.compile(r"\*(.+?)\*|_(.+?)_")
_CODE_RE = re.compile(r"`([^`]+)`")


def _inline(text):
    """Images, links, bold, italic, inline code -- applied to already
    HTML-escaped text, so the only '<'/'>' present are ones we emit here."""
    text = _IMAGE_RE.sub(lambda m: f'<img src="{m.group(2)}" alt="{m.group(1)}">', text)
    def _link(m):
        href = m.group(2)
        external = href.startswith("http://") or href.startswith("https://")
        attrs = ' target="_blank" rel="noopener"' if external else ""
        return f'<a href="{href}"{attrs}>{m.group(1)}</a>'

    text = _LINK_RE.sub(_link, text)
    text = _BOLD_RE.sub(lambda m: f"<strong>{m.group(1) or m.group(2)}</strong>", text)
    text = _ITALIC_RE.sub(lambda m: f"<em>{m.group(1) or m.group(2)}</em>", text)
    text = _CODE_RE.sub(lambda m: f"<code>{m.group(1)}</code>", text)
    return text


def render(markdown_text):
    """Renders a Markdown string to an HTML fragment (no <html>/<body>
    wrapper -- callers drop this straight into a page)."""
    lines = html.escape(markdown_text or "").split("\n")
    out = []
    paragraph = []
    list_items = None

    def flush_paragraph():
        if paragraph:
            out.append(f"<p>{_inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def flush_list():
        nonlocal list_items
        if list_items is not None:
            out.append("<ul>" + "".join(f"<li>{_inline(i)}</li>" for i in list_items) + "</ul>")
            list_items = None

    for raw_line in lines:
        line = raw_line.rstrip()
        if not line.strip():
            flush_paragraph()
            flush_list()
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            flush_paragraph()
            flush_list()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2).strip())}</h{level}>")
            continue

        bullet = _BULLET_RE.match(line)
        if bullet:
            flush_paragraph()
            if list_items is None:
                list_items = []
            list_items.append(bullet.group(1).strip())
            continue

        flush_list()
        paragraph.append(line.strip())

    flush_paragraph()
    flush_list()
    return "\n".join(out)
