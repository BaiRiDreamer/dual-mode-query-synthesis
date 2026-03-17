"""Pydantic models for query synthesis artifacts."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class DiffPatch(BaseModel):
    """Represents a diff patch for a file."""
    path: str
    patch: str
    additions: int = 0
    deletions: int = 0


class PRRecord(BaseModel):
    """Metadata for a single pull request."""
    pr_id: str
    pr_number: int
    repository: str
    title: str
    description: Optional[str] = None
    author: str
    created_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    labels: List[str] = Field(default_factory=list)
    files_changed: List[str] = Field(default_factory=list)
    base_commit: Optional[str] = None
    head_commit: Optional[str] = None
    patches: List[DiffPatch] = Field(default_factory=list)
    status: str = "merged"


class PRChain(BaseModel):
    """Represents a chain of related PRs."""
    chain_id: str
    original_chain: List[str]  # List of "repo/repo#pr_number"
    status: str  # "approved" or "rejected"
    quality_score: float
    file_overlap_rate: Optional[float] = None
    llm_judgment: Dict[str, Any]
    pr_records: List[PRRecord] = Field(default_factory=list)


class ChainMetadata(BaseModel):
    """Metadata for chain-level queries."""
    chain_id: str
    repository: str
    topic: str
    evolution_pattern: str
    quality_score: float
    pr_count: int
    total_commits: int = 0
    file_overlap_rate: float = 0.0


class PRMetadata(BaseModel):
    """Metadata for atomic-level queries."""
    pr_id: str
    pr_number: int
    repository: str
    title: str
    author: str
    created_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    function_type: str
    labels: List[str] = Field(default_factory=list)


class ChainContext(BaseModel):
    """Context about PR's position in chain."""
    chain_id: str
    position_in_chain: int
    total_prs_in_chain: int
    is_first: bool
    is_last: bool
    preceding_pr_ids: List[str] = Field(default_factory=list)
    following_pr_ids: List[str] = Field(default_factory=list)


class TaskScope(BaseModel):
    """Scope of the task."""
    modules: List[str] = Field(default_factory=list)
    files: List[str] = Field(default_factory=list)
    functions: List[str] = Field(default_factory=list)


class TaskSpecification(BaseModel):
    """Task specification for queries."""
    intent: str
    description: Optional[str] = None
    scope: TaskScope
    evolution_narrative: Optional[str] = None
    constraints: List[str] = Field(default_factory=list)


class GroundTruth(BaseModel):
    """Ground truth for validation."""
    patch: str
    base_commit: Optional[str] = None
    head_commit: Optional[str] = None
    validation_criteria: List[str] = Field(default_factory=list)


class PRSequenceItem(BaseModel):
    """Item in PR sequence for chain-level queries."""
    pr_id: str
    title: str
    description: Optional[str] = None
    function_type: str
    files_changed: List[str]
    base_commit: Optional[str] = None
    head_commit: Optional[str] = None
    patches: List[DiffPatch] = Field(default_factory=list)
    role_in_chain: str
    validation_criteria: List[str] = Field(default_factory=list)


class ChainLevelQuery(BaseModel):
    """Chain-level query artifact."""
    query_id: str
    mode: str = "chain_level"
    chain_metadata: ChainMetadata
    task_specification: TaskSpecification
    pr_sequence: List[PRSequenceItem]
    ground_truth: GroundTruth
    prompt: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AtomicLevelQuery(BaseModel):
    """Atomic-level query artifact."""
    query_id: str
    mode: str = "atomic_level"
    pr_metadata: PRMetadata
    chain_context: Optional[ChainContext] = None
    task_specification: TaskSpecification
    ground_truth: GroundTruth
    prompt: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
