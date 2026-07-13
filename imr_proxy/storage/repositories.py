import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from imr_proxy.models.flow import FlowRecord
from imr_proxy.models.session import SessionRecord


def _dump(data: Any) -> str:
    try:
        import orjson

        return orjson.dumps(data, option=orjson.OPT_NAIVE_UTC).decode()
    except Exception:
        return json.dumps(data, default=str, ensure_ascii=False)


@dataclass(slots=True)
class FlowSearch:
    q: str | None = None
    host: str | None = None
    method: str | None = None
    status: int | None = None
    status_class: str | None = None
    severity: str | None = None
    event_type: str | None = None
    state: str | None = None
    tls: str | None = None
    has_findings: bool | None = None
    session_id: str | None = None
    min_duration: float | None = None
    max_duration: float | None = None
    since: str | None = None
    from_time: str | None = None
    to_time: str | None = None
    limit: int = 250
    offset: int = 0
    order: str = "desc"


class SessionRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, s: SessionRecord) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO sessions(id,name,version,created_at,config_snapshot) VALUES (?,?,?,?,?)",
            (s.id, s.name, s.version, s.created_at.isoformat(), _dump(s.config_snapshot)),
        )
        self.conn.commit()

    def latest_id(self) -> str | None:
        row = self.conn.execute("SELECT id FROM sessions ORDER BY created_at DESC LIMIT 1").fetchone()
        return row["id"] if row else None

    def list(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()]


class FlowRepository:
    _SUMMARY_COLUMNS = """
        id, session_id, started_at, updated_at, method, url, host,
        status_code, duration_ms, highest_severity, event_type, state,
        error_message, intercepted_tls, finding_count
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def save(self, flow: FlowRecord) -> None:
        response = flow.response
        self.conn.execute(
            """
            INSERT OR REPLACE INTO flows(
                id,session_id,started_at,updated_at,method,url,host,status_code,
                duration_ms,highest_severity,event_type,state,error_message,
                intercepted_tls,finding_count,data
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                flow.id,
                flow.session_id,
                flow.started_at.isoformat(),
                flow.updated_at.isoformat(),
                flow.request.method,
                flow.request.url,
                flow.request.host,
                response.status_code if response else None,
                flow.duration_ms,
                flow.highest_severity(),
                flow.event_type,
                flow.state,
                flow.error_message,
                int(flow.intercepted_tls),
                len(flow.findings),
                _dump(flow.model_dump(mode="json")),
            ),
        )
        self.conn.execute("DELETE FROM findings WHERE flow_id=?", (flow.id,))
        for finding in flow.findings:
            self.conn.execute(
                """
                INSERT INTO findings(flow_id,session_id,finding_id,severity,confidence,title,data)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    flow.id,
                    flow.session_id,
                    finding.id,
                    finding.severity,
                    finding.confidence,
                    finding.title,
                    _dump(finding.model_dump(mode="json")),
                ),
            )
        self.conn.commit()

    def list_by_session(self, session_id: str, limit: int | None = None) -> list[FlowRecord]:
        sql = "SELECT data FROM flows WHERE session_id=? ORDER BY started_at ASC"
        params: list[Any] = [session_id]
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        return [FlowRecord.model_validate(json.loads(row["data"])) for row in self.conn.execute(sql, params).fetchall()]

    def get(self, flow_id: str) -> FlowRecord | None:
        row = self.conn.execute("SELECT data FROM flows WHERE id=?", (flow_id,)).fetchone()
        return FlowRecord.model_validate(json.loads(row["data"])) if row else None

    @staticmethod
    def _where(search: FlowSearch) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        if search.q:
            needle = f"%{search.q.strip().lower()}%"
            clauses.append("(LOWER(url) LIKE ? OR LOWER(host) LIKE ? OR LOWER(method) LIKE ? OR LOWER(COALESCE(error_message,'')) LIKE ? OR LOWER(data) LIKE ?)")
            params.extend([needle, needle, needle, needle, needle])
        if search.host:
            clauses.append("LOWER(host) LIKE ?")
            params.append(f"%{search.host.strip().lower()}%")
        if search.method:
            clauses.append("UPPER(method)=?")
            params.append(search.method.strip().upper())
        if search.status is not None:
            clauses.append("status_code=?")
            params.append(search.status)
        if search.status_class:
            mapping = {"1xx": (100, 199), "2xx": (200, 299), "3xx": (300, 399), "4xx": (400, 499), "5xx": (500, 599)}
            bounds = mapping.get(search.status_class.lower())
            if bounds:
                clauses.append("status_code BETWEEN ? AND ?")
                params.extend(bounds)
            elif search.status_class.lower() == "none":
                clauses.append("status_code IS NULL")
        if search.severity:
            clauses.append("LOWER(highest_severity)=?")
            params.append(search.severity.lower())
        if search.event_type:
            clauses.append("LOWER(event_type)=?")
            params.append(search.event_type.lower())
        if search.state:
            clauses.append("LOWER(state)=?")
            params.append(search.state.lower())
        if search.tls == "intercepted":
            clauses.append("intercepted_tls=1")
        elif search.tls == "passthrough":
            clauses.append("intercepted_tls=0 AND (event_type IN ('connect','connection') OR LOWER(url) LIKE 'https:%' OR LOWER(url) LIKE 'tls:%')")
        elif search.tls == "http":
            clauses.append("LOWER(url) LIKE 'http:%'")
        if search.has_findings is True:
            clauses.append("finding_count>0")
        elif search.has_findings is False:
            clauses.append("finding_count=0")
        if search.session_id:
            clauses.append("session_id=?")
            params.append(search.session_id)
        if search.min_duration is not None:
            clauses.append("duration_ms>=?")
            params.append(search.min_duration)
        if search.max_duration is not None:
            clauses.append("duration_ms<=?")
            params.append(search.max_duration)
        if search.since:
            clauses.append("updated_at>?")
            params.append(search.since)
        if search.from_time:
            clauses.append("started_at>=?")
            params.append(search.from_time)
        if search.to_time:
            clauses.append("started_at<=?")
            params.append(search.to_time)

        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params

    def search(self, search: FlowSearch) -> tuple[list[dict[str, Any]], int]:
        where, params = self._where(search)
        order = "ASC" if search.order.lower() == "asc" else "DESC"
        limit = max(1, min(int(search.limit), 1000))
        offset = max(0, int(search.offset))
        total = self.conn.execute(f"SELECT COUNT(*) AS total FROM flows{where}", params).fetchone()["total"]
        rows = self.conn.execute(
            f"SELECT {self._SUMMARY_COLUMNS} FROM flows{where} ORDER BY updated_at {order}, started_at {order} LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        return [dict(row) for row in rows], int(total)

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        items, _ = self.search(FlowSearch(limit=limit))
        return items

    def filter_options(self) -> dict[str, list[Any]]:
        def values(column: str, *, limit: int = 250) -> list[Any]:
            rows = self.conn.execute(
                f"SELECT DISTINCT {column} AS value FROM flows WHERE {column} IS NOT NULL AND {column} != '' ORDER BY value LIMIT ?",
                (limit,),
            ).fetchall()
            return [row["value"] for row in rows]

        return {
            "hosts": values("host", limit=500),
            "methods": values("method"),
            "event_types": values("event_type"),
            "states": values("state"),
            "severities": values("highest_severity"),
        }

    def stats(self) -> dict[str, int]:
        row = self.conn.execute(
            """
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN highest_severity IN ('critical','high') THEN 1 ELSE 0 END) AS high_risk,
              SUM(CASE WHEN state='pending' THEN 1 ELSE 0 END) AS pending,
              SUM(CASE WHEN state='error' THEN 1 ELSE 0 END) AS errors,
              SUM(CASE WHEN event_type='connect' THEN 1 ELSE 0 END) AS connects
            FROM flows
            """
        ).fetchone()
        return {key: int(row[key] or 0) for key in row.keys()}
