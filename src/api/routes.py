"""Route definitions for the Football Analysis Platform API."""

import json
import logging
import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse

from starlette.concurrency import run_in_threadpool

from src.api.services.discussion_service import (
    get_saved_discussion,
    list_saved_discussions,
)
from src.discussion.types import DiscussionResult
from src.api.schemas import (
    AgentInfluenceOut,
    AgentInfo,
    AnalyticsResponse,
    DiscussionDetailResponse,
    DiscussionListResponse,
    DiscussionStatusResponse,
    DiscussionSummary,
    HealthResponse,
    MessageOut,
    RoundAgreementOut,
    SentimentOut,
    StancePointOut,
    StartDiscussionRequest,
    StartDiscussionResponse,
    TopicItem,
    TopicsResponse,
)

logger = logging.getLogger("src.api.routes")
router = APIRouter()


# ── Root Redirect ──
@router.get("/", include_in_schema=False)
async def root():
    """Redirect root to Swagger UI docs."""
    return RedirectResponse(url="/docs")


# ── Curated Predefined Topics ──
CURATED_TOPICS = [
    TopicItem(
        id="japan-spain-2022",
        label="Japan's 5-4-1 Low Block vs Spain (2022 World Cup)",
        description="Tactical and performance analysis of Japan's defensive structure and counter-attacking efficiency against Spain.",
    ),
    TopicItem(
        id="argentina-france-2022",
        label="Was France Unlucky in the 2022 World Cup Final?",
        description="Evaluating refereeing decisions, momentum shifts, and tactical changes in the 2022 World Cup Final.",
    ),
    TopicItem(
        id="arsenal-striker-dilemma",
        label="Should Arsenal Sign a Proven Striker in January?",
        description="Statistical and financial analysis comparing Havertz/Jesus with elite central strikers.",
    ),
    TopicItem(
        id="egypt-argentina-officiating",
        label="Did Argentina Win Against Egypt Because of Match Officials?",
        description="Multi-angle debate covering controversial refereeing calls, statistical xG disparity, and tactical game state.",
    ),
    TopicItem(
        id="tuchel-bayern-tactics",
        label="Tuchel's Tactical Setup vs Leverkusen: Masterclass or Collapse?",
        description="Analyzing Bayer Leverkusen's 3-0 victory against Bayern Munich and Tuchel's sudden back-three formation.",
    ),
]


# ── 1. Health Check ──
@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Lightweight system health check",
)
def health_check() -> HealthResponse:
    """Verify that the API server is healthy and running."""
    logger.info("health_check")
    return HealthResponse(status="ok")


# ── 2. Topics ──
@router.get(
    "/topics",
    response_model=TopicsResponse,
    tags=["Topics"],
    summary="List available discussion topics",
)
async def get_topics():
    """Return curated football discussion topics compatible with the knowledge base."""
    return TopicsResponse(topics=CURATED_TOPICS)


# ── 3. List Discussions ──
@router.get(
    "/discussions",
    response_model=DiscussionListResponse,
    tags=["Discussions"],
    summary="List saved discussions",
)
async def get_discussions():
    """Return summary metadata for all saved discussions in outputs/."""
    try:
        raw_summaries = await run_in_threadpool(list_saved_discussions)
        discussions = [
            DiscussionSummary(
                discussion_id=item.get("discussion_id", ""),
                topic=item.get("topic", ""),
                num_agents=int(item.get("num_agents", 0)),
                num_rounds=int(item.get("num_rounds", 0)),
                num_messages=int(item.get("num_messages", 0)),
                timestamp=str(item.get("timestamp", "")),
            )
            for item in raw_summaries
        ]
        return DiscussionListResponse(discussions=discussions)
    
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )
    
    except Exception as exc:
        logger.error("Failed to list discussions: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list discussions: {exc}",
        )


# ── 4. Start Discussion ──
@router.post(
    "/discussions",
    response_model=StartDiscussionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Discussions"],
    summary="Start a new multi-agent discussion",
)
async def start_discussion(req: StartDiscussionRequest):
    """Schedule a real discussion in the background."""
    from src.api.services.discussion_service import enqueue_discussion

    discussion_id = req.discussion_id or f"disc-{uuid4().hex[:8]}"

    return await enqueue_discussion(
        discussion_id=discussion_id,
        request=req,
    )




# ── 5. Discussion Detail ──
@router.get(
    "/discussions/{discussion_id}",
    response_model=DiscussionDetailResponse,
    tags=["Discussions"],
    summary="Get full discussion details",
)
async def get_discussion(discussion_id: str):
    """Load and return the complete persistent record of a single discussion."""
    try:
        discussion: DiscussionResult = await run_in_threadpool(
            get_saved_discussion,
            discussion_id,
        )    
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Discussion '{discussion_id}' not found",
        )
    except Exception as exc:
        logger.error("Error loading discussion %s: %s", discussion_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading discussion: {exc}",
        )

    agents = [
        AgentInfo(agent_id=aid, persona_file=f"personas/{aid}.yaml")
        for aid in discussion.config.agent_ids
    ]

    messages = [
        MessageOut(
            round_num=m.round_num,
            sender_id=m.sender_id,
            recipient_ids=m.recipient_ids,
            content=m.content,
            sentiment_score=m.sentiment_score,
            sentiment_label=m.sentiment_label,
            timestamp=m.timestamp,
        )
        for m in discussion.messages
    ]

    return DiscussionDetailResponse(
        discussion_id=discussion.config.discussion_id,
        topic=discussion.config.topic,
        agents=agents,
        num_rounds=discussion.config.num_rounds,
        graph=discussion.config.graph,
        messages=messages,
        timestamp=discussion.config.timestamp,
    )


# ── 6. Discussion Status ──
@router.get(
    "/discussions/{discussion_id}/status",
    response_model=DiscussionStatusResponse,
    tags=["Discussions"],
    summary="Check discussion execution status",
)
async def get_discussion_status(discussion_id: str):
    """Return runtime status and saved checkpoint progress."""
    from src.api.services.discussion_service import (
        get_discussion_status_record,
    )

    try:
        return await run_in_threadpool(
            get_discussion_status_record,
            discussion_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )

# ── 7. Discussion Analytics ──
@router.get(
    "/discussions/{discussion_id}/analytics",
    response_model=AnalyticsResponse,
    tags=["Analytics"],
    summary="Get analytics for a discussion",
)
async def get_analytics(discussion_id: str):
    """Return cached or newly calculated discussion analytics."""
    from src.api.services.analytics_service import (
        get_discussion_analytics,
    )

    try:
        return await get_discussion_analytics(discussion_id)

    except FileNotFoundError:
        logger.info(
            "Analytics requested for missing discussion: %s",
            discussion_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Discussion '{discussion_id}' not found.",
        )

    except ValueError as exc:
        logger.warning(
            "Rejected analytics request for %s: %s",
            discussion_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid discussion ID or discussion/analytics data.",
        )

    except RuntimeError as exc:
        logger.warning(
            "Analytics temporarily unavailable for %s: %s",
            discussion_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics are temporarily unavailable. Please retry.",
        )

    except Exception:
        logger.exception(
            "Unexpected analytics failure for %s",
            discussion_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analytics processing failed. Check the server logs.",
        )