from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class SettingCreate(BaseModel):
    gitlab_server: str
    api_token: str


class SettingRead(SettingCreate):
    id: int

    class Config:
        orm_mode = True


class RepositoryCreate(BaseModel):
    id: int
    name: str
    path_with_namespace: str


class RepositoryRead(RepositoryCreate):
    last_issue_created_at: Optional[datetime]

    class Config:
        orm_mode = True


class IssueUpdate(BaseModel):
    note: Optional[str] = None
    category: Optional[str] = None


class IssueRead(BaseModel):
    id: int
    project_id: int
    iid: int
    title: str
    description: Optional[str]
    state: str
    labels: Optional[List[str]]
    author: Optional[str]
    assignee: Optional[str]
    assignee_id: Optional[int]
    web_url: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    note: Optional[str]
    category: Optional[str]

    class Config:
        orm_mode = True


class IssueSearchResponse(BaseModel):
    issues: List[IssueRead]
    assignee_summary: Dict[str, int] = Field(default_factory=dict)


class RefreshRequest(BaseModel):
    project_ids: List[int]
    fetch_newer_only: bool = True


class BulkCloseRequest(BaseModel):
    issue_ids: List[int]


class CommitStat(BaseModel):
    week: str
    author: str
    commits: int
    additions: int
    deletions: int


class CommitStatsResponse(BaseModel):
    stats: List[CommitStat]
