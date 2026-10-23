from fastapi import APIRouter

from app.core.agent import Agent
from app.schemas.request import SentenceRequest
from app.schemas.response import SentenceResponse

router = APIRouter()


@router.post("/sentence", response_model=SentenceResponse)
async def create_sentence(request: SentenceRequest) -> SentenceResponse:
    return await Agent().process(request)


@router.post("/", response_model=SentenceResponse)
async def create_sentence_root(request: SentenceRequest) -> SentenceResponse:
    return await Agent().process(request)