"""
hitl_service.py - Human-in-the-Loop (HITL) Workflow Service.
Enforces the mandatory banking governance principle that GenAI assists risk assessments
without executing uncontrolled, unilateral risk or regulatory determinations.
"""

import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from backend.models import HITLReviewItem, HITLReviewRequest
from backend.audit_logger import audit_logger


HITL_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "hitl_queue.json")


class HITLService:
    def __init__(self, queue_path: str = HITL_FILE):
        self.queue_path = queue_path
        self.items: Dict[str, HITLReviewItem] = {}
        self._ensure_dir()
        self._load_or_seed()

    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.queue_path), exist_ok=True)

    def _load_or_seed(self):
        if os.path.exists(self.queue_path):
            try:
                with open(self.queue_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item_data in data:
                        item = HITLReviewItem(**item_data)
                        self.items[item.item_id] = item
            except Exception:
                self.items = {}
        
        # Seed initial sample item if empty so the UI queue looks realistic immediately
        if not self.items:
            sample_item = HITLReviewItem(
                item_id="HITL-REQ-001",
                request_id="REQ-SEED-8891",
                timestamp="2025-02-28T10:15:00Z",
                user_id="USR-ANA-101",
                user_role="Risk_Analyst",
                query="Assess the severity of contractor access finding in cloud bastion hosts.",
                draft_response=(
                    "Based on the retrieved evidence [DOC-AUD-001], there appears to be an elevated risk regarding "
                    "stale SSH keys retained by 14 terminated contractors. Management action plans specify ephemeral JIT "
                    "tokens by June 30, 2025. Recommend monitoring interim compensatory access controls."
                ),
                citations=["[DOC-AUD-001]"],
                severity_level="High",
                status="Pending Review"
            )
            self.items[sample_item.item_id] = sample_item
            self._persist()

    def _persist(self):
        try:
            with open(self.queue_path, "w", encoding="utf-8") as f:
                json.dump([item.model_dump() for item in self.items.values()], f, indent=2)
        except Exception as e:
            print(f"[HITLService] Warning: Could not write HITL queue file: {e}")

    def create_review_item(
        self,
        request_id: str,
        user_id: str,
        user_role: str,
        query: str,
        draft_response: str,
        citations: List[str],
        severity_level: str = "Medium"
    ) -> HITLReviewItem:
        item_id = f"HITL-REQ-{len(self.items) + 1:03d}"
        now_ts = datetime.now().isoformat() + "Z"

        item = HITLReviewItem(
            item_id=item_id,
            request_id=request_id,
            timestamp=now_ts,
            user_id=user_id,
            user_role=user_role,
            query=query,
            draft_response=draft_response,
            final_response=None,
            citations=citations,
            severity_level=severity_level,
            status="Pending Review"
        )
        self.items[item_id] = item
        self._persist()
        return item

    def process_review(self, review_req: HITLReviewRequest) -> Optional[HITLReviewItem]:
        item = self.items.get(review_req.item_id)
        if not item:
            return None

        now_ts = datetime.now().isoformat() + "Z"
        action = review_req.action.lower()

        if action == "approve":
            item.status = "Approved"
            item.final_response = item.draft_response
        elif action == "amend":
            item.status = "Amended"
            item.final_response = review_req.amended_text or item.draft_response
        elif action == "reject":
            item.status = "Rejected"
            item.final_response = "Assessment Rejected by Risk Reviewer. Insufficient evidence or conflicting internal metrics."
        else:
            return None

        item.reviewed_by = review_req.reviewer_id
        item.analyst_notes = review_req.analyst_notes
        item.reviewed_at = now_ts

        # Update matching audit log entry if found
        audit_logger.update_approval(item.request_id, item.status)

        self._persist()
        return item

    def list_items(self, status: Optional[str] = None) -> List[HITLReviewItem]:
        results = list(self.items.values())
        if status:
            results = [i for i in results if i.status.lower() == status.lower()]
        return list(reversed(results))


hitl_service = HITLService()
