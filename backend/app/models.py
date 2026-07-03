"""Pydantic request/response schemas for the API."""

from typing import List, Optional

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    title: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    source: str = "upload"


class IngestResponse(BaseModel):
    doc_id: int
    title: str
    n_chunks: int


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: Optional[int] = None
    hybrid: bool = True


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: Optional[int] = None
    hybrid: bool = True


class EvalRequest(BaseModel):
    hybrid: bool = True
    top_k: Optional[int] = None
