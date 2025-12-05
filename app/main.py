from datetime import datetime, timedelta
from io import BytesIO
from typing import Dict, List, Optional

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .crud import (
    get_setting,
    list_repositories,
    mark_issues_closed,
    save_issues,
    search_issues,
    update_issue_fields,
    upsert_repository,
    upsert_setting,
)
from .database import get_session, init_db
from .gitlab_client import GitLabClient
from .models import Issue
from .schemas import (
    BulkCloseRequest,
    CommitStat,
    CommitStatsResponse,
    IssueSearchResponse,
    IssueRead,
    IssueUpdate,
    RefreshRequest,
    RepositoryRead,
    SettingCreate,
    SettingRead,
)

app = FastAPI(title="GitLab Dashboard", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()


@app.get("/", response_class=HTMLResponse)
async def read_root() -> HTMLResponse:
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


async def get_client(session: AsyncSession) -> GitLabClient:
    setting = await get_setting(session)
    if not setting:
        raise HTTPException(status_code=400, detail="GitLab server and token are not configured yet.")
    return GitLabClient(setting.gitlab_server, setting.api_token)


@app.get("/api/config", response_model=SettingRead)
async def read_config(session: AsyncSession = Depends(get_session)) -> SettingRead:
    setting = await get_setting(session)
    if not setting:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return SettingRead.from_orm(setting)


@app.post("/api/config", response_model=SettingRead)
async def update_config(data: SettingCreate, session: AsyncSession = Depends(get_session)) -> SettingRead:
    setting = await upsert_setting(session, data.gitlab_server, data.api_token)
    return SettingRead.from_orm(setting)


@app.post("/api/repos", response_model=List[RepositoryRead])
async def sync_repositories(
    project_ids: List[int], session: AsyncSession = Depends(get_session)
) -> List[RepositoryRead]:
    client = await get_client(session)
    repos: List[RepositoryRead] = []
    for project_id in project_ids:
        project = await client.fetch_project(project_id)
        repo = await upsert_repository(session, project)
        repos.append(RepositoryRead.from_orm(repo))
    return repos


@app.get("/api/repos", response_model=List[RepositoryRead])
async def read_repositories(session: AsyncSession = Depends(get_session)) -> List[RepositoryRead]:
    repos = await list_repositories(session)
    return [RepositoryRead.from_orm(repo) for repo in repos]


@app.post("/api/issues/refresh", response_model=IssueSearchResponse)
async def refresh_issues(request: RefreshRequest, session: AsyncSession = Depends(get_session)) -> IssueSearchResponse:
    client = await get_client(session)
    for project_id in request.project_ids:
        repo_list = [r for r in await list_repositories(session) if r.id == project_id]
        repo = repo_list[0] if repo_list else None
        created_after: Optional[datetime] = None
        if request.fetch_newer_only and repo and repo.last_issue_created_at:
            created_after = repo.last_issue_created_at
        issues = await client.fetch_issues(project_id, created_after=created_after)
        newest = None
        if issues:
            newest_created = max(issue.get("created_at") for issue in issues)
            newest = datetime.fromisoformat(newest_created.replace("Z", "+00:00")) if newest_created else None
        await save_issues(session, project_id, issues, newest)
    issues, summary = await search_issues(session, request.project_ids)
    return IssueSearchResponse(issues=issues, assignee_summary=summary)


@app.get("/api/issues", response_model=IssueSearchResponse)
async def get_issues(
    project_ids: str = Query(..., description="Comma separated project ids"),
    query: Optional[str] = None,
    author: Optional[str] = None,
    assignee: Optional[str] = None,
    label: Optional[str] = None,
    category: Optional[str] = None,
    note: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
) -> IssueSearchResponse:
    project_list = [int(pid) for pid in project_ids.split(",") if pid]
    issues, summary = await search_issues(session, project_list, query, author, assignee, label, category, note)
    return IssueSearchResponse(issues=issues, assignee_summary=summary)


@app.patch("/api/issues/{issue_id}", response_model=IssueRead)
async def patch_issue(
    issue_id: int, payload: IssueUpdate, session: AsyncSession = Depends(get_session)
) -> IssueRead:
    issue = await update_issue_fields(session, issue_id, payload.dict(exclude_unset=True))
    return issue


@app.post("/api/issues/bulk-close")
async def bulk_close(request: BulkCloseRequest, session: AsyncSession = Depends(get_session)) -> Dict[str, str]:
    client = await get_client(session)
    result = await session.execute(select(Issue).where(Issue.id.in_(request.issue_ids)))
    issues = list(result.scalars())
    for issue in issues:
        await client.close_issue(issue.project_id, issue.iid)
    await mark_issues_closed(session, request.issue_ids)
    return {"status": "closed", "count": len(request.issue_ids)}


@app.get("/api/issues/export")
async def export_issues(
    project_ids: str,
    session: AsyncSession = Depends(get_session),
    query: Optional[str] = None,
    author: Optional[str] = None,
    assignee: Optional[str] = None,
    label: Optional[str] = None,
    category: Optional[str] = None,
    note: Optional[str] = None,
):
    project_list = [int(pid) for pid in project_ids.split(",") if pid]
    issues, _ = await search_issues(session, project_list, query, author, assignee, label, category, note)
    df = pd.DataFrame(
        [
            {
                "ID": issue.id,
                "Project": issue.project_id,
                "IID": issue.iid,
                "Title": issue.title,
                "Author": issue.author,
                "Assignee": issue.assignee,
                "Labels": ", ".join(issue.labels or []),
                "State": issue.state,
                "Category": issue.category or "",
                "Note": issue.note or "",
                "Created": issue.created_at,
                "Updated": issue.updated_at,
                "URL": issue.web_url,
            }
            for issue in issues
        ]
    )
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    headers = {"Content-Disposition": "attachment; filename=issues.xlsx"}
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@app.get("/api/commit-stats", response_model=CommitStatsResponse)
async def get_commit_stats(
    project_ids: str,
    weeks: int = 8,
    session: AsyncSession = Depends(get_session),
) -> CommitStatsResponse:
    project_list = [int(pid) for pid in project_ids.split(",") if pid]
    client = await get_client(session)
    since = datetime.utcnow() - timedelta(weeks=weeks)
    until = datetime.utcnow()
    stats_map: Dict[str, CommitStat] = {}
    for project_id in project_list:
        commits = await client.fetch_commits(project_id, since=since, until=until, with_stats=True)
        for commit in commits:
            committed_date = commit.get("committed_date") or commit.get("created_at")
            if not committed_date:
                continue
            dt = datetime.fromisoformat(committed_date.replace("Z", "+00:00"))
            week_label = f"{dt.isocalendar().year}-W{dt.isocalendar().week:02d}"
            author_name = commit.get("author_name", "Unknown")
            key = f"{author_name}-{week_label}"
            additions = deletions = 0
            stats = commit.get("stats")
            if isinstance(stats, dict):
                additions = stats.get("additions", 0)
                deletions = stats.get("deletions", 0)
            if key not in stats_map:
                stats_map[key] = CommitStat(
                    week=week_label,
                    author=author_name,
                    commits=1,
                    additions=additions,
                    deletions=deletions,
                )
            else:
                existing = stats_map[key]
                existing.commits += 1
                existing.additions += additions
                existing.deletions += deletions
    return CommitStatsResponse(stats=list(stats_map.values()))
