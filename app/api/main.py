"""FastAPI application factory."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import analytics, approvals, documents, opportunities, proposals, quotes
from app.persistence.models import Base, create_all
from app.persistence.repositories import OpportunityRepo
from app.persistence.session import get_engine, session_scope


def create_app(engine=None) -> FastAPI:
    application = FastAPI(title="Proposal Workflow Prototype", version="0.1.0")
    # Resolve the default database lazily on the first request. Importing the
    # ASGI module should not require a local Postgres driver or network access.
    application.state.engine = engine
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3106"],
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

    @application.get("/health")
    def health(request: Request):
        try:
            active_engine = request.app.state.engine or get_engine()
            request.app.state.engine = active_engine
            with session_scope(active_engine) as session:
                ready = bool(OpportunityRepo(session).list())
        except (OSError, SQLAlchemyError):
            return JSONResponse(
                status_code=503,
                content={
                    "status": "running",
                    "ready": False,
                    "reason": "fixture database is unavailable",
                },
            )
        if not ready:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "running",
                    "ready": False,
                    "reason": "fixture data is not seeded",
                },
            )
        return {"status": "running", "ready": True}

    @application.post("/v1/fixture/reset")
    def reset_fixture(request: Request):
        """Replace only local fixture data so browser tests own their lifecycle."""
        from app.cli import seed_all

        active_engine = request.app.state.engine or get_engine()
        request.app.state.engine = active_engine
        Base.metadata.drop_all(active_engine)
        create_all(active_engine)
        with session_scope(active_engine) as session:
            result = seed_all(session)
        return {"status": "reset", "proposalVersions": len(result.version_ids)}

    return application


app = create_app()
