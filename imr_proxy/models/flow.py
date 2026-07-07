from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field
from .finding import Finding
class RequestRecord(BaseModel):
    method: str
    url: str
    scheme: str=""
    host: str=""
    port: int|None=None
    path: str=""
    query: str=""
    headers: dict[str,str]=Field(default_factory=dict)
    cookies: dict[str,str]=Field(default_factory=dict)
    body_text: str|None=None
    body_size: int=0
    is_binary: bool=False
class ResponseRecord(BaseModel):
    status_code: int|None=None
    reason: str=""
    headers: dict[str,str]=Field(default_factory=dict)
    cookies: dict[str,str]=Field(default_factory=dict)
    set_cookies: list[str]=Field(default_factory=list)
    body_text: str|None=None
    body_size: int=0
    is_binary: bool=False
class FlowRecord(BaseModel):
    id: str
    session_id: str
    started_at: datetime=Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float|None=None
    request: RequestRecord
    response: ResponseRecord|None=None
    redirect_to: str|None=None
    intercepted_tls: bool=False
    tls_metadata: dict[str,Any]=Field(default_factory=dict)
    findings: list[Finding]=Field(default_factory=list)
    tags: list[str]=Field(default_factory=list)
    def highest_severity(self)->str:
        return max(self.findings, key=lambda f:f.rank).severity if self.findings else "info"
