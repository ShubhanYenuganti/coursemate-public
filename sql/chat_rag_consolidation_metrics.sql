-- Baseline and soak metrics for chat + RAG consolidation.
-- Run in psql against the production/staging database.

-- 1) Conversation writes/day by table.
SELECT date_trunc('day', created_at) AS day, COUNT(*) AS chat_messages_writes
FROM chat_messages
GROUP BY 1
ORDER BY 1 DESC
LIMIT 30;

SELECT date_trunc('day', created_at) AS day, COUNT(*) AS messages_writes
FROM messages
GROUP BY 1
ORDER BY 1 DESC
LIMIT 30;

-- 2) chat_messages embedding completeness (non-deleted user/assistant rows).
SELECT
    role,
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (WHERE message_embedding IS NOT NULL) AS with_embedding,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE message_embedding IS NOT NULL) / NULLIF(COUNT(*), 0),
        2
    ) AS pct_with_embedding
FROM chat_messages
WHERE is_deleted = FALSE
  AND role IN ('user', 'assistant')
GROUP BY role
ORDER BY role;

-- 3) Legacy retrieval fallback readiness:
-- material coverage in new documents/chunks pipeline.
SELECT
    COUNT(DISTINCT m.id) AS total_materials,
    COUNT(DISTINCT d.material_id) AS materials_with_documents,
    COUNT(DISTINCT d.material_id) FILTER (WHERE c.id IS NOT NULL) AS materials_with_chunks
FROM materials m
LEFT JOIN documents d ON d.material_id = m.id
LEFT JOIN chunks c ON c.document_id = d.id;

-- 4) Pre-drop safety check for legacy tables.
SELECT
    (SELECT COUNT(*) FROM messages) AS legacy_messages_rows,
    (SELECT COUNT(*) FROM material_chunks) AS legacy_material_chunks_rows;
