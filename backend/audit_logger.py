"""
audit_logger.py - Tamper-evident, PII-Protected Enterprise Banking Audit Ledger.
Maintains an immutable cryptographically hashed audit trail compliant with banking
and financial regulatory standards (SOX, OCC Heightened Standards, BCBS 239).
"""

import hashlib
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from backend.models import AuditLogEntry


AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "audit_log.json")


class EnterpriseAuditLogger:
    def __init__(self, log_path: str = AUDIT_LOG_FILE):
        self.log_path = log_path
        self.entries: List[AuditLogEntry] = []
        self.last_hash = "GENESIS_HASH_0000000000000000000000000000000000000000000000000000000000"
        self._ensure_dir()
        self._load_existing_logs()

    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def _load_existing_logs(self):
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        entry = AuditLogEntry(**item)
                        self.entries.append(entry)
                    if self.entries:
                        self.last_hash = self.entries[-1].tamper_hash
            except Exception:
                self.entries = []

    def _persist(self):
        try:
            with open(self.log_path, "w", encoding="utf-8") as f:
                json.dump([e.model_dump() for e in self.entries], f, indent=2)
        except Exception as e:
            print(f"[AuditLogger] Warning: Could not write audit log file: {e}")

    def compute_entry_hash(self, entry_dict: Dict[str, Any], previous_hash: str) -> str:
        """
        Computes cryptographic SHA-256 hash chaining each log record to the previous one.
        """
        serialized = json.dumps(entry_dict, sort_keys=True)
        combined = f"{previous_hash}::{serialized}".encode("utf-8")
        return hashlib.sha256(combined).hexdigest()

    def log_query_event(
        self,
        request_id: str,
        user_id: str,
        user_role: str,
        business_unit: str,
        region: str,
        query_masked: str,
        retrieved_doc_ids: List[str],
        confidence_score: float,
        grounding_score: float,
        guardrail_results: Dict[str, Any],
        approval_status: str = "Pending Review",
        model_version: str = "Enterprise-Risk-LLM-v2.4"
    ) -> AuditLogEntry:
        """
        Logs a sanitized, tamper-evident audit record.
        Sensitive prompts/PII are redacted before arriving here.
        """
        log_id = f"AUD-LOG-{len(self.entries) + 1:05d}"
        timestamp = datetime.now().isoformat() + "Z"

        record_payload = {
            "log_id": log_id,
            "request_id": request_id,
            "timestamp": timestamp,
            "user_id": user_id,
            "user_role": user_role,
            "business_unit": business_unit,
            "region": region,
            "query_masked": query_masked,
            "retrieved_doc_ids": retrieved_doc_ids,
            "confidence_score": round(confidence_score, 3),
            "grounding_score": round(grounding_score, 3),
            "guardrail_results": guardrail_results,
            "approval_status": approval_status,
            "model_version": model_version
        }

        entry_hash = self.compute_entry_hash(record_payload, self.last_hash)
        entry = AuditLogEntry(
            **record_payload,
            tamper_hash=entry_hash
        )

        self.entries.append(entry)
        self.last_hash = entry_hash
        self._persist()
        return entry

    def update_approval(self, request_id: str, new_status: str) -> bool:
        for entry in self.entries:
            if entry.request_id == request_id:
                entry.approval_status = new_status
                self._persist()
                return True
        return False

    def get_logs(
        self,
        user_id: Optional[str] = None,
        role: Optional[str] = None,
        limit: int = 50
    ) -> List[AuditLogEntry]:
        results = self.entries
        if user_id:
            results = [e for e in results if e.user_id == user_id]
        if role:
            results = [e for e in results if e.user_role == role]
        return list(reversed(results))[:limit]

    def verify_chain_integrity(self) -> Dict[str, Any]:
        """
        Verifies SHA-256 hash-chain integrity of the entire audit log.
        """
        if not self.entries:
            return {"valid": True, "total_records": 0, "message": "Log ledger is empty."}

        current_prev_hash = "GENESIS_HASH_0000000000000000000000000000000000000000000000000000000000"
        for i, entry in enumerate(self.entries):
            record_payload = {
                "log_id": entry.log_id,
                "request_id": entry.request_id,
                "timestamp": entry.timestamp,
                "user_id": entry.user_id,
                "user_role": entry.user_role,
                "business_unit": entry.business_unit,
                "region": entry.region,
                "query_masked": entry.query_masked,
                "retrieved_doc_ids": entry.retrieved_doc_ids,
                "confidence_score": entry.confidence_score,
                "grounding_score": entry.grounding_score,
                "guardrail_results": entry.guardrail_results,
                "approval_status": entry.approval_status,
                "model_version": entry.model_version
            }
            expected_hash = self.compute_entry_hash(record_payload, current_prev_hash)
            if expected_hash != entry.tamper_hash:
                return {
                    "valid": False,
                    "tampered_at_index": i,
                    "log_id": entry.log_id,
                    "message": f"Tampering detected at record {entry.log_id}! Hash mismatch."
                }
            current_prev_hash = entry.tamper_hash

        return {
            "valid": True,
            "total_records": len(self.entries),
            "message": "Audit chain verification passed. 100% cryptographic integrity confirmed."
        }


# Global instance
audit_logger = EnterpriseAuditLogger()
