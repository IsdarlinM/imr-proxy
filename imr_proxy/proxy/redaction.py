import re
from typing import Any, Literal
RedactionLevel=Literal["strict","balanced","off"]
SENSITIVE_NAME_RE=re.compile(r"(authorization|cookie|set-cookie|x-api-key|api-key|token|access_token|refresh_token|id_token|password|passwd|secret|client_secret|session|jwt|bearer|basic)", re.I)
JWT_RE=re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
BEARER_RE=re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I)
BASIC_RE=re.compile(r"\bBasic\s+[A-Za-z0-9+/=]{12,}", re.I)
CARD_RE=re.compile(r"\b(?:\d[ -]*?){13,19}\b")
EMAIL_RE=re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
QUERY_RE=re.compile(r"(?i)([?&][^=]*(?:token|key|secret|password|session|jwt)[^=]*=)([^&#\s]+)")
def mask(value: Any, level: RedactionLevel="balanced")->str:
    text="" if value is None else str(value)
    if level=="off": return text
    return "[REDACTED]" if level=="strict" or len(text)<=8 else f"{text[:4]}…{text[-4:]}"
def redact_text(text: str|None, level: RedactionLevel="balanced")->str|None:
    if text is None or level=="off": return text
    out=JWT_RE.sub("[REDACTED_JWT]", text)
    out=BEARER_RE.sub("Bearer [REDACTED]", out)
    out=BASIC_RE.sub("Basic [REDACTED]", out)
    out=CARD_RE.sub("[REDACTED_CARD]", out)
    out=QUERY_RE.sub(lambda m:m.group(1)+mask(m.group(2), level), out)
    return EMAIL_RE.sub("[REDACTED_EMAIL]", out) if level=="strict" else out
def redact_value(name: str, value: Any, level: RedactionLevel="balanced")->str:
    text="" if value is None else str(value)
    return text if level=="off" else (mask(text, level) if SENSITIVE_NAME_RE.search(name) else (redact_text(text, level) or ""))
def redact_headers(headers, level: RedactionLevel="balanced")->dict[str,str]:
    return {str(k):redact_value(str(k),v,level) for k,v in dict(headers).items()}
def redact_cookies(cookies, level: RedactionLevel="balanced")->dict[str,str]:
    return {str(k):redact_value(str(k),v,level) for k,v in dict(cookies).items()}
def redact_url(url: str|None, level: RedactionLevel="balanced")->str|None:
    if url is None or level=="off": return url
    return QUERY_RE.sub(lambda m:m.group(1)+mask(m.group(2), level), url)
