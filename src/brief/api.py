import os
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.middleware.base import RequestResponseEndpoint as CallNext

from brief import editor
from brief.crawl.fetch import normalize_url
from brief.db import Database
from brief.store import Store


class CreateProject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(max_length=2048)

    @field_validator("url")
    @classmethod
    def public_url(cls, url: str) -> str:
        return normalize_url(url)


class GuideBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=500)
    name: str = Field(min_length=1, max_length=100, pattern=r"^[^\r\n]+$")
    purpose: str = Field(min_length=1, max_length=2000)


class Monitoring(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool


class GuideTestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version_id: UUID
    suite_id: UUID | None = None
    questions: list[Annotated[str, Field(min_length=8, max_length=500)]] = Field(default_factory=list, max_length=5)

    @field_validator("questions")
    @classmethod
    def meaningful_questions(cls, values: list[str]) -> list[str]:
        if any(len(q.strip()) < 8 for q in values):
            raise ValueError("Write a question of at least eight characters.")
        return [q.strip() for q in values]


class RevisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)


class PublicationBody(RevisionBody):
    version_id: UUID | None


class DecisionBody(RevisionBody):
    statement: str = Field(min_length=1, max_length=4000)
    kind: Literal["preference", "fact"] = "preference"
    active: bool = True
    question_id: UUID | None = None


class DocumentBody(RevisionBody):
    markdown: str = Field(min_length=3, max_length=100000)


class SessionBody(BaseModel):
    token: str = Field(min_length=20, max_length=100)


def create_app(store: Store | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        worker = None
        if os.environ.get("BRIEF_EMBEDDED_WORKER", "false").lower() == "true":
            from brief.live import DemoWorker, LiveProgress
            from brief.model import OpenAIGenerator

            app.state.live = LiveProgress()
            generator = OpenAIGenerator() if os.environ.get("OPENAI_API_KEY") else None
            worker = DemoWorker(get_store(), generator, app.state.live)
            await worker.start()
        try:
            yield
        finally:
            if worker:
                await worker.stop()

    app = FastAPI(title="Brief source pipeline", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def notify_mutation(request: Request, call_next: CallNext) -> Response:
        response = await call_next(request)
        if request.method in {"POST", "PATCH", "DELETE"} and response.status_code < 400:
            live = getattr(app.state, "live", None)
            if live:
                live.invalidate()
        return response

    if store is not None:
        app.state.store = store
    origins = [s.strip() for s in os.environ.get("FRONTEND_ORIGINS", "http://localhost:5173").split(",") if s.strip()]
    if "*" in origins:
        raise ValueError("FRONTEND_ORIGINS must list exact origins")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Creation-Key"],
    )

    def get_store() -> Store:
        if not hasattr(app.state, "store"):
            app.state.store = Store(Database())
        return app.state.store

    def authenticate(
        project_id: UUID,
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))],
        store: Annotated[Store, Depends(get_store)],
    ) -> dict[str, Any]:
        token = credentials.credentials if credentials else request.cookies.get(f"brief_{project_id.hex}")
        if not token:
            with store.db.connect() as connection:
                row = connection.execute("SELECT site_id FROM projects WHERE id=%s", (project_id,)).fetchone()
            if row:
                token = request.cookies.get(f"brief_{row['site_id'].hex}")
        if not token:
            raise HTTPException(401, "Open your private access link to continue.")
        if not credentials and request.method not in {"GET", "HEAD"} and request.headers.get("origin") not in origins:
            raise HTTPException(403, "Untrusted request origin")
        project = store.get_project(project_id, token)
        if not project:
            raise HTTPException(404, "Project not found")
        return project

    @app.exception_handler(editor.EditConflict)
    async def edit_conflict(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.middleware("http")
    async def private_responses(request: Request, call_next: CallNext) -> Response:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.post("/api/projects/{project_id}/session")
    def session(
        project_id: UUID,
        body: SessionBody,
        request: Request,
        response: Response,
        store: Annotated[Store, Depends(get_store)],
    ) -> dict[str, Any]:
        if request.headers.get("origin") and request.headers["origin"] not in origins:
            raise HTTPException(403, "Untrusted request origin")
        authorized = store.get_project(project_id, body.token)
        if not authorized:
            raise HTTPException(404, "Project not found")
        response.set_cookie(
            f"brief_{authorized['site_id'].hex}",
            body.token,
            httponly=True,
            secure=os.environ.get("BRIEF_SECURE_COOKIES", "true") == "true",
            samesite="lax",
            path="/api/projects",
            max_age=60 * 60 * 24 * 30,
        )
        return {"ok": True}

    @app.get("/api/projects/{project_id}/access-token")
    def access_token(project: Annotated[dict[str, Any], Depends(authenticate)], request: Request) -> dict[str, Any]:
        token = (
            request.cookies.get(f"brief_{project['id'].hex}")
            or request.cookies.get(f"brief_{project['site_id'].hex}")
            or request.headers.get("authorization", "").removeprefix("Bearer ")
        )
        return {"token": token}

    @app.get("/api/projects/{site_id}/document")
    def site_document(
        site_id: UUID,
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))],
        store: Annotated[Store, Depends(get_store)],
        doc: str | None = None,
    ) -> dict[str, Any]:
        from brief.guides import normalize_scope

        token = credentials.credentials if credentials else request.cookies.get(f"brief_{site_id.hex}")
        if not token:
            raise HTTPException(401, "Open your private access link to continue.")
        project = store.get_project(site_id, token, guide_path=normalize_scope(doc) if doc is not None else None)
        if not project or project["site_id"] != site_id:
            raise HTTPException(404, "Document not found")
        return project

    @app.get("/api/projects/{project_id}/events")
    async def progress_events(
        request: Request,
        project: Annotated[dict[str, Any], Depends(authenticate)],
        store: Annotated[Store, Depends(get_store)],
    ) -> StreamingResponse:
        from brief.progress import events, live_events

        live = getattr(app.state, "live", None)
        return StreamingResponse(
            live_events(store, project["id"], request, live) if live else events(store, project["id"], request),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"},
        )

    @app.post("/api/projects/{project_id}/decisions", status_code=202)
    def decision(
        body: DecisionBody,
        project: Annotated[dict[str, Any], Depends(authenticate)],
        store: Annotated[Store, Depends(get_store)],
    ) -> dict[str, Any]:
        return editor.save_decision(store, project["id"], **body.model_dump())

    @app.patch("/api/projects/{project_id}/decisions/{decision_id}", status_code=202)
    def update_decision(
        decision_id: str,
        body: DecisionBody,
        project: Annotated[dict[str, Any], Depends(authenticate)],
        store: Annotated[Store, Depends(get_store)],
    ) -> dict[str, Any]:
        return editor.save_decision(store, project["id"], decision_id=decision_id, **body.model_dump())

    @app.post("/api/projects/{project_id}/questions/{question_id}/dismiss")
    def dismiss(
        question_id: UUID,
        body: RevisionBody,
        project: Annotated[dict[str, Any], Depends(authenticate)],
        store: Annotated[Store, Depends(get_store)],
    ) -> dict[str, Any]:
        editor.dismiss_question(store, project["id"], body.revision, question_id)
        return {"ok": True}

    @app.post("/api/projects/{project_id}/questions", status_code=202)
    def questions(
        body: RevisionBody,
        project: Annotated[dict[str, Any], Depends(authenticate)],
        store: Annotated[Store, Depends(get_store)],
    ) -> dict[str, Any]:
        return editor.ask_more(store, project["id"], body.revision)

    @app.post("/api/projects/{project_id}/versions")
    def save(
        body: DocumentBody,
        project: Annotated[dict[str, Any], Depends(authenticate)],
        store: Annotated[Store, Depends(get_store)],
    ) -> dict[str, Any]:
        return editor.save_document(store, project["id"], body.revision, body.markdown)

    @app.get("/api/projects/{project_id}/versions/{version_id}")
    def version(
        version_id: UUID,
        project: Annotated[dict[str, Any], Depends(authenticate)],
        store: Annotated[Store, Depends(get_store)],
    ) -> dict[str, Any]:
        with store.db.connect() as connection:
            version = connection.execute(
                "SELECT * FROM document_versions WHERE id = %s AND project_id = %s", (version_id, project["id"])
            ).fetchone()
            from brief.refinement_history import attach

            attach(connection, version)
        if not version:
            raise HTTPException(404, "Version not found")
        return version

    @app.post("/api/projects/{project_id}/versions/{version_id}/use")
    def use(
        version_id: UUID,
        body: RevisionBody,
        project: Annotated[dict[str, Any], Depends(authenticate)],
        store: Annotated[Store, Depends(get_store)],
    ) -> dict[str, Any]:
        return editor.use_version(store, project["id"], body.revision, version_id)

    @app.post("/api/projects/{project_id}/guides", status_code=202)
    def add_guide(
        body: GuideBody,
        project: Annotated[dict[str, Any], Depends(authenticate)],
        store: Annotated[Store, Depends(get_store)],
    ) -> dict[str, Any]:
        from brief.guides import create_guide

        return create_guide(store, project["id"], **body.model_dump())

    @app.post("/api/projects/{project_id}/cancel-guide")
    def cancel_guide(
        project: Annotated[dict[str, Any], Depends(authenticate)], store: Annotated[Store, Depends(get_store)]
    ) -> dict[str, Any]:
        from brief.guides import cancel_automatic

        return cancel_automatic(store, project["id"])

    @app.post("/api/projects/{project_id}/resume-guide")
    def resume_guide(
        project: Annotated[dict[str, Any], Depends(authenticate)], store: Annotated[Store, Depends(get_store)]
    ) -> dict[str, Any]:
        from brief.guides import resume_automatic

        return resume_automatic(store, project["id"])

    @app.get("/api/projects/{project_id}/bundle")
    def download_bundle(
        project: Annotated[dict[str, Any], Depends(authenticate)], store: Annotated[Store, Depends(get_store)]
    ) -> Response:
        from brief.guides import bundle

        return Response(
            bundle(store, project["site_id"]),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="llms-guides.zip"'},
        )

    @app.post("/api/projects/{project_id}/site-refresh", status_code=202)
    def site_refresh(
        project: Annotated[dict[str, Any], Depends(authenticate)],
        store: Annotated[Store, Depends(get_store)],
        idempotency_key: Annotated[str, Header(min_length=1, max_length=100)],
    ) -> dict[str, Any]:
        return {
            "jobs": [
                store.enqueue_refresh(g["id"], idempotency_key)["id"]
                for g in project["guides"]
                if not g["auto_cancelled"]
            ]
        }

    @app.post("/api/projects/{project_id}/tests", status_code=202)
    def test_guide(
        body: GuideTestBody,
        project: Annotated[dict[str, Any], Depends(authenticate)],
        store: Annotated[Store, Depends(get_store)],
        idempotency_key: Annotated[str, Header(min_length=1, max_length=100)],
    ) -> dict[str, Any]:
        from brief.guide_tests import enqueue

        if body.suite_id and body.questions:
            raise HTTPException(422, "Use saved questions or new questions, not both.")
        return enqueue(store, project["id"], **body.model_dump(), request_key=idempotency_key)

    @app.post("/api/projects/{project_id}/publication")
    def publish_document(
        body: PublicationBody,
        project: Annotated[dict[str, Any], Depends(authenticate)],
        store: Annotated[Store, Depends(get_store)],
    ) -> dict[str, Any]:
        from brief.publication import publish

        return publish(store, project["id"], body.revision, body.version_id)

    @app.get("/api/published/{publication_id}/llms.txt")
    def public_document(
        publication_id: UUID, store: Annotated[Store, Depends(get_store)], download: bool = False
    ) -> Response:
        with store.db.connect() as connection:
            row = connection.execute(
                """SELECT d.markdown FROM projects p JOIN document_versions d
                ON d.id=p.published_version_id AND d.project_id=p.id WHERE p.publication_id=%s""",
                (publication_id,),
            ).fetchone()
        if not row:
            raise HTTPException(404, "Published guide not found")
        headers = {"X-Content-Type-Options": "nosniff"}
        if download:
            headers["Content-Disposition"] = 'attachment; filename="llms.txt"'
        return Response(row["markdown"], media_type="text/plain", headers=headers)

    @app.post("/api/projects/{project_id}/existing-guide")
    async def existing_guide(
        project: Annotated[dict[str, Any], Depends(authenticate)], store: Annotated[Store, Depends(get_store)]
    ) -> dict[str, Any]:
        import asyncio

        from brief.publication import inspect, save_check

        report = await inspect(project["site_url"])
        await asyncio.to_thread(save_check, store, project["id"], report)
        return report

    @app.post("/api/projects/{project_id}/publication/verify")
    async def verify_publication(
        project: Annotated[dict[str, Any], Depends(authenticate)], store: Annotated[Store, Depends(get_store)]
    ) -> dict[str, Any]:
        from brief.publication import inspect

        with store.db.connect() as connection:
            published = connection.execute(
                "SELECT markdown FROM document_versions WHERE id=%s AND project_id=%s",
                (project["published_version_id"], project["id"]),
            ).fetchone()
        if not published:
            raise HTTPException(409, "Publish a saved version first.")
        report = await inspect(project["site_url"], exact=True)
        matches = any(g["markdown"].strip() == published["markdown"].strip() for g in report["guides"])
        return {"matches": matches, "version_id": project["published_version_id"], **report}

    @app.get("/health")
    def health(store: Annotated[Store, Depends(get_store)]) -> dict[str, Any]:
        with store.db.connect() as connection:
            connection.execute("SELECT 1")
        return {"status": "ok"}

    @app.post("/api/projects", status_code=202)
    def create(
        body: CreateProject,
        store: Annotated[Store, Depends(get_store)],
        x_creation_key: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        # Optional shared key gates project creation during a private demo; not project authorization.
        required = os.environ.get("BRIEF_CREATION_KEY")
        if required and not secrets.compare_digest(required, x_creation_key or ""):
            raise HTTPException(403, "Creation key required")
        project, token, job = store.create_project(body.url)
        return {"project": project, "management_token": token, "job_id": job["id"]}

    @app.get("/api/projects/{project_id}")
    def get_project(project: Annotated[dict[str, Any], Depends(authenticate)]) -> dict[str, Any]:
        return project

    @app.post("/api/projects/{project_id}/refresh", status_code=202)
    def refresh(
        project: Annotated[dict[str, Any], Depends(authenticate)],
        store: Annotated[Store, Depends(get_store)],
        idempotency_key: Annotated[str, Header(min_length=1, max_length=100)],
    ) -> dict[str, Any]:
        job = store.enqueue_refresh(project["id"], idempotency_key)
        return {"job_id": job["id"], "status": job["status"]}

    @app.post("/api/projects/{project_id}/generate", status_code=202)
    def generate(
        project: Annotated[dict[str, Any], Depends(authenticate)],
        store: Annotated[Store, Depends(get_store)],
        idempotency_key: Annotated[str, Header(min_length=1, max_length=100)],
    ) -> dict[str, Any]:
        try:
            job = store.enqueue_generation(project["id"], idempotency_key)
        except ValueError as error:
            raise HTTPException(409, str(error)) from None
        return {"job_id": job["id"], "status": job["status"]}

    @app.patch("/api/projects/{project_id}/monitoring")
    def monitoring(
        body: Monitoring,
        project: Annotated[dict[str, Any], Depends(authenticate)],
        store: Annotated[Store, Depends(get_store)],
    ) -> dict[str, Any]:
        store.set_monitoring(project["id"], body.enabled)
        return {"enabled": body.enabled}

    @app.get("/api/projects/{project_id}/snapshots/{snapshot_id}")
    def snapshot(
        snapshot_id: UUID,
        project: Annotated[dict[str, Any], Depends(authenticate)],
        store: Annotated[Store, Depends(get_store)],
    ) -> dict[str, Any]:
        with store.db.connect() as connection:
            snapshot = connection.execute(
                "SELECT * FROM crawl_snapshots WHERE id = %s AND project_id = %s", (snapshot_id, project["id"])
            ).fetchone()
        if not snapshot:
            raise HTTPException(404, "Snapshot not found")
        return snapshot

    return app


app = create_app()
