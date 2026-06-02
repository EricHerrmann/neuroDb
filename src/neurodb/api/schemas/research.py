from __future__ import annotations
from datetime import datetime

from pydantic import BaseModel


class ResearchQuestion(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    question: str
    status: str
    topic_context: str | None = None
    created_at: datetime | None = None


class Hypothesis(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    mechanism: str | None = None
    evidence_json: list[object] = []
    predictions_json: list[object] = []
    datasets_json: list[object] = []
    confounds_json: list[object] = []
    limitations: str | None = None
    status: str
    created_at: datetime | None = None


class HypothesisReviewItem(BaseModel):
    id: int
    hypothesis_id: int
    model: str
    critique_text: str
    unsupported_claims: list[object]
    missing_confounds: list[object]
    suggested_revisions: str
    status: str
    created_at: datetime | None = None


class ClaimItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    paper_id: int
    text: str
    claim_type: str
    status: str
    created_at: str
    updated_at: str


class ResearchGapItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    question_id: int | None = None
    hypothesis_id: int | None = None
    description: str
    gap_type: str
    status: str
    created_at: str
    updated_at: str


class EvidenceLinkItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    hypothesis_id: int
    claim_id: int | None = None
    paper_id: int | None = None
    packet_id: int | None = None
    note_id: int | None = None
    link_type: str
    status: str
    created_at: str


class TopicGroupingLink(BaseModel):
    topic_id: int
    topic_name: str
    status: str
    proposed: bool = False


class ConceptGroupingLink(BaseModel):
    concept_id: int
    concept_name: str
    status: str
    proposed: bool = False


class ResearchQuestionDetail(BaseModel):
    id: int
    question: str
    status: str
    topic_context: str | None = None
    origin_session_id: int | None = None
    created_at: datetime | None = None
    topics: list[TopicGroupingLink] = []
    concepts: list[ConceptGroupingLink] = []


class CreateQuestionRequest(BaseModel):
    question: str
    topic_context: str | None = None
    origin_session_id: int | None = None


class UpdateQuestionRequest(BaseModel):
    question: str | None = None
    topic_context: str | None = None


class AddTopicLinkRequest(BaseModel):
    topic_id: int


class PatchLinkStatusRequest(BaseModel):
    status: str


class AddConceptLinkRequest(BaseModel):
    concept_id: int


class GroupingItem(BaseModel):
    id: int
    type: str
    name: str
    parent_id: int | None = None
    status: str
    description: str | None = None


class CreateGroupingRequest(BaseModel):
    type: str
    name: str
    parent_id: int | None = None
    description: str | None = None


class PatchGroupingRequest(BaseModel):
    parent_id: int | None = None
    status: str | None = None
