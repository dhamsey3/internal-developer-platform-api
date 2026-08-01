import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default='user', nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Destination(Base):
    __tablename__ = "destinations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    kind = Column(String, index=True, nullable=False)
    provider = Column(String, index=True, nullable=False)
    environment = Column(String, default="development", nullable=False)
    status = Column(String, default="setup_required", nullable=False)
    config = Column(JSON, default=dict)
    capabilities = Column(JSON, default=list)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_application_owner_name"),)
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, index=True, nullable=False)
    destination_id = Column(Integer, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    description = Column(Text)
    source_type = Column(String, nullable=False)
    repository_url = Column(String)
    image = Column(String)
    port = Column(Integer, default=80)
    environment = Column(String, default="development", nullable=False)
    status = Column(String, default="registered", nullable=False)
    resource_requests = Column(JSON, default=list)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class Deployment(Base):
    __tablename__ = 'deployments'
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    namespace = Column(String, index=True, nullable=False)
    image = Column(String, nullable=False)
    port = Column(Integer, default=80)
    container_port = Column(Integer, default=80)
    replicas = Column(Integer, default=1)
    ingress_host = Column(String)
    url = Column(String)
    status = Column(String, default='pending')
    expires_at = Column(DateTime)
    is_sandbox = Column(Boolean, default=False, nullable=False)
    metadata_json = Column(JSON, default=dict)
    last_error = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class Infrastructure(Base):
    __tablename__ = 'infrastructure'
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    cloud_provider = Column(String, default='aws')
    config = Column(JSON, default=dict)
    status = Column(String, default='provisioning')
    last_error = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
