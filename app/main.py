import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

from app.config import settings
from app.schemas import ProspectDiscoveryRequest, ProspectDiscoveryResponse
from app.services.prospect_service import prospect_service
from app.services.llm_service import llm_service
from app.services.search_service import search_service

# Logging setup
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("prospect_discovery_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info("Application starting up...")
    yield
    # Graceful shutdown: close pooled HTTP clients
    logger.info("Closing HTTP client connections...")
    await llm_service.close()
    await search_service.close()
    logger.info("Application shutdown complete.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## AI-Powered Multi-Platform Prospect Discovery API
    Discovers relevant prospects across multiple online platforms based on natural-language search queries.
    Supported platforms: Google, LinkedIn, X, YouTube, Instagram, WhatsApp, Facebook, Email, Threads.
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# Secure CORS configuration
# Note: allow_credentials MUST be False when allow_origins contains '*' for OWASP/W3C compliance
is_wildcard = "*" in settings.ALLOWED_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=not is_wildcard,
    allow_methods=["GET", "POST", "HEAD", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    raw_errors = exc.errors()
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
            "error": "An internal error occurred during prospect discovery."
        }
    )


@app.api_route("/", methods=["GET", "HEAD"], tags=["General"])
async def root(request: Request):
    if request.method == "HEAD":
        return Response(status_code=status.HTTP_200_OK)
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


@app.api_route("/health", methods=["GET", "HEAD"], tags=["General"])
async def health_check(request: Request):
    if request.method == "HEAD":
        return Response(status_code=status.HTTP_200_OK)
    return {
        "status": "UP",
        "environment": settings.APP_ENV,
        "llm_provider": settings.LLM_PROVIDER,
        "search_provider": settings.SEARCH_PROVIDER
    }


@app.get("/doc", include_in_schema=False)
async def redirect_doc_to_docs():
    """Convenient redirect for users typing /doc instead of /docs."""
    return RedirectResponse(url="/docs", status_code=status.HTTP_301_MOVED_PERMANENTLY)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
                "error": "Prospect discovery service encountered an internal processing error."
            }
        )


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG
    )
