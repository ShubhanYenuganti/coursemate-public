"""
RAG retrieval — hybrid dual-embedding search with parent-filter re-ranking.

Embeddings are computed by invoking the embed_query Lambda (no voyageai in Vercel).
Required environment variables:
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

TOP_K = 8


def _invoke_embed_query(query: str = None, image_base64: str = None):
    """Invoke the embed_query Lambda and return (vis_emb, txt_emb).

    Pass either query (text path) or image_base64 (image path).
    Image path returns (vis_emb, vis_emb) — same vector used for both slots.
    """
    import json
    import boto3

    region = os.environ.get('AWS_REGION', 'us-east-1')
    client = boto3.client(
        'lambda',
        region_name=region,
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
    )

    if image_base64:
        payload = json.dumps({'image_base64': image_base64})
    else:
        payload = json.dumps({'query': query})
    response = client.invoke(
        FunctionName='embed_query',
        InvocationType='RequestResponse',
        Payload=payload,
    )

    raw = response['Payload'].read()
    result = json.loads(raw)

    if response.get('FunctionError'):
        raise RuntimeError(f"Lambda function error: {result}")

    if 'body' in result:
        body = json.loads(result['body']) if isinstance(result['body'], str) else result['body']
    else:
        body = result

    if 'error' in body:
        import logging
        logging.getLogger(__name__).error(
            "embed_query Lambda returned an error: %s", body['error']
        )
        return None, None

    vis_emb = body.get('visual_embedding')
    txt_emb = body.get('text_embedding') or body.get('embedding')

    if not vis_emb and not txt_emb:
        import logging
        logging.getLogger(__name__).warning(
            "embed_query Lambda response missing embedding keys. Got keys: %s.",
            list(body.keys()),
        )
        return None, None

    # Image-only path returns visual_embedding only — reuse it for the text slot
    return vis_emb, txt_emb or vis_emb


def _search_chat_images(conn, emb: list, chat_id: int, exclude_message_id: int = None) -> list:
    """Fetch all chat_image_embeddings for chat_id and rank by cosine similarity to emb.
    Excludes rows from exclude_message_id to prevent self-matches on the current message."""
    import math
    if not emb or not chat_id:
        return []
    cursor = conn.cursor()
    if exclude_message_id is not None:
        cursor.execute(
            "SELECT s3_key, filename, embedding::text FROM chat_image_embeddings"
            " WHERE chat_id = %s AND message_id != %s",
            (chat_id, exclude_message_id),
        )
    else:
        cursor.execute(
            "SELECT s3_key, filename, embedding::text FROM chat_image_embeddings WHERE chat_id = %s",
            (chat_id,),
        )
    rows = cursor.fetchall()
    cursor.close()

    norm_q = math.sqrt(sum(x * x for x in emb))
    if norm_q == 0:
        return []

    results = []
    for s3_key, filename, emb_raw in rows:
        try:
            stored = [float(x) for x in emb_raw.strip('[]').split(',')]
            dot = sum(a * b for a, b in zip(emb, stored))
            norm_s = math.sqrt(sum(x * x for x in stored))
            sim = dot / (norm_q * norm_s) if norm_s > 0 else 0.0
            results.append({
                's3_key': s3_key,
                'filename': filename,
                'chunk_type': 'chat_image',
                'similarity': min(1.0, sim + 0.20),
            })
        except Exception:
            continue
    return results


def retrieve_chunks(conn, query: str, material_ids: list, top_k: int = TOP_K,
                    chat_id: int = None, image_s3_keys: list = None,
                    current_message_id: int = None) -> list:
    """
    Hybrid dual-embedding search over the `chunks` table filtered to `material_ids`.

    - Text query: embedded via Lambda for dual (visual + text) hybrid search.
    - Attached images: each image is embedded and run as an additional visual search
      pass; results are merged with the text search pool before the top-K slice.
    - Chat image history: searched by cosine similarity, excluding the current
      message's images to avoid self-matches (current_message_id).

    Returns dicts compatible with api/llm.py _format_context(). Chat image rows
    carry chunk_type='chat_image' with s3_key and filename instead of chunk_text.
    """
    if not material_ids and not chat_id:
        return []

    import base64
    import logging
    import urllib.request
    from services.query.retrieval import hybrid_vector_search
    try:
        from .s3_utils import generate_download_presigned_url
    except ImportError:
        from s3_utils import generate_download_presigned_url

    log = logging.getLogger(__name__)
    has_query = bool(query and query.strip())

    if not has_query and not image_s3_keys:
        return []

    # --- Compute embeddings ---
    text_vis_emb = text_txt_emb = None
    if has_query:
        text_vis_emb, text_txt_emb = _invoke_embed_query(query=query)
        if text_txt_emb is None:
            log.error("embed_query Lambda returned no usable embeddings — skipping text search")

    image_vis_embs = []
    for s3_key in (image_s3_keys or []):
        try:
            url = generate_download_presigned_url(s3_key)
            with urllib.request.urlopen(url) as resp:
                img_bytes = resp.read()
            img_vis, _ = _invoke_embed_query(image_base64=base64.b64encode(img_bytes).decode())
            if img_vis:
                image_vis_embs.append(img_vis)
        except Exception:
            log.exception("Failed to embed image %s for retrieval", s3_key)

    # --- Material chunk search ---
    all_rows = []
    if material_ids:
        if text_txt_emb is not None:
            ctx, _ = hybrid_vector_search(
                conn, text_vis_emb or text_txt_emb, text_txt_emb,
                top_k=top_k, material_ids=material_ids,
            )
            all_rows.extend(ctx)

        for img_vis in image_vis_embs:
            ctx, _ = hybrid_vector_search(
                conn, img_vis, img_vis,
                top_k=top_k, material_ids=material_ids,
            )
            all_rows.extend(ctx)

    # Dedupe by chunk id, keep highest similarity, re-sort, take top-K
    seen: dict = {}
    for row in all_rows:
        rid = str(row['id'])
        if rid not in seen or row.get('similarity', 0) > seen[rid].get('similarity', 0):
            seen[rid] = row
    context = sorted(seen.values(), key=lambda r: r.get('similarity', 0), reverse=True)[:top_k]

    # --- Chat image history search ---
    query_emb_for_chat = text_vis_emb or (image_vis_embs[0] if image_vis_embs else None)
    if chat_id and query_emb_for_chat:
        chat_chunks = _search_chat_images(
            conn, query_emb_for_chat, chat_id, exclude_message_id=current_message_id,
        )
        context = context + chat_chunks

    return context
