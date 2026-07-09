from typing import Literal
from pydantic import BaseModel, Field
Severity=Literal["info","low","medium","high","critical"]
Confidence=Literal["low","medium","high"]
class Finding(BaseModel):
    id: str
    title: str
    severity: Severity="info"
    confidence: Confidence="medium"
    affected_ids: list[str]=Field(default_factory=list)
    evidence: str=""
    explanation: str=""
    impact: str=""
    safe_validation: str="Review the affected request/response in an authorized test environment."
    remediation: str=""
    references: list[str]=Field(default_factory=list)
    false_positive_notes: str=""
    @property
    def rank(self)->int:
        return {"info":0,"low":1,"medium":2,"high":3,"critical":4}[self.severity]
