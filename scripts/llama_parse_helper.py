#!/usr/bin/env python3
"""
Document parsing helper supporting both:
1. LiteParse: Fast, zero-credit, 100% local PDF spatial parser (open-source)
2. LlamaCloud / LlamaParse: Agentic cloud parser for complex documents & tables
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DEFAULT_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY", "llx-AVMBvb0UULqQGzWhFFJScQpwhrTM8hSVMZvjz4PEGQ9utg1P")

def parse_with_liteparse(file_path: str) -> str:
    """Parse PDF locally using LiteParse without using any API credits."""
    from liteparse import LiteParse
    parser = LiteParse()
    parsed_doc = parser.parse(file_path)
    # Extract markdown or text representation
    if hasattr(parsed_doc, "text"):
        return parsed_doc.text
    elif hasattr(parsed_doc, "pages"):
        return "\n\n--- Page Break ---\n\n".join(
            getattr(page, "text", str(page)) for page in parsed_doc.pages
        )
    return str(parsed_doc)

def parse_with_llamacloud(file_path: str, tier: str = "agentic", version: str = "latest", api_key: str = None) -> str:
    """Parse document remotely using LlamaCloud / LlamaParse."""
    from llama_cloud import LlamaCloud
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    client = LlamaCloud(api_key=api_key or DEFAULT_API_KEY)
    with open(path, "rb") as f:
        file_obj = client.files.create(file=f, purpose="parse")

    result = client.parsing.parse(
        file_id=file_obj.id,
        tier=tier,
        version=version,
        expand=["markdown_full"],
    )
    return getattr(result, "markdown_full", "")

def parse_document(file_path: str, mode: str = "lite", api_key: str = None) -> str:
    """
    Parse document using either 'lite' (local LiteParse) or 'agentic'/'cloud' (LlamaCloud).
    """
    if mode == "lite":
        return parse_with_liteparse(file_path)
    return parse_with_llamacloud(file_path, tier=mode, api_key=api_key)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python llama_parse_helper.py <path_to_pdf> [--cloud|--lite]")
        sys.exit(1)
    
    target_file = sys.argv[1]
    target_mode = "agentic" if "--cloud" in sys.argv else "lite"
    
    output = parse_document(target_file, mode=target_mode)
    print(output)
