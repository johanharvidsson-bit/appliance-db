"""One-at-a-time, append-only manual source-candidate review."""

from __future__ import annotations
from hashlib import sha256
import json
from psycopg2.extras import RealDictCursor


def decision_key(candidate_id: int, decision: str, reviewer: str, reason: str) -> str:
    return sha256(
        json.dumps(
            [candidate_id, decision, reviewer.strip(), reason.strip()],
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


class SourceReviewRepository:
    def __init__(self, connection):
        self.connection = connection

    def list(self, site, environment, limit):
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id,backlog_id,entity_type,entity_id,locale,source_type,candidate_url,publisher,title,confidence,status,created_at,updated_at FROM source_candidates WHERE site_id=%s AND environment=%s ORDER BY id LIMIT %s",
                (site, environment, limit),
            )
            return [dict(x) for x in cur.fetchall()]

    def show(self, site, environment, candidate_id):
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id,backlog_id,entity_type,entity_id,locale,source_type,candidate_url,publisher,title,confidence,status,created_at,updated_at FROM source_candidates WHERE site_id=%s AND environment=%s AND id=%s",
                (site, environment, candidate_id),
            )
            candidate = cur.fetchone()
            if not candidate:
                raise ValueError("source candidate not found in requested scope")
            cur.execute(
                "SELECT id,decision,reviewed_by,review_reason,reviewed_at FROM source_candidate_reviews WHERE source_candidate_id=%s ORDER BY reviewed_at,id",
                (candidate_id,),
            )
            return {
                "candidate": dict(candidate),
                "reviews": [dict(x) for x in cur.fetchall()],
            }

    def decide(self, site, environment, candidate_id, decision, reviewer, reason):
        details = self.show(site, environment, candidate_id)
        key = decision_key(candidate_id, decision, reviewer, reason)
        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO source_candidate_reviews(source_candidate_id,decision,reviewed_by,review_reason,decision_key) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(decision_key) DO NOTHING RETURNING id,reviewed_at",
                (candidate_id, decision, reviewer.strip(), reason.strip(), key),
            )
            row = cur.fetchone()
        return {
            "candidate_id": candidate_id,
            "previous_status": details["candidate"]["status"],
            "decision": decision,
            "created": bool(row),
            "review_id": row[0] if row else None,
        }
