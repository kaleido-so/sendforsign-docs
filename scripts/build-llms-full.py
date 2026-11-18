#!/usr/bin/env python3
"""Builds llms-full.txt: a hand-written header (scripts/llms-full.head.txt),
the AI agents pages, and a compact REST API reference generated from the
api-reference/*.mdx pages listed in mint.json navigation.

Run from the repo root after changing docs:  python3 scripts/build-llms-full.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://sendforsign.com/docs"

AGENT_PAGES = [
    "ai-agents/overview",
    "ai-agents/mcp-quickstart",
    "ai-agents/headers",
    "ai-agents/tools",
    "ai-agents/accountability",
    "ai-agents/recipes",
    "ai-agents/prompts",
]
CONCEPT_PAGES = [
    "api-reference/introapi",
    "api-reference/structure",
    "api-reference/authentication",
    "usecase/placeholder-filler",
    "api-reference/webhook/concept",
]
REST_GROUPS = ["Client", "User", "Contract", "PDF and Word", "Placeholder",
               "Recipient", "Template", "Webhook", "Settings"]


def frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    meta = {}
    if m:
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip("'\"")
        text = text[m.end():]
    return meta, text


def strip_mdx(body):
    """Turns Mintlify MDX into plain Markdown good enough for an LLM."""
    body = re.sub(r"<Frame[^>]*>.*?</Frame>", "", body, flags=re.S)
    body = re.sub(r"<img[^>]*/>", "", body)
    # Cards -> bullet links
    body = re.sub(r'<Card title="([^"]+)"[^>]*href="([^"]+)"[^>]*>\s*(.*?)\s*</Card>',
                  lambda m: f"- [{m.group(1)}]({SITE}{m.group(2)}): {' '.join(m.group(3).split())}", body, flags=re.S)
    body = re.sub(r'<(Tab|Step) title="([^"]+)">', r"**\2**", body)
    body = re.sub(r"</?(CardGroup|Tabs|Tab|Steps|Step|Note|Warning|Tip|Info|Expandable|RequestExample|ResponseExample)[^>]*>", "", body)
    body = re.sub(r"\]\((/[^)]*)\)", lambda m: f"]({SITE}{m.group(1)})", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def demote(body):
    """Pushes page headings one level down, leaving code blocks alone."""
    out, fence = [], False
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
        elif not fence and re.match(r"#{1,5} ", line):
            line = "#" + line
        out.append(line)
    return "\n".join(out)


def page(slug):
    meta, body = frontmatter((ROOT / f"{slug}.mdx").read_text())
    return meta, body


def rest_page(slug):
    meta, body = page(slug)
    out = [f"### {meta.get('title', slug)}", f"Source: {SITE}/{slug}"]
    if meta.get("api"):
        out.append(f"Endpoint: `{meta['api']}`")
    intro = body.split("###")[0]
    intro = strip_mdx(re.sub(r"<ParamField.*", "", intro, flags=re.S))
    if intro:
        out.append(intro)
    # Parameters, with nesting from <Expandable>
    params = []
    depth = 0
    for tok in re.finditer(r"<ParamField\s+(\w+)=\"([^\"]+)\"\s+type=\"([^\"]+)\"\s*(required)?\s*>(.*?)(?=<ParamField|</ParamField>|<Expandable)|<Expandable|</Expandable>", body, re.S):
        t = tok.group(0)
        if t.startswith("<Expandable"):
            depth += 1
            continue
        if t.startswith("</Expandable"):
            depth = max(0, depth - 1)
            continue
        kind, name, typ, req, desc = tok.groups()
        desc = " ".join(strip_mdx(desc).split())
        if name == "data" and kind == "body":
            continue
        indent = "  " * max(0, depth - 1)
        params.append(f"{indent}- `{name}` ({kind}, {typ}{', required' if req else ''}): {desc}")
    if params:
        out.append("Parameters:\n" + "\n".join(params))
    ex = re.search(r"<RequestExample>\s*```[^\n]*\n(.*?)```", body, re.S)
    if ex:
        out.append("Example:\n```bash\n" + ex.group(1).strip() + "\n```")
    resp = re.search(r"<ResponseExample>\s*```[^\n]*\n(.*?)```", body, re.S)
    if resp and len(resp.group(1)) < 1500:
        out.append("Response:\n```json\n" + resp.group(1).strip() + "\n```")
    return "\n\n".join(out)


def main():
    nav = json.loads((ROOT / "mint.json").read_text())["navigation"]
    groups = {g["group"]: g["pages"] for g in nav}
    parts = [(ROOT / "scripts" / "llms-full.head.txt").read_text().strip()]

    parts.append("# Part 1. AI agents and the MCP server")
    for slug in AGENT_PAGES:
        meta, body = page(slug)
        parts.append(f"## {meta.get('title', slug)}\nSource: {SITE}/{slug}\n\n{demote(strip_mdx(body))}")

    parts.append("# Part 2. REST API concepts")
    for slug in CONCEPT_PAGES:
        meta, body = page(slug)
        parts.append(f"## {meta.get('title', slug)}\nSource: {SITE}/{slug}\n\n{demote(strip_mdx(body))}")

    parts.append("# Part 3. REST API reference\n\nAll resource endpoints take `POST https://api.sendforsign.com/api/<resource>` "
                 "with body `{\"data\": {\"action\": \"...\", \"clientKey\": \"...\", ...}}` and header "
                 "`X-Sendforsign-Key: YOUR_API_KEY` unless stated otherwise.")
    for g in REST_GROUPS:
        parts.append(f"## {g}")
        for slug in groups.get(g, []):
            parts.append(rest_page(slug))

    (ROOT / "llms-full.txt").write_text("\n\n".join(parts).rstrip() + "\n")
    print("llms-full.txt:", len((ROOT / "llms-full.txt").read_text()), "chars")


if __name__ == "__main__":
    main()
