from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field
from imr_proxy.constants import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_WEB_HOST, DEFAULT_WEB_PORT, DEFAULT_MAX_BODY_SIZE
RedactionLevel=Literal["strict","balanced","off"]
CertMode=Literal["local-ca","mkcert","passthrough"]
class AppConfig(BaseModel):
    host: str=DEFAULT_HOST
    port: int=Field(DEFAULT_PORT, ge=1, le=65535)
    web: bool=True
    web_host: str=DEFAULT_WEB_HOST
    web_port: int=Field(DEFAULT_WEB_PORT, ge=1, le=65535)
    terminal: bool=False
    quiet: bool=False
    verbose: bool=False
    allow_remote: bool=False
    scope: list[str]=Field(default_factory=list)
    exclude: list[str]=Field(default_factory=list)
    upstream_proxy: str|None=None
    proxy_auth: str|None=None
    intercept_https: bool=False
    tls_passthrough: bool=True
    ca_dir: Path|None=None
    cert_mode: CertMode="passthrough"
    storage: Path|None=None
    session_name: str="default"
    max_body_size: int=Field(DEFAULT_MAX_BODY_SIZE, ge=0)
    capture_bodies: bool=True
    redaction_level: RedactionLevel="balanced"
    no_color: bool=False
    jsonl: bool=False
    config: Path|None=None
    def effective_tls_passthrough(self)->bool:
        return self.tls_passthrough or not self.intercept_https or self.cert_mode=="passthrough"
