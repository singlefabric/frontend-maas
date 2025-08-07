# -*- coding: utf-8 -*-
from enum import Enum
from typing import Optional, Union, List

from pydantic import BaseModel


class FilePurpose(str, Enum):
    ASSISTANTS = "assistants"
    BATCH = "batch"
    FINE_TUNE = "fine-tune"
    VISION = "vision"
    USER_DATA = "user_data"
    EVALS = "evals"


class InfBaseReq(BaseModel):
    model: str


class TTSReq(InfBaseReq):
    model: str
    input: str
    voice: str
    speed: float = 1.0


class EmbeddingsReq(InfBaseReq):
    input: Union[List[int], List[List[int]], str, List[str]]
    encoding_format: str = "float"
    dimensions: int = None
    user: Optional[str] = None


class RerankerReq(InfBaseReq):
    query: str
    documents: list[str]
    top_n: Optional[int] = None