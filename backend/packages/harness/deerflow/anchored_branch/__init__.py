"""Anchored Branch domain objects for the CodeRepair learning project.

DeerFlow owns the Thread, Run, Checkpoint, Agent and SSE runtime.  This package
only owns the small amount of domain state needed to continue a conversation
from a selected answer fragment and merge a human decision back to the main
task.
"""

from .context import BranchContext, BranchContextBuilder, read_code_context
from .models import AnchorSelection, BranchDecision, BranchRecord, BranchStatus
from .store import AnchoredBranchStore

__all__ = [
    "AnchorSelection",
    "AnchoredBranchStore",
    "BranchContext",
    "BranchContextBuilder",
    "BranchDecision",
    "BranchRecord",
    "BranchStatus",
    "read_code_context",
]
