import logging
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
import uvicorn

from app.config import settings
from app.schemas import ProspectDiscoveryRequest, ProspectDiscoveryResponse
from app.services.prospect_service import prospect_service

# Logging setup
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("prospect_discovery_api")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## AI-Powered Multi-Platform Prospect Discovery API
    Discovers relevant prospects across multiple online platforms based on natural-language search queries.
    Supported platforms: Google, LinkedIn, X, YouTube, Instagram, WhatsApp, Facebook, Email, Threads.
    """,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for external frontend or web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    raw_errors = exc.errors()
    # Format cleanly for JSON serialization without non-serializable exception objects
    serializable_errors = []
    for err in raw_errors:
        serializable_errors.append({
            "loc": [str(x) for x in err.get("loc", [])],
            "msg": str(err.get("msg", "")),
            "type": str(err.get("type", ""))
        })

    msg = serializable_errors[0]["msg"] if serializable_errors else "Invalid request body"
    logger.warning(f"Validation error on {request.url}: {serializable_errors}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error": f"Invalid query parameter: {msg}",
            "details": serializable_errors
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error on {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "An internal error occurred during prospect discovery.",
            "details": str(exc) if settings.DEBUG else None
        }
    )


@app.get("/", tags=["General"])
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "healthy",
        "endpoints": {
            "prospect_discovery": "POST /prospect-discovery",
            "docs": "/docs",
            "health": "/health"
        }
    }


@app.get("/health", tags=["General"])
async def health_check():
    return {
        "status": "UP",
        "environment": settings.APP_ENV,
        "llm_provider": settings.LLM_PROVIDER,
        "search_provider": settings.SEARCH_PROVIDER
    }


@app.post(
    "/prospect-discovery",
    response_model=ProspectDiscoveryResponse,
    status_code=status.HTTP_200_OK,
    tags=["Prospect Discovery"],
    summary="Discover relevant prospects across multiple platforms"
)
async def discover_prospects(request: ProspectDiscoveryRequest):
    """
    Accepts a natural-language search query, parses the intent (audience, interest, location),
    executes multi-platform discovery, extracts verified public contacts, consolidates duplicates,
    and returns structured JSON.
    """
    try:
        response = await prospect_service.discover_prospects(request)
        return response
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Error in prospect discovery endpoint: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "query": request.query,
                "error": f"Prospect discovery process encountered an error: {str(e)}"
            }
        )


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG
    )
