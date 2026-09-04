"""
server.py - FastAPI Application Server for the Enterprise Risk Intelligence Assistant.
Orchestrates the 7-step pipeline from authentication and pre-retrieval ABAC to LLM synthesis,
output guardrails, immutable audit logging, and human-in-the-loop workflows.
"""

import os
import uuid
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.models import (
    ChatRequest, ChatResponse, PipelineTelemetry,
    HITLReviewRequest, RoleEnum, ClassificationEnum, User
)
from backend.knowledge_base import DOCUMENTS, PERSONAS
from backend.auth_abac import filter_documents_pre_retrieval, get_document_access_matrix
from backend.guardrails import (
    InputGuardrailEngine, OutputGuardrailEngine, SAFE_ABSTENTION_MESSAGE
)
from backend.retrieval import HybridRetriever
from backend.llm_engine import LLMEngine
from backend.audit_logger import audit_logger
from backend.hitl_service import hitl_service


app = FastAPI(
    title="Enterprise Risk Intelligence Assistant (ERM)",
    description="Regulated GenAI Assistant for Enterprise Risk Management, Controls, and Compliance.",
    version="2.4.0"
)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

retriever = HybridRetriever()
llm_engine = LLMEngine()


def resolve_user(user_id_or_key: str) -> User:
    """Helper to resolve user from ID or persona key"""
    if user_id_or_key in PERSONAS:
        return PERSONAS[user_id_or_key]
    for p in PERSONAS.values():
        if p.user_id == user_id_or_key:
            return p
    # Default to Risk Analyst if unknown
    return PERSONAS["risk_analyst"]


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Enterprise Risk Intelligence Assistant",
        "version": "2.4.0",
        "security_profile": "Banking / High-Assurance (RBAC+ABAC Pre-Retrieval)"
    }


@app.get("/api/personas")
def get_personas():
    """Returns available pre-configured enterprise personas for switching"""
    return [
        {
            "id": key,
            "user_id": u.user_id,
            "name": u.name,
            "role": u.role.value if hasattr(u.role, 'value') else str(u.role),
            "business_unit": u.business_unit,
            "region": u.region,
            "clearance_level": u.clearance_level.value if hasattr(u.clearance_level, 'value') else str(u.clearance_level),
            "entitlements": u.entitlements
        }
        for key, u in PERSONAS.items()
    ]


@app.get("/api/documents")
def get_documents_matrix(user_id: str = Query(default="risk_analyst")):
    """Returns the document catalog with real-time ABAC authorization status for the selected user"""
    user = resolve_user(user_id)
    matrix = get_document_access_matrix(user, DOCUMENTS)
    authorized_count = sum(1 for d in matrix if d["is_authorized"])
    return {
        "user": {
            "name": user.name,
            "role": user.role,
            "business_unit": user.business_unit,
            "region": user.region,
            "clearance": user.clearance_level
        },
        "stats": {
            "total_documents": len(matrix),
            "authorized_count": authorized_count,
            "restricted_count": len(matrix) - authorized_count
        },
        "documents": matrix
    }


@app.post("/api/chat", response_model=ChatResponse)
def handle_chat_query(req: ChatRequest):
    """
    Core End-to-End Pipeline Execution:
    1. Authentication & ABAC Pre-Retrieval Filtering
    2. Input Guardrails & PII Masking
    3. Hybrid Retrieval (Vector + Keyword)
    4. Reranking & Score Fusion
    5. Sandboxed LLM Synthesis
    6. Output Guardrails (Grounding, Citations, PII)
    7. Tamper-Evident Audit Logging & HITL Queue
    """
    request_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"
    response_id = f"RESP-{uuid.uuid4().hex[:8].upper()}"
    user = resolve_user(req.user_id)

    # -------------------------------------------------------------
    # STEP 1: Authentication & Pre-Retrieval ABAC Filtering
    # -------------------------------------------------------------
    authorized_docs, abac_telemetry = filter_documents_pre_retrieval(user, DOCUMENTS)
    step1_telemetry = {
        "user_id": user.user_id,
        "role": user.role,
        "business_unit": user.business_unit,
        "region": user.region,
        "clearance_level": user.clearance_level,
        "vault_total": abac_telemetry["total_documents_in_vault"],
        "authorized_count": abac_telemetry["authorized_count"],
        "restricted_count": abac_telemetry["restricted_count"],
        "authorized_doc_ids": abac_telemetry["authorized_doc_ids"]
    }

    # -------------------------------------------------------------
    # STEP 2: Input Guardrails & Direct Injection Check
    # -------------------------------------------------------------
    input_guard = InputGuardrailEngine.inspect_and_sanitize(req.query)
    step2_telemetry = {
        "passed": input_guard.passed,
        "direct_injection_detected": input_guard.direct_injection_detected,
        "threat_category": input_guard.threat_category,
        "pii_detected": input_guard.pii_detected,
        "detected_pii_entities": input_guard.detected_pii_entities,
        "original_query_length": len(req.query),
        "masked_query": input_guard.masked_query
    }

    # Intercept immediate threat if direct injection is detected
    if not input_guard.passed:
        rejection_msg = (
            f"⚠️ **Security Guardrail Alert**: Your query was intercepted and rejected by the Enterprise API Gateway.\n\n"
            f"**Violation Type:** {input_guard.threat_category}\n"
            f"**Reason:** {input_guard.rejection_reason}\n\n"
            f"This incident has been securely recorded in the immutable compliance audit ledger."
        )
        
        # Log security rejection in audit trail
        audit_entry = audit_logger.log_query_event(
            request_id=request_id,
            user_id=user.user_id,
            user_role=str(user.role),
            business_unit=user.business_unit,
            region=user.region,
            query_masked=input_guard.masked_query,
            retrieved_doc_ids=[],
            confidence_score=0.0,
            grounding_score=0.0,
            guardrail_results={"input_guardrail": step2_telemetry, "status": "REJECTED_INPUT_GUARDRAIL"},
            approval_status="Rejected (Security Violation)"
        )

        telemetry = PipelineTelemetry(
            step_1_identity_and_abac=step1_telemetry,
            step_2_input_guardrails=step2_telemetry,
            step_3_hybrid_retrieval={"status": "BYPASSED_SECURITY_INTERCEPTION"},
            step_4_reranking={"status": "BYPASSED_SECURITY_INTERCEPTION"},
            step_5_llm_synthesis={"status": "BYPASSED_SECURITY_INTERCEPTION"},
            step_6_output_guardrails={"status": "BYPASSED_SECURITY_INTERCEPTION"},
            step_7_audit_logged={"log_id": audit_entry.log_id, "status": "Security Violation Logged", "tamper_hash": audit_entry.tamper_hash}
        )

        return ChatResponse(
            request_id=request_id,
            response_id=response_id,
            query_masked=input_guard.masked_query,
            response_text=rejection_msg,
            citations=[],
            retrieved_documents=[],
            confidence_score=0.0,
            grounding_score=0.0,
            abstention=False,
            guardrail_status={"input_passed": False, "violation": input_guard.threat_category},
            telemetry=telemetry
        )

    # -------------------------------------------------------------
    # STEP 3 & 4: Hybrid Retrieval & Reranking (Over Authorized Docs ONLY)
    # -------------------------------------------------------------
    retrieved_docs, retrieval_telemetry = retriever.search(
        query=input_guard.masked_query,
        authorized_documents=authorized_docs,
        top_k=3
    )

    step3_telemetry = {
        "search_space_scope": "Pre-filtered Authorized Documents Only",
        "search_space_size": retrieval_telemetry["search_space_size"],
        "retrieved_count": len(retrieved_docs),
        "vector_scores": retrieval_telemetry.get("vector_scores", []),
        "keyword_scores": retrieval_telemetry.get("keyword_scores", [])
    }

    step4_telemetry = {
        "algorithm": "Reciprocal Rank Fusion (RRF) + Normalized Weighted Blend",
        "combined_scores": retrieval_telemetry.get("combined_scores", []),
        "confidence_max": retrieval_telemetry.get("confidence_max", 0.0),
        "selected_doc_ids": [d.doc_id for d in retrieved_docs]
    }

    # -------------------------------------------------------------
    # STEP 5 & 6: Sandboxed LLM Synthesis & Output Guardrails
    # -------------------------------------------------------------
    final_text, citations, conf_score, ground_score, abstention, output_guard_dict = llm_engine.synthesize_response(
        query=input_guard.masked_query,
        retrieved_documents=retrieved_docs,
        user=user,
        top_confidence=retrieval_telemetry.get("confidence_max", 0.0)
    )

    step5_telemetry = {
        "model_version": llm_engine.model_version,
        "data_instruction_separation": "Strict XML Sandboxing Active",
        "indirect_injection_neutralized": output_guard_dict.get("indirect_injection_neutralized", False),
        "temperature": req.temperature
    }

    step6_telemetry = {
        "output_passed": output_guard_dict.get("passed", True),
        "grounding_score": ground_score,
        "citations_valid": output_guard_dict.get("citations_valid", True),
        "validated_citations": citations,
        "hallucinated_citations": output_guard_dict.get("hallucinated_citations", []),
        "abstention_enforced": abstention,
        "flags": output_guard_dict.get("flags", [])
    }

    # -------------------------------------------------------------
    # STEP 7: Immutable Cryptographic Audit Logging & HITL Queue
    # -------------------------------------------------------------
    initial_status = "Auto-Verified" if abstention else "Pending Review"
    audit_entry = audit_logger.log_query_event(
        request_id=request_id,
        user_id=user.user_id,
        user_role=str(user.role),
        business_unit=user.business_unit,
        region=user.region,
        query_masked=input_guard.masked_query,
        retrieved_doc_ids=[d.doc_id for d in retrieved_docs],
        confidence_score=conf_score,
        grounding_score=ground_score,
        guardrail_results={
            "input": step2_telemetry,
            "output": step6_telemetry
        },
        approval_status=initial_status,
        model_version=llm_engine.model_version
    )

    step7_telemetry = {
        "log_id": audit_entry.log_id,
        "tamper_evident_sha256": audit_entry.tamper_hash,
        "approval_status": initial_status,
        "data_retention_policy": "Banking Standard 7-Year Immutable WORM"
    }

    # If actionable assessment was generated, create Human-in-the-Loop review item
    hitl_item_id = None
    if not abstention and len(retrieved_docs) > 0:
        severity = "High" if any(d.classification == "Restricted" or d.category == "Audit Finding" for d in retrieved_docs) else "Medium"
        hitl_item = hitl_service.create_review_item(
            request_id=request_id,
            user_id=user.user_id,
            user_role=str(user.role),
            query=input_guard.masked_query,
            draft_response=final_text,
            citations=citations,
            severity_level=severity
        )
        hitl_item_id = hitl_item.item_id

    telemetry = PipelineTelemetry(
        step_1_identity_and_abac=step1_telemetry,
        step_2_input_guardrails=step2_telemetry,
        step_3_hybrid_retrieval=step3_telemetry,
        step_4_reranking=step4_telemetry,
        step_5_llm_synthesis=step5_telemetry,
        step_6_output_guardrails=step6_telemetry,
        step_7_audit_logged=step7_telemetry
    )

    return ChatResponse(
        request_id=request_id,
        response_id=response_id,
        query_masked=input_guard.masked_query,
        response_text=final_text,
        citations=citations,
        retrieved_documents=retrieved_docs,
        confidence_score=conf_score,
        grounding_score=ground_score,
        abstention=abstention,
        guardrail_status={
            "input_passed": input_guard.passed,
            "output_passed": output_guard_dict.get("passed", True),
            "pii_masked": input_guard.pii_detected,
            "indirect_injection_neutralized": output_guard_dict.get("indirect_injection_neutralized", False)
        },
        telemetry=telemetry,
        hitl_item_id=hitl_item_id
    )


@app.get("/api/audit-logs")
def get_audit_logs(
    user_id: Optional[str] = None,
    role: Optional[str] = None,
    limit: int = 50
):
    """Retrieves immutable audit logs and returns integrity verification status"""
    logs = audit_logger.get_logs(user_id=user_id, role=role, limit=limit)
    integrity_check = audit_logger.verify_chain_integrity()
    return {
        "integrity": integrity_check,
        "total_records": len(logs),
        "logs": logs
    }


@app.get("/api/hitl/queue")
def get_hitl_queue(status: Optional[str] = None):
    """Returns items in the Human-in-the-Loop review queue"""
    items = hitl_service.list_items(status=status)
    return {
        "count": len(items),
        "items": items
    }


@app.post("/api/hitl/review")
def review_hitl_item(req: HITLReviewRequest):
    """Processes Risk Analyst sign-off (Approve, Amend, Reject)"""
    updated_item = hitl_service.process_review(req)
    if not updated_item:
        raise HTTPException(status_code=404, detail="HITL Review Item not found")
    return {
        "status": "success",
        "item": updated_item,
        "message": f"Review action '{req.action}' successfully registered and stamped in audit ledger."
    }


class ApiKeyRequest(BaseModel):
    provider: str  # "gemini" or "openai"
    api_key: str


@app.post("/api/settings/keys")
def configure_api_keys(req: ApiKeyRequest):
    """Allows user to dynamically connect an external model key with pre-transmission sanitization"""
    if req.provider.lower() == "gemini":
        llm_engine.gemini_key = req.api_key
        os.environ["GEMINI_API_KEY"] = req.api_key
        llm_engine.model_version = "Gemini-1.5-Flash (Pre-Sanitized Hybrid RAG)"
        return {"status": "configured", "provider": "Gemini 1.5 Flash"}
    elif req.provider.lower() == "openai":
        llm_engine.openai_key = req.api_key
        os.environ["OPENAI_API_KEY"] = req.api_key
        llm_engine.model_version = "GPT-4o (Pre-Sanitized Hybrid RAG)"
        return {"status": "configured", "provider": "OpenAI GPT-4o"}
    else:
        raise HTTPException(status_code=400, detail="Unsupported provider. Use 'gemini' or 'openai'.")


# Mount static frontend files
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
