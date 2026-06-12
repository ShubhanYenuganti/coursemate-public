import { describe, expect, it } from "vitest";
import { getFlashcardRatingKey } from "./FlashcardViewer";

describe("flashcard rating keys", () => {
  it("uses the stable persisted card_index instead of display position", () => {
    expect(getFlashcardRatingKey({ card_index: 42 })).toBe("42");
  });
});
