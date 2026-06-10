import tiktoken


class TokenCounter:
    def __init__(self, encoding_name: str = "o200k_base") -> None:
        self.encoding_name = encoding_name
        self.encoding = tiktoken.get_encoding(encoding_name)

    def estimate_text(self, text: str | None) -> int:
        if not text:
            return 1
        return max(1, len(self.encoding.encode(text)))

    def annotate_material_index(self, material_index, page_rows: dict[int, dict]) -> None:
        def _node_tokens(node) -> int:
            total = 0
            for page_num in range(node.start_page, node.end_page + 1):
                row = page_rows.get(page_num) or {}
                total += int(row.get("token_count") or self.estimate_text(row.get("text_content")))
            node.token_count = max(1, total)
            for child in getattr(node, "nodes", []) or []:
                _node_tokens(child)
            return node.token_count

        for node in material_index.nodes:
            _node_tokens(node)
