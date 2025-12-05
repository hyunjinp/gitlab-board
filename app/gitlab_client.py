from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx


class GitLabClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.headers = {"PRIVATE-TOKEN": token}

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        """Return an ISO-8601 string GitLab accepts for time filters."""

        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()

    async def _get(self, url: str, params: Optional[Dict] = None) -> httpx.Response:
        async with httpx.AsyncClient(headers=self.headers) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response

    async def _post(self, url: str, data: Optional[Dict] = None) -> httpx.Response:
        async with httpx.AsyncClient(headers=self.headers) as client:
            response = await client.post(url, data=data)
            response.raise_for_status()
            return response

    async def _put(self, url: str, data: Optional[Dict] = None) -> httpx.Response:
        async with httpx.AsyncClient(headers=self.headers) as client:
            response = await client.put(url, data=data)
            response.raise_for_status()
            return response

    async def fetch_project(self, project_id: int) -> Dict:
        url = f"{self.base_url}/api/v4/projects/{project_id}"
        response = await self._get(url)
        return response.json()

    async def fetch_issues(
        self, project_id: int, created_after: Optional[datetime] = None, page_size: int = 100
    ) -> List[Dict]:
        url = f"{self.base_url}/api/v4/projects/{project_id}/issues"
        params: Dict = {"scope": "all", "per_page": page_size, "order_by": "created_at", "sort": "asc"}
        if created_after:
            params["created_after"] = created_after.isoformat()
        issues: List[Dict] = []
        page = 1
        while True:
            params["page"] = page
            response = await self._get(url, params=params)
            batch = response.json()
            if not batch:
                break
            issues.extend(batch)
            if len(batch) < page_size:
                break
            page += 1
        return issues

    async def close_issue(self, project_id: int, issue_iid: int) -> None:
        url = f"{self.base_url}/api/v4/projects/{project_id}/issues/{issue_iid}"
        await self._put(url, data={"state_event": "close"})

    async def fetch_commits(
        self,
        project_id: int,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        with_stats: bool = True,
        page_size: int = 100,
    ) -> List[Dict]:
        url = f"{self.base_url}/api/v4/projects/{project_id}/repository/commits"
        params: Dict = {"per_page": page_size, "all": True}
        if since:
            params["since"] = self._format_datetime(since)
        if until:
            params["until"] = self._format_datetime(until)
        if with_stats:
            params["with_stats"] = True
        commits: List[Dict] = []
        page = 1
        while True:
            params["page"] = page
            response = await self._get(url, params=params)
            batch = response.json()
            if not batch:
                break
            commits.extend(batch)
            if len(batch) < page_size:
                break
            page += 1
        return commits
