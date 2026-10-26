import uuid

from fastapi import APIRouter, Request

from app.api.dependencies import get_agent
from app.schemas.request import SentenceRequest
from app.schemas.response import SentenceResponse

router = APIRouter()


async def _process(request: Request, body: SentenceRequest) -> SentenceResponse:
    if not getattr(body, "request_id", None):
        body.request_id = str(uuid.uuid4())
    agent = get_agent(request)
    result = await agent.process(body)
    try:
        result.request_id = body.request_id
    except Exception:
        pass
    return result


@router.post("/sentence", response_model=SentenceResponse)
async def create_sentence(request: Request, body: SentenceRequest) -> SentenceResponse:
    return await _process(request, body)


@router.post("/", response_model=SentenceResponse)
async def create_sentence_root(request: Request, body: SentenceRequest) -> SentenceResponse:
    return await _process(request, body)
