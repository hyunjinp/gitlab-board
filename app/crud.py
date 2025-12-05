from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Issue, Repository, Setting


def _parse_datetime(raw_value: Optional[str]) -> Optional[datetime]:
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def upsert_setting(session: AsyncSession, server: str, token: str) -> Setting:
    result = await session.execute(select(Setting).limit(1))
    setting = result.scalar_one_or_none()
    if setting:
        setting.gitlab_server = server
        setting.api_token = token
    else:
        setting = Setting(gitlab_server=server, api_token=token)
        session.add(setting)
    await session.commit()
    await session.refresh(setting)
    return setting


async def get_setting(session: AsyncSession) -> Optional[Setting]:
    result = await session.execute(select(Setting).limit(1))
    return result.scalar_one_or_none()


async def upsert_repository(session: AsyncSession, repo_data: Dict) -> Repository:
    repo_id = repo_data["id"]
    result = await session.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if repo:
        repo.name = repo_data.get("name", repo.name)
        repo.path_with_namespace = repo_data.get("path_with_namespace", repo.path_with_namespace)
    else:
        repo = Repository(
            id=repo_id,
            name=repo_data.get("name", str(repo_id)),
            path_with_namespace=repo_data.get("path_with_namespace", str(repo_id)),
        )
        session.add(repo)
    await session.commit()
    await session.refresh(repo)
    return repo


async def list_repositories(session: AsyncSession) -> List[Repository]:
    result = await session.execute(select(Repository))
    return list(result.scalars())


async def save_issues(
    session: AsyncSession, project_id: int, issues: Iterable[Dict], newest_created_at: Optional[datetime]
) -> None:
    for issue_data in issues:
        result = await session.execute(
            select(Issue).where(and_(Issue.project_id == project_id, Issue.iid == issue_data["iid"]))
        )
        issue = result.scalar_one_or_none()
        if issue:
            issue.title = issue_data.get("title", issue.title)
            issue.description = issue_data.get("description", issue.description)
            issue.state = issue_data.get("state", issue.state)
            issue.labels = issue_data.get("labels", issue.labels)
            issue.author = (issue_data.get("author") or {}).get("name")
            assignee = issue_data.get("assignee")
            issue.assignee = (assignee or {}).get("name") if assignee else None
            issue.assignee_id = (assignee or {}).get("id") if assignee else None
            issue.web_url = issue_data.get("web_url", issue.web_url)
            issue.created_at = _parse_datetime(issue_data.get("created_at"))
            issue.updated_at = _parse_datetime(issue_data.get("updated_at"))
        else:
            assignee = issue_data.get("assignee")
            issue = Issue(
                project_id=project_id,
                iid=issue_data["iid"],
                title=issue_data.get("title", ""),
                description=issue_data.get("description"),
                state=issue_data.get("state", ""),
                labels=issue_data.get("labels"),
                author=(issue_data.get("author") or {}).get("name"),
                assignee=(assignee or {}).get("name") if assignee else None,
                assignee_id=(assignee or {}).get("id") if assignee else None,
                web_url=issue_data.get("web_url"),
                created_at=_parse_datetime(issue_data.get("created_at")),
                updated_at=_parse_datetime(issue_data.get("updated_at")),
            )
            session.add(issue)
    if newest_created_at:
        await session.execute(
            update(Repository)
            .where(Repository.id == project_id)
            .values(last_issue_created_at=newest_created_at)
        )
    await session.commit()


async def search_issues(
    session: AsyncSession,
    project_ids: List[int],
    query: Optional[str] = None,
    author: Optional[str] = None,
    assignee: Optional[str] = None,
    label: Optional[str] = None,
    category: Optional[str] = None,
    note: Optional[str] = None,
) -> Tuple[List[Issue], Dict[str, int]]:
    stmt = select(Issue).where(Issue.project_id.in_(project_ids))
    if query:
        like = f"%{query}%"
        stmt = stmt.where(
            or_(
                Issue.title.ilike(like),
                Issue.description.ilike(like),
            )
        )
    if author:
        stmt = stmt.where(Issue.author == author)
    if assignee:
        stmt = stmt.where(Issue.assignee == assignee)
    if label:
        stmt = stmt.where(func.json_contains(Issue.labels, f'"{label}"'))
    if category:
        stmt = stmt.where(Issue.category == category)
    if note:
        stmt = stmt.where(Issue.note.ilike(f"%{note}%"))
    result = await session.execute(stmt.order_by(Issue.created_at.desc()))
    issues = list(result.scalars())

    summary_stmt = (
        select(Issue.assignee, func.count(Issue.id))
        .where(Issue.project_id.in_(project_ids))
        .group_by(Issue.assignee)
    )
    summary_result = await session.execute(summary_stmt)
    summary = {row[0] or "Unassigned": row[1] for row in summary_result}
    return issues, summary


async def update_issue_fields(session: AsyncSession, issue_id: int, data: Dict) -> Issue:
    result = await session.execute(select(Issue).where(Issue.id == issue_id))
    issue = result.scalar_one_or_none()
    if not issue:
        raise ValueError("Issue not found")
    issue.note = data.get("note", issue.note)
    issue.category = data.get("category", issue.category)
    await session.commit()
    await session.refresh(issue)
    return issue


async def mark_issues_closed(session: AsyncSession, issue_ids: List[int]) -> None:
    await session.execute(update(Issue).where(Issue.id.in_(issue_ids)).values(state="closed"))
    await session.commit()
