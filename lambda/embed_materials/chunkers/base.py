from dataclasses import dataclass, field


@dataclass
class ChunkSpec:
    text: str
    visual_page: int        # 0-based page index for visual embedding
    chunk_index: int
    modal_meta: dict = field(default_factory=dict)
    problem_id: str = None
