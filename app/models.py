from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship

from .database import Base


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, default=1)
    gitlab_server = Column(String(255), nullable=False)
    api_token = Column(String(255), nullable=False)


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    path_with_namespace = Column(String(255), nullable=False)
    last_issue_created_at = Column(DateTime(timezone=True))

    issues = relationship("Issue", back_populates="repository")


class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (UniqueConstraint("project_id", "iid", name="uniq_project_issue"),)

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    iid = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    state = Column(String(50), nullable=False)
    labels = Column(JSON)
    author = Column(String(255))
    assignee = Column(String(255))
    assignee_id = Column(Integer)
    web_url = Column(String(255))
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    note = Column(Text)
    category = Column(String(100))

    repository = relationship("Repository", back_populates="issues")


class IssueHistory(Base):
    __tablename__ = "issue_history"

    id = Column(Integer, primary_key=True)
    issue_id = Column(Integer, nullable=False)
    action = Column(String(50), nullable=False)
    performed_at = Column(DateTime(timezone=True), server_default=func.now())
    performed_by = Column(String(255))
