"""
models.py - Domain models for the Enterprise Risk Intelligence Assistant.
Implements data structures for RBAC, ABAC, Guardrails, Retrieval, Audit, and HITL.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class RoleEnum(str, Enum):
    RISK_ANALYST = "Risk_Analyst"
    RISK_MANAGER = "Risk_Manager"
    COMPLIANCE_ANALYST = "Compliance_Analyst"
    AUDITOR = "Auditor"
    ADMINISTRATOR = "Administrator"


class ClassificationEnum(str, Enum):
    PUBLIC = "Public"
    INTERNAL = "Internal"
    CONFIDENTIAL = "Confidential"
    RESTRICTED = "Restricted"


class User(BaseModel):
    user_id: str
    name: str
    role: RoleEnum
    business_unit: str
    region: str
    clearance_level: ClassificationEnum = ClassificationEnum.INTERNAL
    entitlements: List[str] = Field(default_factory=list)

    class Config:
        use_enum_values = True


class DocumentMetadata(BaseModel):
    doc_id: str
    title: str
    category: str  # Risk Policy, Risk Appetite, Control, Audit Finding, OpRisk Incident, Regulatory, Risk Assessment
    business_unit: str
    region: str
    classification: ClassificationEnum
    allowed_roles: List[RoleEnum]
    need_to_know: List[str] = Field(default_factory=list)
    content: str
    summary: str
    version: str = "1.0"
    effective_date: str = "2025-01-01"
    owner: str = "Enterprise Risk Governance"

    class Config:
        use_enum_values = True


class InputGuardrailResult(BaseModel):
    passed: bool
    direct_injection_detected: bool = False
    pii_detected: bool = False
    original_query: str
    masked_query: str
    detected_pii_entities: List[str] = Field(default_factory=list)
    injection_score: float = 0.0
    threat_category: Optional[str] = None
    rejection_reason: Optional[str] = None


class RetrievedDocument(BaseModel):
    doc_id: str
    title: str
    category: str
    business_unit: str
    region: str
    classification: str
    vector_score: float
    keyword_score: float
    combined_score: float
    snippet: str
    full_content: str
    summary: str = ""


class OutputGuardrailResult(BaseModel):
    passed: bool
    grounding_score: float
    citations_valid: bool
    validated_citations: List[str] = Field(default_factory=list)
    hallucinated_citations: List[str] = Field(default_factory=list)
    pii_sanitized: bool = True
    advisory_policy_passed: bool = True
    abstention_triggered: bool = False
    abstention_reason: Optional[str] = None
    flags: List[str] = Field(default_factory=list)


class PipelineTelemetry(BaseModel):
    step_1_identity_and_abac: Dict[str, Any]
    step_2_input_guardrails: Dict[str, Any]
    step_3_hybrid_retrieval: Dict[str, Any]
    step_4_reranking: Dict[str, Any]
    step_5_llm_synthesis: Dict[str, Any]
    step_6_output_guardrails: Dict[str, Any]
    step_7_audit_logged: Dict[str, Any]


class ChatRequest(BaseModel):
    user_id: str
    query: str
    conversation_id: Optional[str] = None
    temperature: float = 0.2


class ChatResponse(BaseModel):
    request_id: str
    response_id: str
    query_masked: str
    response_text: str
    citations: List[str] = Field(default_factory=list)
    retrieved_documents: List[RetrievedDocument] = Field(default_factory=list)
    confidence_score: float = 0.0
    grounding_score: float = 0.0
    abstention: bool = False
    guardrail_status: Dict[str, Any] = Field(default_factory=dict)
    telemetry: PipelineTelemetry
    hitl_item_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class AuditLogEntry(BaseModel):
    log_id: str
    request_id: str
    timestamp: str
    user_id: str
    user_role: str
    business_unit: str
    region: str
    query_masked: str
    retrieved_doc_ids: List[str]
    confidence_score: float
    grounding_score: float
    guardrail_results: Dict[str, Any]
    approval_status: str  # "Pending Review", "Approved", "Amended", "Rejected", "Auto-Verified"
    model_version: str = "Enterprise-Risk-LLM-v2.4"
    tamper_hash: str


class HITLReviewItem(BaseModel):
    item_id: str
    request_id: str
    timestamp: str
    user_id: str
    user_role: str
    query: str
    draft_response: str
    final_response: Optional[str] = None
    citations: List[str] = Field(default_factory=list)
    severity_level: str  # "Low", "Medium", "High", "Critical"
    status: str  # "Pending Review", "Approved", "Amended", "Rejected"
    reviewed_by: Optional[str] = None
    analyst_notes: Optional[str] = None
    reviewed_at: Optional[str] = None


class HITLReviewRequest(BaseModel):
    item_id: str
    action: str  # "approve", "amend", "reject"
    reviewer_id: str
    analyst_notes: str
    amended_text: Optional[str] = None
