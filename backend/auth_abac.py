"""
auth_abac.py - Pre-Retrieval RBAC + ABAC Authorization Engine.
CRITICAL ENTERPRISE FEATURE: Enforces access control BEFORE vector/keyword retrieval,
ensuring the LLM never sees or processes unauthorized enterprise risk documents.
"""

from typing import List, Tuple, Dict, Any
from backend.models import User, DocumentMetadata, ClassificationEnum, RoleEnum


CLASSIFICATION_HIERARCHY = {
    ClassificationEnum.PUBLIC.value: 1,
    ClassificationEnum.INTERNAL.value: 2,
    ClassificationEnum.CONFIDENTIAL.value: 3,
    ClassificationEnum.RESTRICTED.value: 4,
}


def evaluate_document_access(user: User, doc: DocumentMetadata) -> Tuple[bool, str]:
    """
    Evaluates comprehensive RBAC + ABAC + Entitlement policy for a user against a document.
    Returns: (is_authorized: bool, policy_reason: str)
    """
    # 1. Administrator Persona Rule
    # Admins manage system operations and audit trails, but do not have clearance
    # to browse confidential enterprise risk files unless specifically permitted.
    if user.role == RoleEnum.ADMINISTRATOR:
        if doc.classification in [ClassificationEnum.CONFIDENTIAL, ClassificationEnum.RESTRICTED]:
            return False, "Access Denied: Administrator role is restricted from accessing confidential risk content."
        return True, "Authorized: System administrative overview."

    # 2. RBAC: Role-Based Check
    allowed_roles_str = [r.value if hasattr(r, 'value') else str(r) for r in doc.allowed_roles]
    user_role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
    if user_role_str not in allowed_roles_str:
        return False, f"RBAC Denied: Role '{user_role_str}' not in allowed roles: {allowed_roles_str}"

    # 3. ABAC: Clearance Level vs Document Classification
    user_clearance = user.clearance_level.value if hasattr(user.clearance_level, 'value') else str(user.clearance_level)
    doc_class = doc.classification.value if hasattr(doc.classification, 'value') else str(doc.classification)
    
    user_level_score = CLASSIFICATION_HIERARCHY.get(user_clearance, 1)
    doc_level_score = CLASSIFICATION_HIERARCHY.get(doc_class, 1)

    if user_level_score < doc_level_score:
        return False, f"ABAC Denied: Classification '{doc_class}' requires clearance level >= {doc_class}, user has '{user_clearance}'"

    # 4. ABAC: Regional Jurisdictional Restriction
    if doc.region != "Global" and user.region != "Global":
        if doc.region != user.region:
            return False, f"ABAC Denied: Regional boundary mismatch. Document region is '{doc.region}', user region is '{user.region}'"

    # 5. ABAC: Need-to-Know & Entitlement Check
    # For Confidential and Restricted documents, verify specific business unit entitlement or need-to-know tags
    if doc_level_score >= CLASSIFICATION_HIERARCHY[ClassificationEnum.CONFIDENTIAL.value]:
        has_wildcard = "all" in user.entitlements
        has_matching_tag = any(tag in user.entitlements for tag in doc.need_to_know)
        same_bu = (user.business_unit == doc.business_unit)
        
        if not (has_wildcard or has_matching_tag or same_bu):
            return False, f"ABAC Denied: Need-to-know restriction. User lacks matching entitlements for tags: {doc.need_to_know}"

    return True, "Authorized: Satisfies RBAC role, ABAC classification, regional jurisdiction, and need-to-know controls."


def filter_documents_pre_retrieval(user: User, documents: List[DocumentMetadata]) -> Tuple[List[DocumentMetadata], Dict[str, Any]]:
    """
    CRITICAL ARCHITECTURAL STEP:
    Enforces RBAC + ABAC BEFORE retrieval.
    The search engine index is dynamically scoped to ONLY permitted documents.
    """
    authorized_docs: List[DocumentMetadata] = []
    audit_telemetry = {
        "total_documents_in_vault": len(documents),
        "authorized_count": 0,
        "restricted_count": 0,
        "authorized_doc_ids": [],
        "denial_breakdown": {}
    }

    for doc in documents:
        allowed, reason = evaluate_document_access(user, doc)
        if allowed:
            authorized_docs.append(doc)
            audit_telemetry["authorized_doc_ids"].append(doc.doc_id)
        else:
            audit_telemetry["denial_breakdown"][doc.doc_id] = {
                "title": doc.title,
                "reason": reason
            }

    audit_telemetry["authorized_count"] = len(authorized_docs)
    audit_telemetry["restricted_count"] = len(documents) - len(authorized_docs)

    return authorized_docs, audit_telemetry


def get_document_access_matrix(user: User, documents: List[DocumentMetadata]) -> List[Dict[str, Any]]:
    """
    Generates full access matrix for ERM Portal Document Vault.
    Visualizes green (accessible) vs red (restricted) locks for the active user.
    """
    matrix = []
    for doc in documents:
        allowed, reason = evaluate_document_access(user, doc)
        matrix.append({
            "doc_id": doc.doc_id,
            "title": doc.title,
            "category": doc.category,
            "business_unit": doc.business_unit,
            "region": doc.region,
            "classification": doc.classification.value if hasattr(doc.classification, 'value') else str(doc.classification),
            "allowed_roles": [r.value if hasattr(r, 'value') else str(r) for r in doc.allowed_roles],
            "need_to_know": doc.need_to_know,
            "is_authorized": allowed,
            "policy_reason": reason,
            "summary": doc.summary,
            "version": doc.version,
            "effective_date": doc.effective_date,
            "owner": doc.owner
        })
    return matrix
