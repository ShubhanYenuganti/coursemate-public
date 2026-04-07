# Provider-agnostic entry point for exporting study material content to block-based formats.
# Import the relevant provider module to get provider-specific block builders.

try:
    from .providers import notion as notion_provider
except ImportError:
    from providers import notion as notion_provider


def flashcard_to_notion_toggle_block(card):
    """Convert a flashcard dict to a Notion toggle block."""
    return notion_provider.flashcard_to_toggle_block(card)


def quiz_to_notion_blocks(questions):
    """Convert a list of quiz question dicts to a list of Notion blocks."""
    return notion_provider.quiz_to_blocks(questions)


def report_to_notion_blocks(sections):
    """Convert a list of report section dicts to a list of Notion blocks."""
    return notion_provider.report_to_blocks(sections)
