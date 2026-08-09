"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analytics, approvals, documents, opportunities, proposals, quotes
def create_app(engine=None) -> FastAPI:
    application = FastAPI(title="Proposal Workflow Prototype", version="0.1.0")
    # Resolve the default database lazily on the first request. Importing the
    # ASGI module should not require a local Postgres driver or network access.
    application.state.engine = engine
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(opportunities.router, prefix="/v1")
    application.include_router(proposals.router, prefix="/v1")
    application.include_router(quotes.router, prefix="/v1")
    application.include_router(approvals.router, prefix="/v1")
    application.include_router(documents.router, prefix="/v1")
    application.include_router(analytics.router, prefix="/v1")
    return application


app = create_app()
