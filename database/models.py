from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default='user', nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Deployment(Base):
    __tablename__ = 'deployments'
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    namespace = Column(String, index=True, nullable=False)
    image = Column(String, nullable=False)
    port = Column(Integer, default=80)
    replicas = Column(Integer, default=1)
    ingress_host = Column(String)
    url = Column(String)
    status = Column(String, default='pending')
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
