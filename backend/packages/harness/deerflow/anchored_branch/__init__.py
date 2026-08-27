"""Anchored Branch domain objects for the CodeRepair learning project.

DeerFlow owns the Thread, Run, Checkpoint, Agent and SSE runtime.  This package
only owns the small amount of domain state needed to continue a conversation
from a selected answer fragment without mutating the main conversation.
"""

from .context import BranchContext, BranchContextBuilder, read_code_context
from .models import AnchorSelection, BranchContextStrategy, BranchRecord, BranchStatus
from .store import AnchoredBranchStore

__all__ = [
    "AnchorSelection",
    "AnchoredBranchStore",
    "BranchContext",
    "BranchContextBuilder",
    "BranchContextStrategy",
    "BranchRecord",
    "BranchStatus",
    "read_code_context",
]
