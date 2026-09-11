from __future__ import annotations

import os
import socket
import ipaddress
import concurrent.futures
import base64
import re
import hashlib
import hmac
import secrets
import csv
import io
import json
import logging
import threading
import time
import uuid
import resource
import subprocess
import shutil
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from contextvars import ContextVar
from cryptography.fernet import Fernet, InvalidToken
import unicodedata
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Float,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./eduvigia.db")
DB_POOL_SIZE = max(2, int(os.getenv("EDUVIGIA_DB_POOL_SIZE", "10")))
DB_MAX_OVERFLOW = max(0, int(os.getenv("EDUVIGIA_DB_MAX_OVERFLOW", "20")))
DB_POOL_TIMEOUT_SECONDS = max(5, int(os.getenv("EDUVIGIA_DB_POOL_TIMEOUT_SECONDS", "30")))
DB_POOL_RECYCLE_SECONDS = max(60, int(os.getenv("EDUVIGIA_DB_POOL_RECYCLE_SECONDS", "1800")))

_engine_options = {"pool_pre_ping": True}
if DATABASE_URL.startswith("postgresql"):
    _engine_options.update(
        pool_size=DB_POOL_SIZE,
        max_overflow=DB_MAX_OVERFLOW,
        pool_timeout=DB_POOL_TIMEOUT_SECONDS,
        pool_recycle=DB_POOL_RECYCLE_SECONDS,
    )
engine = create_engine(DATABASE_URL, **_engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class School(Base):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str | None] = mapped_column(String(40), nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(300))
    neighborhood: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    latitude: Mapped[str | None] = mapped_column(String(40), nullable=True)
    longitude: Mapped[str | None] = mapped_column(String(40), nullable=True)
    kit_type: Mapped[str] = mapped_column(String(20), default="KIT_01")
    responsible: Mapped[str | None] = mapped_column(String(160), nullable=True)
    operational_status: Mapped[str] = mapped_column(String(30), default="IMPLANTACAO")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Recorder(Base):
    __tablename__ = "recorders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(180))
    manufacturer: Mapped[str] = mapped_column(String(80), default="Hikvision")
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(64))
    http_port: Mapped[int] = mapped_column(Integer, default=80)
    https_port: Mapped[int] = mapped_column(Integer, default=443)
    rtsp_port: Mapped[int] = mapped_column(Integer, default=554)
    sdk_port: Mapped[int] = mapped_column(Integer, default=8000)
    username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    password: Mapped[str | None] = mapped_column(String(180), nullable=True)
    channel_count: Mapped[int] = mapped_column(Integer, default=16)
    firmware: Mapped[str | None] = mapped_column(String(120), nullable=True)
    firmware_released_date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    mac_address: Mapped[str | None] = mapped_column(String(40), nullable=True)
    discovered_channel_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_discovery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class VideoDevice(Base):
    __tablename__ = "video_devices"
    __table_args__ = (UniqueConstraint("school_id", "ip_address", "rtsp_port", name="uq_video_devices_school_ip_rtsp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    manufacturer: Mapped[str] = mapped_column(String(80), default="Hikvision")
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(64))
    http_port: Mapped[int] = mapped_column(Integer, default=80)
    https_port: Mapped[int] = mapped_column(Integer, default=443)
    rtsp_port: Mapped[int] = mapped_column(Integer, default=554)
    username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    password: Mapped[str | None] = mapped_column(String(180), nullable=True)
    device_type: Mapped[str] = mapped_column(String(40), default="CAMERA")
    channel_count: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str | None] = mapped_column(String(40), nullable=True, unique=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160))
    location: Mapped[str] = mapped_column(String(160))
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    port: Mapped[int] = mapped_column(Integer, default=554)
    username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    password: Mapped[str | None] = mapped_column(String(180), nullable=True)
    manufacturer: Mapped[str] = mapped_column(String(80), default="Hikvision")
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    camera_type: Mapped[str] = mapped_column(String(40), default="FIXA")
    rtsp_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    rtsp_url_main: Mapped[str | None] = mapped_column(String(600), nullable=True)
    rtsp_url_sub: Mapped[str | None] = mapped_column(String(600), nullable=True)
    stream_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    main_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    sub_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    is_totem_camera: Mapped[bool] = mapped_column(Boolean, default=False)
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stream_profile: Mapped[str] = mapped_column(String(20), default="MAIN")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_frame_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_type: Mapped[str] = mapped_column(String(30), default="CAMERA_IP")
    device_id: Mapped[int | None] = mapped_column(ForeignKey("video_devices.id", ondelete="SET NULL"), nullable=True, index=True)
    logical_channel: Mapped[int] = mapped_column(Integer, default=1)
    sensor_type: Mapped[str] = mapped_column(String(30), default="VISIBLE")
    sensor_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    primary_sensor: Mapped[bool] = mapped_column(Boolean, default=True)
    recorder_id: Mapped[int | None] = mapped_column(ForeignKey("recorders.id", ondelete="SET NULL"), nullable=True)
    nvr_channel: Mapped[int] = mapped_column(Integer, default=1)
    stream_name_main: Mapped[str | None] = mapped_column(String(140), nullable=True)
    stream_name_sub: Mapped[str | None] = mapped_column(String(140), nullable=True)
    rtsp_path_main: Mapped[str | None] = mapped_column(String(600), nullable=True)
    rtsp_path_sub: Mapped[str | None] = mapped_column(String(600), nullable=True)
    codec: Mapped[str | None] = mapped_column(String(30), nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(40), nullable=True)
    fps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    main_codec: Mapped[str | None] = mapped_column(String(30), nullable=True)
    main_resolution: Mapped[str | None] = mapped_column(String(40), nullable=True)
    main_fps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    main_bitrate_kbps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sub_codec: Mapped[str | None] = mapped_column(String(30), nullable=True)
    sub_resolution: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sub_fps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sub_bitrate_kbps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ptz_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ptz_protocol: Mapped[str] = mapped_column(String(30), default="HIKVISION_ISAPI")
    ptz_http_port: Mapped[int] = mapped_column(Integer, default=80)
    ptz_https: Mapped[bool] = mapped_column(Boolean, default=False)
    ptz_channel: Mapped[int] = mapped_column(Integer, default=1)
    ptz_last_command_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ptz_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int | None] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True
    )
    camera_id: Mapped[int | None] = mapped_column(
        ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True, index=True
    )
    school_name: Mapped[str] = mapped_column(String(200))
    camera_name: Mapped[str] = mapped_column(String(160))
    event_type: Mapped[str] = mapped_column(String(120))
    priority: Mapped[str] = mapped_column(String(20), default="MEDIA")
    status: Mapped[str] = mapped_column(String(30), default="NOVO")
    source: Mapped[str] = mapped_column(String(30), default="SISTEMA")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    evidence_path: Mapped[str | None] = mapped_column(String(700), nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assigned_user_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event_occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AlertActivity(Base):
    __tablename__ = "alert_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[int] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(60))
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_name: Mapped[str] = mapped_column(String(160), default="Sistema")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


class CameraEvent(Base):
    __tablename__ = "camera_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), index=True
    )
    camera_id: Mapped[int | None] = mapped_column(
        ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True, index=True
    )
    recorder_id: Mapped[int | None] = mapped_column(
        ForeignKey("recorders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(40), default="GENERIC")
    provider_event_type: Mapped[str] = mapped_column(String(160))
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    event_state: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    severity: Mapped[str] = mapped_column(String(20), default="MEDIA")
    correlation_key: Mapped[str] = mapped_column(String(240), index=True)
    event_uid: Mapped[str | None] = mapped_column(String(180), nullable=True, unique=True)
    source_channel: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    repeat_count: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    alert_id: Mapped[int | None] = mapped_column(
        ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class CameraHealth(Base):
    __tablename__ = "camera_health"
    __table_args__ = (UniqueConstraint("camera_id", name="uq_camera_health_camera"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("cameras.id", ondelete="CASCADE"), index=True
    )
    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), index=True
    )
    state: Mapped[str] = mapped_column(String(20), default="UNKNOWN", index=True)
    rtsp_online: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    main_online: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    sub_online: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    recording_status: Mapped[str] = mapped_column(String(30), default="UNKNOWN")
    storage_status: Mapped[str] = mapped_column(String(30), default="UNKNOWN")
    tamper_active: Mapped[bool] = mapped_column(Boolean, default=False)
    motion_active: Mapped[bool] = mapped_column(Boolean, default=False)
    ntp_offset_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bitrate_kbps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(40), nullable=True)
    codec: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_video_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class RecorderHealth(Base):
    __tablename__ = "recorder_health"
    __table_args__ = (UniqueConstraint("recorder_id", name="uq_recorder_health_recorder"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recorder_id: Mapped[int] = mapped_column(
        ForeignKey("recorders.id", ondelete="CASCADE"), index=True
    )
    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), index=True
    )
    state: Mapped[str] = mapped_column(String(20), default="UNKNOWN", index=True)
    recording_status: Mapped[str] = mapped_column(String(30), default="UNKNOWN")
    storage_status: Mapped[str] = mapped_column(String(30), default="UNKNOWN")
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Occurrence(Base):
    __tablename__ = "occurrences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    protocol: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    school_id: Mapped[int | None] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True
    )
    school_name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40), default="SEGURANCA")
    priority: Mapped[str] = mapped_column(String(20), default="MEDIA")
    status: Mapped[str] = mapped_column(String(30), default="ABERTA")
    description: Mapped[str] = mapped_column(Text)
    assigned_team: Mapped[str | None] = mapped_column(String(160), nullable=True)
    alert_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OccurrenceSequence(Base):
    __tablename__ = "occurrence_sequences"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, default=0)


class DispatchTeam(Base):
    __tablename__ = "dispatch_teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    team_type: Mapped[str] = mapped_column(String(60), default="INTERNA")
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="DISPONIVEL")
    current_occurrence_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class OccurrenceEvent(Base):
    __tablename__ = "occurrence_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    occurrence_id: Mapped[int] = mapped_column(
        ForeignKey("occurrences.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(Text)
    user_name: Mapped[str] = mapped_column(String(120), default="Operador Local")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )



class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int | None] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"), nullable=True
    )
    category: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(160))
    manufacturer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    asset_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location: Mapped[str | None] = mapped_column(String(180), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="OPERACIONAL")
    installed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    warranty_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), index=True
    )
    maintenance_type: Mapped[str] = mapped_column(String(50), default="PREVENTIVA")
    description: Mapped[str] = mapped_column(Text)
    technician: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="ABERTA")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(String(240), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )



class UserAccount(Base):
    __tablename__ = "user_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(40), default="OPERADOR_GUARDA")
    school_id: Mapped[int | None] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="CASCADE"), index=True
    )
    token: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )



class CameraFavorite(Base):
    __tablename__ = "camera_favorites"
    __table_args__ = (UniqueConstraint("user_id", "camera_id", name="uq_camera_favorites_user_camera"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="CASCADE"), index=True
    )
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("cameras.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class VideoWallLayout(Base):
    __tablename__ = "video_wall_layouts"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_video_wall_layouts_user_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_accounts.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    grid_size: Mapped[int] = mapped_column(Integer, default=4)
    quality_mode: Mapped[str] = mapped_column(String(10), default="AUTO")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class VideoWallSlot(Base):
    __tablename__ = "video_wall_slots"
    __table_args__ = (UniqueConstraint("layout_id", "slot_index", name="uq_video_wall_slots_layout_slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    layout_id: Mapped[int] = mapped_column(ForeignKey("video_wall_layouts.id", ondelete="CASCADE"), index=True)
    slot_index: Mapped[int] = mapped_column(Integer)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class FloorPlan(Base):
    __tablename__ = "floor_plans"
    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_floor_plans_school_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    building: Mapped[str | None] = mapped_column(String(120), nullable=True)
    floor_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    filename: Mapped[str] = mapped_column(String(220))
    original_name: Mapped[str | None] = mapped_column(String(260), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(80))
    file_path: Mapped[str] = mapped_column(String(700))
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class FloorPlanCamera(Base):
    __tablename__ = "floor_plan_cameras"
    __table_args__ = (UniqueConstraint("floor_plan_id", "camera_id", name="uq_floor_plan_camera"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    floor_plan_id: Mapped[int] = mapped_column(ForeignKey("floor_plans.id", ondelete="CASCADE"), index=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    x_percent: Mapped[float] = mapped_column(Float)
    y_percent: Mapped[float] = mapped_column(Float)
    rotation_deg: Mapped[float] = mapped_column(Float, default=0.0)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class CameraPTZLease(Base):
    __tablename__ = "camera_ptz_leases"
    __table_args__ = (UniqueConstraint("camera_id", name="uq_camera_ptz_leases_camera"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_accounts.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class CameraPTZPreset(Base):
    __tablename__ = "camera_ptz_presets"
    __table_args__ = (UniqueConstraint("camera_id", "preset_no", name="uq_camera_ptz_presets_camera_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    preset_no: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(120))
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    school_id: Mapped[int | None] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(180))
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default="INFO")
    module: Mapped[str] = mapped_column(String(80), default="Sistema")
    entity_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class NotificationRead(Base):
    __tablename__ = "notification_reads"
    __table_args__ = (UniqueConstraint("notification_id", "user_id", name="uq_notification_reads_notification_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notification_id: Mapped[int] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="CASCADE"), index=True
    )
    read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    occurrence_id: Mapped[int | None] = mapped_column(
        ForeignKey("occurrences.id", ondelete="SET NULL"), nullable=True, index=True
    )
    school_id: Mapped[int | None] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True
    )
    camera_id: Mapped[int | None] = mapped_column(
        ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True, index=True
    )
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("video_devices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    logical_channel: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sensor_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    evidence_type: Mapped[str] = mapped_column(String(40), default="SNAPSHOT")
    filename: Mapped[str] = mapped_column(String(240))
    original_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(100), default="image/jpeg")
    file_path: Mapped[str] = mapped_column(String(600))
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_origin: Mapped[str | None] = mapped_column(String(40), nullable=True)
    integrity_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    observation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(160), default="Operador Local")
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class EvidenceCustodyEvent(Base):
    __tablename__ = "evidence_custody_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(40))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True)
    user_name: Mapped[str] = mapped_column(String(160), default="Sistema")
    sha256_observed: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


class SupportRequest(Base):
    __tablename__ = "support_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    protocol: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(180))
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    category: Mapped[str] = mapped_column(String(60), default="ACESSO")
    subject: Mapped[str] = mapped_column(String(220))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="ABERTO")
    source: Mapped[str] = mapped_column(String(40), default="LOGIN")
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_name: Mapped[str] = mapped_column(String(120), default="Sistema")
    user_email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    user_role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    school_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    module: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(120))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    outcome: Mapped[str] = mapped_column(String(30), default="SUCCESS")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )










class SchoolIn(BaseModel):
    code: str | None = None
    name: str = Field(min_length=2, max_length=200)
    address: str = Field(min_length=3, max_length=300)
    neighborhood: str | None = None
    city: str | None = None
    phone: str | None = None
    email: str | None = None
    latitude: str | None = None
    longitude: str | None = None
    kit_type: Literal[
        "KIT_01", "KIT_02", "KIT_03", "KIT_04", "KIT_05", "KIT_06", "KIT_07", "KIT_08",
        "KIT_09", "KIT_10", "KIT_11", "KIT_12", "KIT_13", "KIT_14", "KIT_15", "KIT_16"
    ] = "KIT_01"
    responsible: str | None = None
    operational_status: Literal["IMPLANTACAO", "OPERACIONAL", "MANUTENCAO", "INATIVA"] = "IMPLANTACAO"
    notes: str | None = None


class SchoolOut(SchoolIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    active: bool
    created_at: datetime


class RecorderIn(BaseModel):
    school_id: int
    name: str = Field(min_length=2, max_length=180)
    manufacturer: str = "Hikvision"
    model: str | None = None
    serial_number: str | None = None
    ip_address: str
    http_port: int = 80
    https_port: int = 443
    rtsp_port: int = 554
    sdk_port: int = 8000
    username: str | None = None
    password: str | None = None
    channel_count: int = Field(default=16, ge=1, le=256)
    firmware: str | None = None
    firmware_released_date: str | None = None
    device_type: str | None = None
    mac_address: str | None = None
    notes: str | None = None


class RecorderOut(RecorderIn):
    model_config = ConfigDict(from_attributes=True)
    password: str | None = Field(default=None, exclude=True)
    id: int
    status: str
    last_check_at: datetime | None = None
    last_error: str | None = None
    discovered_channel_count: int | None = None
    last_discovery_at: datetime | None = None
    active: bool
    created_at: datetime


class VideoDeviceIn(BaseModel):
    school_id: int
    name: str = Field(min_length=2, max_length=180)
    manufacturer: str = "Hikvision"
    model: str | None = None
    serial_number: str | None = None
    ip_address: str
    http_port: int = Field(default=80, ge=0, le=65535)
    https_port: int = Field(default=443, ge=0, le=65535)
    rtsp_port: int = Field(default=554, ge=1, le=65535)
    username: str | None = None
    password: str | None = None
    device_type: Literal["CAMERA", "BISPECTRUM", "MULTISENSOR"] = "CAMERA"
    channel_count: int = Field(default=1, ge=1, le=32)


class VideoDeviceOut(VideoDeviceIn):
    model_config = ConfigDict(from_attributes=True)
    password: str | None = Field(default=None, exclude=True)
    id: int
    status: str
    last_check_at: datetime | None = None
    last_error: str | None = None
    active: bool = True
    created_at: datetime


class VideoDeviceAdoptIn(BaseModel):
    device_type: Literal["CAMERA", "BISPECTRUM", "MULTISENSOR"] = "BISPECTRUM"
    sensor_type: Literal["VISIBLE", "THERMAL", "FUSION", "GENERIC"] = "VISIBLE"
    sensor_label: str | None = Field(default=None, max_length=120)
    logical_channel: int = Field(default=1, ge=1, le=32)


class VideoDeviceChannelIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    location: str = Field(min_length=2, max_length=160)
    logical_channel: int = Field(ge=1, le=32)
    sensor_type: Literal["VISIBLE", "THERMAL", "FUSION", "GENERIC"] = "VISIBLE"
    sensor_label: str | None = Field(default=None, max_length=120)
    primary_sensor: bool = False
    camera_type: Literal["FIXA", "DOME", "BULLET", "PTZ", "TERMICA"] = "FIXA"
    main_codec: str | None = "H.264"
    main_resolution: str | None = None
    main_fps: int | None = Field(default=None, ge=1, le=60)
    main_bitrate_kbps: int | None = Field(default=None, ge=64, le=100000)
    sub_codec: str | None = "H.264"
    sub_resolution: str | None = None
    sub_fps: int | None = Field(default=None, ge=1, le=60)
    sub_bitrate_kbps: int | None = Field(default=None, ge=32, le=50000)
    ptz_enabled: bool = False


class VideoDeviceChannelsIn(BaseModel):
    channels: list[VideoDeviceChannelIn] = Field(min_length=1, max_length=32)


class CameraIn(BaseModel):
    school_id: int
    name: str = Field(min_length=2, max_length=160)
    location: str = Field(min_length=2, max_length=160)
    ip_address: str | None = None
    port: int = 554
    username: str | None = None
    password: str | None = None
    manufacturer: str = "Hikvision"
    model: str | None = None
    camera_type: Literal["FIXA", "DOME", "BULLET", "PTZ", "TERMICA"] = "FIXA"
    rtsp_url: str | None = None
    rtsp_url_main: str | None = None
    rtsp_url_sub: str | None = None
    stream_name: str | None = None
    is_totem_camera: bool = False
    stream_profile: Literal["MAIN", "SUB"] = "SUB"
    source_type: Literal["CAMERA_IP", "NVR", "DVR", "RTSP_CUSTOM"] = "CAMERA_IP"
    device_id: int | None = None
    logical_channel: int = Field(default=1, ge=1, le=32)
    sensor_type: Literal["VISIBLE", "THERMAL", "FUSION", "GENERIC"] = "VISIBLE"
    sensor_label: str | None = Field(default=None, max_length=120)
    primary_sensor: bool = True
    recorder_id: int | None = None
    nvr_channel: int = Field(default=1, ge=1, le=256)
    codec: str | None = None
    resolution: str | None = None
    fps: int | None = None
    main_codec: str | None = None
    main_resolution: str | None = None
    main_fps: int | None = Field(default=None, ge=1, le=60)
    main_bitrate_kbps: int | None = Field(default=None, ge=64, le=100000)
    sub_codec: str | None = None
    sub_resolution: str | None = None
    sub_fps: int | None = Field(default=None, ge=1, le=60)
    sub_bitrate_kbps: int | None = Field(default=None, ge=32, le=50000)
    ptz_enabled: bool = False
    ptz_protocol: Literal["HIKVISION_ISAPI"] = "HIKVISION_ISAPI"
    ptz_http_port: int = Field(default=80, ge=1, le=65535)
    ptz_https: bool = False
    ptz_channel: int = Field(default=1, ge=1, le=256)


class CameraOut(CameraIn):
    model_config = ConfigDict(from_attributes=True)
    code: str | None = None
    password: str | None = Field(default=None, exclude=True)
    rtsp_url: str | None = Field(default=None, exclude=True)
    rtsp_url_main: str | None = Field(default=None, exclude=True)
    rtsp_url_sub: str | None = Field(default=None, exclude=True)
    id: int
    status: str
    main_status: str = "PENDING"
    sub_status: str = "PENDING"
    last_check_at: datetime | None
    last_error: str | None = None
    last_frame_at: datetime | None = None
    stream_name_main: str | None = None
    stream_name_sub: str | None = None
    rtsp_path_main: str | None = Field(default=None, exclude=True)
    rtsp_path_sub: str | None = Field(default=None, exclude=True)
    ptz_last_command_at: datetime | None = None
    ptz_last_error: str | None = None


class PTZLeaseIn(BaseModel):
    force: bool = False


class PTZMoveIn(BaseModel):
    direction: Literal["UP", "DOWN", "LEFT", "RIGHT", "UP_LEFT", "UP_RIGHT", "DOWN_LEFT", "DOWN_RIGHT", "ZOOM_IN", "ZOOM_OUT"]
    speed: int = Field(default=4, ge=1, le=7)


class PTZPresetIn(BaseModel):
    preset_no: int = Field(ge=1, le=256)
    name: str = Field(min_length=1, max_length=120)


class CameraStatusIn(BaseModel):
    status: Literal["ONLINE", "OFFLINE", "PENDING"]


class RecorderChannelImportItem(BaseModel):
    channel: int = Field(ge=1, le=256)
    name: str | None = Field(default=None, max_length=160)
    location: str | None = Field(default=None, max_length=160)
    camera_type: Literal["FIXA", "DOME", "BULLET", "PTZ", "TERMICA"] = "FIXA"
    codec: str | None = Field(default=None, max_length=30)
    resolution: str | None = Field(default=None, max_length=40)
    fps: int | None = Field(default=None, ge=1, le=60)
    main_codec: str | None = Field(default=None, max_length=30)
    main_resolution: str | None = Field(default=None, max_length=40)
    main_fps: int | None = Field(default=None, ge=1, le=60)
    main_bitrate_kbps: int | None = Field(default=None, ge=64, le=100000)
    sub_codec: str | None = Field(default=None, max_length=30)
    sub_resolution: str | None = Field(default=None, max_length=40)
    sub_fps: int | None = Field(default=None, ge=1, le=60)
    sub_bitrate_kbps: int | None = Field(default=None, ge=32, le=50000)


class RecorderChannelImportIn(BaseModel):
    channels: list[RecorderChannelImportItem] = Field(min_length=1, max_length=64)
    update_existing: bool = False
    test_after_import: bool = False


class RecorderChannelBatchIn(BaseModel):
    channels: list[int] | None = None
    profile: Literal["MAIN", "SUB", "BOTH"] = "BOTH"
    provision: bool = True


class CameraBatchIn(BaseModel):
    camera_ids: list[int] | None = None
    provision: bool = True


class MonitoringStatusRefreshIn(BaseModel):
    camera_ids: list[int] = Field(min_length=1, max_length=16)


class VideoWallLayoutIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    grid_size: Literal[1, 4, 9, 16] = 4
    quality_mode: Literal["AUTO", "SUB", "MAIN"] = "AUTO"
    camera_ids: list[int | None] = Field(default_factory=list, max_length=16)


class FloorPlanPlacementIn(BaseModel):
    camera_id: int
    x_percent: float = Field(ge=0, le=100)
    y_percent: float = Field(ge=0, le=100)
    rotation_deg: float = Field(default=0, ge=-360, le=360)
    label: str | None = Field(default=None, max_length=120)


class FloorPlanPlacementsIn(BaseModel):
    placements: list[FloorPlanPlacementIn] = Field(default_factory=list, max_length=128)


class CameraEventIn(BaseModel):
    provider: Literal["GENERIC", "HIKVISION_ISAPI", "ONVIF", "EDUVIGIA_HEALTH"] = "GENERIC"
    provider_event_type: str = Field(min_length=1, max_length=160)
    event_state: str = Field(default="ACTIVE", max_length=40)
    school_id: int | None = None
    camera_id: int | None = None
    recorder_id: int | None = None
    source_channel: int | None = Field(default=None, ge=1, le=1024)
    occurred_at: datetime | None = None
    severity: Literal["INFO", "BAIXA", "MEDIA", "ALTA", "CRITICA"] | None = None
    event_uid: str | None = Field(default=None, max_length=180)
    metadata: dict = Field(default_factory=dict)
    raw_payload: str | None = Field(default=None, max_length=20000)


class CameraEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    school_id: int
    camera_id: int | None
    recorder_id: int | None
    provider: str
    provider_event_type: str
    event_type: str
    event_state: str
    severity: str
    source_channel: int | None
    first_seen_at: datetime
    last_seen_at: datetime
    occurred_at: datetime
    repeat_count: int
    active: bool
    alert_id: int | None
    metadata: dict = Field(default_factory=dict)


class CameraHealthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    camera_id: int
    school_id: int
    state: str
    rtsp_online: bool | None
    main_online: bool | None
    sub_online: bool | None
    recording_status: str
    storage_status: str
    tamper_active: bool
    motion_active: bool
    ntp_offset_ms: int | None
    fps: int | None
    bitrate_kbps: int | None
    resolution: str | None
    codec: str | None
    last_event_at: datetime | None
    last_seen_at: datetime | None
    last_video_at: datetime | None
    last_error: str | None
    updated_at: datetime


class RecorderHealthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    recorder_id: int
    school_id: int
    state: str
    recording_status: str
    storage_status: str
    last_event_at: datetime | None
    last_seen_at: datetime | None
    last_error: str | None
    updated_at: datetime


class CameraEventIngestOut(BaseModel):
    accepted: bool
    heartbeat: bool = False
    deduplicated: bool = False
    event_id: int | None = None
    alert_id: int | None = None
    event_type: str | None = None
    state: str | None = None
    repeat_count: int = 0


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    school_id: int | None = None
    camera_id: int | None = None
    school_name: str
    camera_name: str
    event_type: str
    priority: str
    status: str
    summary: str | None = None
    evidence_path: str | None = None
    assigned_user_id: int | None = None
    assigned_user_name: str | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    event_occurred_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None


class AlertCreateIn(BaseModel):
    school_id: int
    camera_id: int | None = None
    event_type: str = Field(min_length=3, max_length=120)
    priority: Literal["BAIXA", "MEDIA", "ALTA", "CRITICA"] = "MEDIA"
    summary: str | None = Field(default=None, max_length=500)


class AlertWorkflowIn(BaseModel):
    status: Literal["NOVO", "EM_ATENDIMENTO", "CONFIRMADO", "DESCARTADO", "ENCERRADO"]
    note: str | None = Field(default=None, max_length=1000)


class AlertAssignIn(BaseModel):
    assigned_user_id: int | None = None
    assigned_user_name: str | None = Field(default=None, max_length=160)
    note: str | None = Field(default=None, max_length=1000)


class AlertActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    alert_id: int
    action: str
    from_status: str | None = None
    to_status: str | None = None
    note: str | None = None
    user_id: int | None = None
    user_name: str
    created_at: datetime


class OccurrenceIn(BaseModel):
    school_name: str
    category: str = "SEGURANCA"
    priority: str = "MEDIA"
    description: str
    assigned_team: str | None = None


class OccurrenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    protocol: str
    school_id: int | None = None
    school_name: str
    category: str
    priority: str
    status: str
    description: str
    assigned_team: str | None
    alert_id: int | None
    created_at: datetime
    closed_at: datetime | None


class OccurrenceStatusIn(BaseModel):
    status: Literal["ABERTA", "EM_ANALISE", "DESPACHADA", "EM_ATENDIMENTO", "ENCERRADA"]
    assigned_team: str | None = None



class TeamIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    team_type: Literal["INTERNA", "DIRECAO", "GUARDA", "MANUTENCAO", "SAUDE"] = "INTERNA"
    phone: str | None = None
    notes: str | None = None


class TeamOut(TeamIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    current_occurrence_id: int | None
    active: bool
    created_at: datetime


class TeamStatusIn(BaseModel):
    status: Literal["DISPONIVEL", "ACIONADA", "EM_DESLOCAMENTO", "EM_ATENDIMENTO", "INDISPONIVEL"]


class OccurrenceEventIn(BaseModel):
    event_type: str = "OBSERVACAO"
    description: str = Field(min_length=2)


class OccurrenceEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    occurrence_id: int
    event_type: str
    description: str
    user_name: str
    created_at: datetime



class EquipmentIn(BaseModel):
    school_id: int | None = None
    category: Literal["CAMERA", "NVR", "SWITCH_POE", "TOTEM", "NOBREAK", "GATEWAY", "ROTEADOR", "SERVIDOR", "LINK", "OUTRO"]
    name: str = Field(min_length=2, max_length=160)
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    asset_number: str | None = None
    location: str | None = None
    status: Literal["OPERACIONAL", "MANUTENCAO", "OFFLINE", "ESTOQUE", "BAIXADO"] = "OPERACIONAL"
    installed_at: datetime | None = None
    warranty_until: datetime | None = None
    notes: str | None = None


class EquipmentOut(EquipmentIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class MaintenanceIn(BaseModel):
    maintenance_type: Literal["PREVENTIVA", "CORRETIVA", "INSPECAO", "TROCA"] = "PREVENTIVA"
    description: str = Field(min_length=2)
    technician: str | None = None
    status: Literal["ABERTA", "AGENDADA", "EM_EXECUCAO", "CONCLUIDA", "CANCELADA"] = "ABERTA"
    scheduled_at: datetime | None = None


class MaintenanceOut(MaintenanceIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    equipment_id: int
    completed_at: datetime | None
    created_at: datetime


class MaintenanceStatusIn(BaseModel):
    status: Literal["ABERTA", "AGENDADA", "EM_EXECUCAO", "CONCLUIDA", "CANCELADA"]


class SettingIn(BaseModel):
    value: str
    description: str | None = None


class SettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    key: str
    value: str
    description: str | None
    updated_at: datetime



class LoginIn(BaseModel):
    email: str
    password: str


class LoginOut(BaseModel):
    token: str
    expires_at: datetime
    user: dict


CANONICAL_ROLES = Literal[
    "ADMIN_SECRETARIA",
    "GESTOR_SECRETARIA",
    "SUPERVISOR_GUARDA",
    "OPERADOR_GUARDA",
    "DESPACHANTE_GUARDA",
    "GESTOR_ESCOLA",
    "OPERADOR_ESCOLA",
    "TECNICO",
]


class UserIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=180)
    password: str = Field(min_length=10, max_length=128)
    role: CANONICAL_ROLES = "OPERADOR_GUARDA"
    school_id: int | None = None
    active: bool = True


class UserUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=180)
    role: CANONICAL_ROLES
    school_id: int | None = None
    active: bool = True


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)


class PasswordResetIn(BaseModel):
    new_password: str = Field(min_length=10, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    role: str
    school_id: int | None
    active: bool
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime



class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int | None
    school_id: int | None = None
    title: str
    message: str
    severity: str
    module: str
    entity_type: str | None
    entity_id: int | None
    read_at: datetime | None
    created_at: datetime



class CameraProvisionOut(BaseModel):
    ok: bool
    stream_name: str
    rtsp_url_masked: str
    mediamtx_status: str
    detail: str


class StreamAccessOut(BaseModel):
    camera_id: int
    profile: Literal["MAIN", "SUB"]
    stream_name: str
    ready: bool
    webrtc_url: str
    hls_url: str
    expires_at: datetime


class MediaMTXAuthIn(BaseModel):
    user: str | None = None
    password: str | None = None
    ip: str | None = None
    action: str
    path: str | None = None
    protocol: str | None = None
    id: str | None = None
    query: str | None = None


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    occurrence_id: int | None
    school_id: int | None = None
    camera_id: int | None
    device_id: int | None = None
    logical_channel: int | None = None
    sensor_type: str | None = None
    evidence_type: str
    filename: str
    original_name: str | None
    mime_type: str
    sha256: str | None = None
    file_size_bytes: int | None = None
    source_start_at: datetime | None = None
    source_end_at: datetime | None = None
    source_origin: str | None = None
    integrity_status: str = "PENDING"
    observation: str | None
    created_by: str
    created_at: datetime


class PlaybackRangeIn(BaseModel):
    start_at: datetime
    end_at: datetime
    max_results: int = Field(default=100, ge=1, le=200)


class PlaybackExportIn(BaseModel):
    start_at: datetime
    end_at: datetime
    occurrence_id: int | None = None
    observation: str | None = Field(default=None, max_length=1000)


class PlaybackPreviewOut(BaseModel):
    token: str
    expires_at: datetime
    duration_seconds: int
    filename: str


class EvidenceVerifyOut(BaseModel):
    evidence_id: int
    expected_sha256: str | None
    observed_sha256: str | None
    integrity_status: Literal["VERIFIED", "MISMATCH", "MISSING"]
    checked_at: datetime


class EvidenceCustodyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    evidence_id: int
    action: str
    user_id: int | None
    user_name: str
    sha256_observed: str | None
    detail: str | None
    created_at: datetime


class SchoolDetailOut(BaseModel):
    school: SchoolOut
    cameras: list[CameraOut]
    equipment: list[EquipmentOut]
    alerts: list[AlertOut]
    occurrences: list[OccurrenceOut]
    availability_percent: float


class SupportRequestIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=180)
    phone: str | None = Field(default=None, max_length=40)
    category: Literal["ACESSO", "SENHA", "ERRO", "CAMERA", "NVR", "OUTRO"] = "ACESSO"
    subject: str = Field(min_length=3, max_length=220)
    message: str = Field(min_length=10, max_length=4000)


class SupportRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    protocol: str
    name: str
    email: str
    phone: str | None
    category: str
    subject: str
    message: str
    status: str
    source: str
    created_at: datetime


class HomologationOut(BaseModel):
    version: str
    checked_at: datetime
    application: dict
    services: dict
    video: dict
    cameras: dict
    ports: dict


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int | None = None
    user_name: str
    user_email: str | None = None
    user_role: str | None = None
    school_id: int | None = None
    module: str
    action: str
    details: str | None
    ip_address: str | None = None
    user_agent: str | None = None
    outcome: str
    created_at: datetime
















def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


AUDIT_ACTOR: ContextVar[dict | None] = ContextVar("eduvigia_audit_actor", default=None)
AUDIT_IP: ContextVar[str | None] = ContextVar("eduvigia_audit_ip", default=None)
AUDIT_USER_AGENT: ContextVar[str | None] = ContextVar("eduvigia_audit_user_agent", default=None)


def audit(
    db: Session,
    module: str,
    action: str,
    details: str | None = None,
    *,
    request: Request | None = None,
    user: UserAccount | None = None,
    user_name: str | None = None,
    outcome: str = "SUCCESS",
) -> None:
    context_actor = AUDIT_ACTOR.get() or {}
    actor_id = user.id if user else context_actor.get("id")
    actor_name = user.name if user else user_name or context_actor.get("name") or "Sistema"
    actor_email = user.email if user else context_actor.get("email")
    actor_role = user.role if user else context_actor.get("role")
    actor_school_id = user.school_id if user else context_actor.get("school_id")
    ip_address = (
        request.client.host
        if request and request.client
        else AUDIT_IP.get()
    )
    user_agent = (
        request.headers.get("User-Agent")
        if request
        else AUDIT_USER_AGENT.get()
    )
    db.add(
        AuditLog(
            user_id=actor_id,
            user_name=actor_name,
            user_email=actor_email,
            user_role=actor_role,
            school_id=actor_school_id,
            module=module,
            action=action,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            outcome=outcome,
        )
    )



def notify(
    db: Session,
    title: str,
    message: str,
    severity: str = "INFO",
    module: str = "Sistema",
    user_id: int | None = None,
    school_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> None:
    db.add(
        Notification(
            user_id=user_id,
            school_id=school_id,
            title=title,
            message=message,
            severity=severity,
            module=module,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    )


def occurrence_protocol(db: Session) -> str:
    year = datetime.now().year
    if DATABASE_URL.startswith("postgresql"):
        db.execute(
            text(
                "INSERT INTO occurrence_sequences (year, last_value) VALUES (:year, 0) "
                "ON CONFLICT (year) DO NOTHING"
            ),
            {"year": year},
        )
        sequence = db.execute(
            text(
                "UPDATE occurrence_sequences SET last_value = last_value + 1 "
                "WHERE year = :year RETURNING last_value"
            ),
            {"year": year},
        ).scalar_one()
    else:
        sequence_row = db.get(OccurrenceSequence, year)
        if not sequence_row:
            sequence_row = OccurrenceSequence(year=year, last_value=0)
            db.add(sequence_row)
            db.flush()
        sequence_row.last_value += 1
        db.flush()
        sequence = sequence_row.last_value
    return f"EDU-{year}-{int(sequence):05d}"


def ensure_camera_code(db: Session, camera: Camera) -> str:
    if camera.code:
        return camera.code
    if not camera.id:
        db.flush()
    camera.code = f"CAM-{int(camera.id):06d}"
    return camera.code


def ensure_schema() -> None:
    """Applies additive compatibility changes without deleting existing data."""
    if not DATABASE_URL.startswith("postgresql"):
        return
    statements = [
        "CREATE EXTENSION IF NOT EXISTS pg_stat_statements",
        "ALTER TABLE schools ADD COLUMN IF NOT EXISTS code VARCHAR(40)",
        "ALTER TABLE schools ADD COLUMN IF NOT EXISTS neighborhood VARCHAR(120)",
        "ALTER TABLE schools ADD COLUMN IF NOT EXISTS city VARCHAR(120)",
        "ALTER TABLE schools ADD COLUMN IF NOT EXISTS phone VARCHAR(40)",
        "ALTER TABLE schools ADD COLUMN IF NOT EXISTS email VARCHAR(180)",
        "ALTER TABLE schools ADD COLUMN IF NOT EXISTS latitude VARCHAR(40)",
        "ALTER TABLE schools ADD COLUMN IF NOT EXISTS longitude VARCHAR(40)",
        "ALTER TABLE schools ADD COLUMN IF NOT EXISTS operational_status VARCHAR(30) DEFAULT 'IMPLANTACAO'",
        "ALTER TABLE schools ADD COLUMN IF NOT EXISTS notes TEXT",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS port INTEGER DEFAULT 554",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS username VARCHAR(120)",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS password VARCHAR(180)",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS manufacturer VARCHAR(80) DEFAULT 'Hikvision'",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS model VARCHAR(120)",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS camera_type VARCHAR(40) DEFAULT 'FIXA'",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS stream_name VARCHAR(120)",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS last_check_at TIMESTAMPTZ",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS stream_profile VARCHAR(20) DEFAULT 'MAIN'",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS last_error TEXT",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS last_frame_at TIMESTAMPTZ",
        "CREATE TABLE IF NOT EXISTS recorders (id SERIAL PRIMARY KEY, school_id INTEGER NOT NULL REFERENCES schools(id) ON DELETE CASCADE, name VARCHAR(180) NOT NULL, manufacturer VARCHAR(80) DEFAULT 'Hikvision', model VARCHAR(120), serial_number VARCHAR(120), ip_address VARCHAR(64) NOT NULL, http_port INTEGER DEFAULT 80, https_port INTEGER DEFAULT 443, rtsp_port INTEGER DEFAULT 554, sdk_port INTEGER DEFAULT 8000, username VARCHAR(120), password VARCHAR(180), channel_count INTEGER DEFAULT 16, firmware VARCHAR(120), status VARCHAR(20) DEFAULT 'PENDING', last_check_at TIMESTAMPTZ, last_error TEXT, notes TEXT, active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW())",
        "ALTER TABLE recorders ADD COLUMN IF NOT EXISTS firmware_released_date VARCHAR(40)",
        "ALTER TABLE recorders ADD COLUMN IF NOT EXISTS device_type VARCHAR(80)",
        "ALTER TABLE recorders ADD COLUMN IF NOT EXISTS mac_address VARCHAR(40)",
        "ALTER TABLE recorders ADD COLUMN IF NOT EXISTS discovered_channel_count INTEGER",
        "ALTER TABLE recorders ADD COLUMN IF NOT EXISTS last_discovery_at TIMESTAMPTZ",
        "CREATE INDEX IF NOT EXISTS ix_recorders_school_id ON recorders (school_id)",
        "CREATE INDEX IF NOT EXISTS ix_cameras_recorder_channel ON cameras (recorder_id, nvr_channel)",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS source_type VARCHAR(30) DEFAULT 'CAMERA_IP'",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS recorder_id INTEGER REFERENCES recorders(id) ON DELETE SET NULL",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS nvr_channel INTEGER DEFAULT 1",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS stream_name_main VARCHAR(140)",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS stream_name_sub VARCHAR(140)",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS rtsp_path_main VARCHAR(600)",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS rtsp_path_sub VARCHAR(600)",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS rtsp_url_main VARCHAR(600)",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS rtsp_url_sub VARCHAR(600)",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS main_status VARCHAR(20) DEFAULT 'PENDING'",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS sub_status VARCHAR(20) DEFAULT 'PENDING'",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS main_codec VARCHAR(30)",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS main_resolution VARCHAR(40)",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS main_fps INTEGER",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS main_bitrate_kbps INTEGER",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS sub_codec VARCHAR(30)",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS sub_resolution VARCHAR(40)",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS sub_fps INTEGER",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS sub_bitrate_kbps INTEGER",
        "CREATE TABLE IF NOT EXISTS camera_favorites (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE, camera_id INTEGER NOT NULL REFERENCES cameras(id) ON DELETE CASCADE, created_at TIMESTAMPTZ DEFAULT NOW(), CONSTRAINT uq_camera_favorites_user_camera UNIQUE(user_id, camera_id))",
        "CREATE INDEX IF NOT EXISTS ix_camera_favorites_user_id ON camera_favorites (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_camera_favorites_camera_id ON camera_favorites (camera_id)",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS codec VARCHAR(30)",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS resolution VARCHAR(40)",
        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS fps INTEGER",
        "ALTER TABLE user_accounts ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER DEFAULT 0",
        "ALTER TABLE user_accounts ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ",
        "ALTER TABLE user_accounts ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMPTZ",
        "ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS ip_address VARCHAR(64)",
        "ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS user_agent VARCHAR(300)",
        "ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ",
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS school_id INTEGER REFERENCES schools(id) ON DELETE SET NULL",
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS camera_id INTEGER REFERENCES cameras(id) ON DELETE SET NULL",
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS source VARCHAR(30) DEFAULT 'SISTEMA'",
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION",
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS summary VARCHAR(500)",
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS evidence_path VARCHAR(700)",
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS payload_json TEXT",
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS assigned_user_id INTEGER",
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS assigned_user_name VARCHAR(160)",
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS acknowledged_at TIMESTAMPTZ",
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ",
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS event_occurred_at TIMESTAMPTZ",
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
        "ALTER TABLE occurrences ADD COLUMN IF NOT EXISTS school_id INTEGER REFERENCES schools(id) ON DELETE SET NULL",
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_id INTEGER",
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_email VARCHAR(180)",
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_role VARCHAR(40)",
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS school_id INTEGER",
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS ip_address VARCHAR(64)",
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_agent VARCHAR(300)",
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS outcome VARCHAR(30) DEFAULT 'SUCCESS'",
        "CREATE INDEX IF NOT EXISTS ix_alerts_school_id ON alerts (school_id)",
        "CREATE INDEX IF NOT EXISTS ix_alerts_camera_id ON alerts (camera_id)",
        "CREATE INDEX IF NOT EXISTS ix_alerts_status_priority ON alerts (status, priority)",
        "CREATE TABLE IF NOT EXISTS alert_activities (id SERIAL PRIMARY KEY, alert_id INTEGER NOT NULL REFERENCES alerts(id) ON DELETE CASCADE, action VARCHAR(60) NOT NULL, from_status VARCHAR(30), to_status VARCHAR(30), note TEXT, user_id INTEGER, user_name VARCHAR(160) DEFAULT 'Sistema', created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS ix_alert_activities_alert_id ON alert_activities (alert_id)",
        "CREATE INDEX IF NOT EXISTS ix_alert_activities_created_at ON alert_activities (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_occurrences_school_id ON occurrences (school_id)",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_school_id ON audit_logs (school_id)",
        "UPDATE alerts SET school_id = schools.id FROM schools WHERE alerts.school_id IS NULL AND LOWER(TRIM(alerts.school_name)) = LOWER(TRIM(schools.name))",
        "UPDATE occurrences SET school_id = schools.id FROM schools WHERE occurrences.school_id IS NULL AND LOWER(TRIM(occurrences.school_name)) = LOWER(TRIM(schools.name))",
        "UPDATE alerts SET camera_id = cameras.id FROM cameras WHERE alerts.camera_id IS NULL AND alerts.school_id = cameras.school_id AND LOWER(TRIM(alerts.camera_name)) = LOWER(TRIM(cameras.name))",
        "CREATE TABLE IF NOT EXISTS support_requests (id SERIAL PRIMARY KEY, protocol VARCHAR(40) UNIQUE NOT NULL, name VARCHAR(160) NOT NULL, email VARCHAR(180) NOT NULL, phone VARCHAR(40), category VARCHAR(60) DEFAULT 'ACESSO', subject VARCHAR(220) NOT NULL, message TEXT NOT NULL, status VARCHAR(30) DEFAULT 'ABERTO', source VARCHAR(40) DEFAULT 'LOGIN', ip_address VARCHAR(64), user_agent VARCHAR(300), created_at TIMESTAMPTZ DEFAULT NOW())",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))




APP_VERSION = "2.0.0-F7-R3"
EXPECTED_ALEMBIC_REVISION = "20260911_209_f7r3"
DATA_DIR = Path(os.getenv("EDUVIGIA_DATA_DIR", "/app/data"))
EVIDENCE_DIR = DATA_DIR / "evidence"
PLAYBACK_DIR = DATA_DIR / "playback"
FLOORPLAN_DIR = DATA_DIR / "floorplans"
PLAYBACK_EXPORT_MAX_SECONDS = max(60, min(int(os.getenv("EDUVIGIA_PLAYBACK_EXPORT_MAX_SECONDS", "1800")), 7200))
PLAYBACK_PREVIEW_MAX_SECONDS = max(15, min(int(os.getenv("EDUVIGIA_PLAYBACK_PREVIEW_MAX_SECONDS", "120")), 300))
PLAYBACK_PREVIEW_TTL_SECONDS = max(60, min(int(os.getenv("EDUVIGIA_PLAYBACK_PREVIEW_TTL_SECONDS", "600")), 1800))
PLAYBACK_PREVIEWS: dict[str, dict] = {}
PLAYBACK_PREVIEW_LOCK = threading.Lock()
MEDIAMTX_API = os.getenv("MEDIAMTX_API", "http://mediamtx:9997")
STREAM_TOKEN_TTL_SECONDS = max(60, min(int(os.getenv("EDUVIGIA_STREAM_TOKEN_TTL_SECONDS", "300")), 900))
STREAM_WEBRTC_PUBLIC_PORT = int(os.getenv("EDUVIGIA_WEBRTC_PUBLIC_PORT", "18889"))
STREAM_HLS_PUBLIC_PORT = int(os.getenv("EDUVIGIA_HLS_PUBLIC_PORT", "18888"))
STORAGE_WARNING_PERCENT = max(50, min(int(os.getenv("EDUVIGIA_STORAGE_WARNING_PERCENT", "80")), 99))
STORAGE_CRITICAL_PERCENT = max(STORAGE_WARNING_PERCENT + 1, min(int(os.getenv("EDUVIGIA_STORAGE_CRITICAL_PERCENT", "95")), 100))
BACKUP_RETENTION_DAYS = max(1, int(os.getenv("EDUVIGIA_BACKUP_RETENTION_DAYS", "30")))
AUDIT_RETENTION_DAYS = max(30, int(os.getenv("EDUVIGIA_AUDIT_RETENTION_DAYS", "365")))
APP_STARTED_MONOTONIC = time.monotonic()
APP_STARTUP_COMPLETE = False
REQUEST_METRICS_LOCK = threading.Lock()
REQUEST_METRICS = {
    "total": 0,
    "active": 0,
    "latency_seconds_sum": 0.0,
    "status_2xx": 0,
    "status_3xx": 0,
    "status_4xx": 0,
    "status_5xx": 0,
}
LOGGER = logging.getLogger("eduvigia")
if not LOGGER.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    LOGGER.addHandler(handler)
LOGGER.setLevel(getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO))
SECURE_STREAM_PATTERN = re.compile(r"^(?P<base>.+)-(?P<nonce>[0-9a-f]{8})-(?P<profile>main|sub)$")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
FLOORPLAN_DIR.mkdir(parents=True, exist_ok=True)
PLAYBACK_DIR.mkdir(parents=True, exist_ok=True)


def slug_stream_name(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value or "")
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    normalized = "".join(
        character.lower() if character.isalnum() else "-"
        for character in ascii_value.strip()
    )
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return normalized.strip("-")[:110] or f"camera-{secrets.token_hex(3)}"


def generate_camera_stream_base(db: Session, camera: Camera) -> str:
    school = db.get(School, camera.school_id)
    school_code = (school.code if school and school.code else school.name if school else f"escola-{camera.school_id}")
    source = "nvr" if camera.source_type == "NVR" else "dvr" if camera.source_type == "DVR" else "device" if camera.device_id else "cam"
    logical_channel = int(camera.logical_channel or 1) if camera.device_id else int(camera.nvr_channel or 1)
    channel = f"-ch{logical_channel:02d}" if camera.source_type in {"NVR", "DVR"} or camera.device_id else ""
    base = slug_stream_name(f"{school_code}-{source}{channel}-{camera.location or camera.name}")
    return base[:110]


def ensure_unique_stream_base(db: Session, camera: Camera, requested: str | None = None) -> str:
    base = slug_stream_name(requested) if requested else generate_camera_stream_base(db, camera)
    candidate = base
    suffix = 2
    query = db.query(Camera).filter(Camera.id != (camera.id or 0))
    used = {
        value
        for row in query.all()
        for value in (row.stream_name, row.stream_name_main, row.stream_name_sub)
        if value
    }
    while candidate in used or f"{candidate}-main" in used or f"{candidate}-sub" in used:
        candidate = f"{base[:103]}-{suffix:02d}"
        suffix += 1
    return candidate


def _strip_stream_profile(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    for suffix in ("-main", "-sub"):
        if cleaned.lower().endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break
    return cleaned or None


def _secure_stream_base_from_camera(camera: Camera) -> str | None:
    for value in (camera.stream_name_main, camera.stream_name_sub, camera.stream_name):
        if not value:
            continue
        match = SECURE_STREAM_PATTERN.match(value.strip().lower())
        if match:
            return f"{match.group('base')}-{match.group('nonce')}"
    return None


def ensure_secure_camera_streams(
    db: Session,
    camera: Camera,
    requested: str | None = None,
) -> tuple[str, list[str]]:
    previous = [
        value for value in (camera.stream_name, camera.stream_name_main, camera.stream_name_sub)
        if value
    ]
    requested_base = _strip_stream_profile(requested)
    current_secure_base = _secure_stream_base_from_camera(camera)

    if requested_base:
        requested_base = slug_stream_name(requested_base)
        if re.search(r"-[0-9a-f]{8}$", requested_base):
            candidate = requested_base
        elif current_secure_base and requested_base == current_secure_base.rsplit("-", 1)[0]:
            candidate = current_secure_base
        else:
            candidate = f"{requested_base[:100]}-{secrets.token_hex(4)}"
    elif current_secure_base:
        candidate = current_secure_base
    else:
        generated = generate_camera_stream_base(db, camera)
        candidate = f"{generated[:100]}-{secrets.token_hex(4)}"

    used = {
        value
        for row in db.query(Camera).filter(Camera.id != (camera.id or 0)).all()
        for value in (row.stream_name, row.stream_name_main, row.stream_name_sub)
        if value
    }
    while f"{candidate}-main" in used or f"{candidate}-sub" in used:
        candidate = f"{candidate[:100]}-{secrets.token_hex(4)}"

    camera.stream_name_main = f"{candidate}-main"
    camera.stream_name_sub = f"{candidate}-sub"
    camera.stream_name = (
        camera.stream_name_main
        if (camera.stream_profile or "SUB").upper() == "MAIN"
        else camera.stream_name_sub
    )
    camera.rtsp_path_main = build_camera_rtsp(db, camera, "MAIN")
    camera.rtsp_path_sub = build_camera_rtsp(db, camera, "SUB")
    obsolete = [value for value in previous if value not in {camera.stream_name_main, camera.stream_name_sub}]
    return candidate, list(dict.fromkeys(obsolete))


def recorder_for_camera(db: Session, camera: Camera) -> Recorder | None:
    return db.get(Recorder, camera.recorder_id) if camera.recorder_id else None


def camera_connection_values(db: Session, camera: Camera) -> tuple[str, int, str | None, str | None]:
    recorder = recorder_for_camera(db, camera)
    if recorder:
        return (recorder.ip_address, recorder.rtsp_port or 554, recorder.username, decrypt_secret(recorder.password))
    if camera.device_id:
        device = db.get(VideoDevice, camera.device_id)
        if not device:
            raise HTTPException(409, "Dispositivo físico da câmera não encontrado")
        return (device.ip_address, device.rtsp_port or 554, device.username, decrypt_secret(device.password))
    return (camera.ip_address or "", camera.port or 554, camera.username, decrypt_secret(camera.password))


def build_camera_rtsp(db: Session, camera: Camera, profile: str | None = None) -> str:
    selected_profile = (profile or camera.stream_profile or "SUB").upper()
    if camera.source_type == "RTSP_CUSTOM":
        custom_url = (
            camera.rtsp_url_main if selected_profile == "MAIN" else camera.rtsp_url_sub
        ) or camera.rtsp_url
        if custom_url:
            return custom_url
        raise HTTPException(400, f"Informe a URL RTSP do perfil {selected_profile}")

    ip_address, port, username, password = camera_connection_values(db, camera)
    if not ip_address:
        raise HTTPException(400, "Informe o IP da câmera ou selecione um gravador")

    user = urllib.parse.quote(username or "", safe="")
    secret = urllib.parse.quote(password or "", safe="")
    credentials = ""
    if user:
        credentials = user + (f":{secret}" if secret else "") + "@"

    channel_number = int(camera.logical_channel or 1) if camera.device_id else (int(camera.nvr_channel or 1) if camera.source_type in {"NVR", "DVR"} else 1)
    suffix = 2 if selected_profile == "SUB" else 1
    hik_channel = channel_number * 100 + suffix
    return f"rtsp://{credentials}{ip_address}:{port}/Streaming/Channels/{hik_channel}"



def build_hikvision_rtsp(camera: Camera, db: Session | None = None) -> str:
    if db is None:
        with SessionLocal() as session:
            return build_camera_rtsp(session, camera)
    return build_camera_rtsp(db, camera)



def mask_rtsp_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    username = parsed.username
    credentials = f"{username}:***@" if username else ""
    return urllib.parse.urlunsplit(
        (parsed.scheme, f"{credentials}{hostname}{port}", parsed.path, parsed.query, "")
    )


def sanitize_sensitive_payload(value):
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in {"password", "pass", "secret", "token"}:
                sanitized[key] = "********"
            else:
                sanitized[key] = sanitize_sensitive_payload(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_sensitive_payload(item) for item in value]
    if isinstance(value, str) and value.lower().startswith(("rtsp://", "rtsps://")):
        try:
            return mask_rtsp_url(value)
        except Exception:
            return "rtsp://***"
    return value


def mediamtx_request(
    method: str,
    endpoint: str,
    body: dict | None = None,
    timeout: float = 5.0,
) -> tuple[int, dict | str]:
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    request = urllib.request.Request(
        f"{MEDIAMTX_API}{endpoint}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                return response.status, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return response.status, raw
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = raw
        return error.code, payload
    except OSError as error:
        return 0, str(error)


def _upsert_mediamtx_path(stream_name: str, source: str) -> dict:
    status, _ = mediamtx_request(
        "GET",
        f"/v3/config/paths/get/{urllib.parse.quote(stream_name, safe='')}",
    )
    payload = {
        "source": source,
        "sourceProtocol": "tcp",
        "sourceOnDemand": True,
        "sourceOnDemandStartTimeout": "15s",
        "sourceOnDemandCloseAfter": "30s",
    }
    if status == 200:
        write_status, _ = mediamtx_request(
            "PATCH",
            f"/v3/config/paths/patch/{urllib.parse.quote(stream_name, safe='')}",
            payload,
        )
    else:
        write_status, _ = mediamtx_request(
            "POST",
            f"/v3/config/paths/add/{urllib.parse.quote(stream_name, safe='')}",
            payload,
        )
    return {"ok": write_status in (200, 201), "http_status": write_status}


def provision_camera_paths(camera: Camera, db: Session | None = None) -> tuple[bool, dict]:
    owns_session = db is None
    session = db or SessionLocal()
    try:
        ensure_secure_camera_streams(session, camera)
        results = {
            "MAIN": _upsert_mediamtx_path(
                camera.stream_name_main or "",
                build_camera_rtsp(session, camera, "MAIN"),
            ),
            "SUB": _upsert_mediamtx_path(
                camera.stream_name_sub or "",
                build_camera_rtsp(session, camera, "SUB"),
            ),
        }
        if owns_session:
            session.commit()
        return all(item["ok"] for item in results.values()), results
    finally:
        if owns_session:
            session.close()


def provision_camera_path(camera: Camera, db: Session | None = None) -> tuple[bool, str]:
    ok, results = provision_camera_paths(camera, db)
    summary = "; ".join(
        f"{profile}={'OK' if result['ok'] else 'FALHA'}({result['http_status']})"
        for profile, result in results.items()
    )
    return ok, summary


def delete_camera_path(stream_name: str | None) -> None:
    if not stream_name or stream_name == "teste":
        return
    mediamtx_request(
        "DELETE",
        f"/v3/config/paths/delete/{urllib.parse.quote(stream_name, safe='')}",
    )


def delete_camera_paths(camera: Camera) -> None:
    for stream_name in dict.fromkeys(
        value for value in (camera.stream_name, camera.stream_name_main, camera.stream_name_sub) if value
    ):
        delete_camera_path(stream_name)


def mediamtx_path_status(stream_name: str | None) -> dict:
    if not stream_name:
        return {"ready": False, "detail": "Stream não configurado"}
    status, result = mediamtx_request(
        "GET",
        f"/v3/paths/get/{urllib.parse.quote(stream_name, safe='')}",
    )
    if status == 200 and isinstance(result, dict):
        return {
            "ready": bool(result.get("ready")),
            "detail": sanitize_sensitive_payload(result),
        }
    return {"ready": False, "detail": sanitize_sensitive_payload(result)}


def _stream_signing_key() -> bytes:
    value = os.getenv("EDUVIGIA_STREAM_SIGNING_KEY", "").strip()
    if len(value) < 32:
        raise RuntimeError("EDUVIGIA_STREAM_SIGNING_KEY deve possuir pelo menos 32 caracteres")
    return value.encode("utf-8")


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_stream_token(*, user_id: int, camera_id: int, school_id: int | None, path: str, profile: str, kind: str = "camera") -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=STREAM_TOKEN_TTL_SECONDS)
    payload = {
        "v": 1,
        "uid": user_id,
        "cam": camera_id,
        "sid": school_id,
        "path": path,
        "profile": profile,
        "kind": kind,
        "exp": int(expires_at.timestamp()),
        "nonce": secrets.token_hex(8),
    }
    encoded = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _b64url_encode(hmac.new(_stream_signing_key(), encoded.encode("ascii"), hashlib.sha256).digest())
    return f"{encoded}.{signature}", expires_at


def validate_stream_token(token: str) -> dict:
    try:
        encoded, signature = token.split(".", 1)
        expected = _b64url_encode(hmac.new(_stream_signing_key(), encoded.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("assinatura inválida")
        payload = json.loads(_b64url_decode(encoded).decode("utf-8"))
        if payload.get("v") != 1 or int(payload.get("exp", 0)) <= int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("token expirado")
        if not payload.get("path") or not payload.get("uid"):
            raise ValueError("token incompleto")
        return payload
    except Exception as error:
        raise HTTPException(403, "Token de vídeo inválido ou expirado") from error


def _public_media_base(request: Request, *, protocol: str) -> str:
    env_name = "EDUVIGIA_WEBRTC_PUBLIC_BASE" if protocol == "webrtc" else "EDUVIGIA_HLS_PUBLIC_BASE"
    configured = os.getenv(env_name, "").strip().rstrip("/")
    if configured:
        return configured
    forwarded_host = request.headers.get("x-forwarded-host", "").split(",")[0].strip()
    host_value = forwarded_host or request.headers.get("host", "")
    parsed_host = urllib.parse.urlsplit(f"//{host_value}").hostname or request.url.hostname or "localhost"
    if ":" in parsed_host and not parsed_host.startswith("["):
        parsed_host = f"[{parsed_host}]"
    request_scheme = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip().lower()
    configured_scheme = os.getenv("EDUVIGIA_MEDIA_PUBLIC_SCHEME", "https").strip().lower()
    scheme = configured_scheme if configured_scheme in {"http", "https"} else request_scheme
    port = STREAM_WEBRTC_PUBLIC_PORT if protocol == "webrtc" else STREAM_HLS_PUBLIC_PORT
    return f"{scheme}://{parsed_host}:{port}"


PASSWORD_ITERATIONS = 260_000
SESSION_HOURS = 12
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
MIN_PASSWORD_LENGTH = 10
CREDENTIAL_KEY = os.getenv("EDUVIGIA_CREDENTIAL_KEY", "").strip()


def _fernet() -> Fernet | None:
    if not CREDENTIAL_KEY:
        return None
    try:
        return Fernet(CREDENTIAL_KEY.encode("utf-8"))
    except Exception:
        return None


def encrypt_secret(value: str | None) -> str | None:
    if not value:
        return value
    if value.startswith("enc:v1:"):
        return value
    cipher = _fernet()
    if not cipher:
        raise HTTPException(
            503,
            "EDUVIGIA_CREDENTIAL_KEY não está configurada; credencial não foi armazenada",
        )
    token = cipher.encrypt(value.encode("utf-8")).decode("utf-8")
    return f"enc:v1:{token}"


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return value
    if not value.startswith("enc:v1:"):
        return value
    cipher = _fernet()
    if not cipher:
        raise HTTPException(500, "Chave de credenciais não configurada")
    try:
        return cipher.decrypt(value.removeprefix("enc:v1:").encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise HTTPException(500, "Não foi possível descriptografar a credencial técnica")


def token_digest(token: str) -> str:
    return "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def validate_password_policy(password: str) -> None:
    problems = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"mínimo de {MIN_PASSWORD_LENGTH} caracteres")
    if not any(character.isupper() for character in password):
        problems.append("uma letra maiúscula")
    if not any(character.islower() for character in password):
        problems.append("uma letra minúscula")
    if not any(character.isdigit() for character in password):
        problems.append("um número")
    if not any(not character.isalnum() for character in password):
        problems.append("um caractere especial")
    if problems:
        raise HTTPException(400, "A senha deve conter " + ", ".join(problems))



def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def user_payload(user: UserAccount) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "school_id": user.school_id,
        "active": user.active,
        "must_change_password": user.must_change_password,
    }


def resolve_session(db: Session, token: str | None) -> UserAccount | None:
    if not token:
        return None
    digest = token_digest(token)
    session_row = (
        db.query(AuthSession)
        .filter(AuthSession.token.in_([digest, token]))
        .first()
    )
    if not session_row:
        return None
    now = datetime.now(timezone.utc)
    expires = session_row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= now:
        db.delete(session_row)
        db.commit()
        return None
    user = db.get(UserAccount, session_row.user_id)
    if not user or not user.active:
        return None
    session_row.last_seen_at = now
    db.commit()
    return user


def require_user(request: Request, db: Session = Depends(db_session)) -> UserAccount:
    state_user = getattr(request.state, "user", None)
    if state_user:
        user = db.get(UserAccount, state_user["id"])
        if user and user.active:
            return user

    authorization = request.headers.get("Authorization", "")
    token = authorization.removeprefix("Bearer ").strip()
    user = resolve_session(db, token)
    if not user:
        raise HTTPException(401, "Sessão inválida ou expirada")
    return user



def request_user(request: Request, db: Session = Depends(db_session)) -> UserAccount:
    state_user = getattr(request.state, "user", None)
    if not state_user:
        raise HTTPException(401, "Sessão inválida ou expirada")
    user = db.get(UserAccount, state_user["id"])
    if not user or not user.active:
        raise HTTPException(401, "Usuário inativo")
    return user


ROLE_PROFILES = {
    "ADMIN_SECRETARIA": {
        "environment": "SECRETARIA",
        "label": "Administrador da Secretaria",
        "permissions": ["*"],
        "school_required": False,
    },
    "GESTOR_SECRETARIA": {
        "environment": "SECRETARIA",
        "label": "Gestor da Secretaria",
        "permissions": [
            "dashboard:view", "schools:view", "schools:write", "cameras:view",
            "cameras:write", "monitor:view", "maps:view", "floorplans:view", "floorplans:write", "alerts:view", "events:view", "events:operate", "occurrences:view",
            "equipment:view", "equipment:write", "reports:view", "audit:view",
            "settings:view", "users:view",
            "ptz:control", "playback:view", "evidence:export", "evidence:verify",
            "wall:view", "wall:write",
        ],
        "school_required": False,
    },
    "SUPERVISOR_GUARDA": {
        "environment": "GUARDA",
        "label": "Supervisor da Guarda",
        "permissions": [
            "dashboard:view", "command:view", "schools:view", "cameras:view",
            "monitor:view", "maps:view", "floorplans:view", "alerts:view", "alerts:operate", "events:view", "events:operate", "occurrences:view",
            "occurrences:operate", "dispatch:view", "dispatch:operate",
            "ptz:control", "playback:view", "evidence:export", "evidence:verify",
            "wall:view", "wall:write",
        ],
        "school_required": False,
    },
    "OPERADOR_GUARDA": {
        "environment": "GUARDA",
        "label": "Operador da Guarda",
        "permissions": [
            "dashboard:view", "command:view", "schools:view", "cameras:view",
            "monitor:view", "maps:view", "floorplans:view", "alerts:view", "alerts:operate", "events:view", "events:operate", "occurrences:view",
            "occurrences:operate", "dispatch:view",
            "ptz:control", "playback:view", "evidence:export", "evidence:verify",
            "wall:view", "wall:write",
        ],
        "school_required": False,
    },
    "DESPACHANTE_GUARDA": {
        "environment": "GUARDA",
        "label": "Despachante da Guarda",
        "permissions": [
            "dashboard:view", "command:view", "schools:view", "cameras:view",
            "monitor:view", "maps:view", "floorplans:view", "alerts:view", "alerts:operate", "events:view", "events:operate", "occurrences:view",
            "occurrences:operate", "dispatch:view", "dispatch:operate",
            "ptz:control", "playback:view", "evidence:export", "evidence:verify",
            "wall:view", "wall:write",
        ],
        "school_required": False,
    },
    "GESTOR_ESCOLA": {
        "environment": "ESCOLA",
        "label": "Gestor da Escola",
        "permissions": [
            "dashboard:view", "schools:view", "cameras:view", "monitor:view", "maps:view", "floorplans:view", "floorplans:write",
            "alerts:view", "events:view", "occurrences:view", "sos:use", "chat:use", "ptt:use",
            "ptz:control", "playback:view", "evidence:verify",
        ],
        "school_required": True,
    },
    "OPERADOR_ESCOLA": {
        "environment": "ESCOLA",
        "label": "Operador da Escola",
        "permissions": [
            "dashboard:view", "schools:view", "cameras:view", "monitor:view", "maps:view", "floorplans:view",
            "alerts:view", "events:view", "occurrences:view", "sos:use", "chat:use", "ptt:use",
            "ptz:control", "playback:view", "evidence:verify",
        ],
        "school_required": True,
    },
    "TECNICO": {
        "environment": "SECRETARIA",
        "label": "Técnico",
        "permissions": [
            "dashboard:view", "schools:view", "cameras:view", "cameras:write",
            "monitor:view", "maps:view", "floorplans:view", "floorplans:write", "events:view", "events:operate", "equipment:view", "equipment:write",
            "infrastructure:view", "homologation:view",
            "ptz:control", "playback:view", "evidence:verify", "wall:view",
        ],
        "school_required": False,
    },
}

LEGACY_ROLE_TO_CANONICAL = {
    "ADMIN": "ADMIN_SECRETARIA",
    "SUPERVISOR": "GESTOR_SECRETARIA",
    "GESTAO": "GESTOR_SECRETARIA",
    "DESPACHANTE": "DESPACHANTE_GUARDA",
    "ESCOLA": "GESTOR_ESCOLA",
    "TECNICO": "TECNICO",
}

SCHOOL_REQUIRED_ROLES = {
    "GESTOR_ESCOLA", "OPERADOR_ESCOLA",
    "ESCOLA", "OPERADOR",
}
PASSWORD_CHANGE_ALLOWED_PATHS = {
    "/auth/me",
    "/auth/change-password",
    "/auth/logout",
}


def canonical_role(role: str, school_id: int | None = None) -> str:
    if role == "OPERADOR":
        return "OPERADOR_ESCOLA" if school_id else "OPERADOR_GUARDA"
    return LEGACY_ROLE_TO_CANONICAL.get(role, role)


def role_profile(role: str, school_id: int | None = None) -> dict:
    return ROLE_PROFILES.get(canonical_role(role, school_id), {
        "environment": "UNKNOWN",
        "label": role,
        "permissions": [],
        "school_required": False,
    })


def role_permissions(role: str, school_id: int | None = None) -> list[str]:
    return list(role_profile(role, school_id).get("permissions", []))


def role_matches(user: UserAccount, allowed_roles: tuple[str, ...]) -> bool:
    return canonical_role(user.role, user.school_id) in allowed_roles


def is_admin_role(role: str, school_id: int | None = None) -> bool:
    return canonical_role(role, school_id) == "ADMIN_SECRETARIA"


def scoped_school_id(user: UserAccount) -> int | None:
    canonical = canonical_role(user.role, user.school_id)
    if canonical in {"GESTOR_ESCOLA", "OPERADOR_ESCOLA"}:
        if not user.school_id:
            raise HTTPException(403, "Perfil da escola sem unidade escolar vinculada")
        return user.school_id
    if canonical == "TECNICO" and user.school_id:
        return user.school_id
    return None


def validate_role_school_binding(role: str, school_id: int | None) -> None:
    canonical = canonical_role(role, school_id)
    profile = ROLE_PROFILES.get(canonical)
    if not profile:
        raise HTTPException(400, "Perfil de acesso inválido")
    if profile["school_required"] and not school_id:
        raise HTTPException(400, "O perfil selecionado exige vínculo com uma unidade escolar")
    if school_id and canonical not in {"GESTOR_ESCOLA", "OPERADOR_ESCOLA", "TECNICO"}:
        raise HTTPException(400, "Este perfil não aceita vínculo com uma unidade escolar específica")

def ensure_school_access(user: UserAccount, school_id: int | None) -> None:
    restricted_school_id = scoped_school_id(user)
    if restricted_school_id is None:
        return
    if school_id is None or int(school_id) != int(restricted_school_id):
        raise HTTPException(404, "Recurso não encontrado")


def school_scope_query(query, model, user: UserAccount):
    restricted_school_id = scoped_school_id(user)
    if restricted_school_id is not None:
        query = query.filter(model.school_id == restricted_school_id)
    return query


def school_for_name(db: Session, school_name: str | None) -> School | None:
    if not school_name:
        return None
    normalized = school_name.strip()
    return (
        db.query(School)
        .filter(School.name.ilike(normalized))
        .first()
    )


def ensure_school_name_access(
    db: Session,
    user: UserAccount,
    school_name: str | None,
    explicit_school_id: int | None = None,
) -> School | None:
    school = db.get(School, explicit_school_id) if explicit_school_id else school_for_name(db, school_name)
    restricted_school_id = scoped_school_id(user)
    if restricted_school_id is not None:
        if not school or school.id != restricted_school_id:
            raise HTTPException(404, "Recurso não encontrado")
    return school


def scope_alert_query(query, db: Session, user: UserAccount):
    restricted_school_id = scoped_school_id(user)
    if restricted_school_id is None:
        return query
    school = db.get(School, restricted_school_id)
    if not school:
        raise HTTPException(403, "Escola vinculada não encontrada")
    return query.filter(
        (Alert.school_id == restricted_school_id)
        | ((Alert.school_id.is_(None)) & (Alert.school_name == school.name))
    )


def scope_occurrence_query(query, db: Session, user: UserAccount):
    restricted_school_id = scoped_school_id(user)
    if restricted_school_id is None:
        return query
    school = db.get(School, restricted_school_id)
    if not school:
        raise HTTPException(403, "Escola vinculada não encontrada")
    return query.filter(
        (Occurrence.school_id == restricted_school_id)
        | ((Occurrence.school_id.is_(None)) & (Occurrence.school_name == school.name))
    )


def ensure_camera_access(user: UserAccount, camera: Camera | None) -> Camera:
    if not camera:
        raise HTTPException(404, "Câmera não encontrada")
    ensure_school_access(user, camera.school_id)
    return camera


def ensure_recorder_access(user: UserAccount, recorder: Recorder | None) -> Recorder:
    if not recorder:
        raise HTTPException(404, "Gravador não encontrado")
    ensure_school_access(user, recorder.school_id)
    return recorder


def ensure_equipment_access(user: UserAccount, equipment: Equipment | None) -> Equipment:
    if not equipment:
        raise HTTPException(404, "Equipamento não encontrado")
    ensure_school_access(user, equipment.school_id)
    return equipment


def ensure_occurrence_access(
    db: Session,
    user: UserAccount,
    occurrence: Occurrence | None,
) -> Occurrence:
    if not occurrence:
        raise HTTPException(404, "Ocorrência não encontrada")
    ensure_school_name_access(
        db,
        user,
        occurrence.school_name,
        occurrence.school_id,
    )
    return occurrence


def ensure_alert_access(
    db: Session,
    user: UserAccount,
    alert: Alert | None,
) -> Alert:
    if not alert:
        raise HTTPException(404, "Alerta não encontrado")
    ensure_school_name_access(db, user, alert.school_name, alert.school_id)
    return alert


ALERT_ACTIVE_STATUSES = {"NOVO", "EM_ATENDIMENTO", "CONFIRMADO"}
ALERT_TERMINAL_STATUSES = {"DESCARTADO", "ENCERRADO"}


def alert_priority_from_severity(severity: str | None) -> str:
    normalized = (severity or "MEDIA").strip().upper()
    return normalized if normalized in {"BAIXA", "MEDIA", "ALTA", "CRITICA"} else "MEDIA"


def add_alert_activity(
    db: Session,
    alert: Alert,
    action: str,
    *,
    from_status: str | None = None,
    to_status: str | None = None,
    note: str | None = None,
    user: UserAccount | None = None,
    user_name: str | None = None,
) -> AlertActivity:
    row = AlertActivity(
        alert_id=alert.id,
        action=action,
        from_status=from_status,
        to_status=to_status,
        note=(note or "").strip() or None,
        user_id=user.id if user else None,
        user_name=user.name if user else (user_name or "Sistema"),
    )
    db.add(row)
    return row


def alert_evidence_file(alert: Alert) -> Path | None:
    raw = (alert.evidence_path or "").strip().replace("\\", "/")
    if not raw:
        return None
    candidate = (DATA_DIR / raw.lstrip("/")).resolve()
    data_root = DATA_DIR.resolve()
    try:
        candidate.relative_to(data_root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def alert_detail_out(db: Session, alert: Alert) -> dict:
    activities = (
        db.query(AlertActivity)
        .filter(AlertActivity.alert_id == alert.id)
        .order_by(AlertActivity.created_at.asc())
        .all()
    )
    occurrence = db.query(Occurrence).filter(Occurrence.alert_id == alert.id).first()
    camera = db.get(Camera, alert.camera_id) if alert.camera_id else None
    payload = _json_loads_object(alert.payload_json)
    return {
        **AlertOut.model_validate(alert).model_dump(),
        "payload": payload,
        "has_evidence": alert_evidence_file(alert) is not None,
        "evidence_url": f"/alerts/{alert.id}/evidence" if alert_evidence_file(alert) is not None else None,
        "activities": [AlertActivityOut.model_validate(item).model_dump() for item in activities],
        "occurrence": OccurrenceOut.model_validate(occurrence).model_dump() if occurrence else None,
        "camera": CameraOut.model_validate(camera).model_dump() if camera else None,
    }


def set_alert_status(
    db: Session,
    alert: Alert,
    status: str,
    *,
    user: UserAccount,
    note: str | None = None,
) -> Alert:
    target = status.strip().upper()
    if target not in {"NOVO", "EM_ATENDIMENTO", "CONFIRMADO", "DESCARTADO", "ENCERRADO"}:
        raise HTTPException(422, "Status de alerta inválido")
    previous = alert.status
    alert.status = target
    alert.updated_at = datetime.now(timezone.utc)
    if target in {"EM_ATENDIMENTO", "CONFIRMADO"} and alert.acknowledged_at is None:
        alert.acknowledged_at = datetime.now(timezone.utc)
    if target in ALERT_TERMINAL_STATUSES:
        alert.resolved_at = datetime.now(timezone.utc)
    elif previous in ALERT_TERMINAL_STATUSES:
        alert.resolved_at = None
    add_alert_activity(
        db,
        alert,
        "STATUS_ATUALIZADO",
        from_status=previous,
        to_status=target,
        note=note,
        user=user,
    )
    return alert


CAMERA_EVENT_LABELS = {
    "CAMERA_ONLINE": "Câmera online",
    "CAMERA_OFFLINE": "Câmera offline",
    "VIDEO_LOSS": "Perda de vídeo",
    "VIDEO_RESTORED": "Vídeo restabelecido",
    "RTSP_FAILURE": "Falha no RTSP",
    "RTSP_RESTORED": "RTSP restabelecido",
    "MOTION": "Movimento detectado",
    "TAMPER": "Sabotagem / obstrução",
    "LINE_CROSSING": "Cruzamento de linha",
    "INTRUSION": "Intrusão em área",
    "REGION_ENTRANCE": "Entrada em região",
    "REGION_EXIT": "Saída de região",
    "OBJECT_LEFT": "Objeto abandonado",
    "OBJECT_REMOVED": "Objeto removido",
    "PEOPLE_COUNTING": "Contagem de pessoas",
    "OCCUPANCY": "Ocupação",
    "QUEUE": "Fila / permanência",
    "AUDIO_ALARM": "Evento de áudio",
    "DIGITAL_INPUT": "Entrada digital / alarme físico",
    "RECORDING_FAILURE": "Falha de gravação",
    "RECORDING_RESTORED": "Gravação restabelecida",
    "STORAGE_FAILURE": "Falha de armazenamento",
    "STORAGE_WARNING": "Alerta de armazenamento",
    "NTP_DRIFT": "Desvio de horário / NTP",
    "PTZ_FAULT": "Falha de PTZ",
    "RECORDER_OFFLINE": "Gravador offline",
    "RECORDER_ONLINE": "Gravador online",
    "DEVICE_REBOOT": "Dispositivo reiniciado",
    "UNKNOWN_DEVICE_EVENT": "Evento de dispositivo não catalogado",
}

CAMERA_EVENT_DEFAULT_SEVERITY = {
    "CAMERA_ONLINE": "INFO",
    "CAMERA_OFFLINE": "ALTA",
    "VIDEO_LOSS": "ALTA",
    "VIDEO_RESTORED": "INFO",
    "RTSP_FAILURE": "ALTA",
    "RTSP_RESTORED": "INFO",
    "MOTION": "MEDIA",
    "TAMPER": "ALTA",
    "LINE_CROSSING": "ALTA",
    "INTRUSION": "ALTA",
    "REGION_ENTRANCE": "MEDIA",
    "REGION_EXIT": "MEDIA",
    "OBJECT_LEFT": "ALTA",
    "OBJECT_REMOVED": "ALTA",
    "PEOPLE_COUNTING": "INFO",
    "OCCUPANCY": "INFO",
    "QUEUE": "MEDIA",
    "AUDIO_ALARM": "MEDIA",
    "DIGITAL_INPUT": "ALTA",
    "RECORDING_FAILURE": "ALTA",
    "RECORDING_RESTORED": "INFO",
    "STORAGE_FAILURE": "CRITICA",
    "STORAGE_WARNING": "ALTA",
    "NTP_DRIFT": "MEDIA",
    "PTZ_FAULT": "MEDIA",
    "RECORDER_OFFLINE": "ALTA",
    "RECORDER_ONLINE": "INFO",
    "DEVICE_REBOOT": "MEDIA",
    "UNKNOWN_DEVICE_EVENT": "BAIXA",
}

CAMERA_EVENT_ALERT_TYPES = {
    "CAMERA_OFFLINE",
    "VIDEO_LOSS",
    "RTSP_FAILURE",
    "MOTION",
    "TAMPER",
    "LINE_CROSSING",
    "INTRUSION",
    "REGION_ENTRANCE",
    "REGION_EXIT",
    "OBJECT_LEFT",
    "OBJECT_REMOVED",
    "QUEUE",
    "AUDIO_ALARM",
    "DIGITAL_INPUT",
    "RECORDING_FAILURE",
    "STORAGE_FAILURE",
    "STORAGE_WARNING",
    "NTP_DRIFT",
    "PTZ_FAULT",
    "RECORDER_OFFLINE",
    "DEVICE_REBOOT",
}

CAMERA_EVENT_AUTO_RECOVERY_TYPES = {
    "CAMERA_OFFLINE",
    "VIDEO_LOSS",
    "RTSP_FAILURE",
    "RECORDING_FAILURE",
    "STORAGE_FAILURE",
    "RECORDER_OFFLINE",
}

CAMERA_EVENT_RECOVERY_TO_FAULT = {
    "CAMERA_ONLINE": "CAMERA_OFFLINE",
    "VIDEO_RESTORED": "VIDEO_LOSS",
    "RTSP_RESTORED": "RTSP_FAILURE",
    "RECORDING_RESTORED": "RECORDING_FAILURE",
    "RECORDER_ONLINE": "RECORDER_OFFLINE",
}

CAMERA_EVENT_PROVIDER_ALIASES = {
    "cameraoffline": "CAMERA_OFFLINE",
    "offline": "CAMERA_OFFLINE",
    "cameraonline": "CAMERA_ONLINE",
    "online": "CAMERA_ONLINE",
    "videoloss": "VIDEO_LOSS",
    "video_loss": "VIDEO_LOSS",
    "videoexception": "VIDEO_LOSS",
    "videorestored": "VIDEO_RESTORED",
    "videorecovery": "VIDEO_RESTORED",
    "rtspfailure": "RTSP_FAILURE",
    "rtsp_failure": "RTSP_FAILURE",
    "rtsprestored": "RTSP_RESTORED",
    "motion": "MOTION",
    "motiondetection": "MOTION",
    "vmd": "MOTION",
    "tamper": "TAMPER",
    "tamperdetection": "TAMPER",
    "videotampering": "TAMPER",
    "linedetection": "LINE_CROSSING",
    "linecrossing": "LINE_CROSSING",
    "line_crossing": "LINE_CROSSING",
    "fielddetection": "INTRUSION",
    "intrusion": "INTRUSION",
    "regionentrance": "REGION_ENTRANCE",
    "regionenter": "REGION_ENTRANCE",
    "regionexiting": "REGION_EXIT",
    "regionexit": "REGION_EXIT",
    "unattendedbaggage": "OBJECT_LEFT",
    "objectleft": "OBJECT_LEFT",
    "attendedbaggage": "OBJECT_REMOVED",
    "objectremoved": "OBJECT_REMOVED",
    "peoplecounting": "PEOPLE_COUNTING",
    "people_counting": "PEOPLE_COUNTING",
    "occupancy": "OCCUPANCY",
    "queuedetection": "QUEUE",
    "queue": "QUEUE",
    "audioexception": "AUDIO_ALARM",
    "audioalarm": "AUDIO_ALARM",
    "digitalinput": "DIGITAL_INPUT",
    "ioalarm": "DIGITAL_INPUT",
    "recordingfailure": "RECORDING_FAILURE",
    "recordingexception": "RECORDING_FAILURE",
    "recordingrestored": "RECORDING_RESTORED",
    "diskerror": "STORAGE_FAILURE",
    "hdderror": "STORAGE_FAILURE",
    "storagefailure": "STORAGE_FAILURE",
    "diskfull": "STORAGE_WARNING",
    "storagewarning": "STORAGE_WARNING",
    "ntpdrift": "NTP_DRIFT",
    "timeerror": "NTP_DRIFT",
    "ptzfault": "PTZ_FAULT",
    "recorderoffline": "RECORDER_OFFLINE",
    "recorderonline": "RECORDER_ONLINE",
    "devicereboot": "DEVICE_REBOOT",
    "reboot": "DEVICE_REBOOT",
}

ACTIVE_EVENT_STATES = {"ACTIVE", "TRUE", "ON", "START", "STARTED", "TRIGGERED", "1"}
INACTIVE_EVENT_STATES = {"INACTIVE", "FALSE", "OFF", "STOP", "STOPPED", "CLEARED", "RECOVERED", "0"}


def _event_json(value: object) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
    except Exception:
        return json.dumps({"value": str(value)}, ensure_ascii=False)


def _event_metadata(row: CameraEvent) -> dict:
    try:
        value = json.loads(row.metadata_json or "{}")
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def camera_event_out(row: CameraEvent) -> CameraEventOut:
    return CameraEventOut(
        id=row.id,
        school_id=row.school_id,
        camera_id=row.camera_id,
        recorder_id=row.recorder_id,
        provider=row.provider,
        provider_event_type=row.provider_event_type,
        event_type=row.event_type,
        event_state=row.event_state,
        severity=row.severity,
        source_channel=row.source_channel,
        first_seen_at=row.first_seen_at,
        last_seen_at=row.last_seen_at,
        occurred_at=row.occurred_at,
        repeat_count=row.repeat_count,
        active=row.active,
        alert_id=row.alert_id,
        metadata=_event_metadata(row),
    )


def normalize_camera_event_type(provider_event_type: str, provider: str = "GENERIC") -> str:
    raw = (provider_event_type or "").strip()
    if not raw:
        return "UNKNOWN_DEVICE_EVENT"
    canonical = raw.upper().replace("-", "_").replace(" ", "_")
    if canonical in CAMERA_EVENT_LABELS:
        return canonical

    compact = re.sub(r"[^a-z0-9]+", "", raw.lower())
    if compact in CAMERA_EVENT_PROVIDER_ALIASES:
        return CAMERA_EVENT_PROVIDER_ALIASES[compact]

    lower = raw.lower()
    topic_patterns = (
        ("cellmotion", "MOTION"),
        ("motion", "MOTION"),
        ("tamper", "TAMPER"),
        ("videoloss", "VIDEO_LOSS"),
        ("linecross", "LINE_CROSSING"),
        ("linedetection", "LINE_CROSSING"),
        ("intrusion", "INTRUSION"),
        ("fielddetection", "INTRUSION"),
        ("digitalinput", "DIGITAL_INPUT"),
        ("recording", "RECORDING_FAILURE"),
        ("storage", "STORAGE_FAILURE"),
        ("disk", "STORAGE_FAILURE"),
    )
    for needle, event_type in topic_patterns:
        if needle in lower:
            return event_type
    return "UNKNOWN_DEVICE_EVENT"


def normalize_camera_event_state(value: str | None) -> tuple[str, bool]:
    normalized = (value or "ACTIVE").strip().upper()
    if normalized in ACTIVE_EVENT_STATES:
        return "ACTIVE", True
    if normalized in INACTIVE_EVENT_STATES:
        return "INACTIVE", False
    if normalized in {"INFO", "UPDATE", "UPDATED"}:
        return "INFO", False
    return "ACTIVE", True


def _event_correlation_key(
    *,
    school_id: int,
    camera_id: int | None,
    recorder_id: int | None,
    event_type: str,
    source_channel: int | None,
    provider_event_type: str | None = None,
) -> str:
    provider_suffix = ""
    if event_type == "UNKNOWN_DEVICE_EVENT" and provider_event_type:
        provider_suffix = "|provider_event:" + re.sub(r"[^a-z0-9_.:-]+", "_", provider_event_type.lower())[:80]
    return (
        f"school:{school_id}|camera:{camera_id or 0}|recorder:{recorder_id or 0}"
        f"|channel:{source_channel or 0}|event:{event_type}{provider_suffix}"
    )[:240]


def _event_advisory_lock(db: Session, correlation_key: str) -> None:
    if DATABASE_URL.startswith("postgresql"):
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:event_key))"),
            {"event_key": correlation_key},
        )


def _resolve_event_camera(
    db: Session,
    *,
    school_id: int | None,
    camera_id: int | None,
    recorder_id: int | None,
    source_channel: int | None,
) -> tuple[School, Camera | None, Recorder | None]:
    camera = db.get(Camera, camera_id) if camera_id else None
    recorder = db.get(Recorder, recorder_id) if recorder_id else None

    if camera and recorder and camera.recorder_id and camera.recorder_id != recorder.id:
        raise HTTPException(422, "Câmera e gravador informados não correspondem")

    if not camera and recorder and source_channel:
        camera = (
            db.query(Camera)
            .filter(
                Camera.recorder_id == recorder.id,
                Camera.nvr_channel == int(source_channel),
            )
            .order_by(Camera.id.asc())
            .first()
        )

    resolved_school_id = school_id
    if camera:
        resolved_school_id = camera.school_id
        if recorder is None and camera.recorder_id:
            recorder = db.get(Recorder, camera.recorder_id)
    elif recorder:
        resolved_school_id = recorder.school_id

    if not resolved_school_id:
        raise HTTPException(422, "Evento sem escola/câmera/gravador identificável")

    school = db.get(School, int(resolved_school_id))
    if not school:
        raise HTTPException(404, "Escola do evento não encontrada")

    if camera and camera.school_id != school.id:
        raise HTTPException(422, "Câmera não pertence à escola informada")
    if recorder and recorder.school_id != school.id:
        raise HTTPException(422, "Gravador não pertence à escola informada")

    return school, camera, recorder


def _camera_health_row(db: Session, camera: Camera) -> CameraHealth:
    row = db.query(CameraHealth).filter(CameraHealth.camera_id == camera.id).first()
    if not row:
        row = CameraHealth(
            camera_id=camera.id,
            school_id=camera.school_id,
            state="UNKNOWN",
            main_online=(camera.main_status == "ONLINE") if camera.main_status else None,
            sub_online=(camera.sub_status == "ONLINE") if camera.sub_status else None,
            rtsp_online=(camera.status == "ONLINE") if camera.status else None,
            fps=camera.fps,
            resolution=camera.resolution,
            codec=camera.codec,
            last_seen_at=camera.last_check_at,
            last_video_at=camera.last_frame_at,
            last_error=camera.last_error,
        )
        db.add(row)
        db.flush()
    return row


def _recorder_health_row(db: Session, recorder: Recorder) -> RecorderHealth:
    row = db.query(RecorderHealth).filter(RecorderHealth.recorder_id == recorder.id).first()
    if not row:
        row = RecorderHealth(
            recorder_id=recorder.id,
            school_id=recorder.school_id,
            state=recorder.status if recorder.status in {"ONLINE", "OFFLINE", "DEGRADADO"} else "UNKNOWN",
            last_seen_at=recorder.last_check_at,
            last_error=recorder.last_error,
        )
        db.add(row)
        db.flush()
    return row


def _recompute_camera_health_state(row: CameraHealth) -> None:
    if row.rtsp_online is False:
        row.state = "OFFLINE"
    elif row.storage_status == "FAILURE" or row.recording_status == "FAILURE":
        row.state = "DEGRADADO"
    elif row.tamper_active:
        row.state = "DEGRADADO"
    elif row.main_online is False and row.sub_online is False:
        row.state = "OFFLINE"
    elif row.main_online is False or row.sub_online is False:
        row.state = "DEGRADADO"
    elif row.rtsp_online is True:
        row.state = "ONLINE"
    else:
        row.state = "UNKNOWN"


def _apply_event_to_health(
    db: Session,
    *,
    camera: Camera | None,
    recorder: Recorder | None,
    event_type: str,
    active: bool,
    occurred_at: datetime,
    metadata: dict,
) -> None:
    if camera:
        health = _camera_health_row(db, camera)
        health.last_event_at = occurred_at
        health.last_seen_at = occurred_at
        if event_type in {"CAMERA_ONLINE", "RTSP_RESTORED", "VIDEO_RESTORED"}:
            health.rtsp_online = True
            if event_type == "VIDEO_RESTORED":
                health.last_video_at = occurred_at
        elif event_type in {"CAMERA_OFFLINE", "RTSP_FAILURE"}:
            health.rtsp_online = False if active else True
        elif event_type == "VIDEO_LOSS":
            health.rtsp_online = False if active else True
        elif event_type == "TAMPER":
            health.tamper_active = bool(active)
        elif event_type == "MOTION":
            health.motion_active = bool(active)
        elif event_type == "RECORDING_FAILURE":
            health.recording_status = "FAILURE" if active else "OK"
        elif event_type == "RECORDING_RESTORED":
            health.recording_status = "OK"
        elif event_type == "STORAGE_FAILURE":
            health.storage_status = "FAILURE" if active else "OK"
        elif event_type == "STORAGE_WARNING":
            health.storage_status = "WARNING" if active else "OK"

        if "recording_status" in metadata:
            health.recording_status = str(metadata["recording_status"]).upper()[:30]
        if "storage_status" in metadata:
            health.storage_status = str(metadata["storage_status"]).upper()[:30]
        if metadata.get("ntp_offset_ms") is not None:
            try:
                health.ntp_offset_ms = int(metadata["ntp_offset_ms"])
            except (TypeError, ValueError):
                pass
        if metadata.get("fps") is not None:
            try:
                health.fps = max(0, min(int(round(float(metadata["fps"]))), 240))
            except (TypeError, ValueError):
                pass
        if metadata.get("bitrate_kbps") is not None:
            try:
                health.bitrate_kbps = max(0, int(float(metadata["bitrate_kbps"])))
            except (TypeError, ValueError):
                pass
        if metadata.get("resolution"):
            health.resolution = str(metadata["resolution"])[:40]
        if metadata.get("codec"):
            health.codec = str(metadata["codec"])[:30]
        if metadata.get("error"):
            health.last_error = str(metadata["error"])[:1000]
        elif event_type in {"CAMERA_ONLINE", "RTSP_RESTORED", "VIDEO_RESTORED"}:
            health.last_error = None

        _recompute_camera_health_state(health)

    if recorder:
        health = _recorder_health_row(db, recorder)
        health.last_event_at = occurred_at
        health.last_seen_at = occurred_at
        if event_type == "RECORDER_OFFLINE":
            health.state = "OFFLINE" if active else "ONLINE"
        elif event_type == "RECORDER_ONLINE":
            health.state = "ONLINE"
            health.last_error = None
        elif event_type == "RECORDING_FAILURE":
            health.recording_status = "FAILURE" if active else "OK"
        elif event_type == "RECORDING_RESTORED":
            health.recording_status = "OK"
        elif event_type == "STORAGE_FAILURE":
            health.storage_status = "FAILURE" if active else "OK"
        elif event_type == "STORAGE_WARNING":
            health.storage_status = "WARNING" if active else "OK"
        if metadata.get("error"):
            health.last_error = str(metadata["error"])[:1000]


def _auto_close_device_alert(db: Session, alert: Alert, note: str) -> None:
    if alert.status in ALERT_TERMINAL_STATUSES:
        return
    previous = alert.status
    alert.status = "ENCERRADO"
    alert.resolved_at = datetime.now(timezone.utc)
    alert.updated_at = alert.resolved_at
    add_alert_activity(
        db,
        alert,
        "RECUPERACAO_AUTOMATICA",
        from_status=previous,
        to_status="ENCERRADO",
        note=note,
        user_name="Sistema",
    )


def ingest_camera_event(
    db: Session,
    payload: CameraEventIn,
) -> CameraEventIngestOut:
    school, camera, recorder = _resolve_event_camera(
        db,
        school_id=payload.school_id,
        camera_id=payload.camera_id,
        recorder_id=payload.recorder_id,
        source_channel=payload.source_channel,
    )
    event_type = normalize_camera_event_type(payload.provider_event_type, payload.provider)
    event_state, active = normalize_camera_event_state(payload.event_state)
    if event_type in CAMERA_EVENT_RECOVERY_TO_FAULT and active:
        event_type = CAMERA_EVENT_RECOVERY_TO_FAULT[event_type]
        event_state = "INACTIVE"
        active = False
    occurred_at = _as_utc(payload.occurred_at or datetime.now(timezone.utc))
    metadata = dict(payload.metadata or {})
    resolved_channel = payload.source_channel
    if resolved_channel is None and camera:
        resolved_channel = int(camera.nvr_channel or camera.logical_channel or 1)
    correlation_key = _event_correlation_key(
        school_id=school.id,
        camera_id=camera.id if camera else None,
        recorder_id=recorder.id if recorder else None,
        event_type=event_type,
        source_channel=resolved_channel,
        provider_event_type=payload.provider_event_type,
    )

    _event_advisory_lock(db, correlation_key)

    if payload.event_uid:
        existing_uid = (
            db.query(CameraEvent)
            .filter(CameraEvent.event_uid == payload.event_uid)
            .first()
        )
        if existing_uid:
            existing_uid.repeat_count = int(existing_uid.repeat_count or 1) + 1
            existing_uid.last_seen_at = occurred_at
            existing_uid.updated_at = datetime.now(timezone.utc)
            db.flush()
            return CameraEventIngestOut(
                accepted=True,
                deduplicated=True,
                event_id=existing_uid.id,
                alert_id=existing_uid.alert_id,
                event_type=existing_uid.event_type,
                state=existing_uid.event_state,
                repeat_count=existing_uid.repeat_count,
            )

    active_row = (
        db.query(CameraEvent)
        .filter(
            CameraEvent.correlation_key == correlation_key,
            CameraEvent.active.is_(True),
        )
        .order_by(CameraEvent.id.desc())
        .first()
    )

    # Hikvision alertStream usa videoloss/inactive como heartbeat em algumas famílias.
    if (
        not active
        and active_row is None
        and payload.provider == "HIKVISION_ISAPI"
        and re.sub(r"[^a-z0-9]+", "", payload.provider_event_type.lower()) == "videoloss"
    ):
        _apply_event_to_health(
            db,
            camera=camera,
            recorder=recorder,
            event_type="CAMERA_ONLINE",
            active=False,
            occurred_at=occurred_at,
            metadata=metadata,
        )
        db.flush()
        return CameraEventIngestOut(
            accepted=True,
            heartbeat=True,
            event_type="CAMERA_ONLINE",
            state="INFO",
            repeat_count=0,
        )

    if active:
        if active_row:
            active_row.repeat_count = int(active_row.repeat_count or 1) + 1
            active_row.last_seen_at = occurred_at
            active_row.occurred_at = occurred_at
            active_row.event_state = "ACTIVE"
            active_row.provider_event_type = payload.provider_event_type
            active_row.metadata_json = _event_json(metadata)
            if payload.raw_payload:
                active_row.raw_payload_json = _event_json({"raw": payload.raw_payload})
            active_row.updated_at = datetime.now(timezone.utc)
            _apply_event_to_health(
                db,
                camera=camera,
                recorder=recorder,
                event_type=event_type,
                active=True,
                occurred_at=occurred_at,
                metadata=metadata,
            )
            db.flush()
            return CameraEventIngestOut(
                accepted=True,
                deduplicated=True,
                event_id=active_row.id,
                alert_id=active_row.alert_id,
                event_type=event_type,
                state="ACTIVE",
                repeat_count=active_row.repeat_count,
            )

        severity = payload.severity or CAMERA_EVENT_DEFAULT_SEVERITY.get(event_type, "BAIXA")
        row = CameraEvent(
            school_id=school.id,
            camera_id=camera.id if camera else None,
            recorder_id=recorder.id if recorder else None,
            provider=payload.provider,
            provider_event_type=payload.provider_event_type,
            event_type=event_type,
            event_state="ACTIVE",
            severity=severity,
            correlation_key=correlation_key,
            event_uid=payload.event_uid,
            source_channel=resolved_channel,
            first_seen_at=occurred_at,
            last_seen_at=occurred_at,
            occurred_at=occurred_at,
            repeat_count=1,
            active=True,
            metadata_json=_event_json(metadata),
            raw_payload_json=_event_json({"raw": payload.raw_payload}) if payload.raw_payload else None,
        )
        db.add(row)
        db.flush()

        if event_type in CAMERA_EVENT_ALERT_TYPES:
            camera_name = camera.name if camera else (recorder.name if recorder else "Dispositivo")
            alert = Alert(
                school_id=school.id,
                camera_id=camera.id if camera else None,
                school_name=school.name,
                camera_name=camera_name,
                event_type=CAMERA_EVENT_LABELS.get(event_type, event_type),
                priority=alert_priority_from_severity(severity),
                status="NOVO",
                source="DISPOSITIVO",
                summary=(
                    f"{CAMERA_EVENT_LABELS.get(event_type, event_type)}"
                    + (f" — {camera.location}" if camera and camera.location else "")
                ),
                payload_json=_event_json(
                    {
                        "device_event_id": row.id,
                        "provider": payload.provider,
                        "provider_event_type": payload.provider_event_type,
                        "source_channel": resolved_channel,
                        "metadata": metadata,
                    }
                ),
                event_occurred_at=occurred_at,
            )
            db.add(alert)
            db.flush()
            row.alert_id = alert.id
            add_alert_activity(
                db,
                alert,
                "CRIADO_POR_DISPOSITIVO",
                to_status="NOVO",
                note=f"Evento normalizado {event_type}; provider={payload.provider}",
                user_name="Sistema",
            )
            notify(
                db,
                title=CAMERA_EVENT_LABELS.get(event_type, "Evento de câmera"),
                message=f"{school.name} — {camera_name}",
                severity="CRITICAL" if severity == "CRITICA" else "WARNING" if severity in {"ALTA", "MEDIA"} else "INFO",
                module="Eventos de Câmera",
                school_id=school.id,
                entity_type="alert",
                entity_id=alert.id,
            )

        _apply_event_to_health(
            db,
            camera=camera,
            recorder=recorder,
            event_type=event_type,
            active=True,
            occurred_at=occurred_at,
            metadata=metadata,
        )
        db.flush()
        return CameraEventIngestOut(
            accepted=True,
            event_id=row.id,
            alert_id=row.alert_id,
            event_type=event_type,
            state="ACTIVE",
            repeat_count=1,
        )

    if active_row:
        active_row.active = False
        active_row.event_state = "INACTIVE"
        active_row.last_seen_at = occurred_at
        active_row.occurred_at = occurred_at
        active_row.repeat_count = int(active_row.repeat_count or 1) + 1
        active_row.metadata_json = _event_json(metadata)
        if payload.raw_payload:
            active_row.raw_payload_json = _event_json({"raw": payload.raw_payload})
        active_row.updated_at = datetime.now(timezone.utc)

        if active_row.alert_id and event_type in CAMERA_EVENT_AUTO_RECOVERY_TYPES:
            alert = db.get(Alert, active_row.alert_id)
            if alert:
                _auto_close_device_alert(
                    db,
                    alert,
                    f"Recuperação automática recebida do dispositivo ({payload.provider}).",
                )
                notify(
                    db,
                    title=f"{CAMERA_EVENT_LABELS.get(event_type, event_type)} normalizado",
                    message=f"{school.name} — {camera.name if camera else recorder.name if recorder else 'Dispositivo'}",
                    severity="INFO",
                    module="Eventos de Câmera",
                    school_id=school.id,
                    entity_type="alert",
                    entity_id=alert.id,
                )

        _apply_event_to_health(
            db,
            camera=camera,
            recorder=recorder,
            event_type=event_type,
            active=False,
            occurred_at=occurred_at,
            metadata=metadata,
        )
        db.flush()
        return CameraEventIngestOut(
            accepted=True,
            deduplicated=True,
            event_id=active_row.id,
            alert_id=active_row.alert_id,
            event_type=event_type,
            state="INACTIVE",
            repeat_count=active_row.repeat_count,
        )

    _apply_event_to_health(
        db,
        camera=camera,
        recorder=recorder,
        event_type=event_type,
        active=False,
        occurred_at=occurred_at,
        metadata=metadata,
    )
    db.flush()
    return CameraEventIngestOut(
        accepted=True,
        event_type=event_type,
        state="INACTIVE",
        repeat_count=0,
    )


def _parse_hikvision_datetime(value: str | None) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_hikvision_event_xml(raw_body: bytes) -> list[dict]:
    text_body = raw_body.decode("utf-8", errors="ignore").strip()
    if not text_body:
        return []

    fragments = re.findall(
        r"<(?:[A-Za-z0-9_]+:)?EventNotificationAlert\b.*?</(?:[A-Za-z0-9_]+:)?EventNotificationAlert>",
        text_body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not fragments and "<EventNotificationAlert" in text_body:
        fragments = [text_body]

    events: list[dict] = []
    for fragment in fragments[:100]:
        try:
            root = ET.fromstring(fragment)
        except ET.ParseError:
            continue

        values: dict[str, str] = {}
        for element in root.iter():
            local = element.tag.split("}")[-1]
            value = (element.text or "").strip()
            if value and local not in values:
                values[local] = value

        event_type = values.get("eventType") or values.get("EventType")
        if not event_type:
            continue

        channel_value = (
            values.get("channelID")
            or values.get("dynChannelID")
            or values.get("inputPort")
            or values.get("videoInputChannelID")
        )
        channel = None
        if channel_value:
            try:
                channel = normalize_hikvision_channel_number(channel_value, 1)
            except Exception:
                channel = None

        events.append(
            {
                "provider_event_type": event_type,
                "event_state": values.get("eventState") or "ACTIVE",
                "source_channel": channel,
                "occurred_at": _parse_hikvision_datetime(values.get("dateTime")),
                "event_uid": values.get("UUID") or values.get("eventID"),
                "metadata": {
                    key: value
                    for key, value in values.items()
                    if key not in {
                        "eventType",
                        "EventType",
                        "eventState",
                        "channelID",
                        "dynChannelID",
                        "inputPort",
                        "videoInputChannelID",
                        "dateTime",
                        "UUID",
                        "eventID",
                    }
                },
                "raw_payload": fragment[:20000],
            }
        )
    return events




def parse_hikvision_event_json(raw_body: bytes) -> list[dict]:
    try:
        payload = json.loads(raw_body.decode("utf-8", errors="ignore"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []

    candidates = payload if isinstance(payload, list) else [payload]
    events: list[dict] = []
    for candidate in candidates[:100]:
        if not isinstance(candidate, dict):
            continue
        root = candidate.get("EventNotificationAlert") if isinstance(candidate.get("EventNotificationAlert"), dict) else candidate
        event_type = root.get("eventType") or root.get("EventType") or root.get("type")
        if not event_type:
            continue
        channel_value = root.get("channelID") or root.get("dynChannelID") or root.get("inputPort") or root.get("videoInputChannelID")
        channel = None
        if channel_value is not None:
            try:
                channel = normalize_hikvision_channel_number(str(channel_value), 1)
            except Exception:
                channel = None
        occurred = _parse_hikvision_datetime(root.get("dateTime") or root.get("time"))
        metadata = {
            str(key): value
            for key, value in root.items()
            if key not in {
                "eventType", "EventType", "type", "eventState", "channelID", "dynChannelID",
                "inputPort", "videoInputChannelID", "dateTime", "time", "UUID", "eventID"
            }
            and isinstance(value, (str, int, float, bool, type(None)))
        }
        events.append(
            {
                "provider_event_type": str(event_type),
                "event_state": str(root.get("eventState") or root.get("state") or "ACTIVE"),
                "source_channel": channel,
                "occurred_at": occurred,
                "event_uid": root.get("UUID") or root.get("eventID"),
                "metadata": metadata,
                "raw_payload": json.dumps(candidate, ensure_ascii=False, default=str)[:20000],
            }
        )
    return events


def parse_hikvision_event_payload(raw_body: bytes) -> list[dict]:
    stripped = raw_body.lstrip()
    if stripped.startswith(b"{") or stripped.startswith(b"["):
        parsed_json = parse_hikvision_event_json(raw_body)
        if parsed_json:
            return parsed_json
    return parse_hikvision_event_xml(raw_body)


def _extract_first_jpeg(raw_body: bytes) -> bytes | None:
    start = raw_body.find(b"\xff\xd8\xff")
    if start < 0:
        return None
    end = raw_body.find(b"\xff\xd9", start + 3)
    if end < 0:
        return None
    image = raw_body[start : end + 2]
    if len(image) < 4 or len(image) > 6_000_000:
        return None
    return image


def attach_hikvision_event_evidence(db: Session, alert_id: int | None, raw_body: bytes) -> str | None:
    if not alert_id:
        return None
    alert = db.get(Alert, alert_id)
    if not alert:
        return None
    image = _extract_first_jpeg(raw_body)
    if not image:
        return None
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"alert-{alert.id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.jpg"
    path = EVIDENCE_DIR / filename
    path.write_bytes(image)
    alert.evidence_path = f"evidence/{filename}"
    alert.updated_at = datetime.now(timezone.utc)
    add_alert_activity(
        db,
        alert,
        "EVIDENCIA_RECEBIDA",
        from_status=alert.status,
        to_status=alert.status,
        note="Snapshot JPEG recebido junto ao evento do dispositivo.",
        user_name="Hikvision ISAPI",
    )
    return alert.evidence_path


def require_event_ingest_key(
    x_eduvigia_event_key: str | None = Header(default=None, alias="X-EduVigIA-Event-Key"),
) -> None:
    expected = os.getenv("EDUVIGIA_EVENT_INGEST_KEY", "").strip()
    if not expected:
        raise HTTPException(503, "EDUVIGIA_EVENT_INGEST_KEY não configurada")
    provided = (x_eduvigia_event_key or "").strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(401, "Chave de ingestão de eventos inválida")


def scope_camera_event_query(query, user: UserAccount):
    restricted_school_id = scoped_school_id(user)
    if restricted_school_id is not None:
        query = query.filter(CameraEvent.school_id == restricted_school_id)
    return query


def scope_camera_health_query(query, user: UserAccount):
    restricted_school_id = scoped_school_id(user)
    if restricted_school_id is not None:
        query = query.filter(CameraHealth.school_id == restricted_school_id)
    return query


def scope_recorder_health_query(query, user: UserAccount):
    restricted_school_id = scoped_school_id(user)
    if restricted_school_id is not None:
        query = query.filter(RecorderHealth.school_id == restricted_school_id)
    return query


def require_roles(*roles: str):
    def dependency(user: UserAccount = Depends(require_user)) -> UserAccount:
        if not role_matches(user, roles):
            raise HTTPException(403, "Perfil sem permissão para esta operação")
        return user
    return dependency


def require_permission(permission: str):
    def dependency(user: UserAccount = Depends(require_user)) -> UserAccount:
        permissions = role_permissions(user.role, user.school_id)
        if "*" not in permissions and permission not in permissions:
            raise HTTPException(403, "Perfil sem permissão para esta operação")
        return user
    return dependency


app = FastAPI(title="EduVigIA API", version=APP_VERSION)
CORS_ORIGINS = [
    item.strip()
    for item in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5177,http://127.0.0.1:5177",
    ).split(",")
    if item.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=os.getenv(
        "CORS_ORIGIN_REGEX",
        r"^https?://(localhost|127\.0\.0\.1|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(?::\d+)?$",
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


PUBLIC_PATHS = {
    "/health",
    "/live",
    "/ready",
    "/metrics",
    "/auth/login",
    "/support/info",
    "/support/requests",
    "/internal/mediamtx-auth",
    "/docs",
    "/openapi.json",
    "/redoc",
}


@app.middleware("http")
async def authentication_middleware(request: Request, call_next):
    ip_token = AUDIT_IP.set(request.client.host if request.client else None)
    user_agent_token = AUDIT_USER_AGENT.set(request.headers.get("User-Agent"))
    actor_token = AUDIT_ACTOR.set(None)
    try:
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if (
            path in PUBLIC_PATHS
            or path.startswith("/docs")
            or path.startswith("/redoc")
            or path.startswith("/integrations/camera-events/")
        ):
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        token = authorization.removeprefix("Bearer ").strip()

        with SessionLocal() as db:
            user = resolve_session(db, token)
            if not user:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Sessão inválida ou expirada"},
                )
            if user.must_change_password and path not in PASSWORD_CHANGE_ALLOWED_PATHS:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Troca de senha obrigatória antes de continuar",
                        "code": "PASSWORD_CHANGE_REQUIRED",
                    },
                )
            payload = user_payload(user)
            request.state.user = payload
            AUDIT_ACTOR.set(payload)

        return await call_next(request)
    finally:
        AUDIT_ACTOR.reset(actor_token)
        AUDIT_IP.reset(ip_token)
        AUDIT_USER_AGENT.reset(user_agent_token)


def _normalized_metric_path(path: str) -> str:
    value = re.sub(r"/(?P<id>\d+)(?=/|$)", "/{id}", path or "/")
    return value[:160]


def _pool_snapshot() -> dict:
    pool = engine.pool
    result = {
        "configured_size": DB_POOL_SIZE if DATABASE_URL.startswith("postgresql") else None,
        "configured_max_overflow": DB_MAX_OVERFLOW if DATABASE_URL.startswith("postgresql") else None,
        "timeout_seconds": DB_POOL_TIMEOUT_SECONDS,
        "recycle_seconds": DB_POOL_RECYCLE_SECONDS,
    }
    for key, method_name in (
        ("size", "size"),
        ("checked_in", "checkedin"),
        ("checked_out", "checkedout"),
        ("overflow", "overflow"),
    ):
        method = getattr(pool, method_name, None)
        try:
            result[key] = method() if callable(method) else None
        except Exception:
            result[key] = None
    return result


def _storage_readiness() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(DATA_DIR)
    used_percent = round((usage.used / usage.total) * 100, 2) if usage.total else 0.0
    probe = DATA_DIR / ".eduvigia-write-probe"
    writable = False
    error = None
    try:
        probe.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
        probe.unlink(missing_ok=True)
        writable = True
    except Exception as exc:
        error = str(exc)
    status = "ONLINE" if writable else "OFFLINE"
    if writable and used_percent >= STORAGE_CRITICAL_PERCENT:
        status = "CRITICAL"
    elif writable and used_percent >= STORAGE_WARNING_PERCENT:
        status = "WARNING"
    return {
        "status": status,
        "writable": writable,
        "used_percent": used_percent,
        "free_bytes": usage.free,
        "warning_percent": STORAGE_WARNING_PERCENT,
        "critical_percent": STORAGE_CRITICAL_PERCENT,
        "error": error,
    }


def collect_readiness(db: Session | None = None) -> dict:
    owns_db = db is None
    current_db = db or SessionLocal()
    services: dict[str, dict] = {}
    try:
        started = time.monotonic()
        try:
            current_db.execute(text("SELECT 1"))
            services["database"] = {
                "status": "ONLINE",
                "latency_ms": round((time.monotonic() - started) * 1000, 2),
            }
        except Exception as exc:
            services["database"] = {"status": "OFFLINE", "error": str(exc)}

        try:
            import redis as redis_client

            started = time.monotonic()
            client = redis_client.from_url(
                os.getenv("REDIS_URL", "redis://redis:6379/0"),
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            pong = client.ping()
            services["redis"] = {
                "status": "ONLINE" if pong else "OFFLINE",
                "latency_ms": round((time.monotonic() - started) * 1000, 2),
            }
            client.close()
        except Exception as exc:
            services["redis"] = {"status": "OFFLINE", "error": str(exc)}

        services["mediamtx"] = _tcp_check("mediamtx", 9997, timeout=2.0)
        services["storage"] = _storage_readiness()
        required_online = (
            APP_STARTUP_COMPLETE
            and services["database"].get("status") == "ONLINE"
            and services["redis"].get("status") == "ONLINE"
            and services["mediamtx"].get("status") == "ONLINE"
            and services["storage"].get("status") not in {"OFFLINE", "CRITICAL"}
        )
        return {
            "ready": bool(required_online),
            "status": "READY" if required_online else "NOT_READY",
            "version": APP_VERSION,
            "checked_at": datetime.now(timezone.utc),
            "startup_complete": APP_STARTUP_COMPLETE,
            "services": services,
        }
    finally:
        if owns_db:
            current_db.close()


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", "").strip()[:80] or uuid.uuid4().hex
    request.state.request_id = request_id
    started = time.monotonic()
    with REQUEST_METRICS_LOCK:
        REQUEST_METRICS["active"] += 1
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        elapsed = time.monotonic() - started
        bucket = f"status_{status_code // 100}xx"
        with REQUEST_METRICS_LOCK:
            REQUEST_METRICS["active"] = max(0, REQUEST_METRICS["active"] - 1)
            REQUEST_METRICS["total"] += 1
            REQUEST_METRICS["latency_seconds_sum"] += elapsed
            if bucket in REQUEST_METRICS:
                REQUEST_METRICS[bucket] += 1
        LOGGER.info(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": _normalized_metric_path(request.url.path),
                    "status": status_code,
                    "duration_ms": round(elapsed * 1000, 2),
                    "client_ip": request.client.host if request.client else None,
                },
                ensure_ascii=False,
            )
        )


def enforce_runtime_schema_revision() -> None:
    """Block an existing PostgreSQL runtime from starting against the wrong Alembic revision."""
    if not DATABASE_URL.startswith("postgresql"):
        return
    with engine.connect() as connection:
        has_revision = connection.execute(
            text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
        ).scalar()
        if not has_revision:
            return
        current = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if current and str(current) != EXPECTED_ALEMBIC_REVISION:
            raise RuntimeError(
                f"Schema incompatível: runtime={APP_VERSION}; "
                f"alembic={current}; esperado={EXPECTED_ALEMBIC_REVISION}. "
                "Aplique a migration antes de iniciar a API."
            )


@app.on_event("startup")
def startup() -> None:
    enforce_runtime_schema_revision()
    Base.metadata.create_all(engine)
    ensure_schema()
    Base.metadata.create_all(engine)

    with SessionLocal() as db:
        if db.query(UserAccount).count() == 0:
            bootstrap_password = os.getenv(
                "EDUVIGIA_BOOTSTRAP_ADMIN_PASSWORD",
                "",
            ).strip()
            if not bootstrap_password:
                raise RuntimeError(
                    "EDUVIGIA_BOOTSTRAP_ADMIN_PASSWORD deve ser configurada para a instalação inicial"
                )
            validate_password_policy(bootstrap_password)
            db.add(
                UserAccount(
                    name="Administrador EduVigIA",
                    email=os.getenv("EDUVIGIA_BOOTSTRAP_ADMIN_EMAIL", "admin@eduvigia.local").strip().lower(),
                    password_hash=hash_password(bootstrap_password),
                    role="ADMIN_SECRETARIA",
                    active=True,
                    must_change_password=True,
                )
            )
            db.commit()


        if db.query(Notification).count() == 0:
            db.add(
                Notification(
                    title="EduVigIA atualizado",
                    message=f"Versão {APP_VERSION}: VMS multi-canal com PTZ, playback, Video Wall e Mapas Operacionais.",
                    severity="INFO",
                    module="Sistema",
                )
            )
            db.commit()

        if db.query(SystemSetting).count() == 0:
            db.add_all(
                [
                    SystemSetting(
                        key="alert_retention_days",
                        value="180",
                        description="Dias de retenção de alertas",
                    ),
                    SystemSetting(
                        key="occurrence_sla_minutes",
                        value="15",
                        description="Tempo de resposta operacional esperado",
                    ),
                    SystemSetting(
                        key="default_camera_manufacturer",
                        value="Hikvision",
                        description="Fabricante padrão no cadastro de câmeras",
                    ),
                ]
            )
            db.commit()

        if db.query(DispatchTeam).count() == 0:
            db.add_all(
                [
                    DispatchTeam(name="Equipe 01", team_type="INTERNA", phone=""),
                    DispatchTeam(name="Direção Escolar", team_type="DIRECAO", phone=""),
                    DispatchTeam(name="Manutenção Técnica", team_type="MANUTENCAO", phone=""),
                ]
            )
            db.commit()

        if (
            os.getenv("EDUVIGIA_SEED_DEMO_DATA", "false").strip().lower() == "true"
            and db.query(Alert).count() == 0
        ):
            db.add_all(
                [
                    Alert(
                        school_name="E.M. Darcy Ribeiro",
                        camera_name="Cam-02 Pátio 1",
                        event_type="Possível queda",
                        priority="ALTA",
                    ),
                    Alert(
                        school_name="E.M. Darcy Ribeiro",
                        camera_name="Cam-03 Entrada Leste",
                        event_type="Invasão perimetral",
                        priority="CRITICA",
                    ),
                    Alert(
                        school_name="E.M. João Silva",
                        camera_name="Cam-04 Corredor",
                        event_type="Aluno isolado",
                        priority="MEDIA",
                    ),
                    Alert(
                        school_name="E.M. Anísio Teixeira",
                        camera_name="Cam-01 Pátio",
                        event_type="Aglomeração",
                        priority="BAIXA",
                    ),
                ]
            )
            db.commit()

        schools_by_name = {
            school.name.strip().lower(): school
            for school in db.query(School).all()
        }
        for alert in db.query(Alert).filter(Alert.school_id.is_(None)).all():
            school = schools_by_name.get((alert.school_name or "").strip().lower())
            if school:
                alert.school_id = school.id
        for occurrence in db.query(Occurrence).filter(Occurrence.school_id.is_(None)).all():
            school = schools_by_name.get((occurrence.school_name or "").strip().lower())
            if school:
                occurrence.school_id = school.id
        for alert in db.query(Alert).filter(Alert.camera_id.is_(None), Alert.school_id.isnot(None)).all():
            camera = (
                db.query(Camera)
                .filter(
                    Camera.school_id == alert.school_id,
                    Camera.name.ilike((alert.camera_name or "").strip()),
                )
                .first()
            )
            if camera:
                alert.camera_id = camera.id
        db.commit()

        # Reprovisionamento automático dos paths após reinicialização.
        # Falhas individuais não impedem a inicialização da API.
        for camera in db.query(Camera).all():
            try:
                _, obsolete_streams = ensure_secure_camera_streams(db, camera)
                for obsolete_stream in obsolete_streams:
                    delete_camera_path(obsolete_stream)
                ok, detail = provision_camera_path(camera, db)
                camera.last_error = None if ok else detail
            except Exception as error:
                camera.last_error = str(error)
        db.commit()

    global APP_STARTUP_COMPLETE
    APP_STARTUP_COMPLETE = True
    LOGGER.info(json.dumps({"event": "startup_complete", "version": APP_VERSION}, ensure_ascii=False))


@app.on_event("shutdown")
def shutdown() -> None:
    global APP_STARTUP_COMPLETE
    APP_STARTUP_COMPLETE = False
    engine.dispose()


@app.get("/live")
def live():
    return {
        "status": "alive",
        "system": "EduVigIA",
        "version": APP_VERSION,
        "uptime_seconds": round(time.monotonic() - APP_STARTED_MONOTONIC, 2),
    }


@app.get("/ready")
def ready():
    snapshot = collect_readiness()
    return JSONResponse(status_code=200 if snapshot["ready"] else 503, content=json.loads(json.dumps(snapshot, default=str)))


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    with REQUEST_METRICS_LOCK:
        counters = dict(REQUEST_METRICS)
    pool = _pool_snapshot()
    db_up = 0
    schools = cameras = recorders = sessions = 0
    alerts_active = alerts_new = alerts_critical = 0
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            db_up = 1
            schools = db.query(School).filter(School.active.is_(True)).count()
            cameras = db.query(Camera).count()
            recorders = db.query(Recorder).count()
            sessions = db.query(AuthSession).filter(AuthSession.expires_at > datetime.now(timezone.utc)).count()
            alerts_active = db.query(Alert).filter(Alert.status.in_(["NOVO", "EM_ATENDIMENTO", "CONFIRMADO"])).count()
            alerts_new = db.query(Alert).filter(Alert.status == "NOVO").count()
            alerts_critical = db.query(Alert).filter(
                Alert.status.in_(["NOVO", "EM_ATENDIMENTO", "CONFIRMADO"]),
                Alert.priority == "CRITICA",
            ).count()
    except Exception:
        pass
    try:
        memory_bytes = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
    except Exception:
        memory_bytes = 0
    lines = [
        "# HELP eduvigia_info Build information.",
        "# TYPE eduvigia_info gauge",
        f'eduvigia_info{{version="{APP_VERSION}",environment="{os.getenv("APP_ENV", "development")}"}} 1',
        "# HELP eduvigia_uptime_seconds Process uptime.",
        "# TYPE eduvigia_uptime_seconds gauge",
        f"eduvigia_uptime_seconds {time.monotonic() - APP_STARTED_MONOTONIC:.3f}",
        "# HELP eduvigia_http_requests_total Total HTTP requests.",
        "# TYPE eduvigia_http_requests_total counter",
        f"eduvigia_http_requests_total {counters['total']}",
        f"eduvigia_http_requests_active {counters['active']}",
        f"eduvigia_http_request_duration_seconds_sum {counters['latency_seconds_sum']:.6f}",
        f"eduvigia_http_responses_2xx_total {counters['status_2xx']}",
        f"eduvigia_http_responses_3xx_total {counters['status_3xx']}",
        f"eduvigia_http_responses_4xx_total {counters['status_4xx']}",
        f"eduvigia_http_responses_5xx_total {counters['status_5xx']}",
        f"eduvigia_database_up {db_up}",
        f"eduvigia_database_pool_checked_out {pool.get('checked_out') or 0}",
        f"eduvigia_database_pool_size {pool.get('size') or 0}",
        f"eduvigia_schools_active {schools}",
        f"eduvigia_cameras_total {cameras}",
        f"eduvigia_recorders_total {recorders}",
        f"eduvigia_auth_sessions_active {sessions}",
        "# HELP eduvigia_alerts_active Alertas operacionais ativos.",
        "# TYPE eduvigia_alerts_active gauge",
        f"eduvigia_alerts_active {alerts_active}",
        "# HELP eduvigia_alerts_new Alertas aguardando triagem.",
        "# TYPE eduvigia_alerts_new gauge",
        f"eduvigia_alerts_new {alerts_new}",
        "# HELP eduvigia_alerts_critical Alertas críticos ativos.",
        "# TYPE eduvigia_alerts_critical gauge",
        f"eduvigia_alerts_critical {alerts_critical}",
        f"eduvigia_process_memory_bytes {memory_bytes}",
    ]
    return "\n".join(lines) + "\n"


@app.get("/health")
def health():
    return {
        "status": "ok",
        "system": "EduVigIA",
        "version": APP_VERSION,
        "video_gateway": "seguro",
        "stream_auth": "token_temporario",
        "infrastructure": "runtime_operational",
        "readiness": "/ready",
        "metrics": "/metrics",
    }


@app.get("/dashboard")
def dashboard(
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    restricted_school_id = scoped_school_id(user)
    school_query = db.query(School).filter(School.active.is_(True))
    if restricted_school_id is not None:
        school_query = school_query.filter(School.id == restricted_school_id)
    camera_query = school_scope_query(db.query(Camera), Camera, user)
    occurrence_query = scope_occurrence_query(db.query(Occurrence), db, user)
    alert_query = scope_alert_query(db.query(Alert), db, user)

    teams = (
        db.query(DispatchTeam)
        .filter(DispatchTeam.status.in_(["ACIONADA", "EM_DESLOCAMENTO", "EM_ATENDIMENTO"]))
        .count()
        if canonical_role(user.role, user.school_id) in {"ADMIN_SECRETARIA", "SUPERVISOR_GUARDA", "DESPACHANTE_GUARDA"}
        else 0
    )

    return {
        "schools": school_query.count(),
        "cameras": camera_query.count(),
        "online": camera_query.filter(Camera.status == "ONLINE").count(),
        "alerts": alert_query.filter(Alert.status.in_(["NOVO", "EM_ATENDIMENTO", "CONFIRMADO"])).count(),
        "occurrences": occurrence_query.filter(Occurrence.status != "ENCERRADA").count(),
        "teams": teams,
        "offline": camera_query.filter(Camera.status == "OFFLINE").count(),
        "pending": camera_query.filter(Camera.status == "PENDING").count(),
    }


@app.get("/schools", response_model=list[SchoolOut])
def schools(
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    query = db.query(School)
    restricted_school_id = scoped_school_id(user)
    if restricted_school_id is not None:
        query = query.filter(School.id == restricted_school_id)
    if search:
        term = f"%{search}%"
        query = query.filter(
            School.name.ilike(term)
            | School.address.ilike(term)
            | School.code.ilike(term)
        )
    if status:
        query = query.filter(School.operational_status == status.upper())
    return query.order_by(School.active.desc(), School.name.asc()).all()


@app.get("/schools/{school_id}", response_model=SchoolOut)
def school_detail(
    school_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    ensure_school_access(user, school_id)
    row = db.get(School, school_id)
    if not row:
        raise HTTPException(404, "Escola não encontrada")
    return row



@app.get("/schools/{school_id}/details")
def school_details(
    school_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    ensure_school_access(user, school_id)

    school = db.get(School, school_id)
    if not school:
        raise HTTPException(404, "Escola não encontrada")

    cameras = db.query(Camera).filter(Camera.school_id == school_id).all()
    equipment = db.query(Equipment).filter(Equipment.school_id == school_id).all()
    alerts = (
        db.query(Alert)
        .filter((Alert.school_id == school.id) | ((Alert.school_id.is_(None)) & (Alert.school_name == school.name)))
        .order_by(Alert.created_at.desc())
        .limit(20)
        .all()
    )
    occurrences = (
        db.query(Occurrence)
        .filter((Occurrence.school_id == school.id) | ((Occurrence.school_id.is_(None)) & (Occurrence.school_name == school.name)))
        .order_by(Occurrence.created_at.desc())
        .limit(20)
        .all()
    )
    online = len([camera for camera in cameras if camera.status == "ONLINE"])
    availability = round((online / len(cameras) * 100), 2) if cameras else 0.0

    return {
        "school": SchoolOut.model_validate(school),
        "cameras": [CameraOut.model_validate(camera) for camera in cameras],
        "equipment": [EquipmentOut.model_validate(item) for item in equipment],
        "alerts": [AlertOut.model_validate(item) for item in alerts],
        "occurrences": [OccurrenceOut.model_validate(item) for item in occurrences],
        "availability_percent": availability,
    }


@app.post("/schools", response_model=SchoolOut)
def create_school(
    payload: SchoolIn,
    db: Session = Depends(db_session),
    _: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA")),
):
    if payload.code and db.query(School).filter(School.code == payload.code).first():
        raise HTTPException(409, "Já existe uma escola com este código")
    row = School(**payload.model_dump())
    db.add(row)
    audit(db, "Escolas", "Cadastro", payload.name)
    db.commit()
    db.refresh(row)
    return row


@app.put("/schools/{school_id}", response_model=SchoolOut)
def update_school(
    school_id: int,
    payload: SchoolIn,
    db: Session = Depends(db_session),
    _: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA")),
):
    row = db.get(School, school_id)
    if not row:
        raise HTTPException(404, "Escola não encontrada")
    if payload.code:
        duplicate = db.query(School).filter(School.code == payload.code, School.id != school_id).first()
        if duplicate:
            raise HTTPException(409, "Já existe uma escola com este código")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    audit(db, "Escolas", "Edição", f"{row.id} - {row.name}")
    db.commit()
    db.refresh(row)
    return row


@app.patch("/schools/{school_id}/toggle", response_model=SchoolOut)
def toggle_school(
    school_id: int,
    db: Session = Depends(db_session),
    _: UserAccount = Depends(require_roles("ADMIN_SECRETARIA")),
):
    row = db.get(School, school_id)
    if not row:
        raise HTTPException(404, "Escola não encontrada")
    row.active = not row.active
    action_label = "ativada" if row.active else "inativada"
    notify(
        db,
        title=f"Escola {action_label}",
        message=f"{row.name} foi {action_label} no cadastro institucional.",
        severity="INFO" if row.active else "WARNING",
        module="Escolas",
        school_id=row.id,
        entity_type="school",
        entity_id=row.id,
    )
    audit(db, "Escolas", "Ativação/Inativação", f"{row.name}: {row.active}")
    db.commit()
    db.refresh(row)
    return row




def _xml_text(root: ET.Element, local_name: str) -> str | None:
    for element in root.iter():
        if element.tag.split("}")[-1] == local_name:
            value = (element.text or "").strip()
            if value:
                return value
            for attribute_name in ("opt", "min", "max", "default"):
                attribute_value = (element.attrib.get(attribute_name) or "").strip()
                if attribute_value:
                    return attribute_value
    return None


def _xml_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"false", "offline", "disabled", "0", "no"}


def normalize_hikvision_channel_number(value: object, fallback: int) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return fallback
    # Alguns endpoints Hikvision retornam o identificador do stream (101, 201...)
    # em vez do número lógico do canal. Nesses casos, convertemos para 1, 2...
    if number >= 100 and number % 100 in range(1, 10):
        logical = number // 100
        if logical >= 1:
            return logical
    return max(1, number)


def _validate_ip_address(value: str, label: str = "Endereço IP") -> str:
    cleaned = (value or "").strip()
    try:
        ipaddress.ip_address(cleaned)
    except ValueError:
        raise HTTPException(400, f"{label} inválido: {cleaned or 'não informado'}")
    return cleaned


def _validate_port(value: int, label: str, *, allow_zero: bool = False) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        raise HTTPException(400, f"{label} inválida")
    if allow_zero and port == 0:
        return port
    if port < 1 or port > 65535:
        minimum = 0 if allow_zero else 1
        raise HTTPException(400, f"{label} deve estar entre {minimum} e 65535")
    return port


def validate_recorder_payload(
    db: Session,
    payload: RecorderIn,
    *,
    exclude_id: int | None = None,
) -> None:
    ip_value = _validate_ip_address(payload.ip_address, "IP do gravador")
    _validate_port(payload.http_port, "Porta HTTP", allow_zero=True)
    _validate_port(payload.https_port, "Porta HTTPS", allow_zero=True)
    _validate_port(payload.rtsp_port, "Porta RTSP")
    _validate_port(payload.sdk_port, "Porta SDK", allow_zero=True)
    if not payload.http_port and not payload.https_port:
        raise HTTPException(400, "Informe ao menos uma porta HTTP ou HTTPS para o ISAPI")
    duplicate = db.query(Recorder).filter(
        Recorder.school_id == payload.school_id,
        Recorder.ip_address == ip_value,
    )
    if exclude_id:
        duplicate = duplicate.filter(Recorder.id != exclude_id)
    if duplicate.first():
        raise HTTPException(409, "Já existe um gravador com este IP nesta escola")


def validate_camera_payload(
    db: Session,
    payload: CameraIn,
    *,
    exclude_id: int | None = None,
) -> None:
    duplicate = db.query(Camera).filter(Camera.school_id == payload.school_id)
    if exclude_id:
        duplicate = duplicate.filter(Camera.id != exclude_id)

    if payload.ptz_enabled:
        if payload.ptz_protocol != "HIKVISION_ISAPI":
            raise HTTPException(400, "Nesta fase, PTZ homologado somente por Hikvision ISAPI")
        _validate_port(payload.ptz_http_port, "Porta HTTP/HTTPS PTZ")
        if payload.camera_type != "PTZ":
            raise HTTPException(400, "Controle PTZ exige câmera cadastrada como tipo PTZ")

    if payload.device_id:
        device = db.get(VideoDevice, payload.device_id)
        if not device or not device.active:
            raise HTTPException(404, "Dispositivo físico não encontrado")
        if device.school_id != payload.school_id:
            raise HTTPException(400, "O dispositivo físico pertence a outra escola")
        device_duplicate = duplicate.filter(Camera.device_id == payload.device_id, Camera.logical_channel == payload.logical_channel)
        if device_duplicate.first():
            raise HTTPException(409, "Este canal lógico do dispositivo já está cadastrado")
        return

    if payload.source_type in {"NVR", "DVR"}:
        if not payload.recorder_id:
            raise HTTPException(400, "Selecione o gravador para o canal NVR/DVR")
        duplicate = duplicate.filter(
            Camera.recorder_id == payload.recorder_id,
            Camera.nvr_channel == payload.nvr_channel,
        )
        if duplicate.first():
            raise HTTPException(409, "Este canal do gravador já está cadastrado")
    elif payload.source_type == "CAMERA_IP":
        ip_value = _validate_ip_address(payload.ip_address or "", "IP da câmera")
        _validate_port(payload.port, "Porta RTSP")
        duplicate = duplicate.filter(
            Camera.source_type == "CAMERA_IP",
            Camera.ip_address == ip_value,
            Camera.port == payload.port,
        )
        if duplicate.first():
            raise HTTPException(409, "Já existe uma câmera direta com este IP e porta nesta escola")
    elif payload.source_type == "RTSP_CUSTOM":
        main_url = (payload.rtsp_url_main or payload.rtsp_url or "").strip()
        sub_url = (payload.rtsp_url_sub or payload.rtsp_url or "").strip()
        if not main_url or not sub_url:
            raise HTTPException(400, "Informe as URLs RTSP MAIN e SUB")
        if not main_url.lower().startswith(("rtsp://", "rtsps://")) or not sub_url.lower().startswith(("rtsp://", "rtsps://")):
            raise HTTPException(400, "As URLs MAIN/SUB devem começar com rtsp:// ou rtsps://")


def _hikvision_request(
    recorder: Recorder,
    path: str,
    *,
    method: str = "GET",
    timeout: int = 8,
) -> tuple[int, bytes, str]:
    scheme = "https" if int(recorder.https_port or 0) > 0 and int(recorder.http_port or 80) == 0 else "http"
    port = recorder.https_port if scheme == "https" else recorder.http_port
    url = f"{scheme}://{recorder.ip_address}:{port}{path}"

    password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    password_mgr.add_password(
        None,
        url,
        recorder.username or "",
        decrypt_secret(recorder.password) or "",
    )
    handlers: list[object] = [
        urllib.request.HTTPDigestAuthHandler(password_mgr),
        urllib.request.HTTPBasicAuthHandler(password_mgr),
    ]
    if scheme == "https":
        import ssl

        handlers.append(urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    opener = urllib.request.build_opener(*handlers)
    request = urllib.request.Request(
        url,
        method=method,
        headers={
            "Accept": "application/xml",
            "User-Agent": f"EduVigIA/{APP_VERSION}",
        },
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.read(), response.headers.get_content_type()
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="ignore")
        if error.code in {401, 403}:
            raise HTTPException(502, "Credenciais ISAPI recusadas pelo equipamento")
        raise HTTPException(
            status_code=502,
            detail=f"ISAPI respondeu HTTP {error.code}: {detail[:220] or error.reason}",
        )
    except urllib.error.URLError as error:
        raise HTTPException(
            status_code=502,
            detail=f"Falha de conexão ISAPI: {error.reason}",
        )
    except TimeoutError:
        raise HTTPException(504, "Tempo limite ao consultar o ISAPI")




def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _validate_playback_range(start_at: datetime, end_at: datetime, *, max_seconds: int = PLAYBACK_EXPORT_MAX_SECONDS) -> tuple[datetime, datetime, int]:
    start = _as_utc(start_at)
    end = _as_utc(end_at)
    seconds = int((end - start).total_seconds())
    if seconds <= 0:
        raise HTTPException(400, "O fim do playback deve ser posterior ao início")
    if seconds > max_seconds:
        raise HTTPException(400, f"Intervalo máximo permitido: {max_seconds // 60} minuto(s)")
    return start, end, seconds


def _playback_target(db: Session, camera: Camera) -> dict:
    channel = int(camera.logical_channel or 1)
    if camera.source_type in {"NVR", "DVR"} and camera.recorder_id:
        recorder = db.get(Recorder, camera.recorder_id)
        if not recorder:
            raise HTTPException(409, "Gravador da câmera não encontrado")
        use_https = int(recorder.https_port or 0) > 0 and int(recorder.http_port or 80) == 0
        return {
            "host": recorder.ip_address,
            "rtsp_port": int(recorder.rtsp_port or 554),
            "http_port": int(recorder.https_port if use_https else recorder.http_port or 80),
            "https": use_https,
            "username": recorder.username or "",
            "password": decrypt_secret(recorder.password) or "",
            "channel": int(camera.nvr_channel or 1),
            "origin": "NVR" if camera.source_type == "NVR" else "DVR",
        }
    if camera.device_id:
        device = db.get(VideoDevice, camera.device_id)
        if not device:
            raise HTTPException(409, "Dispositivo físico da câmera não encontrado")
        use_https = int(device.https_port or 0) > 0 and int(device.http_port or 80) == 0
        return {
            "host": device.ip_address,
            "rtsp_port": int(device.rtsp_port or 554),
            "http_port": int(device.https_port if use_https else device.http_port or 80),
            "https": use_https,
            "username": device.username or "",
            "password": decrypt_secret(device.password) or "",
            "channel": channel,
            "origin": "DEVICE",
        }
    if camera.source_type == "RTSP_CUSTOM":
        raise HTTPException(501, "Playback por RTSP customizado exige integração de gravação específica")
    if not camera.ip_address:
        raise HTTPException(409, "Origem de playback não configurada")
    return {
        "host": camera.ip_address,
        "rtsp_port": int(camera.port or 554),
        "http_port": int(camera.ptz_http_port or 80),
        "https": bool(camera.ptz_https),
        "username": camera.username or "",
        "password": decrypt_secret(camera.password) or "",
        "channel": 1,
        "origin": "CAMERA",
    }


def build_hikvision_playback_rtsp(db: Session, camera: Camera, start_at: datetime, end_at: datetime) -> str:
    start, end, _ = _validate_playback_range(start_at, end_at)
    target = _playback_target(db, camera)
    user = urllib.parse.quote(target["username"], safe="")
    secret = urllib.parse.quote(target["password"], safe="")
    credentials = user + (f":{secret}" if secret else "") + "@" if user else ""
    track = int(target["channel"]) * 100 + 1
    start_q = start.strftime("%Y%m%dT%H%M%SZ")
    end_q = end.strftime("%Y%m%dT%H%M%SZ")
    return f"rtsp://{credentials}{target['host']}:{target['rtsp_port']}/Streaming/tracks/{track}?starttime={start_q}&endtime={end_q}"


def _playback_xml_request(db: Session, camera: Camera, body: bytes, timeout: int = 8) -> tuple[int, bytes]:
    target = _playback_target(db, camera)
    scheme = "https" if target["https"] else "http"
    url = f"{scheme}://{target['host']}:{target['http_port']}/ISAPI/ContentMgmt/search"
    password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    password_mgr.add_password(None, url, target["username"], target["password"])
    handlers: list[object] = [urllib.request.HTTPDigestAuthHandler(password_mgr), urllib.request.HTTPBasicAuthHandler(password_mgr)]
    if scheme == "https":
        import ssl
        handlers.append(urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    opener = urllib.request.build_opener(*handlers)
    request = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type":"application/xml", "Accept":"application/xml", "User-Agent":f"EduVigIA/{APP_VERSION}"})
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        if error.code in {401,403}:
            raise HTTPException(502, "Credenciais de playback recusadas pelo equipamento")
        raise HTTPException(502, f"Busca de gravação respondeu HTTP {error.code}")
    except urllib.error.URLError as error:
        raise HTTPException(502, f"Falha ao consultar gravações: {error.reason}")


def _xml_local(node: ET.Element, name: str) -> list[ET.Element]:
    return [item for item in node.iter() if item.tag.rsplit('}', 1)[-1] == name]


def _parse_hikvision_recordings(payload: bytes) -> list[dict]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        raise HTTPException(502, "Resposta de busca de gravações inválida")
    matches=[]
    for item in _xml_local(root, "searchMatchItem"):
        starts=_xml_local(item,"startTime")
        ends=_xml_local(item,"endTime")
        if not starts or not ends or not starts[0].text or not ends[0].text:
            continue
        types=_xml_local(item,"metadataDescriptor") or _xml_local(item,"recordType")
        matches.append({"start_at": starts[0].text, "end_at": ends[0].text, "record_type": (types[0].text if types and types[0].text else "CONTINUOUS")})
    return matches


def _playback_search_body(camera: Camera, start_at: datetime, end_at: datetime, max_results: int) -> bytes:
    start, end, _ = _validate_playback_range(start_at, end_at, max_seconds=24*60*60)
    track = (int(camera.nvr_channel or 1) if camera.source_type in {"NVR","DVR"} else int(camera.logical_channel or 1)) * 100 + 1
    search_id = str(uuid.uuid4())
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>'
           f'<CMSearchDescription><searchID>{search_id}</searchID>'
           f'<trackList><trackID>{track}</trackID></trackList>'
           f'<timeSpanList><timeSpan><startTime>{start.isoformat().replace("+00:00","Z")}</startTime>'
           f'<endTime>{end.isoformat().replace("+00:00","Z")}</endTime></timeSpan></timeSpanList>'
           f'<maxResults>{int(max_results)}</maxResults><searchResultPosition>0</searchResultPosition>'
           f'<metadataList><metadataDescriptor>//recordType.meta.std-cgi.com</metadataDescriptor></metadataList>'
           f'</CMSearchDescription>')
    return xml.encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_custody(db: Session, evidence: Evidence, action: str, user: UserAccount, *, observed: str | None = None, detail: str | None = None) -> None:
    db.add(EvidenceCustodyEvent(evidence_id=evidence.id, action=action, user_id=user.id, user_name=user.name, sha256_observed=observed, detail=detail))


def _run_playback_export(source: str, target: Path, duration_seconds: int, timeout_seconds: int | None = None) -> None:
    timeout = timeout_seconds or min(max(duration_seconds + 45, 60), PLAYBACK_EXPORT_MAX_SECONDS + 90)
    command=["ffmpeg","-hide_banner","-loglevel","error","-rtsp_transport","tcp","-i",source,"-t",str(duration_seconds),"-map","0:v:0","-map","0:a?","-c","copy","-movflags","+faststart","-y",str(target)]
    try:
        process=subprocess.run(command,capture_output=True,text=True,timeout=timeout)
    except subprocess.TimeoutExpired:
        raise HTTPException(504,"Tempo limite ao recuperar trecho gravado")
    if process.returncode != 0 or not target.exists() or target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(502,(process.stderr or "Não foi possível recuperar o trecho gravado")[-700:])


def _cleanup_playback_previews() -> None:
    now=datetime.now(timezone.utc)
    with PLAYBACK_PREVIEW_LOCK:
        expired=[token for token,item in PLAYBACK_PREVIEWS.items() if item["expires_at"] <= now]
        for token in expired:
            Path(PLAYBACK_PREVIEWS[token]["path"]).unlink(missing_ok=True)
            PLAYBACK_PREVIEWS.pop(token,None)

PTZ_LEASE_SECONDS = max(15, min(120, int(os.getenv("EDUVIGIA_PTZ_LEASE_SECONDS", "30"))))
PTZ_SPEED_MAP = {1: 15, 2: 30, 3: 45, 4: 60, 5: 75, 6: 90, 7: 100}
PTZ_DIRECTIONS = {
    "UP": (0, 1, 0),
    "DOWN": (0, -1, 0),
    "LEFT": (-1, 0, 0),
    "RIGHT": (1, 0, 0),
    "UP_LEFT": (-1, 1, 0),
    "UP_RIGHT": (1, 1, 0),
    "DOWN_LEFT": (-1, -1, 0),
    "DOWN_RIGHT": (1, -1, 0),
    "ZOOM_IN": (0, 0, 1),
    "ZOOM_OUT": (0, 0, -1),
}


def _ptz_target(camera: Camera, db: Session) -> dict:
    if not camera.ptz_enabled:
        raise HTTPException(409, "Controle PTZ não está habilitado para esta câmera")
    if (camera.ptz_protocol or "HIKVISION_ISAPI") != "HIKVISION_ISAPI":
        raise HTTPException(501, "Protocolo PTZ ainda não homologado")
    channel = int(camera.ptz_channel or camera.nvr_channel or 1)
    if camera.source_type in {"NVR", "DVR"} and camera.recorder_id:
        recorder = db.get(Recorder, camera.recorder_id)
        if not recorder:
            raise HTTPException(409, "Gravador da câmera não encontrado")
        use_https = int(recorder.https_port or 0) > 0 and int(recorder.http_port or 80) == 0
        return {
            "host": recorder.ip_address,
            "port": int(recorder.https_port if use_https else recorder.http_port),
            "https": use_https,
            "username": recorder.username or "",
            "password": decrypt_secret(recorder.password) or "",
            "channel": channel,
            "via": "RECORDER",
        }
    if camera.device_id:
        device = db.get(VideoDevice, camera.device_id)
        if not device:
            raise HTTPException(409, "Dispositivo físico PTZ não encontrado")
        use_https = bool(camera.ptz_https) or (int(device.https_port or 0) > 0 and int(device.http_port or 80) == 0)
        return {
            "host": device.ip_address,
            "port": int(device.https_port if use_https else device.http_port or 80),
            "https": use_https,
            "username": device.username or "",
            "password": decrypt_secret(device.password) or "",
            "channel": int(camera.ptz_channel or camera.logical_channel or 1),
            "via": "VIDEO_DEVICE",
        }
    if not camera.ip_address:
        raise HTTPException(409, "IP de controle PTZ não configurado")
    return {
        "host": camera.ip_address,
        "port": int(camera.ptz_http_port or 80),
        "https": bool(camera.ptz_https),
        "username": camera.username or "",
        "password": decrypt_secret(camera.password) or "",
        "channel": channel,
        "via": "CAMERA",
    }


def _ptz_xml_request(camera: Camera, db: Session, path: str, *, method: str = "GET", body: bytes | None = None, timeout: int = 5) -> tuple[int, bytes]:
    target = _ptz_target(camera, db)
    scheme = "https" if target["https"] else "http"
    url = f"{scheme}://{target['host']}:{target['port']}{path}"
    password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    password_mgr.add_password(None, url, target["username"], target["password"])
    handlers: list[object] = [
        urllib.request.HTTPDigestAuthHandler(password_mgr),
        urllib.request.HTTPBasicAuthHandler(password_mgr),
    ]
    if target["https"]:
        import ssl
        handlers.append(urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    opener = urllib.request.build_opener(*handlers)
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/xml",
            "Content-Type": "application/xml; charset=UTF-8",
            "User-Agent": f"EduVigIA/{APP_VERSION}",
        },
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="ignore")
        if error.code in {401, 403}:
            raise HTTPException(502, "Credenciais PTZ/ISAPI recusadas pelo equipamento")
        raise HTTPException(502, f"PTZ/ISAPI respondeu HTTP {error.code}: {detail[:220] or error.reason}")
    except urllib.error.URLError as error:
        raise HTTPException(502, f"Falha de conexão PTZ/ISAPI: {error.reason}")
    except TimeoutError:
        raise HTTPException(504, "Tempo limite no controle PTZ")


def _ptz_continuous_xml(pan: int, tilt: int, zoom: int) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<PTZData version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">'
        f'<pan>{pan}</pan><tilt>{tilt}</tilt><zoom>{zoom}</zoom>'
        '</PTZData>'
    ).encode("utf-8")


def _ptz_current_lease(db: Session, camera_id: int) -> CameraPTZLease | None:
    row = db.query(CameraPTZLease).filter(CameraPTZLease.camera_id == camera_id).first()
    if not row:
        return None
    now = datetime.now(timezone.utc)
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if expires <= now:
        db.delete(row)
        db.flush()
        return None
    return row


def _ptz_lease_payload(db: Session, row: CameraPTZLease | None, user: UserAccount) -> dict:
    if not row:
        return {"active": False, "mine": False, "holder": None, "expires_at": None}
    holder = db.get(UserAccount, row.user_id)
    return {
        "active": True,
        "mine": row.user_id == user.id,
        "holder": holder.name if holder else f"Usuário #{row.user_id}",
        "expires_at": row.expires_at,
    }


def _require_ptz_lease(db: Session, camera: Camera, user: UserAccount) -> CameraPTZLease:
    lease = _ptz_current_lease(db, camera.id)
    if not lease or lease.user_id != user.id:
        raise HTTPException(409, "Assuma o controle PTZ antes de movimentar a câmera")
    lease.expires_at = datetime.now(timezone.utc) + timedelta(seconds=PTZ_LEASE_SECONDS)
    lease.updated_at = datetime.now(timezone.utc)
    db.flush()
    return lease


def _send_ptz_move(db: Session, camera: Camera, direction: str, speed: int) -> None:
    target = _ptz_target(camera, db)
    vector = PTZ_DIRECTIONS[direction]
    scalar = PTZ_SPEED_MAP[int(speed)]
    pan = vector[0] * scalar
    tilt = vector[1] * scalar
    zoom = vector[2] * scalar
    path = f"/ISAPI/PTZCtrl/channels/{target['channel']}/continuous"
    _ptz_xml_request(camera, db, path, method="PUT", body=_ptz_continuous_xml(pan, tilt, zoom))


def _send_ptz_stop(db: Session, camera: Camera) -> None:
    target = _ptz_target(camera, db)
    path = f"/ISAPI/PTZCtrl/channels/{target['channel']}/continuous"
    _ptz_xml_request(camera, db, path, method="PUT", body=_ptz_continuous_xml(0, 0, 0))


def _send_ptz_preset_set(db: Session, camera: Camera, preset_no: int, name: str) -> None:
    target = _ptz_target(camera, db)
    safe_name = re.sub(r"[<>]", "", name).strip()[:120] or f"Preset {preset_no}"
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<PTZPreset version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">'
        f'<id>{preset_no}</id><presetName>{safe_name}</presetName>'
        '</PTZPreset>'
    ).encode("utf-8")
    _ptz_xml_request(camera, db, f"/ISAPI/PTZCtrl/channels/{target['channel']}/presets/{preset_no}", method="PUT", body=body)


def _send_ptz_preset_goto(db: Session, camera: Camera, preset_no: int) -> None:
    target = _ptz_target(camera, db)
    _ptz_xml_request(camera, db, f"/ISAPI/PTZCtrl/channels/{target['channel']}/presets/{preset_no}/goto", method="PUT", body=b"")


def _send_ptz_preset_delete(db: Session, camera: Camera, preset_no: int) -> None:
    target = _ptz_target(camera, db)
    _ptz_xml_request(camera, db, f"/ISAPI/PTZCtrl/channels/{target['channel']}/presets/{preset_no}", method="DELETE")

def hikvision_device_info(recorder: Recorder) -> dict:
    status, body, _ = _hikvision_request(recorder, "/ISAPI/System/deviceInfo")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as error:
        raise HTTPException(502, f"Resposta XML inválida do ISAPI: {error}")
    return {
        "http_status": status,
        "device_name": _xml_text(root, "deviceName"),
        "device_id": _xml_text(root, "deviceID"),
        "model": _xml_text(root, "model"),
        "serial_number": _xml_text(root, "serialNumber"),
        "mac_address": _xml_text(root, "macAddress"),
        "firmware_version": _xml_text(root, "firmwareVersion"),
        "firmware_released_date": _xml_text(root, "firmwareReleasedDate"),
        "device_type": _xml_text(root, "deviceType"),
    }


def hikvision_channels(recorder: Recorder) -> list[dict]:
    candidate_paths = (
        "/ISAPI/ContentMgmt/InputProxy/channels",
        "/ISAPI/System/Video/inputs/channels",
    )
    last_error: Exception | None = None
    for path in candidate_paths:
        try:
            _, body, _ = _hikvision_request(recorder, path)
            root = ET.fromstring(body)
            channels_by_number: dict[int, dict] = {}
            for element in root.iter():
                local = element.tag.split("}")[-1]
                if local not in {"InputProxyChannel", "VideoInputChannel"}:
                    continue
                data: dict[str, str] = {}
                for child in element.iter():
                    child_local = child.tag.split("}")[-1]
                    value = (child.text or "").strip()
                    if value:
                        data[child_local] = value
                raw_channel_id = (
                    data.get("id")
                    or data.get("videoInputChannelID")
                    or data.get("inputPort")
                    or str(len(channels_by_number) + 1)
                )
                channel_number = normalize_hikvision_channel_number(
                    raw_channel_id,
                    len(channels_by_number) + 1,
                )
                channels_by_number[channel_number] = {
                    "channel": channel_number,
                    "raw_channel_id": str(raw_channel_id),
                    "name": data.get("name") or data.get("channelName") or f"Canal {channel_number:02d}",
                    "enabled": _xml_bool(data.get("enabled"), True),
                    "online": _xml_bool(data.get("online", data.get("status")), True),
                    "ip_address": data.get("ipAddress"),
                    "model": data.get("model"),
                    "serial_number": data.get("serialNumber"),
                    "firmware": data.get("firmwareVersion"),
                    "source_path": path,
                }
            if channels_by_number:
                return [channels_by_number[key] for key in sorted(channels_by_number)]
        except Exception as error:
            last_error = error
    if last_error:
        raise last_error
    return []


def hikvision_stream_capabilities(recorder: Recorder, channel: int) -> dict:
    results: dict[str, dict] = {}
    for profile, suffix in (("MAIN", 1), ("SUB", 2)):
        channel_id = channel * 100 + suffix
        path = f"/ISAPI/Streaming/channels/{channel_id}/capabilities"
        try:
            _, body, _ = _hikvision_request(recorder, path, timeout=4)
            root = ET.fromstring(body)
            width = _xml_text(root, "videoResolutionWidth")
            height = _xml_text(root, "videoResolutionHeight")
            results[profile] = {
                "channel_id": channel_id,
                "video_codec_type": _xml_text(root, "videoCodecType"),
                "video_resolution_width": width,
                "video_resolution_height": height,
                "resolution": f"{width}x{height}" if width and height else None,
                "max_frame_rate": _xml_text(root, "maxFrameRate"),
                "constant_bit_rate": _xml_text(root, "constantBitRate"),
                "success": True,
            }
        except Exception as error:
            results[profile] = {
                "channel_id": channel_id,
                "success": False,
                "error": str(error),
            }
    return results


def _safe_float_rate(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    try:
        if "/" in value:
            numerator, denominator = value.split("/", 1)
            denominator_value = float(denominator)
            return round(float(numerator) / denominator_value, 2) if denominator_value else None
        return round(float(value), 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _codec_label(codec_name: str | None) -> str | None:
    normalized = (codec_name or "").strip().lower()
    return {
        "h264": "H.264",
        "hevc": "H.265",
        "h265": "H.265",
        "mjpeg": "MJPEG",
    }.get(normalized, normalized.upper() if normalized else None)


def _sanitize_probe_error(detail: str, source: str) -> str:
    cleaned = (detail or "Falha ao abrir o stream RTSP").strip()
    try:
        cleaned = cleaned.replace(source, mask_rtsp_url(source))
    except Exception:
        pass
    cleaned = re.sub(r"rtsp://[^\s/@]+:[^\s/@]+@", "rtsp://***:***@", cleaned, flags=re.IGNORECASE)
    return cleaned[-500:]


def probe_rtsp_source(source: str, *, timeout: int = 15) -> dict:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-rtsp_transport",
        "tcp",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,avg_frame_rate,r_frame_rate",
        "-of",
        "json",
        source,
    ]
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Tempo limite ao abrir o stream RTSP"}
    except FileNotFoundError:
        return {"ok": False, "error": "ffprobe não está disponível no container da API"}
    except Exception as error:
        return {"ok": False, "error": str(error)}

    if process.returncode != 0:
        return {
            "ok": False,
            "error": _sanitize_probe_error(process.stderr, source),
        }
    try:
        payload = json.loads(process.stdout or "{}")
        stream = (payload.get("streams") or [{}])[0]
    except (json.JSONDecodeError, IndexError, TypeError):
        return {"ok": False, "error": "ffprobe não retornou metadados de vídeo válidos"}

    width = stream.get("width")
    height = stream.get("height")
    fps = _safe_float_rate(stream.get("avg_frame_rate") or stream.get("r_frame_rate"))
    return {
        "ok": True,
        "codec": _codec_label(stream.get("codec_name")),
        "width": width,
        "height": height,
        "resolution": f"{width}x{height}" if width and height else None,
        "fps": fps,
    }


def test_camera_profiles(
    db: Session,
    camera: Camera,
    *,
    profiles: tuple[str, ...] = ("MAIN", "SUB"),
    provision: bool = True,
) -> dict:
    ip_address, port, _, _ = camera_connection_values(db, camera)
    reachable = False
    tcp_error = None
    if ip_address:
        try:
            with socket.create_connection((ip_address, int(port or 554)), timeout=4.0):
                reachable = True
        except OSError as error:
            tcp_error = str(error)
    else:
        tcp_error = "IP da câmera ou do gravador não informado"

    results: dict[str, dict] = {}
    if reachable:
        for profile in profiles:
            try:
                source = build_camera_rtsp(db, camera, profile)
                results[profile] = probe_rtsp_source(source)
            except Exception as error:
                results[profile] = {"ok": False, "error": str(error)}
    else:
        for profile in profiles:
            results[profile] = {"ok": False, "error": tcp_error}

    successful_profiles = [profile for profile, result in results.items() if result.get("ok")]
    provisioned = False
    provision_detail = "Não executado"
    if successful_profiles and provision:
        try:
            provisioned, provision_detail = provision_camera_path(camera, db)
        except Exception as error:
            provision_detail = str(error)

    for profile_name in profiles:
        result = results.get(profile_name) or {}
        status_value = "ONLINE" if result.get("ok") else "OFFLINE"
        if profile_name == "MAIN":
            camera.main_status = status_value
            if result.get("ok"):
                camera.main_codec = result.get("codec") or camera.main_codec
                camera.main_resolution = result.get("resolution") or camera.main_resolution
                if result.get("fps"):
                    camera.main_fps = max(1, min(int(round(result["fps"])), 60))
        elif profile_name == "SUB":
            camera.sub_status = status_value
            if result.get("ok"):
                camera.sub_codec = result.get("codec") or camera.sub_codec
                camera.sub_resolution = result.get("resolution") or camera.sub_resolution
                if result.get("fps"):
                    camera.sub_fps = max(1, min(int(round(result["fps"])), 60))

    preferred = results.get("SUB") if results.get("SUB", {}).get("ok") else None
    if not preferred:
        preferred = results.get("MAIN") if results.get("MAIN", {}).get("ok") else None
    if preferred:
        camera.codec = preferred.get("codec") or camera.codec
        camera.resolution = preferred.get("resolution") or camera.resolution
        if preferred.get("fps"):
            camera.fps = max(1, min(int(round(preferred["fps"])), 60))

    camera.status = "ONLINE" if successful_profiles else "OFFLINE"
    camera.last_check_at = datetime.now(timezone.utc)
    if successful_profiles:
        camera.last_frame_at = camera.last_check_at
        failed_profiles = [profile for profile in profiles if profile not in successful_profiles]
        camera.last_error = (
            f"Perfil(is) indisponível(is): {', '.join(failed_profiles)}"
            if failed_profiles
            else None
        )
    else:
        camera.last_error = next(
            (result.get("error") for result in results.values() if result.get("error")),
            tcp_error or "Nenhum perfil RTSP respondeu",
        )

    return {
        "camera_id": camera.id,
        "status": camera.status,
        "reachable": reachable,
        "profiles": results,
        "provisioned": provisioned,
        "provision_detail": provision_detail,
        "checked_at": camera.last_check_at,
    }


def test_recorder_connectivity(recorder: Recorder) -> dict:
    tests: dict[str, dict] = {}
    for label, port in (
        ("HTTP", recorder.http_port),
        ("HTTPS", recorder.https_port),
        ("RTSP", recorder.rtsp_port),
        ("SDK", recorder.sdk_port),
    ):
        if not port:
            tests[label] = {"ok": False, "port": None, "error": "Porta não configurada"}
            continue
        try:
            with socket.create_connection((recorder.ip_address, int(port)), timeout=4):
                tests[label] = {"ok": True, "port": int(port)}
        except OSError as error:
            tests[label] = {"ok": False, "port": int(port), "error": str(error)}

    device = None
    try:
        device = hikvision_device_info(recorder)
        tests["ISAPI"] = {"ok": True, "http_status": device.get("http_status")}
    except Exception as error:
        tests["ISAPI"] = {"ok": False, "error": str(error)}

    rtsp_ok = bool(tests.get("RTSP", {}).get("ok"))
    isapi_ok = bool(tests.get("ISAPI", {}).get("ok"))
    status = "ONLINE" if rtsp_ok and isapi_ok else "DEGRADADO" if rtsp_ok else "OFFLINE"
    return {"status": status, "tests": tests, "device": device}


@app.get("/recorders", response_model=list[RecorderOut])
def list_recorders(
    school_id: int | None = Query(default=None),
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    query = school_scope_query(db.query(Recorder), Recorder, user)
    if school_id:
        ensure_school_access(user, school_id)
        query = query.filter(Recorder.school_id == school_id)
    return query.order_by(Recorder.id.desc()).all()


@app.post("/recorders", response_model=RecorderOut)
def create_recorder(
    payload: RecorderIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    ensure_school_access(actor, payload.school_id)
    if not db.get(School, payload.school_id):
        raise HTTPException(404, "Escola não encontrada")
    validate_recorder_payload(db, payload)
    values = payload.model_dump()
    values["password"] = encrypt_secret(values.get("password"))
    row = Recorder(**values)
    db.add(row)
    db.flush()
    audit(db, "Gravadores", "Cadastro", f"{row.name} — {row.ip_address}", user=actor)
    db.commit()
    db.refresh(row)
    return row


@app.put("/recorders/{recorder_id}", response_model=RecorderOut)
def update_recorder(
    recorder_id: int,
    payload: RecorderIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    row = ensure_recorder_access(actor, db.get(Recorder, recorder_id))
    ensure_school_access(actor, payload.school_id)
    if not db.get(School, payload.school_id):
        raise HTTPException(404, "Escola não encontrada")
    validate_recorder_payload(db, payload, exclude_id=recorder_id)
    values = payload.model_dump()
    if values.get("password"):
        values["password"] = encrypt_secret(values["password"])
    else:
        values["password"] = row.password
    for key, value in values.items():
        setattr(row, key, value)
    audit(db, "Gravadores", "Edição", f"{row.id} — {row.name}", user=actor)
    db.commit()
    db.refresh(row)
    return row


@app.post("/recorders/{recorder_id}/test")
def test_recorder(
    recorder_id: int,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    row = ensure_recorder_access(actor, db.get(Recorder, recorder_id))
    previous_status = row.status
    result = test_recorder_connectivity(row)
    device = result.get("device") or {}

    row.model = device.get("model") or row.model
    row.serial_number = device.get("serial_number") or row.serial_number
    row.firmware = device.get("firmware_version") or row.firmware
    row.firmware_released_date = device.get("firmware_released_date") or row.firmware_released_date
    row.device_type = device.get("device_type") or row.device_type
    row.mac_address = device.get("mac_address") or row.mac_address
    row.last_check_at = datetime.now(timezone.utc)
    row.status = result["status"]
    row.last_error = None if row.status == "ONLINE" else next(
        (item.get("error") for item in result["tests"].values() if item.get("error")),
        "Gravador com conectividade parcial",
    )
    if previous_status != row.status:
        ingest_camera_event(
            db,
            CameraEventIn(
                provider="EDUVIGIA_HEALTH",
                provider_event_type="RECORDER_OFFLINE",
                event_state="ACTIVE" if row.status == "OFFLINE" else "INACTIVE",
                recorder_id=row.id,
                occurred_at=row.last_check_at,
                metadata={
                    "source": "recorder_test",
                    "previous_status": previous_status,
                    "new_status": row.status,
                    "error": row.last_error,
                    "rtsp_ok": bool(result["tests"].get("RTSP", {}).get("ok")),
                    "isapi_ok": bool(result["tests"].get("ISAPI", {}).get("ok")),
                },
            ),
        )
    else:
        health = _recorder_health_row(db, row)
        health.state = row.status
        health.last_seen_at = row.last_check_at
        health.last_error = row.last_error
    audit(
        db,
        "Gravadores",
        "Teste completo",
        f"{row.name}: {row.status}; RTSP={result['tests'].get('RTSP', {}).get('ok')}; ISAPI={result['tests'].get('ISAPI', {}).get('ok')}",
        user=actor,
    )
    db.commit()
    return {
        "recorder_id": row.id,
        "status": row.status,
        "tests": result["tests"],
        "device": device or None,
        "checked_at": row.last_check_at,
    }


@app.get("/recorders/{recorder_id}/channels")
def recorder_channels(
    recorder_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    row = ensure_recorder_access(user, db.get(Recorder, recorder_id))
    existing = {
        camera.nvr_channel: camera
        for camera in db.query(Camera).filter(Camera.recorder_id == recorder_id).all()
    }
    return [
        {
            "channel": channel,
            "name": existing[channel].name if channel in existing else f"Canal {channel:02d}",
            "location": existing[channel].location if channel in existing else "",
            "camera_id": existing[channel].id if channel in existing else None,
            "configured": channel in existing,
        }
        for channel in range(1, row.channel_count + 1)
    ]



@app.post("/recorders/{recorder_id}/discover")
def discover_recorder(
    recorder_id: int,
    include_capabilities: bool = Query(default=True),
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    row = ensure_recorder_access(actor, db.get(Recorder, recorder_id))
    device = hikvision_device_info(row)
    channels = hikvision_channels(row)
    existing = {
        camera.nvr_channel: camera
        for camera in db.query(Camera).filter(Camera.recorder_id == recorder_id).all()
    }

    capabilities_by_channel: dict[int, dict] = {}
    if include_capabilities and channels:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(channels))) as executor:
            future_map = {
                executor.submit(hikvision_stream_capabilities, row, item["channel"]): item["channel"]
                for item in channels
                if item.get("enabled", True)
            }
            for future in concurrent.futures.as_completed(future_map):
                channel_number = future_map[future]
                try:
                    capabilities_by_channel[channel_number] = future.result()
                except Exception as error:
                    capabilities_by_channel[channel_number] = {
                        "MAIN": {"success": False, "error": str(error)},
                        "SUB": {"success": False, "error": str(error)},
                    }

    enriched_channels = []
    for item in channels:
        channel_number = item["channel"]
        camera = existing.get(channel_number)
        enriched_channels.append(
            {
                **item,
                "configured": camera is not None,
                "camera_id": camera.id if camera else None,
                "camera_status": camera.status if camera else None,
                "capabilities": capabilities_by_channel.get(channel_number),
            }
        )

    highest_channel = max((item["channel"] for item in channels), default=0)
    discovered_count = len(channels)
    row.model = device.get("model") or row.model
    row.serial_number = device.get("serial_number") or row.serial_number
    row.firmware = device.get("firmware_version") or row.firmware
    row.firmware_released_date = device.get("firmware_released_date") or row.firmware_released_date
    row.device_type = device.get("device_type") or row.device_type
    row.mac_address = device.get("mac_address") or row.mac_address
    row.channel_count = max(row.channel_count or 0, highest_channel, discovered_count)
    row.discovered_channel_count = discovered_count
    row.last_discovery_at = datetime.now(timezone.utc)
    row.status = "ONLINE"
    row.last_check_at = row.last_discovery_at
    row.last_error = None

    audit(
        db,
        "Gravadores",
        "Descoberta ISAPI",
        f"{row.name}: {discovered_count} canal(is); configurados={len(existing)}",
        user=actor,
    )
    db.commit()
    return {
        "recorder_id": row.id,
        "device": device,
        "channels": enriched_channels,
        "channel_count": discovered_count,
        "configured_count": len(existing),
        "discovered_at": row.last_discovery_at,
    }


@app.get("/recorders/{recorder_id}/channel-capabilities/{channel}")
def recorder_channel_capabilities(
    recorder_id: int,
    channel: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    row = ensure_recorder_access(user, db.get(Recorder, recorder_id))
    if channel < 1 or channel > 256:
        raise HTTPException(400, "Canal inválido")
    return {
        "recorder_id": row.id,
        "channel": channel,
        "profiles": hikvision_stream_capabilities(row, channel),
    }


@app.post("/recorders/{recorder_id}/import-channels")
def import_recorder_channels(
    recorder_id: int,
    payload: RecorderChannelImportIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    row = ensure_recorder_access(actor, db.get(Recorder, recorder_id))

    channel_numbers = [item.channel for item in payload.channels]
    if len(channel_numbers) != len(set(channel_numbers)):
        raise HTTPException(400, "A lista contém canais duplicados")

    try:
        discovered = {item["channel"]: item for item in hikvision_channels(row)}
    except Exception:
        discovered = {}

    created = 0
    updated = 0
    skipped = 0
    failed = 0
    details: list[dict] = []
    affected: list[Camera] = []
    source_type = "DVR" if "DVR" in (row.device_type or "").upper() else "NVR"

    for item_model in payload.channels:
        item = item_model.model_dump()
        channel = item_model.channel
        info = discovered.get(channel, {})
        existing = (
            db.query(Camera)
            .filter(Camera.recorder_id == recorder_id, Camera.nvr_channel == channel)
            .first()
        )

        if existing and not payload.update_existing:
            skipped += 1
            details.append({"channel": channel, "status": "SKIPPED", "camera_id": existing.id})
            continue

        if existing:
            camera = existing
            camera.name = item.get("name") or info.get("name") or camera.name
            camera.location = item.get("location") or info.get("name") or camera.location
            camera.camera_type = item.get("camera_type") or camera.camera_type
            camera.ptz_enabled = camera.camera_type == "PTZ"
            camera.ptz_channel = channel
            camera.model = info.get("model") or camera.model or row.model
            camera.codec = item.get("codec") or item.get("sub_codec") or camera.codec
            camera.resolution = item.get("resolution") or item.get("sub_resolution") or camera.resolution
            camera.fps = int(item.get("fps") or item.get("sub_fps") or camera.fps or 10)
            camera.main_codec = item.get("main_codec") or camera.main_codec
            camera.main_resolution = item.get("main_resolution") or camera.main_resolution
            camera.main_fps = item.get("main_fps") or camera.main_fps
            camera.main_bitrate_kbps = item.get("main_bitrate_kbps") or camera.main_bitrate_kbps
            camera.sub_codec = item.get("sub_codec") or item.get("codec") or camera.sub_codec
            camera.sub_resolution = item.get("sub_resolution") or item.get("resolution") or camera.sub_resolution
            camera.sub_fps = item.get("sub_fps") or item.get("fps") or camera.sub_fps
            camera.sub_bitrate_kbps = item.get("sub_bitrate_kbps") or camera.sub_bitrate_kbps
            camera.source_type = source_type
            camera.school_id = row.school_id
            camera.ip_address = None
            camera.port = row.rtsp_port
            camera.username = None
            camera.password = None
            camera.rtsp_url = None
            updated += 1
            status_label = "UPDATED"
        else:
            camera = Camera(
                school_id=row.school_id,
                name=item.get("name") or info.get("name") or f"Canal {channel:02d}",
                location=item.get("location") or info.get("name") or f"Canal {channel:02d}",
                manufacturer=row.manufacturer or "Hikvision",
                model=info.get("model") or row.model,
                camera_type=item.get("camera_type") or "FIXA",
                ptz_enabled=(item.get("camera_type") or "FIXA") == "PTZ",
                ptz_protocol="HIKVISION_ISAPI",
                ptz_channel=channel,
                ip_address=None,
                port=row.rtsp_port,
                username=None,
                password=None,
                rtsp_url=None,
                status="PENDING",
                is_totem_camera=False,
                stream_profile="SUB",
                source_type=source_type,
                recorder_id=row.id,
                nvr_channel=channel,
                codec=item.get("codec") or item.get("sub_codec") or "H.264",
                resolution=item.get("resolution") or item.get("sub_resolution") or "960x540",
                fps=int(item.get("fps") or item.get("sub_fps") or 10),
                main_codec=item.get("main_codec"),
                main_resolution=item.get("main_resolution"),
                main_fps=item.get("main_fps"),
                main_bitrate_kbps=item.get("main_bitrate_kbps"),
                sub_codec=item.get("sub_codec") or item.get("codec") or "H.264",
                sub_resolution=item.get("sub_resolution") or item.get("resolution") or "960x540",
                sub_fps=item.get("sub_fps") or item.get("fps") or 10,
                sub_bitrate_kbps=item.get("sub_bitrate_kbps"),
            )
            db.add(camera)
            db.flush()
            ensure_camera_code(db, camera)
            created += 1
            status_label = "CREATED"

        ensure_secure_camera_streams(db, camera)
        try:
            ok, provision_detail = provision_camera_path(camera, db)
            camera.last_error = None if ok else provision_detail
            if not ok:
                failed += 1
        except Exception as error:
            camera.last_error = str(error)
            failed += 1

        affected.append(camera)
        details.append(
            {
                "channel": channel,
                "status": status_label,
                "camera_id": camera.id,
                "stream_main": camera.stream_name_main,
                "stream_sub": camera.stream_name_sub,
                "provisioned": not bool(camera.last_error),
            }
        )

    if payload.test_after_import:
        for camera in affected[:64]:
            result = test_camera_profiles(db, camera, profiles=("MAIN", "SUB"), provision=True)
            for detail in details:
                if detail.get("camera_id") == camera.id:
                    detail["test"] = result
                    break

    row.discovered_channel_count = max(row.discovered_channel_count or 0, len(discovered))
    row.last_discovery_at = datetime.now(timezone.utc)
    audit(
        db,
        "Gravadores",
        "Importação de canais",
        f"{row.name}: criados={created}; atualizados={updated}; ignorados={skipped}; falhas={failed}",
        user=actor,
    )
    db.commit()

    return {
        "ok": failed == 0,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
        "details": details,
    }


@app.post("/recorders/{recorder_id}/test-channels")
def test_recorder_channels(
    recorder_id: int,
    payload: RecorderChannelBatchIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    row = ensure_recorder_access(actor, db.get(Recorder, recorder_id))
    query = db.query(Camera).filter(Camera.recorder_id == recorder_id)
    if payload.channels:
        unique_channels = sorted(set(int(value) for value in payload.channels))
        if any(value < 1 or value > 256 for value in unique_channels):
            raise HTTPException(400, "Canal inválido na seleção")
        query = query.filter(Camera.nvr_channel.in_(unique_channels))
    cameras = query.order_by(Camera.nvr_channel.asc()).all()
    if not cameras:
        raise HTTPException(404, "Nenhum canal cadastrado para testar")
    if len(cameras) > 64:
        raise HTTPException(400, "Teste em lote limitado a 64 canais por execução")

    profiles = ("MAIN", "SUB") if payload.profile == "BOTH" else (payload.profile,)
    results = []
    for camera in cameras:
        try:
            results.append(
                test_camera_profiles(db, camera, profiles=profiles, provision=payload.provision)
            )
        except Exception as error:
            camera.status = "OFFLINE"
            camera.last_check_at = datetime.now(timezone.utc)
            camera.last_error = str(error)
            results.append({"camera_id": camera.id, "status": "OFFLINE", "error": str(error)})

    online = sum(1 for item in results if item.get("status") == "ONLINE")
    audit(
        db,
        "Gravadores",
        "Teste de canais em lote",
        f"{row.name}: online={online}; total={len(results)}",
        user=actor,
    )
    db.commit()
    return {
        "recorder_id": row.id,
        "tested": len(results),
        "online": online,
        "offline": len(results) - online,
        "results": results,
    }


@app.post("/recorders/{recorder_id}/reprovision")
def reprovision_recorder_channels(
    recorder_id: int,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    row = ensure_recorder_access(actor, db.get(Recorder, recorder_id))
    cameras = db.query(Camera).filter(Camera.recorder_id == recorder_id).all()
    results = []
    for camera in cameras:
        try:
            ok, detail = provision_camera_path(camera, db)
        except Exception as error:
            ok, detail = False, str(error)
        camera.last_error = None if ok else detail
        results.append({"camera_id": camera.id, "channel": camera.nvr_channel, "ok": ok, "detail": detail})
    db.commit()
    audit(
        db,
        "Gravadores",
        "Reprovisionamento em lote",
        f"{row.name}: sucesso={sum(1 for item in results if item['ok'])}; total={len(results)}",
        user=actor,
    )
    db.commit()
    return {
        "recorder_id": row.id,
        "total": len(results),
        "provisioned": sum(1 for item in results if item["ok"]),
        "failed": sum(1 for item in results if not item["ok"]),
        "results": results,
    }


@app.get("/recorders/{recorder_id}/inventory")
def recorder_inventory(
    recorder_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    row = ensure_recorder_access(user, db.get(Recorder, recorder_id))
    cameras = db.query(Camera).filter(Camera.recorder_id == recorder_id).order_by(Camera.nvr_channel.asc()).all()
    return {
        "recorder": RecorderOut.model_validate(row),
        "summary": {
            "configured": len(cameras),
            "online": sum(1 for camera in cameras if camera.status == "ONLINE"),
            "offline": sum(1 for camera in cameras if camera.status == "OFFLINE"),
            "pending": sum(1 for camera in cameras if camera.status == "PENDING"),
            "main_ready": sum(1 for camera in cameras if camera.stream_name_main),
            "sub_ready": sum(1 for camera in cameras if camera.stream_name_sub),
        },
        "channels": [CameraOut.model_validate(camera) for camera in cameras],
    }


@app.delete("/recorders/{recorder_id}")
def delete_recorder(
    recorder_id: int,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA")),
):
    row = ensure_recorder_access(actor, db.get(Recorder, recorder_id))
    linked = db.query(Camera).filter(Camera.recorder_id == recorder_id).count()
    if linked:
        raise HTTPException(409, f"Gravador possui {linked} câmera(s) vinculada(s)")
    audit(db, "Gravadores", "Exclusão", row.name, user=actor)
    db.delete(row)
    db.commit()
    return {"ok": True}


def _video_device_request(device: VideoDevice, path: str, *, timeout: int = 8) -> tuple[int, bytes, str]:
    scheme = "https" if int(device.https_port or 0) > 0 and int(device.http_port or 80) == 0 else "http"
    port = device.https_port if scheme == "https" else device.http_port
    url = f"{scheme}://{device.ip_address}:{port}{path}"
    password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    password_mgr.add_password(None, url, device.username or "", decrypt_secret(device.password) or "")
    handlers: list[object] = [urllib.request.HTTPDigestAuthHandler(password_mgr), urllib.request.HTTPBasicAuthHandler(password_mgr)]
    if scheme == "https":
        import ssl
        handlers.append(urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    opener = urllib.request.build_opener(*handlers)
    request = urllib.request.Request(url, method="GET", headers={"Accept": "application/xml", "User-Agent": f"EduVigIA/{APP_VERSION}"})
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.read(), response.headers.get_content_type()
    except urllib.error.HTTPError as error:
        if error.code in {401, 403}:
            raise HTTPException(502, "Credenciais ISAPI recusadas pelo dispositivo")
        raise HTTPException(502, f"ISAPI respondeu HTTP {error.code}")
    except urllib.error.URLError as error:
        raise HTTPException(502, f"Falha de conexão ISAPI: {error.reason}")


def _discover_video_device_channels(device: VideoDevice) -> list[dict]:
    _, body, _ = _video_device_request(device, "/ISAPI/Streaming/channels", timeout=6)
    root = ET.fromstring(body)
    found: dict[int, dict] = {}
    for element in root.iter():
        if element.tag.split("}")[-1] != "StreamingChannel":
            continue
        channel_id = None
        enabled = True
        for child in element.iter():
            local = child.tag.split("}")[-1]
            if local == "id" and child.text and channel_id is None:
                try: channel_id = int(child.text.strip())
                except ValueError: pass
            elif local == "enabled" and child.text:
                enabled = _xml_bool(child.text, True)
        if not channel_id:
            continue
        logical = normalize_hikvision_channel_number(channel_id, 1)
        suffix = int(channel_id) % 100 if int(channel_id) >= 100 else 1
        row = found.setdefault(logical, {"logical_channel": logical, "main": False, "sub": False, "enabled": False})
        row["enabled"] = row["enabled"] or enabled
        if suffix == 1: row["main"] = True
        elif suffix == 2: row["sub"] = True
    return [found[key] for key in sorted(found)]


@app.get("/video-devices", response_model=list[VideoDeviceOut])
def video_devices(
    school_id: int | None = Query(default=None),
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    query = school_scope_query(db.query(VideoDevice), VideoDevice, user)
    if school_id:
        ensure_school_access(user, school_id)
        query = query.filter(VideoDevice.school_id == school_id)
    return query.order_by(VideoDevice.id.desc()).all()


@app.post("/video-devices", response_model=VideoDeviceOut)
def create_video_device(
    payload: VideoDeviceIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    ensure_school_access(actor, payload.school_id)
    if not db.get(School, payload.school_id):
        raise HTTPException(404, "Escola não encontrada")
    ip_value = _validate_ip_address(payload.ip_address, "IP do dispositivo")
    duplicate = db.query(VideoDevice).filter(VideoDevice.school_id == payload.school_id, VideoDevice.ip_address == ip_value, VideoDevice.rtsp_port == payload.rtsp_port).first()
    if duplicate:
        raise HTTPException(409, "Já existe um dispositivo físico com este IP/RTSP nesta escola")
    values = payload.model_dump()
    values["password"] = encrypt_secret(values.get("password"))
    row = VideoDevice(**values)
    db.add(row)
    audit(db, "VMS", "Dispositivo físico cadastrado", f"device={row.name}; type={row.device_type}; ip={row.ip_address}", user=actor)
    db.commit(); db.refresh(row)
    return row


@app.put("/video-devices/{device_id}", response_model=VideoDeviceOut)
def update_video_device(
    device_id: int, payload: VideoDeviceIn, db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    row = db.get(VideoDevice, device_id)
    if not row:
        raise HTTPException(404, "Dispositivo físico não encontrado")
    ensure_school_access(actor, row.school_id); ensure_school_access(actor, payload.school_id)
    values = payload.model_dump()
    values["password"] = encrypt_secret(values["password"]) if values.get("password") else row.password
    for key, value in values.items(): setattr(row, key, value)
    audit(db, "VMS", "Dispositivo físico atualizado", f"device={row.id}", user=actor)
    db.commit(); db.refresh(row)
    return row


@app.post("/video-devices/{device_id}/discover")
def discover_video_device(
    device_id: int, db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    row = db.get(VideoDevice, device_id)
    if not row: raise HTTPException(404, "Dispositivo físico não encontrado")
    ensure_school_access(actor, row.school_id)
    try:
        channels = _discover_video_device_channels(row)
        row.status = "ONLINE"; row.last_error = None; row.last_check_at = datetime.now(timezone.utc)
        row.channel_count = max(row.channel_count or 1, len(channels) or 1)
        db.commit()
        return {"device_id": row.id, "device_type": row.device_type, "channels": channels}
    except HTTPException as error:
        row.status = "OFFLINE"; row.last_error = str(error.detail); row.last_check_at = datetime.now(timezone.utc); db.commit(); raise


@app.post("/video-devices/{device_id}/adopt-camera/{camera_id}", response_model=VideoDeviceOut)
def adopt_camera_into_video_device(
    device_id: int, camera_id: int, payload: VideoDeviceAdoptIn, db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    device = db.get(VideoDevice, device_id)
    camera = ensure_camera_access(actor, db.get(Camera, camera_id))
    if not device: raise HTTPException(404, "Dispositivo físico não encontrado")
    ensure_school_access(actor, device.school_id)
    if camera.school_id != device.school_id: raise HTTPException(400, "Câmera e dispositivo pertencem a escolas diferentes")
    if db.query(Camera).filter(Camera.device_id == device.id, Camera.logical_channel == payload.logical_channel, Camera.id != camera.id).first():
        raise HTTPException(409, "Canal lógico já utilizado neste dispositivo")
    camera.device_id = device.id; camera.logical_channel = payload.logical_channel; camera.sensor_type = payload.sensor_type
    camera.sensor_label = payload.sensor_label; camera.primary_sensor = True
    camera.ip_address = None; camera.username = None; camera.password = None; camera.port = device.rtsp_port
    ensure_secure_camera_streams(db, camera)
    audit(db, "VMS", "Câmera vinculada ao dispositivo multisensor", f"camera={camera.id}; device={device.id}; channel={camera.logical_channel}; sensor={camera.sensor_type}", user=actor)
    db.commit(); db.refresh(device)
    return device


@app.post("/video-devices/{device_id}/channels", response_model=list[CameraOut])
def create_video_device_channels(
    device_id: int, payload: VideoDeviceChannelsIn, db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    device = db.get(VideoDevice, device_id)
    if not device: raise HTTPException(404, "Dispositivo físico não encontrado")
    ensure_school_access(actor, device.school_id)
    requested = [item.logical_channel for item in payload.channels]
    if len(requested) != len(set(requested)): raise HTTPException(400, "Há canais lógicos duplicados na solicitação")
    existing = {row.logical_channel for row in db.query(Camera).filter(Camera.device_id == device.id).all()}
    conflict = sorted(set(requested) & existing)
    if conflict: raise HTTPException(409, f"Canal(is) já cadastrado(s): {conflict}")
    created=[]
    for item in payload.channels:
        row = Camera(
            school_id=device.school_id, name=item.name, location=item.location, manufacturer=device.manufacturer, model=device.model,
            camera_type=item.camera_type, source_type="CAMERA_IP", device_id=device.id, logical_channel=item.logical_channel,
            sensor_type=item.sensor_type, sensor_label=item.sensor_label, primary_sensor=item.primary_sensor, port=device.rtsp_port,
            main_codec=item.main_codec, main_resolution=item.main_resolution, main_fps=item.main_fps, main_bitrate_kbps=item.main_bitrate_kbps,
            sub_codec=item.sub_codec, sub_resolution=item.sub_resolution, sub_fps=item.sub_fps, sub_bitrate_kbps=item.sub_bitrate_kbps,
            codec=item.sub_codec, resolution=item.sub_resolution, fps=item.sub_fps, ptz_enabled=item.ptz_enabled,
            ptz_protocol="HIKVISION_ISAPI", ptz_channel=item.logical_channel,
        )
        db.add(row); db.flush(); ensure_camera_code(db, row); ensure_secure_camera_streams(db, row)
        try:
            ok, detail = provision_camera_path(row, db); row.last_error = None if ok else detail
        except Exception as error:
            row.last_error = str(error)
        created.append(row)
    device.channel_count = max(int(device.channel_count or 1), max(requested))
    audit(db, "VMS", "Canais multisensor cadastrados", f"device={device.id}; channels={requested}", user=actor)
    db.commit()
    for row in created: db.refresh(row)
    return created


@app.delete("/video-devices/{device_id}")
def delete_video_device(
    device_id: int, db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    row = db.get(VideoDevice, device_id)
    if not row: raise HTTPException(404, "Dispositivo físico não encontrado")
    ensure_school_access(actor, row.school_id)
    if db.query(Camera).filter(Camera.device_id == row.id).count():
        raise HTTPException(409, "Remova ou desvincule os canais antes de excluir o dispositivo físico")
    db.delete(row); audit(db, "VMS", "Dispositivo físico excluído", f"device={device_id}", user=actor); db.commit()
    return {"ok": True}


@app.get("/cameras", response_model=list[CameraOut])
def cameras(
    school_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    query = school_scope_query(db.query(Camera), Camera, user)
    if school_id:
        ensure_school_access(user, school_id)
        query = query.filter(Camera.school_id == school_id)
    if status:
        query = query.filter(Camera.status == status.upper())
    if search:
        term = f"%{search}%"
        query = query.filter(
            Camera.name.ilike(term)
            | Camera.code.ilike(term)
            | Camera.location.ilike(term)
            | Camera.ip_address.ilike(term)
        )
    return query.order_by(Camera.id.desc()).all()


@app.post("/cameras", response_model=CameraOut)
def create_camera(
    payload: CameraIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    ensure_school_access(actor, payload.school_id)
    if not db.get(School, payload.school_id):
        raise HTTPException(404, "Escola não encontrada")
    if payload.recorder_id:
        recorder = ensure_recorder_access(actor, db.get(Recorder, payload.recorder_id))
        if recorder.school_id != payload.school_id:
            raise HTTPException(400, "O gravador pertence a outra escola")
    validate_camera_payload(db, payload)

    values = payload.model_dump()
    values["password"] = encrypt_secret(values.get("password"))
    row = Camera(**values)
    db.add(row)
    db.flush()
    ensure_camera_code(db, row)

    ensure_secure_camera_streams(db, row, payload.stream_name)

    provision_ok = False
    provision_detail = ""
    try:
        provision_ok, provision_detail = provision_camera_path(row, db)
    except Exception as error:
        provision_detail = str(error)

    row.last_error = None if provision_ok else provision_detail
    audit(
        db,
        "Câmeras",
        "Cadastro",
        f"{row.name} — stream={row.stream_name} — MediaMTX={provision_ok}",
        user=actor,
    )
    db.commit()
    db.refresh(row)
    return row


@app.put("/cameras/{camera_id}", response_model=CameraOut)
def update_camera(
    camera_id: int,
    payload: CameraIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    row = ensure_camera_access(actor, db.get(Camera, camera_id))
    ensure_school_access(actor, payload.school_id)
    if not db.get(School, payload.school_id):
        raise HTTPException(404, "Escola não encontrada")
    if payload.recorder_id:
        recorder = ensure_recorder_access(actor, db.get(Recorder, payload.recorder_id))
        if recorder.school_id != payload.school_id:
            raise HTTPException(400, "O gravador pertence a outra escola")
    validate_camera_payload(db, payload, exclude_id=camera_id)

    previous_streams = [value for value in (row.stream_name, row.stream_name_main, row.stream_name_sub) if value]
    values = payload.model_dump()
    if values.get("password"):
        values["password"] = encrypt_secret(values["password"])
    else:
        values["password"] = row.password
    if payload.source_type == "RTSP_CUSTOM":
        if not (values.get("rtsp_url") or "").strip():
            values["rtsp_url"] = row.rtsp_url
        if not (values.get("rtsp_url_main") or "").strip():
            values["rtsp_url_main"] = row.rtsp_url_main
        if not (values.get("rtsp_url_sub") or "").strip():
            values["rtsp_url_sub"] = row.rtsp_url_sub
    for key, value in values.items():
        setattr(row, key, value)

    _, obsolete_streams = ensure_secure_camera_streams(db, row, payload.stream_name)
    for previous_stream in dict.fromkeys(previous_streams + obsolete_streams):
        if previous_stream not in {row.stream_name_main, row.stream_name_sub}:
            delete_camera_path(previous_stream)

    provision_ok = False
    provision_detail = ""
    try:
        provision_ok, provision_detail = provision_camera_path(row, db)
    except Exception as error:
        provision_detail = str(error)
    row.last_error = None if provision_ok else provision_detail

    audit(
        db,
        "Câmeras",
        "Edição",
        f"{row.id} - {row.name} — MediaMTX={provision_ok}",
        user=actor,
    )
    db.commit()
    db.refresh(row)
    return row


@app.patch("/cameras/{camera_id}/status")
def update_camera_status(
    camera_id: int,
    payload: CameraStatusIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    row = ensure_camera_access(actor, db.get(Camera, camera_id))
    previous_status = row.status
    row.status = payload.status
    row.last_check_at = datetime.now(timezone.utc)
    if previous_status != row.status and row.status in {"ONLINE", "OFFLINE"}:
        ingest_camera_event(
            db,
            CameraEventIn(
                provider="EDUVIGIA_HEALTH",
                provider_event_type="CAMERA_OFFLINE",
                event_state="ACTIVE" if row.status == "OFFLINE" else "INACTIVE",
                camera_id=row.id,
                occurred_at=row.last_check_at,
                metadata={"source": "manual_status", "previous_status": previous_status, "new_status": row.status},
            ),
        )
    audit(db, "Câmeras", "Status alterado", f"{row.name}: {row.status}", user=actor)
    db.commit()
    return {"ok": True, "status": row.status}


@app.post("/cameras/{camera_id}/test")
def test_camera(
    camera_id: int,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    row = ensure_camera_access(actor, db.get(Camera, camera_id))
    previous_status = row.status
    result = test_camera_profiles(db, row, profiles=("MAIN", "SUB"), provision=True)
    if previous_status != row.status:
        ingest_camera_event(
            db,
            CameraEventIn(
                provider="EDUVIGIA_HEALTH",
                provider_event_type="RTSP_FAILURE",
                event_state="ACTIVE" if row.status == "OFFLINE" else "INACTIVE",
                camera_id=row.id,
                occurred_at=row.last_check_at,
                metadata={
                    "source": "camera_test",
                    "main_online": row.main_status == "ONLINE",
                    "sub_online": row.sub_status == "ONLINE",
                    "fps": row.fps,
                    "resolution": row.resolution,
                    "codec": row.codec,
                    "error": row.last_error,
                },
            ),
        )
    audit(
        db,
        "Câmeras",
        "Teste MAIN/SUB",
        f"{row.name}: {row.status}; MAIN={result['profiles'].get('MAIN', {}).get('ok')}; SUB={result['profiles'].get('SUB', {}).get('ok')}; MediaMTX={result['provisioned']}",
        user=actor,
    )
    db.commit()
    return result


@app.post("/cameras/test-batch")
def test_cameras_batch(
    payload: CameraBatchIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    query = school_scope_query(db.query(Camera), Camera, actor)
    if payload.camera_ids:
        unique_ids = sorted(set(int(value) for value in payload.camera_ids))
        query = query.filter(Camera.id.in_(unique_ids))
    cameras = query.order_by(Camera.id.asc()).limit(65).all()
    if not cameras:
        raise HTTPException(404, "Nenhuma câmera encontrada para testar")
    if len(cameras) > 64:
        raise HTTPException(400, "Teste em lote limitado a 64 câmeras por execução")

    results = []
    for camera in cameras:
        previous_status = camera.status
        try:
            results.append(
                test_camera_profiles(
                    db, camera, profiles=("MAIN", "SUB"), provision=payload.provision
                )
            )
        except Exception as error:
            camera.status = "OFFLINE"
            camera.last_check_at = datetime.now(timezone.utc)
            camera.last_error = str(error)
            results.append({"camera_id": camera.id, "status": "OFFLINE", "error": str(error)})
        if previous_status != camera.status:
            ingest_camera_event(
                db,
                CameraEventIn(
                    provider="EDUVIGIA_HEALTH",
                    provider_event_type="RTSP_FAILURE",
                    event_state="ACTIVE" if camera.status == "OFFLINE" else "INACTIVE",
                    camera_id=camera.id,
                    occurred_at=camera.last_check_at,
                    metadata={
                        "source": "camera_batch_test",
                        "main_online": camera.main_status == "ONLINE",
                        "sub_online": camera.sub_status == "ONLINE",
                        "fps": camera.fps,
                        "resolution": camera.resolution,
                        "codec": camera.codec,
                        "error": camera.last_error,
                    },
                ),
            )
    online = sum(1 for item in results if item.get("status") == "ONLINE")
    audit(
        db,
        "Câmeras",
        "Teste em lote",
        f"online={online}; total={len(results)}",
        user=actor,
    )
    db.commit()
    return {
        "tested": len(results),
        "online": online,
        "offline": len(results) - online,
        "results": results,
    }


@app.get("/monitoring/favorites")
def monitoring_favorites(
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    rows = (
        db.query(CameraFavorite)
        .filter(CameraFavorite.user_id == user.id)
        .order_by(CameraFavorite.created_at.asc())
        .all()
    )
    camera_ids = []
    for row in rows:
        camera = db.get(Camera, row.camera_id)
        if not camera:
            continue
        try:
            ensure_camera_access(user, camera)
        except HTTPException:
            continue
        camera_ids.append(camera.id)
    return {"camera_ids": camera_ids}


@app.put("/monitoring/favorites/{camera_id}")
def add_monitoring_favorite(
    camera_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    camera = ensure_camera_access(user, db.get(Camera, camera_id))
    existing = (
        db.query(CameraFavorite)
        .filter(CameraFavorite.user_id == user.id, CameraFavorite.camera_id == camera.id)
        .first()
    )
    if not existing:
        db.add(CameraFavorite(user_id=user.id, camera_id=camera.id))
        db.commit()
    return {"ok": True, "camera_id": camera.id, "favorite": True}


@app.delete("/monitoring/favorites/{camera_id}")
def remove_monitoring_favorite(
    camera_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    camera = ensure_camera_access(user, db.get(Camera, camera_id))
    row = (
        db.query(CameraFavorite)
        .filter(CameraFavorite.user_id == user.id, CameraFavorite.camera_id == camera.id)
        .first()
    )
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True, "camera_id": camera.id, "favorite": False}


def _video_wall_layout_payload(db: Session, row: VideoWallLayout, user: UserAccount) -> dict:
    slots = db.query(VideoWallSlot).filter(VideoWallSlot.layout_id == row.id).order_by(VideoWallSlot.slot_index.asc()).all()
    camera_ids: list[int | None] = [None] * row.grid_size
    slot_rows = []
    for slot in slots:
        camera = db.get(Camera, slot.camera_id)
        if not camera:
            continue
        try:
            ensure_camera_access(user, camera)
        except HTTPException:
            continue
        if 0 <= slot.slot_index < row.grid_size:
            camera_ids[slot.slot_index] = camera.id
            slot_rows.append({
                "slot_index": slot.slot_index,
                "camera_id": camera.id,
                "camera_name": camera.name,
                "school_id": camera.school_id,
                "logical_channel": camera.logical_channel,
                "sensor_type": camera.sensor_type,
            })
    return {
        "id": row.id, "name": row.name, "grid_size": row.grid_size,
        "quality_mode": row.quality_mode, "is_default": row.is_default,
        "camera_ids": camera_ids, "slots": slot_rows,
        "created_at": row.created_at, "updated_at": row.updated_at,
    }


def _validate_video_wall_payload(db: Session, payload: VideoWallLayoutIn, user: UserAccount) -> list[int | None]:
    camera_ids = list(payload.camera_ids[:payload.grid_size])
    camera_ids += [None] * (payload.grid_size - len(camera_ids))
    concrete = [int(value) for value in camera_ids if value is not None]
    if len(concrete) != len(set(concrete)):
        raise HTTPException(400, "A mesma câmera não pode ocupar dois slots do mesmo layout")
    for camera_id in concrete:
        ensure_camera_access(user, db.get(Camera, camera_id))
    return camera_ids



def _map_coordinate(value: str | None, *, latitude: bool) -> float | None:
    if value is None:
        return None
    raw = str(value).strip().replace(",", ".")
    if not raw:
        return None
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return None
    limit = 90.0 if latitude else 180.0
    if number < -limit or number > limit:
        return None
    return round(number, 7)


def _school_map_status(active_alerts: int, open_occurrences: int, offline: int, total: int) -> str:
    if open_occurrences > 0 or active_alerts >= 2:
        return "CRITICAL"
    if active_alerts > 0 or offline > 0 or total == 0:
        return "ATTENTION"
    return "NORMAL"


def _floor_plan_payload(db: Session, row: FloorPlan) -> dict:
    placements = (
        db.query(FloorPlanCamera)
        .filter(FloorPlanCamera.floor_plan_id == row.id)
        .order_by(FloorPlanCamera.id.asc())
        .all()
    )
    camera_ids = [item.camera_id for item in placements]
    cameras = {c.id: c for c in db.query(Camera).filter(Camera.id.in_(camera_ids)).all()} if camera_ids else {}
    return {
        "id": row.id,
        "school_id": row.school_id,
        "name": row.name,
        "building": row.building,
        "floor_label": row.floor_label,
        "original_name": row.original_name,
        "mime_type": row.mime_type,
        "active": row.active,
        "image_url": f"/floor-plans/{row.id}/file",
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "placements": [
            {
                "id": item.id,
                "camera_id": item.camera_id,
                "x_percent": item.x_percent,
                "y_percent": item.y_percent,
                "rotation_deg": item.rotation_deg,
                "label": item.label,
                "camera_name": cameras.get(item.camera_id).name if cameras.get(item.camera_id) else f"Câmera #{item.camera_id}",
                "logical_channel": cameras.get(item.camera_id).logical_channel if cameras.get(item.camera_id) else None,
                "sensor_type": cameras.get(item.camera_id).sensor_type if cameras.get(item.camera_id) else None,
                "status": cameras.get(item.camera_id).status if cameras.get(item.camera_id) else "UNKNOWN",
            }
            for item in placements
        ],
    }


def _valid_floor_plan_image(content: bytes, mime_type: str) -> bool:
    if mime_type == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "image/jpeg":
        return len(content) >= 3 and content[:3] == b"\xff\xd8\xff"
    if mime_type == "image/webp":
        return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    return False


def _ensure_floor_plan_access(db: Session, user: UserAccount, floor_plan_id: int) -> FloorPlan:
    row = db.get(FloorPlan, floor_plan_id)
    if not row:
        raise HTTPException(404, "Planta não encontrada")
    ensure_school_access(user, row.school_id)
    return row


@app.get("/floor-plans")
def list_floor_plans(
    school_id: int | None = Query(default=None),
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("floorplans:view")),
):
    query = school_scope_query(db.query(FloorPlan), FloorPlan, user).filter(FloorPlan.active.is_(True))
    if school_id is not None:
        ensure_school_access(user, school_id)
        query = query.filter(FloorPlan.school_id == school_id)
    rows = query.order_by(FloorPlan.school_id.asc(), FloorPlan.name.asc()).all()
    return [_floor_plan_payload(db, row) for row in rows]


@app.post("/floor-plans")
def create_floor_plan(
    school_id: int = Form(...),
    name: str = Form(...),
    building: str = Form(default=""),
    floor_label: str = Form(default=""),
    file: UploadFile = File(...),
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("floorplans:write")),
):
    ensure_school_access(user, school_id)
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(404, "Escola não encontrada")
    clean_name = name.strip()
    if len(clean_name) < 2 or len(clean_name) > 160:
        raise HTTPException(400, "Nome da planta inválido")
    if db.query(FloorPlan).filter(FloorPlan.school_id == school_id, FloorPlan.name == clean_name, FloorPlan.active.is_(True)).first():
        raise HTTPException(409, "Já existe uma planta ativa com este nome nesta escola")
    allowed = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    if file.content_type not in allowed:
        raise HTTPException(400, "Envie a planta em JPG, PNG ou WebP")
    content = file.file.read()
    if not content:
        raise HTTPException(400, "Arquivo da planta vazio")
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(413, "Planta maior que 15 MB")
    if not _valid_floor_plan_image(content, file.content_type):
        raise HTTPException(400, "Conteúdo do arquivo não corresponde a uma imagem válida")
    safe_name = f"floorplan-{school_id}-{secrets.token_hex(10)}{allowed[file.content_type]}"
    target = FLOORPLAN_DIR / safe_name
    target.write_bytes(content)
    row = FloorPlan(
        school_id=school_id, name=clean_name, building=(building.strip()[:120] or None),
        floor_label=(floor_label.strip()[:80] or None), filename=safe_name,
        original_name=(file.filename or safe_name)[:260], mime_type=file.content_type,
        file_path=str(target), created_by_user_id=user.id, active=True,
    )
    db.add(row); db.flush()
    audit(db, "Plantas Baixas", "Cadastro", f"floor_plan={row.id};school={school_id};name={row.name}", user=user)
    db.commit(); db.refresh(row)
    return _floor_plan_payload(db, row)


@app.get("/floor-plans/{floor_plan_id}/file")
def floor_plan_file(
    floor_plan_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("floorplans:view")),
):
    row = _ensure_floor_plan_access(db, user, floor_plan_id)
    path = Path(row.file_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "Arquivo físico da planta não encontrado")
    return FileResponse(path, media_type=row.mime_type, filename=row.original_name or row.filename)


@app.put("/floor-plans/{floor_plan_id}/cameras")
def save_floor_plan_cameras(
    floor_plan_id: int,
    payload: FloorPlanPlacementsIn,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("floorplans:write")),
):
    row = _ensure_floor_plan_access(db, user, floor_plan_id)
    seen: set[int] = set()
    for item in payload.placements:
        if item.camera_id in seen:
            raise HTTPException(400, "A mesma câmera não pode ser posicionada duas vezes na mesma planta")
        seen.add(item.camera_id)
        camera = ensure_camera_access(user, db.get(Camera, item.camera_id))
        if camera.school_id != row.school_id:
            raise HTTPException(400, "A câmera deve pertencer à mesma escola da planta")
    db.query(FloorPlanCamera).filter(FloorPlanCamera.floor_plan_id == row.id).delete(synchronize_session=False)
    for item in payload.placements:
        db.add(FloorPlanCamera(
            floor_plan_id=row.id, camera_id=item.camera_id,
            x_percent=float(item.x_percent), y_percent=float(item.y_percent),
            rotation_deg=float(item.rotation_deg), label=(item.label.strip()[:120] if item.label else None),
        ))
    row.updated_at = datetime.now(timezone.utc)
    audit(db, "Plantas Baixas", "Posicionamento de câmeras", f"floor_plan={row.id};cameras={len(payload.placements)}", user=user)
    db.commit(); db.refresh(row)
    return _floor_plan_payload(db, row)


@app.delete("/floor-plans/{floor_plan_id}", status_code=204)
def delete_floor_plan(
    floor_plan_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("floorplans:write")),
):
    row = _ensure_floor_plan_access(db, user, floor_plan_id)
    path = Path(row.file_path)
    audit(db, "Plantas Baixas", "Exclusão", f"floor_plan={row.id};name={row.name}", user=user)
    db.delete(row); db.commit()
    try:
        if path.exists() and path.is_file() and FLOORPLAN_DIR.resolve() in path.resolve().parents:
            path.unlink()
    except OSError:
        pass


@app.get("/maps/overview")
def operational_map_overview(
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("maps:view")),
):
    school_query = db.query(School).filter(School.active.is_(True))
    restricted_school_id = scoped_school_id(user)
    if restricted_school_id is not None:
        school_query = school_query.filter(School.id == restricted_school_id)
    schools_rows = school_query.order_by(School.name.asc()).all()

    school_ids = [row.id for row in schools_rows]
    camera_rows = db.query(Camera).filter(Camera.school_id.in_(school_ids)).all() if school_ids else []
    alert_rows = db.query(Alert).filter(Alert.school_id.in_(school_ids)).all() if school_ids else []
    occurrence_rows = db.query(Occurrence).filter(Occurrence.school_id.in_(school_ids)).all() if school_ids else []

    camera_by_school: dict[int, list[Camera]] = {}
    for camera in camera_rows:
        camera_by_school.setdefault(camera.school_id, []).append(camera)
    alert_by_school: dict[int, list[Alert]] = {}
    for alert in alert_rows:
        if alert.school_id is not None:
            alert_by_school.setdefault(alert.school_id, []).append(alert)
    occurrence_by_school: dict[int, list[Occurrence]] = {}
    for occurrence in occurrence_rows:
        if occurrence.school_id is not None:
            occurrence_by_school.setdefault(occurrence.school_id, []).append(occurrence)

    points = []
    unlocated = []
    for school in schools_rows:
        lat = _map_coordinate(school.latitude, latitude=True)
        lon = _map_coordinate(school.longitude, latitude=False)
        cameras = camera_by_school.get(school.id, [])
        online = sum(1 for camera in cameras if camera.status == "ONLINE")
        offline = sum(1 for camera in cameras if camera.status == "OFFLINE")
        pending = max(0, len(cameras) - online - offline)
        alerts = [item for item in alert_by_school.get(school.id, []) if item.status not in {"DESCARTADO", "ENCERRADO", "RESOLVIDO"}]
        occurrences = [item for item in occurrence_by_school.get(school.id, []) if item.status not in {"ENCERRADA", "ENCERRADO"}]
        status = _school_map_status(len(alerts), len(occurrences), offline, len(cameras))
        base = {
            "school_id": school.id,
            "school_name": school.name,
            "code": school.code,
            "address": school.address,
            "neighborhood": school.neighborhood,
            "city": school.city,
            "operational_status": school.operational_status,
            "cameras_total": len(cameras),
            "cameras_online": online,
            "cameras_offline": offline,
            "cameras_pending": pending,
            "active_alerts": len(alerts),
            "open_occurrences": len(occurrences),
            "map_status": status,
        }
        if lat is None or lon is None:
            unlocated.append(base)
        else:
            points.append({**base, "latitude": lat, "longitude": lon})

    return {
        "points": points,
        "unlocated": unlocated,
        "summary": {
            "schools_total": len(schools_rows),
            "schools_located": len(points),
            "schools_unlocated": len(unlocated),
            "critical": sum(1 for item in points if item["map_status"] == "CRITICAL"),
            "attention": sum(1 for item in points if item["map_status"] == "ATTENTION"),
            "normal": sum(1 for item in points if item["map_status"] == "NORMAL"),
        },
        "tile_url_template": os.getenv("EDUVIGIA_MAP_TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png"),
        "attribution": os.getenv("EDUVIGIA_MAP_ATTRIBUTION", "© OpenStreetMap contributors"),
    }


@app.get("/video-wall/layouts")
def list_video_wall_layouts(
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("wall:view")),
):
    rows = db.query(VideoWallLayout).filter(VideoWallLayout.user_id == user.id).order_by(VideoWallLayout.is_default.desc(), VideoWallLayout.name.asc()).all()
    return [_video_wall_layout_payload(db, row, user) for row in rows]


@app.post("/video-wall/layouts")
def create_video_wall_layout(
    payload: VideoWallLayoutIn,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("wall:write")),
):
    name = payload.name.strip()
    duplicate = db.query(VideoWallLayout).filter(VideoWallLayout.user_id == user.id, VideoWallLayout.name == name).first()
    if duplicate:
        raise HTTPException(409, "Já existe um layout com este nome")
    camera_ids = _validate_video_wall_payload(db, payload, user)
    row = VideoWallLayout(user_id=user.id, name=name, grid_size=payload.grid_size, quality_mode=payload.quality_mode, is_default=False)
    db.add(row); db.flush()
    for slot_index, camera_id in enumerate(camera_ids):
        if camera_id is not None:
            db.add(VideoWallSlot(layout_id=row.id, slot_index=slot_index, camera_id=int(camera_id)))
    audit(db, "Video Wall", "Criar layout", f"layout_id={row.id};grid={row.grid_size}", user=user)
    db.commit(); db.refresh(row)
    return _video_wall_layout_payload(db, row, user)


@app.put("/video-wall/layouts/{layout_id}")
def update_video_wall_layout(
    layout_id: int, payload: VideoWallLayoutIn,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("wall:write")),
):
    row = db.get(VideoWallLayout, layout_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "Layout não encontrado")
    name = payload.name.strip()
    duplicate = db.query(VideoWallLayout).filter(VideoWallLayout.user_id == user.id, VideoWallLayout.name == name, VideoWallLayout.id != row.id).first()
    if duplicate:
        raise HTTPException(409, "Já existe um layout com este nome")
    camera_ids = _validate_video_wall_payload(db, payload, user)
    row.name=name; row.grid_size=payload.grid_size; row.quality_mode=payload.quality_mode; row.updated_at=datetime.now(timezone.utc)
    db.query(VideoWallSlot).filter(VideoWallSlot.layout_id == row.id).delete(synchronize_session=False)
    for slot_index, camera_id in enumerate(camera_ids):
        if camera_id is not None:
            db.add(VideoWallSlot(layout_id=row.id, slot_index=slot_index, camera_id=int(camera_id)))
    audit(db, "Video Wall", "Atualizar layout", f"layout_id={row.id};grid={row.grid_size}", user=user)
    db.commit(); db.refresh(row)
    return _video_wall_layout_payload(db, row, user)


@app.post("/video-wall/layouts/{layout_id}/default")
def default_video_wall_layout(
    layout_id: int, db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("wall:write")),
):
    row = db.get(VideoWallLayout, layout_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "Layout não encontrado")
    db.query(VideoWallLayout).filter(VideoWallLayout.user_id == user.id).update({VideoWallLayout.is_default: False}, synchronize_session=False)
    row.is_default=True; row.updated_at=datetime.now(timezone.utc)
    audit(db, "Video Wall", "Definir layout padrão", f"layout_id={row.id}", user=user)
    db.commit(); db.refresh(row)
    return _video_wall_layout_payload(db, row, user)


@app.delete("/video-wall/layouts/{layout_id}")
def delete_video_wall_layout(
    layout_id: int, db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("wall:write")),
):
    row = db.get(VideoWallLayout, layout_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "Layout não encontrado")
    audit(db, "Video Wall", "Excluir layout", f"layout_id={row.id};name={row.name}", user=user)
    db.query(VideoWallSlot).filter(VideoWallSlot.layout_id == row.id).delete(synchronize_session=False)
    db.delete(row); db.commit()
    return {"ok": True, "layout_id": layout_id}


def _tcp_camera_status(item: tuple[int, str, int]) -> tuple[int, bool, str | None]:
    camera_id, host, port = item
    try:
        with socket.create_connection((host, int(port or 554)), timeout=2.5):
            return camera_id, True, None
    except OSError as error:
        return camera_id, False, str(error)


@app.post("/monitoring/status-refresh")
def monitoring_status_refresh(
    payload: MonitoringStatusRefreshIn,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    unique_ids = list(dict.fromkeys(int(value) for value in payload.camera_ids))[:16]
    cameras = []
    probes = []
    for camera_id in unique_ids:
        camera = ensure_camera_access(user, db.get(Camera, camera_id))
        cameras.append(camera)
        recorder = recorder_for_camera(db, camera)
        host = recorder.ip_address if recorder else (camera.ip_address or "")
        port = (recorder.rtsp_port if recorder else camera.port) or 554
        probes.append((camera.id, host, int(port)))

    results: dict[int, tuple[bool, str | None]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(probes) or 1)) as executor:
        for camera_id, ok, error in executor.map(_tcp_camera_status, probes):
            results[camera_id] = (ok, error)

    checked_at = datetime.now(timezone.utc)
    response = []
    for camera in cameras:
        ok, error = results.get(camera.id, (False, "Falha de verificação"))
        previous_status = camera.status
        camera.status = "ONLINE" if ok else "OFFLINE"
        camera.last_check_at = checked_at
        if ok:
            if camera.last_error and camera.last_error.startswith("Conectividade RTSP"):
                camera.last_error = None
        else:
            camera.last_error = f"Conectividade RTSP: {error or 'indisponível'}"

        if previous_status != camera.status:
            ingest_camera_event(
                db,
                CameraEventIn(
                    provider="EDUVIGIA_HEALTH",
                    provider_event_type="CAMERA_OFFLINE",
                    event_state="ACTIVE" if camera.status == "OFFLINE" else "INACTIVE",
                    camera_id=camera.id,
                    occurred_at=checked_at,
                    metadata={
                        "source": "monitoring_status_refresh",
                        "previous_status": previous_status,
                        "new_status": camera.status,
                        "error": None if ok else camera.last_error,
                    },
                ),
            )

        response.append({
            "camera_id": camera.id,
            "status": camera.status,
            "checked_at": checked_at,
            "error": None if ok else camera.last_error,
        })
    db.commit()
    return {"checked": len(response), "cameras": response}


@app.get("/monitoring/schools-summary")
def monitoring_schools_summary(
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    school_query = db.query(School)
    restricted_school_id = scoped_school_id(user)
    if restricted_school_id is not None:
        school_query = school_query.filter(School.id == restricted_school_id)

    result = []
    for school in school_query.order_by(School.name.asc()).all():
        cameras = db.query(Camera).filter(Camera.school_id == school.id).all()
        online = len([item for item in cameras if item.status == "ONLINE"])
        offline = len([item for item in cameras if item.status == "OFFLINE"])
        pending = len(cameras) - online - offline
        active_alerts = (
            db.query(Alert)
            .filter(
                ((Alert.school_id == school.id) | ((Alert.school_id.is_(None)) & (Alert.school_name == school.name))),
                Alert.status.notin_(["DESCARTADO", "ENCERRADO"]),
            )
            .count()
        )
        latest_alert = (
            db.query(Alert)
            .filter((Alert.school_id == school.id) | ((Alert.school_id.is_(None)) & (Alert.school_name == school.name)))
            .order_by(Alert.created_at.desc())
            .first()
        )
        result.append(
            {
                "school_id": school.id,
                "school_name": school.name,
                "school_code": school.code,
                "active": school.active,
                "total_cameras": len(cameras),
                "online": online,
                "offline": offline,
                "pending": pending,
                "active_alerts": active_alerts,
                "availability_percent": round((online / len(cameras) * 100), 2) if cameras else 0.0,
                "latest_event": (
                    {
                        "type": latest_alert.event_type,
                        "status": latest_alert.status,
                        "created_at": latest_alert.created_at,
                    }
                    if latest_alert
                    else None
                ),
            }
        )
    return result


@app.post("/cameras/provision-all")
def provision_all_cameras(
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    query = school_scope_query(db.query(Camera), Camera, actor)
    provisioned = 0
    failed = 0
    details = []
    for camera in query.order_by(Camera.id.asc()).all():
        try:
            ok, detail = provision_camera_path(camera, db)
            camera.last_error = None if ok else detail
            provisioned += 1 if ok else 0
            failed += 0 if ok else 1
            details.append({
                "camera_id": camera.id,
                "camera_name": camera.name,
                "stream_name": camera.stream_name,
                "ok": ok,
                "detail": detail,
            })
        except Exception as error:
            camera.last_error = str(error)
            failed += 1
            details.append({
                "camera_id": camera.id,
                "camera_name": camera.name,
                "stream_name": camera.stream_name,
                "ok": False,
                "detail": str(error),
            })
    audit(
        db,
        "Câmeras",
        "Provisionamento em lote",
        f"Sucesso={provisioned}; falhas={failed}",
        user=actor,
    )
    db.commit()
    return {
        "ok": failed == 0,
        "provisioned": provisioned,
        "failed": failed,
        "total": provisioned + failed,
        "details": details,
    }


@app.post("/cameras/{camera_id}/provision", response_model=CameraProvisionOut)
def provision_camera(
    camera_id: int,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    row = ensure_camera_access(actor, db.get(Camera, camera_id))
    try:
        ok, detail = provision_camera_path(row, db)
        row.last_error = None if ok else detail
        audit(db, "Câmeras", "Provisionamento", f"{row.name}: {ok}", user=actor)
        db.commit()
        return CameraProvisionOut(
            ok=ok,
            stream_name=row.stream_name or "",
            rtsp_url_masked=mask_rtsp_url(build_hikvision_rtsp(row, db)),
            mediamtx_status="CONFIGURADO" if ok else "FALHA",
            detail=detail,
        )
    except Exception as error:
        row.last_error = str(error)
        audit(db, "Câmeras", "Provisionamento", f"{row.name}: {error}", user=actor, outcome="FAILURE")
        db.commit()
        return CameraProvisionOut(
            ok=False,
            stream_name=row.stream_name or "",
            rtsp_url_masked=mask_rtsp_url(build_hikvision_rtsp(row, db)),
            mediamtx_status="FALHA",
            detail=str(error),
        )


@app.get("/cameras/{camera_id}/stream-status")
def camera_stream_status(
    camera_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    row = ensure_camera_access(user, db.get(Camera, camera_id))
    main_status = mediamtx_path_status(row.stream_name_main)
    sub_status = mediamtx_path_status(row.stream_name_sub)
    return {
        "camera_id": row.id,
        "selected_profile": row.stream_profile,
        "main": {
            "stream_name": row.stream_name_main,
            "status": row.main_status,
            "codec": row.main_codec,
            "resolution": row.main_resolution,
            "fps": row.main_fps,
            "bitrate_kbps": row.main_bitrate_kbps,
            **main_status,
        },
        "sub": {
            "stream_name": row.stream_name_sub,
            "status": row.sub_status,
            "codec": row.sub_codec,
            "resolution": row.sub_resolution,
            "fps": row.sub_fps,
            "bitrate_kbps": row.sub_bitrate_kbps,
            **sub_status,
        },
    }




@app.get("/cameras/{camera_id}/playback/capabilities")
def camera_playback_capabilities(
    camera_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("playback:view")),
):
    camera=ensure_camera_access(user, db.get(Camera,camera_id))
    target=_playback_target(db,camera)
    return {
        "camera_id": camera.id,
        "device_id": camera.device_id,
        "logical_channel": camera.logical_channel,
        "sensor_type": camera.sensor_type,
        "source_origin": target["origin"],
        "channel": target["channel"],
        "provider": "HIKVISION_RTSP_ISAPI",
        "search_supported": True,
        "preview_supported": True,
        "export_supported": "evidence:export" in role_permissions(user.role,user.school_id) or "*" in role_permissions(user.role,user.school_id),
    }


@app.post("/cameras/{camera_id}/playback/search")
def camera_playback_search(
    camera_id: int,
    payload: PlaybackRangeIn,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("playback:view")),
):
    camera=ensure_camera_access(user, db.get(Camera,camera_id))
    start,end,_=_validate_playback_range(payload.start_at,payload.end_at,max_seconds=24*60*60)
    body=_playback_search_body(camera,start,end,payload.max_results)
    status,response=_playback_xml_request(db,camera,body)
    segments=_parse_hikvision_recordings(response)
    audit(db,"Playback","Busca de gravações",f"camera_id={camera.id};channel={camera.logical_channel};results={len(segments)}",user=user)
    db.commit()
    return {"camera_id":camera.id,"start_at":start,"end_at":end,"count":len(segments),"segments":segments,"http_status":status}


@app.post("/cameras/{camera_id}/playback/preview", response_model=PlaybackPreviewOut)
def camera_playback_preview(
    camera_id: int,
    payload: PlaybackRangeIn,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("playback:view")),
):
    camera=ensure_camera_access(user, db.get(Camera,camera_id))
    start,end,duration=_validate_playback_range(payload.start_at,payload.end_at,max_seconds=PLAYBACK_PREVIEW_MAX_SECONDS)
    _cleanup_playback_previews()
    token=secrets.token_urlsafe(32)
    filename=f"preview-{camera.id}-{token[:12]}.mp4"
    target=PLAYBACK_DIR/filename
    source=build_hikvision_playback_rtsp(db,camera,start,end)
    _run_playback_export(source,target,duration)
    expires=datetime.now(timezone.utc)+timedelta(seconds=PLAYBACK_PREVIEW_TTL_SECONDS)
    with PLAYBACK_PREVIEW_LOCK:
        PLAYBACK_PREVIEWS[token]={"path":str(target),"camera_id":camera.id,"user_id":user.id,"expires_at":expires}
    audit(db,"Playback","Pré-visualização",f"camera_id={camera.id};seconds={duration}",user=user)
    db.commit()
    return PlaybackPreviewOut(token=token,expires_at=expires,duration_seconds=duration,filename=filename)


@app.get("/playback/previews/{token}")
def playback_preview_file(
    token: str,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("playback:view")),
):
    _cleanup_playback_previews()
    with PLAYBACK_PREVIEW_LOCK:
        item=PLAYBACK_PREVIEWS.get(token)
    if not item or item["expires_at"] <= datetime.now(timezone.utc):
        raise HTTPException(404,"Pré-visualização expirada")
    if item["user_id"] != user.id and canonical_role(user.role,user.school_id) != "ADMIN_SECRETARIA":
        raise HTTPException(403,"Pré-visualização pertence a outro operador")
    camera=ensure_camera_access(user,db.get(Camera,item["camera_id"]))
    path=Path(item["path"])
    if not path.exists(): raise HTTPException(404,"Arquivo temporário não encontrado")
    return FileResponse(path,media_type="video/mp4",filename=f"playback-{camera.id}.mp4")


@app.post("/cameras/{camera_id}/playback/export", response_model=EvidenceOut)
def camera_playback_export(
    camera_id: int,
    payload: PlaybackExportIn,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("evidence:export")),
):
    camera=ensure_camera_access(user,db.get(Camera,camera_id))
    start,end,duration=_validate_playback_range(payload.start_at,payload.end_at)
    occurrence=None
    if payload.occurrence_id is not None:
        occurrence=ensure_occurrence_access(db,user,db.get(Occurrence,payload.occurrence_id))
        if occurrence.school_id and occurrence.school_id != camera.school_id:
            raise HTTPException(400,"A câmera e a ocorrência pertencem a escolas diferentes")
    source=build_hikvision_playback_rtsp(db,camera,start,end)
    filename=f"evidence-cam-{camera.id}-{start.strftime('%Y%m%dT%H%M%SZ')}-{end.strftime('%H%M%SZ')}-{secrets.token_hex(4)}.mp4"
    target=EVIDENCE_DIR/filename
    _run_playback_export(source,target,duration)
    digest=_sha256_file(target)
    target_info=_playback_target(db,camera)
    row=Evidence(
        occurrence_id=occurrence.id if occurrence else None,
        school_id=camera.school_id,camera_id=camera.id,device_id=camera.device_id,
        logical_channel=camera.logical_channel,sensor_type=camera.sensor_type,
        evidence_type="VIDEO_EXPORT",filename=filename,original_name=filename,mime_type="video/mp4",
        file_path=str(target),sha256=digest,file_size_bytes=target.stat().st_size,
        source_start_at=start,source_end_at=end,source_origin=target_info["origin"],integrity_status="VERIFIED",
        observation=payload.observation,created_by=user.name,created_by_user_id=user.id,
    )
    db.add(row); db.flush()
    _record_custody(db,row,"CREATED",user,observed=digest,detail=f"Exportação de playback; channel={camera.logical_channel}; sensor={camera.sensor_type}")
    if occurrence:
        db.add(OccurrenceEvent(occurrence_id=occurrence.id,event_type="EVIDENCIA",description=f"Trecho de vídeo exportado da câmera {camera.name} ({duration}s).",user_name=user.name))
    audit(db,"Evidências","Exportação forense",f"evidence_id={row.id};camera_id={camera.id};sha256={digest}",user=user)
    db.commit(); db.refresh(row)
    return row


@app.get("/evidence/{evidence_id}/verify", response_model=EvidenceVerifyOut)
def verify_evidence(
    evidence_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("evidence:verify")),
):
    row=db.get(Evidence,evidence_id)
    if not row: raise HTTPException(404,"Evidência não encontrada")
    if row.camera_id: ensure_camera_access(user,db.get(Camera,row.camera_id))
    elif row.occurrence_id: ensure_occurrence_access(db,user,db.get(Occurrence,row.occurrence_id))
    path=Path(row.file_path)
    observed=_sha256_file(path) if path.exists() else None
    status="MISSING" if observed is None else ("VERIFIED" if row.sha256 and hmac.compare_digest(row.sha256,observed) else "MISMATCH")
    row.integrity_status=status
    _record_custody(db,row,"VERIFY",user,observed=observed,detail=f"integrity={status}")
    audit(db,"Evidências","Verificação de integridade",f"evidence_id={row.id};status={status}",user=user,outcome="SUCCESS" if status=="VERIFIED" else "FAILURE")
    db.commit()
    return EvidenceVerifyOut(evidence_id=row.id,expected_sha256=row.sha256,observed_sha256=observed,integrity_status=status,checked_at=datetime.now(timezone.utc))


@app.get("/evidence/{evidence_id}/custody", response_model=list[EvidenceCustodyOut])
def evidence_custody(
    evidence_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("evidence:verify")),
):
    row=db.get(Evidence,evidence_id)
    if not row: raise HTTPException(404,"Evidência não encontrada")
    if row.camera_id: ensure_camera_access(user,db.get(Camera,row.camera_id))
    elif row.occurrence_id: ensure_occurrence_access(db,user,db.get(Occurrence,row.occurrence_id))
    return db.query(EvidenceCustodyEvent).filter(EvidenceCustodyEvent.evidence_id==row.id).order_by(EvidenceCustodyEvent.created_at.asc(),EvidenceCustodyEvent.id.asc()).all()


@app.get("/cameras/{camera_id}/ptz/status")
def camera_ptz_status(
    camera_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("ptz:control")),
):
    camera = ensure_camera_access(user, db.get(Camera, camera_id))
    lease = _ptz_current_lease(db, camera.id)
    presets = db.query(CameraPTZPreset).filter(CameraPTZPreset.camera_id == camera.id).order_by(CameraPTZPreset.preset_no.asc()).all()
    return {
        "camera_id": camera.id,
        "enabled": bool(camera.ptz_enabled),
        "protocol": camera.ptz_protocol,
        "channel": camera.ptz_channel,
        "lease_seconds": PTZ_LEASE_SECONDS,
        "lease": _ptz_lease_payload(db, lease, user),
        "presets": [{"preset_no": item.preset_no, "name": item.name} for item in presets],
        "last_command_at": camera.ptz_last_command_at,
        "last_error": camera.ptz_last_error,
    }


@app.post("/cameras/{camera_id}/ptz/lease")
def camera_ptz_acquire_lease(
    camera_id: int,
    payload: PTZLeaseIn,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("ptz:control")),
):
    camera = ensure_camera_access(user, db.get(Camera, camera_id))
    _ptz_target(camera, db)
    current = _ptz_current_lease(db, camera.id)
    canonical = canonical_role(user.role, user.school_id)
    can_force = canonical in {"ADMIN_SECRETARIA", "SUPERVISOR_GUARDA"}
    if current and current.user_id != user.id:
        if not (payload.force and can_force):
            holder = db.get(UserAccount, current.user_id)
            raise HTTPException(409, f"PTZ em uso por {holder.name if holder else 'outro operador'}")
        db.delete(current)
        db.flush()
        current = None
    now = datetime.now(timezone.utc)
    if not current:
        current = CameraPTZLease(camera_id=camera.id, user_id=user.id, acquired_at=now, expires_at=now + timedelta(seconds=PTZ_LEASE_SECONDS), updated_at=now)
        db.add(current)
    else:
        current.expires_at = now + timedelta(seconds=PTZ_LEASE_SECONDS)
        current.updated_at = now
    audit(db, "PTZ", "Controle assumido", f"camera={camera.id}; force={bool(payload.force and can_force)}", user=user)
    db.commit()
    db.refresh(current)
    return {"ok": True, "lease": _ptz_lease_payload(db, current, user)}


@app.delete("/cameras/{camera_id}/ptz/lease")
def camera_ptz_release_lease(
    camera_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("ptz:control")),
):
    camera = ensure_camera_access(user, db.get(Camera, camera_id))
    current = _ptz_current_lease(db, camera.id)
    if current and current.user_id == user.id:
        try:
            _send_ptz_stop(db, camera)
        except Exception:
            pass
        db.delete(current)
        audit(db, "PTZ", "Controle liberado", f"camera={camera.id}", user=user)
        db.commit()
    return {"ok": True}


@app.post("/cameras/{camera_id}/ptz/move")
def camera_ptz_move(
    camera_id: int,
    payload: PTZMoveIn,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("ptz:control")),
):
    camera = ensure_camera_access(user, db.get(Camera, camera_id))
    _require_ptz_lease(db, camera, user)
    try:
        _send_ptz_move(db, camera, payload.direction, payload.speed)
        camera.ptz_last_command_at = datetime.now(timezone.utc)
        camera.ptz_last_error = None
        audit(db, "PTZ", "Movimento", f"camera={camera.id}; direction={payload.direction}; speed={payload.speed}", user=user)
        db.commit()
        return {"ok": True, "direction": payload.direction, "speed": payload.speed}
    except HTTPException as error:
        camera.ptz_last_error = str(error.detail)
        db.commit()
        raise


@app.post("/cameras/{camera_id}/ptz/stop")
def camera_ptz_stop(
    camera_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("ptz:control")),
):
    camera = ensure_camera_access(user, db.get(Camera, camera_id))
    _require_ptz_lease(db, camera, user)
    try:
        _send_ptz_stop(db, camera)
        camera.ptz_last_command_at = datetime.now(timezone.utc)
        camera.ptz_last_error = None
        audit(db, "PTZ", "STOP", f"camera={camera.id}", user=user)
        db.commit()
        return {"ok": True}
    except HTTPException as error:
        camera.ptz_last_error = str(error.detail)
        db.commit()
        raise


@app.get("/cameras/{camera_id}/ptz/presets")
def camera_ptz_presets(
    camera_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("ptz:control")),
):
    camera = ensure_camera_access(user, db.get(Camera, camera_id))
    _ptz_target(camera, db)
    rows = db.query(CameraPTZPreset).filter(CameraPTZPreset.camera_id == camera.id).order_by(CameraPTZPreset.preset_no.asc()).all()
    return {"camera_id": camera.id, "presets": [{"preset_no": row.preset_no, "name": row.name} for row in rows]}


@app.post("/cameras/{camera_id}/ptz/presets")
def camera_ptz_save_preset(
    camera_id: int,
    payload: PTZPresetIn,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("ptz:control")),
):
    camera = ensure_camera_access(user, db.get(Camera, camera_id))
    _require_ptz_lease(db, camera, user)
    _send_ptz_preset_set(db, camera, payload.preset_no, payload.name)
    row = db.query(CameraPTZPreset).filter(CameraPTZPreset.camera_id == camera.id, CameraPTZPreset.preset_no == payload.preset_no).first()
    if not row:
        row = CameraPTZPreset(camera_id=camera.id, preset_no=payload.preset_no, name=payload.name.strip(), created_by_user_id=user.id)
        db.add(row)
    else:
        row.name = payload.name.strip()
        row.created_by_user_id = user.id
    camera.ptz_last_command_at = datetime.now(timezone.utc)
    audit(db, "PTZ", "Preset salvo", f"camera={camera.id}; preset={payload.preset_no}; name={payload.name.strip()[:120]}", user=user)
    db.commit()
    return {"ok": True, "preset_no": payload.preset_no, "name": payload.name.strip()}


@app.post("/cameras/{camera_id}/ptz/presets/{preset_no}/goto")
def camera_ptz_goto_preset(
    camera_id: int,
    preset_no: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("ptz:control")),
):
    if preset_no < 1 or preset_no > 256:
        raise HTTPException(422, "Preset fora do intervalo 1..256")
    camera = ensure_camera_access(user, db.get(Camera, camera_id))
    _require_ptz_lease(db, camera, user)
    _send_ptz_preset_goto(db, camera, preset_no)
    camera.ptz_last_command_at = datetime.now(timezone.utc)
    camera.ptz_last_error = None
    audit(db, "PTZ", "Preset chamado", f"camera={camera.id}; preset={preset_no}", user=user)
    db.commit()
    return {"ok": True, "preset_no": preset_no}


@app.delete("/cameras/{camera_id}/ptz/presets/{preset_no}")
def camera_ptz_delete_preset(
    camera_id: int,
    preset_no: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("ptz:control")),
):
    if preset_no < 1 or preset_no > 256:
        raise HTTPException(422, "Preset fora do intervalo 1..256")
    camera = ensure_camera_access(user, db.get(Camera, camera_id))
    _require_ptz_lease(db, camera, user)
    _send_ptz_preset_delete(db, camera, preset_no)
    row = db.query(CameraPTZPreset).filter(CameraPTZPreset.camera_id == camera.id, CameraPTZPreset.preset_no == preset_no).first()
    if row:
        db.delete(row)
    audit(db, "PTZ", "Preset excluído", f"camera={camera.id}; preset={preset_no}", user=user)
    db.commit()
    return {"ok": True, "preset_no": preset_no}

@app.get("/cameras/{camera_id}/stream-access", response_model=StreamAccessOut)
def camera_stream_access(
    camera_id: int,
    request: Request,
    profile: Literal["MAIN", "SUB"] = Query(default="SUB"),
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    row = ensure_camera_access(user, db.get(Camera, camera_id))
    ensure_secure_camera_streams(db, row)
    selected_profile = profile.upper()
    stream_name = row.stream_name_main if selected_profile == "MAIN" else row.stream_name_sub
    if not stream_name:
        raise HTTPException(409, "Perfil de stream ainda não foi configurado")
    token, expires_at = create_stream_token(
        user_id=user.id,
        camera_id=row.id,
        school_id=row.school_id,
        path=stream_name,
        profile=selected_profile,
    )
    query = urllib.parse.urlencode({
        "token": token,
        "autoplay": "true",
        "muted": "true",
        "controls": "false",
    })
    status = mediamtx_path_status(stream_name)
    audit(
        db,
        "Monitoramento",
        "Acesso temporário ao stream",
        f"camera={row.id}; perfil={selected_profile}; expira={expires_at.isoformat()}",
        user=user,
    )
    db.commit()
    return StreamAccessOut(
        camera_id=row.id,
        profile=selected_profile,
        stream_name=stream_name,
        ready=status["ready"],
        webrtc_url=f"{_public_media_base(request, protocol='webrtc')}/{urllib.parse.quote(stream_name, safe='')}?{query}",
        hls_url=f"{_public_media_base(request, protocol='hls')}/{urllib.parse.quote(stream_name, safe='')}/index.m3u8?{urllib.parse.urlencode({'token': token})}",
        expires_at=expires_at,
    )


@app.get("/streams/test-access")
def test_stream_access(
    request: Request,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    token, expires_at = create_stream_token(
        user_id=user.id,
        camera_id=0,
        school_id=user.school_id,
        path="teste",
        profile="SUB",
        kind="test",
    )
    query = urllib.parse.urlencode({
        "token": token,
        "autoplay": "true",
        "muted": "true",
        "controls": "false",
    })
    return {
        "camera_id": 0,
        "profile": "SUB",
        "stream_name": "teste",
        "ready": mediamtx_path_status("teste")["ready"],
        "webrtc_url": f"{_public_media_base(request, protocol='webrtc')}/teste?{query}",
        "hls_url": f"{_public_media_base(request, protocol='hls')}/teste/index.m3u8?{urllib.parse.urlencode({'token': token})}",
        "expires_at": expires_at,
    }


@app.post("/internal/mediamtx-auth", include_in_schema=False)
def mediamtx_auth(
    payload: MediaMTXAuthIn,
    db: Session = Depends(db_session),
):
    if payload.action != "read":
        raise HTTPException(403, "Ação de mídia não autorizada")
    query_values = urllib.parse.parse_qs((payload.query or "").lstrip("?"), keep_blank_values=True)
    token = (query_values.get("token") or [payload.password or ""])[0]
    claims = validate_stream_token(token)
    requested_path = (payload.path or "").strip("/")
    if not hmac.compare_digest(str(claims.get("path", "")), requested_path):
        raise HTTPException(403, "Token não pertence a este stream")


    user = db.get(UserAccount, int(claims["uid"]))
    if not user or not user.active:
        raise HTTPException(403, "Usuário do stream não está ativo")

    if claims.get("kind") == "test":
        if requested_path != "teste":
            raise HTTPException(403, "Stream de teste inválido")
        return {"ok": True}

    camera = db.get(Camera, int(claims.get("cam", 0)))
    camera = ensure_camera_access(user, camera)
    allowed_paths = {camera.stream_name_main, camera.stream_name_sub}
    if requested_path not in allowed_paths or int(claims.get("sid") or 0) != int(camera.school_id):
        raise HTTPException(403, "Câmera ou escola não autorizada")
    return {"ok": True}


@app.delete("/cameras/{camera_id}")
def delete_camera(
    camera_id: int,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA")),
):
    row = ensure_camera_access(actor, db.get(Camera, camera_id))
    name = row.name
    delete_camera_paths(row)
    db.delete(row)
    audit(db, "Câmeras", "Exclusão", name, user=actor)
    db.commit()
    return {"ok": True}




@app.get("/camera-events/catalog")
def camera_event_catalog(
    user: UserAccount = Depends(require_permission("events:view")),
):
    return {
        "version": "F7-R3",
        "event_types": [
            {
                "event_type": event_type,
                "label": CAMERA_EVENT_LABELS[event_type],
                "default_severity": CAMERA_EVENT_DEFAULT_SEVERITY.get(event_type, "BAIXA"),
                "creates_alert": event_type in CAMERA_EVENT_ALERT_TYPES,
                "auto_recovery": event_type in CAMERA_EVENT_AUTO_RECOVERY_TYPES,
            }
            for event_type in CAMERA_EVENT_LABELS
        ],
        "providers": ["GENERIC", "HIKVISION_ISAPI", "ONVIF", "EDUVIGIA_HEALTH"],
    }


@app.get("/camera-events", response_model=list[CameraEventOut])
def list_camera_events(
    school_id: int | None = Query(default=None),
    camera_id: int | None = Query(default=None),
    recorder_id: int | None = Query(default=None),
    event_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    active: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("events:view")),
):
    query = scope_camera_event_query(db.query(CameraEvent), user)
    if school_id is not None:
        ensure_school_access(user, school_id)
        query = query.filter(CameraEvent.school_id == school_id)
    if camera_id is not None:
        ensure_camera_access(user, db.get(Camera, camera_id))
        query = query.filter(CameraEvent.camera_id == camera_id)
    if recorder_id is not None:
        ensure_recorder_access(user, db.get(Recorder, recorder_id))
        query = query.filter(CameraEvent.recorder_id == recorder_id)
    if event_type:
        query = query.filter(CameraEvent.event_type == normalize_camera_event_type(event_type))
    if severity:
        query = query.filter(CameraEvent.severity == severity.strip().upper())
    if active is not None:
        query = query.filter(CameraEvent.active.is_(active))
    rows = query.order_by(CameraEvent.last_seen_at.desc(), CameraEvent.id.desc()).limit(limit).all()
    return [camera_event_out(row) for row in rows]


@app.get("/camera-events/overview")
def camera_events_overview(
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("events:view")),
):
    query = scope_camera_event_query(db.query(CameraEvent), user)
    active_rows = query.filter(CameraEvent.active.is_(True)).all()
    recent_rows = (
        scope_camera_event_query(db.query(CameraEvent), user)
        .order_by(CameraEvent.last_seen_at.desc())
        .limit(10)
        .all()
    )
    health_query = scope_camera_health_query(db.query(CameraHealth), user)
    health_rows = health_query.all()
    recorder_rows = scope_recorder_health_query(db.query(RecorderHealth), user).all()
    return {
        "active_events": len(active_rows),
        "critical_events": len([row for row in active_rows if row.severity == "CRITICA"]),
        "high_events": len([row for row in active_rows if row.severity == "ALTA"]),
        "offline_cameras": len([row for row in health_rows if row.state == "OFFLINE"]),
        "degraded_cameras": len([row for row in health_rows if row.state == "DEGRADADO"]),
        "offline_recorders": len([row for row in recorder_rows if row.state == "OFFLINE"]),
        "recent": [camera_event_out(row).model_dump() for row in recent_rows],
    }


def _camera_health_payload(camera: Camera, health: CameraHealth | None) -> dict:
    if health:
        return CameraHealthOut.model_validate(health).model_dump()
    state = (
        "ONLINE"
        if camera.status == "ONLINE"
        else "OFFLINE"
        if camera.status == "OFFLINE"
        else "UNKNOWN"
    )
    return {
        "camera_id": camera.id,
        "school_id": camera.school_id,
        "state": state,
        "rtsp_online": True if camera.status == "ONLINE" else False if camera.status == "OFFLINE" else None,
        "main_online": True if camera.main_status == "ONLINE" else False if camera.main_status == "OFFLINE" else None,
        "sub_online": True if camera.sub_status == "ONLINE" else False if camera.sub_status == "OFFLINE" else None,
        "recording_status": "UNKNOWN",
        "storage_status": "UNKNOWN",
        "tamper_active": False,
        "motion_active": False,
        "ntp_offset_ms": None,
        "fps": camera.fps,
        "bitrate_kbps": camera.main_bitrate_kbps or camera.sub_bitrate_kbps,
        "resolution": camera.resolution,
        "codec": camera.codec,
        "last_event_at": None,
        "last_seen_at": camera.last_check_at,
        "last_video_at": camera.last_frame_at,
        "last_error": camera.last_error,
        "updated_at": camera.last_check_at or datetime.now(timezone.utc),
    }


@app.get("/camera-health")
def list_camera_health(
    school_id: int | None = Query(default=None),
    state: str | None = Query(default=None),
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("events:view")),
):
    camera_query = school_scope_query(db.query(Camera), Camera, user)
    if school_id is not None:
        ensure_school_access(user, school_id)
        camera_query = camera_query.filter(Camera.school_id == school_id)
    cameras = camera_query.order_by(Camera.school_id.asc(), Camera.name.asc()).all()
    health_by_camera = {
        row.camera_id: row
        for row in scope_camera_health_query(db.query(CameraHealth), user)
        .filter(CameraHealth.camera_id.in_([camera.id for camera in cameras] or [-1]))
        .all()
    }
    rows = [_camera_health_payload(camera, health_by_camera.get(camera.id)) for camera in cameras]
    if state:
        normalized = state.strip().upper()
        rows = [row for row in rows if row["state"] == normalized]
    return rows


@app.get("/recorder-health")
def list_recorder_health(
    school_id: int | None = Query(default=None),
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("events:view")),
):
    recorder_query = school_scope_query(db.query(Recorder), Recorder, user)
    if school_id is not None:
        ensure_school_access(user, school_id)
        recorder_query = recorder_query.filter(Recorder.school_id == school_id)
    recorders = recorder_query.order_by(Recorder.school_id.asc(), Recorder.name.asc()).all()
    health_by_recorder = {
        row.recorder_id: row
        for row in scope_recorder_health_query(db.query(RecorderHealth), user)
        .filter(RecorderHealth.recorder_id.in_([recorder.id for recorder in recorders] or [-1]))
        .all()
    }
    result = []
    for recorder in recorders:
        health = health_by_recorder.get(recorder.id)
        if health:
            result.append(RecorderHealthOut.model_validate(health).model_dump())
        else:
            result.append(
                {
                    "recorder_id": recorder.id,
                    "school_id": recorder.school_id,
                    "state": recorder.status if recorder.status in {"ONLINE", "OFFLINE", "DEGRADADO"} else "UNKNOWN",
                    "recording_status": "UNKNOWN",
                    "storage_status": "UNKNOWN",
                    "last_event_at": None,
                    "last_seen_at": recorder.last_check_at,
                    "last_error": recorder.last_error,
                    "updated_at": recorder.last_check_at or recorder.created_at,
                }
            )
    return result


@app.post("/camera-events/simulate", response_model=CameraEventIngestOut)
def simulate_camera_event(
    payload: CameraEventIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_permission("events:operate")),
):
    if payload.camera_id:
        ensure_camera_access(actor, db.get(Camera, payload.camera_id))
    if payload.recorder_id:
        ensure_recorder_access(actor, db.get(Recorder, payload.recorder_id))
    if payload.school_id:
        ensure_school_access(actor, payload.school_id)
    simulated = payload.model_copy(update={"provider": "GENERIC"})
    result = ingest_camera_event(db, simulated)
    audit(
        db,
        "Eventos de Câmera",
        "Simulação",
        f"type={result.event_type};event_id={result.event_id};alert_id={result.alert_id}",
        user=actor,
    )
    db.commit()
    return result


@app.post("/integrations/camera-events/ingest", response_model=CameraEventIngestOut)
def external_camera_event_ingest(
    payload: CameraEventIn,
    _: None = Depends(require_event_ingest_key),
    db: Session = Depends(db_session),
):
    result = ingest_camera_event(db, payload)
    audit(
        db,
        "Eventos de Câmera",
        "Ingestão externa",
        f"provider={payload.provider};type={result.event_type};event_id={result.event_id}",
        user_name="Camera Event Adapter",
    )
    db.commit()
    return result


@app.post("/integrations/camera-events/hikvision")
async def hikvision_camera_event_ingest(
    request: Request,
    recorder_id: int | None = Query(default=None),
    camera_id: int | None = Query(default=None),
    school_id: int | None = Query(default=None),
    _: None = Depends(require_event_ingest_key),
    db: Session = Depends(db_session),
):
    raw_body = await request.body()
    if len(raw_body) > 8_000_000:
        raise HTTPException(413, "Payload de eventos excede 8 MB")
    parsed = parse_hikvision_event_payload(raw_body)
    if not parsed:
        raise HTTPException(422, "Nenhum EventNotificationAlert Hikvision válido encontrado")

    results = []
    for item in parsed:
        payload = CameraEventIn(
            provider="HIKVISION_ISAPI",
            provider_event_type=item["provider_event_type"],
            event_state=item["event_state"],
            school_id=school_id,
            camera_id=camera_id,
            recorder_id=recorder_id,
            source_channel=item.get("source_channel"),
            occurred_at=item.get("occurred_at"),
            event_uid=item.get("event_uid"),
            metadata=item.get("metadata") or {},
            raw_payload=item.get("raw_payload"),
        )
        result = ingest_camera_event(db, payload)
        evidence_path = attach_hikvision_event_evidence(db, result.alert_id, raw_body)
        result_payload = result.model_dump()
        if evidence_path:
            result_payload["evidence_path"] = evidence_path
        results.append(result_payload)

    audit(
        db,
        "Eventos de Câmera",
        "Ingestão Hikvision",
        f"recorder_id={recorder_id};camera_id={camera_id};eventos={len(results)}",
        user_name="Hikvision ISAPI",
    )
    db.commit()
    return {"accepted": len(results), "events": results}


@app.get("/recorders/{recorder_id}/event-integration")
def recorder_event_integration(
    recorder_id: int,
    request: Request,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_permission("events:operate")),
):
    recorder = ensure_recorder_access(user, db.get(Recorder, recorder_id))
    base = str(request.base_url).rstrip("/")
    return {
        "recorder_id": recorder.id,
        "provider": "HIKVISION_ISAPI" if (recorder.manufacturer or "").lower().startswith("hik") else "GENERIC",
        "software_receiver": {
            "method": "POST",
            "url": f"{base}/integrations/camera-events/hikvision?recorder_id={recorder.id}",
            "authentication": "X-EduVigIA-Event-Key",
            "max_payload_bytes": 8_000_000,
        },
        "pull_reference": "/ISAPI/Event/notification/alertStream",
        "status": "SOFTWARE_CORE_READY_HARDWARE_BINDING_PENDING",
    }


@app.post("/alerts", response_model=AlertOut)
def create_alert(
    payload: AlertCreateIn,
    request: Request,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_permission("alerts:operate")),
):
    school = db.get(School, payload.school_id)
    if not school:
        raise HTTPException(404, "Escola não encontrada")
    ensure_school_access(actor, school.id)
    camera = None
    if payload.camera_id:
        camera = ensure_camera_access(actor, db.get(Camera, payload.camera_id))
        if camera.school_id != school.id:
            raise HTTPException(422, "A câmera não pertence à escola selecionada")
    row = Alert(
        school_id=school.id,
        camera_id=camera.id if camera else None,
        school_name=school.name,
        camera_name=camera.name if camera else "Sem câmera vinculada",
        event_type=payload.event_type.strip(),
        priority=payload.priority,
        status="NOVO",
        source="MANUAL",
        confidence=None,
        summary=(payload.summary or "").strip() or None,
        event_occurred_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.flush()
    add_alert_activity(db, row, "CRIADO", to_status="NOVO", user=actor)
    notify(
        db,
        title="Novo alerta operacional",
        message=f"{row.event_type} — {row.school_name}",
        severity="CRITICAL" if row.priority == "CRITICA" else "WARNING",
        module="Central de Alertas",
        school_id=row.school_id,
        entity_type="alert",
        entity_id=row.id,
    )
    audit(db, "Central de Alertas", "Cadastro manual", f"Alerta #{row.id}: {row.event_type}", request=request, user=actor)
    db.commit()
    db.refresh(row)
    return row


@app.get("/alerts", response_model=list[AlertOut])
def alerts(
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    school_id: int | None = Query(default=None),
    camera_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    query = scope_alert_query(db.query(Alert), db, user)
    if status:
        query = query.filter(Alert.status == status.upper())
    if priority:
        query = query.filter(Alert.priority == priority.upper())
    if school_id:
        ensure_school_access(user, school_id)
        query = query.filter(Alert.school_id == school_id)
    if camera_id:
        camera = ensure_camera_access(user, db.get(Camera, camera_id))
        query = query.filter(Alert.camera_id == camera.id)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            (Alert.event_type.ilike(term))
            | (Alert.school_name.ilike(term))
            | (Alert.camera_name.ilike(term))
            | (Alert.summary.ilike(term))
        )
    return query.order_by(Alert.created_at.desc()).limit(limit).all()


@app.get("/alerts/overview")
def alerts_overview(
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    query = scope_alert_query(db.query(Alert), db, user)
    rows = query.order_by(Alert.created_at.desc()).limit(500).all()
    active = [row for row in rows if row.status in ALERT_ACTIVE_STATUSES]
    now = datetime.now(timezone.utc)
    last_24h = []
    for row in rows:
        if not row.created_at:
            continue
        created_at = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=timezone.utc)
        if (now - created_at).total_seconds() <= 86400:
            last_24h.append(row)
    return {
        "version": APP_VERSION,
        "summary": {
            "total": len(rows),
            "active": len(active),
            "new": len([row for row in active if row.status == "NOVO"]),
            "in_service": len([row for row in active if row.status == "EM_ATENDIMENTO"]),
            "critical": len([row for row in active if row.priority == "CRITICA"]),
            "with_evidence": len([row for row in rows if row.evidence_path]),
            "last_24h": len(last_24h),
        },
        "by_priority": {
            priority: len([row for row in active if row.priority == priority])
            for priority in ["CRITICA", "ALTA", "MEDIA", "BAIXA"]
        },
        "latest": [AlertOut.model_validate(row).model_dump() for row in rows[:20]],
    }


@app.get("/alerts/{alert_id}/details")
def alert_details(
    alert_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    row = ensure_alert_access(db, user, db.get(Alert, alert_id))
    return alert_detail_out(db, row)


@app.get("/alerts/{alert_id}/evidence")
def alert_evidence(
    alert_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    row = ensure_alert_access(db, user, db.get(Alert, alert_id))
    evidence = alert_evidence_file(row)
    if not evidence:
        raise HTTPException(404, "Evidência não encontrada")
    return FileResponse(
        evidence,
        media_type="image/jpeg",
        filename=f"alerta-{row.id}-{evidence.name}",
        headers={"Cache-Control": "private, no-store"},
    )


@app.patch("/alerts/{alert_id}/workflow")
def alert_workflow(
    alert_id: int,
    payload: AlertWorkflowIn,
    request: Request,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "SUPERVISOR_GUARDA", "OPERADOR_GUARDA", "DESPACHANTE_GUARDA")),
):
    row = ensure_alert_access(db, actor, db.get(Alert, alert_id))
    set_alert_status(db, row, payload.status, user=actor, note=payload.note)
    notify(
        db,
        title=f"Alerta {row.status.lower().replace('_', ' ')}",
        message=f"{row.event_type} — {row.school_name} — {row.camera_name}",
        severity="CRITICAL" if row.priority == "CRITICA" else "WARNING",
        module="Central de Alertas",
        school_id=row.school_id,
        entity_type="alert",
        entity_id=row.id,
    )
    audit(db, "Central de Alertas", row.status, f"Alerta #{row.id}: {row.event_type}", request=request, user=actor)
    db.commit()
    db.refresh(row)
    return alert_detail_out(db, row)


@app.post("/alerts/{alert_id}/assign")
def alert_assign(
    alert_id: int,
    payload: AlertAssignIn,
    request: Request,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "SUPERVISOR_GUARDA", "OPERADOR_GUARDA", "DESPACHANTE_GUARDA")),
):
    row = ensure_alert_access(db, actor, db.get(Alert, alert_id))
    assigned_name = (payload.assigned_user_name or "").strip()
    assigned_id = payload.assigned_user_id
    if assigned_id:
        assigned_user = db.get(UserAccount, assigned_id)
        if not assigned_user or not assigned_user.active:
            raise HTTPException(404, "Usuário responsável não encontrado")
        if assigned_user.school_id and row.school_id and assigned_user.school_id != row.school_id:
            raise HTTPException(422, "O responsável não pertence à escola do alerta")
        assigned_name = assigned_user.name
    row.assigned_user_id = assigned_id
    row.assigned_user_name = assigned_name or None
    row.updated_at = datetime.now(timezone.utc)
    add_alert_activity(
        db,
        row,
        "ATRIBUICAO",
        from_status=row.status,
        to_status=row.status,
        note=payload.note or (f"Responsável: {assigned_name}" if assigned_name else "Atribuição removida"),
        user=actor,
    )
    audit(db, "Central de Alertas", "Atribuição", f"Alerta #{row.id}; responsável={assigned_name or 'nenhum'}", request=request, user=actor)
    db.commit()
    db.refresh(row)
    return alert_detail_out(db, row)


@app.patch("/alerts/{alert_id}/{action}")
def alert_action(
    alert_id: int,
    action: str,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "SUPERVISOR_GUARDA", "OPERADOR_GUARDA", "DESPACHANTE_GUARDA")),
):
    row = ensure_alert_access(db, actor, db.get(Alert, alert_id))
    mapping = {
        "confirm": "CONFIRMADO",
        "dismiss": "DESCARTADO",
        "analyze": "EM_ATENDIMENTO",
        "close": "ENCERRADO",
        "reopen": "NOVO",
    }
    if action not in mapping:
        raise HTTPException(400, "Ação inválida")
    set_alert_status(db, row, mapping[action], user=actor)
    notify(
        db,
        title=f"Alerta {mapping[action].lower().replace('_', ' ')}",
        message=f"{row.event_type} — {row.school_name} — {row.camera_name}",
        severity="WARNING" if action != "dismiss" else "INFO",
        module="Central de Alertas",
        school_id=row.school_id,
        entity_type="alert",
        entity_id=row.id,
    )
    audit(db, "Central de Alertas", mapping[action], f"{row.event_type} - {row.school_name}", user=actor)
    db.commit()
    return {"ok": True, "status": row.status}


@app.post("/alerts/{alert_id}/occurrence", response_model=OccurrenceOut)
def alert_to_occurrence(
    alert_id: int,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "SUPERVISOR_GUARDA", "OPERADOR_GUARDA", "DESPACHANTE_GUARDA")),
):
    alert_row = ensure_alert_access(db, actor, db.get(Alert, alert_id))
    existing = db.query(Occurrence).filter(Occurrence.alert_id == alert_row.id).first()
    if existing:
        ensure_occurrence_access(db, actor, existing)
        return existing

    school = ensure_school_name_access(db, actor, alert_row.school_name, alert_row.school_id)
    if not school:
        raise HTTPException(409, "O alerta não possui uma escola válida vinculada")
    row = Occurrence(
        protocol=occurrence_protocol(db),
        school_id=school.id,
        school_name=alert_row.school_name,
        category="SEGURANCA",
        priority=alert_row.priority,
        description=(alert_row.summary or f"{alert_row.event_type} detectado na câmera {alert_row.camera_name}.")
        + (f" Evidência: {alert_row.evidence_path}." if alert_row.evidence_path else ""),
        alert_id=alert_row.id,
    )
    previous_alert_status = alert_row.status
    alert_row.status = "ENCERRADO"
    alert_row.resolved_at = datetime.now(timezone.utc)
    alert_row.updated_at = datetime.now(timezone.utc)
    db.add(row)
    db.flush()
    db.add(
        OccurrenceEvent(
            occurrence_id=row.id,
            event_type="ABERTURA",
            description=f"Ocorrência aberta automaticamente a partir do alerta #{alert_row.id}.",
            user_name=actor.name,
        )
    )
    add_alert_activity(
        db,
        alert_row,
        "OCORRENCIA_ABERTA",
        from_status=previous_alert_status,
        to_status="ENCERRADO",
        note=f"Ocorrência {row.protocol} criada.",
        user=actor,
    )
    notify(
        db,
        title="Nova ocorrência",
        message=f"{row.protocol} aberta para {row.school_name}",
        severity="CRITICAL" if row.priority == "CRITICA" else "WARNING",
        module="Ocorrências",
        school_id=row.school_id,
        entity_type="occurrence",
        entity_id=row.id,
    )
    audit(db, "Ocorrências", "Abertura por alerta", row.protocol, user=actor)
    db.commit()
    db.refresh(row)
    return row


@app.get("/occurrences", response_model=list[OccurrenceOut])
def occurrences(
    status: str | None = Query(default=None),
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    query = scope_occurrence_query(db.query(Occurrence), db, user)
    if status:
        query = query.filter(Occurrence.status == status.upper())
    return query.order_by(Occurrence.created_at.desc()).all()


@app.post("/occurrences", response_model=OccurrenceOut)
def create_occurrence(
    payload: OccurrenceIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "SUPERVISOR_GUARDA", "OPERADOR_GUARDA", "DESPACHANTE_GUARDA")),
):
    school = ensure_school_name_access(db, actor, payload.school_name)
    if not school:
        raise HTTPException(404, "Escola não encontrada")
    row = Occurrence(
        protocol=occurrence_protocol(db),
        school_id=school.id,
        **payload.model_dump(),
    )
    db.add(row)
    db.flush()
    db.add(
        OccurrenceEvent(
            occurrence_id=row.id,
            event_type="ABERTURA",
            description="Ocorrência aberta manualmente pelo operador.",
            user_name=actor.name,
        )
    )
    notify(
        db,
        title="Ocorrência aberta",
        message=f"{row.protocol} — {row.school_name}",
        severity="WARNING",
        module="Ocorrências",
        school_id=row.school_id,
        entity_type="occurrence",
        entity_id=row.id,
    )
    audit(db, "Ocorrências", "Abertura manual", row.protocol, user=actor)
    db.commit()
    db.refresh(row)
    return row



@app.get("/occurrences/{occurrence_id}/details")
def occurrence_details(
    occurrence_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    occurrence = ensure_occurrence_access(db, user, db.get(Occurrence, occurrence_id))
    events = (
        db.query(OccurrenceEvent)
        .filter(OccurrenceEvent.occurrence_id == occurrence_id)
        .order_by(OccurrenceEvent.created_at.asc())
        .all()
    )
    evidence = (
        db.query(Evidence)
        .filter(Evidence.occurrence_id == occurrence_id)
        .order_by(Evidence.created_at.desc())
        .all()
    )
    response = OccurrenceOut.model_validate(occurrence).model_dump()
    response["events"] = [OccurrenceEventOut.model_validate(item).model_dump() for item in events]
    response["evidence"] = [EvidenceOut.model_validate(item).model_dump() for item in evidence]
    return response


@app.patch("/occurrences/{occurrence_id}", response_model=OccurrenceOut)
def update_occurrence(
    occurrence_id: int,
    payload: OccurrenceStatusIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "SUPERVISOR_GUARDA", "OPERADOR_GUARDA", "DESPACHANTE_GUARDA")),
):
    row = ensure_occurrence_access(db, actor, db.get(Occurrence, occurrence_id))
    previous_status = row.status
    row.status = payload.status

    if payload.assigned_team is not None:
        row.assigned_team = payload.assigned_team

    team = None
    if row.assigned_team:
        team = db.query(DispatchTeam).filter(DispatchTeam.name == row.assigned_team).first()

    if payload.status == "DESPACHADA" and team:
        team.status = "ACIONADA"
        team.current_occurrence_id = row.id
    elif payload.status == "EM_ATENDIMENTO" and team:
        team.status = "EM_ATENDIMENTO"
        team.current_occurrence_id = row.id
    elif payload.status == "ENCERRADA":
        row.closed_at = datetime.now(timezone.utc)
        if team:
            team.status = "DISPONIVEL"
            team.current_occurrence_id = None

    db.add(
        OccurrenceEvent(
            occurrence_id=row.id,
            event_type="STATUS",
            description=f"Status alterado de {previous_status} para {row.status}"
            + (f" — equipe: {row.assigned_team}" if row.assigned_team else ""),
            user_name=actor.name,
        )
    )
    notify(
        db,
        title="Ocorrência atualizada",
        message=f"{row.protocol}: {previous_status} → {row.status}",
        severity="INFO" if row.status == "ENCERRADA" else "WARNING",
        module="Ocorrências",
        school_id=row.school_id,
        entity_type="occurrence",
        entity_id=row.id,
    )
    audit(db, "Ocorrências", "Mudança de status", f"{row.protocol}: {row.status}", user=actor)
    db.commit()
    db.refresh(row)
    return row



@app.get("/teams", response_model=list[TeamOut])
def teams(
    db: Session = Depends(db_session),
    _: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "SUPERVISOR_GUARDA", "DESPACHANTE_GUARDA")),
):
    return (
        db.query(DispatchTeam)
        .filter(DispatchTeam.active.is_(True))
        .order_by(DispatchTeam.name.asc())
        .all()
    )


@app.post("/teams", response_model=TeamOut)
def create_team(
    payload: TeamIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "SUPERVISOR_GUARDA", "DESPACHANTE_GUARDA")),
):
    if db.query(DispatchTeam).filter(DispatchTeam.name == payload.name).first():
        raise HTTPException(409, "Já existe uma equipe com este nome")
    row = DispatchTeam(**payload.model_dump())
    db.add(row)
    audit(db, "Despacho", "Cadastro de equipe", row.name, user=actor)
    db.commit()
    db.refresh(row)
    return row


@app.patch("/teams/{team_id}/status", response_model=TeamOut)
def update_team_status(
    team_id: int,
    payload: TeamStatusIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "SUPERVISOR_GUARDA", "DESPACHANTE_GUARDA")),
):
    row = db.get(DispatchTeam, team_id)
    if not row:
        raise HTTPException(404, "Equipe não encontrada")
    row.status = payload.status
    if payload.status == "DISPONIVEL":
        row.current_occurrence_id = None
    audit(db, "Despacho", "Status da equipe", f"{row.name}: {row.status}", user=actor)
    db.commit()
    db.refresh(row)
    return row


@app.get(
    "/occurrences/{occurrence_id}/events",
    response_model=list[OccurrenceEventOut],
)
def occurrence_events(
    occurrence_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    ensure_occurrence_access(db, user, db.get(Occurrence, occurrence_id))
    return (
        db.query(OccurrenceEvent)
        .filter(OccurrenceEvent.occurrence_id == occurrence_id)
        .order_by(OccurrenceEvent.created_at.desc())
        .all()
    )


@app.post(
    "/occurrences/{occurrence_id}/events",
    response_model=OccurrenceEventOut,
)
def add_occurrence_event(
    occurrence_id: int,
    payload: OccurrenceEventIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "SUPERVISOR_GUARDA", "OPERADOR_GUARDA", "DESPACHANTE_GUARDA")),
):
    occurrence = ensure_occurrence_access(db, actor, db.get(Occurrence, occurrence_id))
    row = OccurrenceEvent(
        occurrence_id=occurrence_id,
        event_type=payload.event_type,
        description=payload.description,
        user_name=actor.name,
    )
    db.add(row)
    audit(db, "Ocorrências", "Registro de histórico", occurrence.protocol, user=actor)
    db.commit()
    db.refresh(row)
    return row




@app.get("/support/info")
def support_info():
    return {
        "title": "Suporte EduVigIA",
        "email": os.getenv("SUPPORT_EMAIL", "suporte@eduvigia.local"),
        "phone": os.getenv("SUPPORT_PHONE", "(81) 0000-0000"),
        "hours": os.getenv("SUPPORT_HOURS", "Segunda a sexta, das 08h às 18h"),
    }


@app.post("/support/requests", response_model=SupportRequestOut)
def create_support_request(
    payload: SupportRequestIn,
    request: Request,
    db: Session = Depends(db_session),
):
    protocol = f"SUP-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
    row = SupportRequest(
        protocol=protocol,
        name=payload.name.strip(),
        email=payload.email.strip().lower(),
        phone=payload.phone.strip() if payload.phone else None,
        category=payload.category,
        subject=payload.subject.strip(),
        message=payload.message.strip(),
        source="LOGIN",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    db.add(row)
    db.flush()
    audit(
        db,
        "Suporte",
        "Solicitação criada",
        protocol,
        request=request,
        user_name=row.name,
    )
    db.commit()
    db.refresh(row)
    return row


@app.get("/support/requests", response_model=list[SupportRequestOut])
def list_support_requests(
    status: str | None = Query(default=None),
    db: Session = Depends(db_session),
    _: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    query = db.query(SupportRequest)
    if status:
        query = query.filter(SupportRequest.status == status)
    return query.order_by(SupportRequest.created_at.desc()).limit(200).all()


@app.patch("/support/requests/{request_id}", response_model=SupportRequestOut)
def update_support_request(
    request_id: int,
    payload: dict,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    row = db.get(SupportRequest, request_id)
    if not row:
        raise HTTPException(404, "Solicitação de suporte não encontrada")
    status = str(payload.get("status", "")).upper()
    if status not in {"ABERTO", "EM_ATENDIMENTO", "RESOLVIDO", "CANCELADO"}:
        raise HTTPException(400, "Status de suporte inválido")
    row.status = status
    audit(
        db,
        "Suporte",
        "Status atualizado",
        f"{row.protocol}: {status}",
        user=actor,
    )
    db.commit()
    db.refresh(row)
    return row


@app.post("/auth/login", response_model=LoginOut)
def login(payload: LoginIn, request: Request, db: Session = Depends(db_session)):
    email = payload.email.strip().lower()
    user = db.query(UserAccount).filter(UserAccount.email == email).first()
    now = datetime.now(timezone.utc)

    if user and user.locked_until:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > now:
            minutes = max(1, int((locked_until - now).total_seconds() // 60) + 1)
            audit(
                db,
                "Autenticação",
                "Login bloqueado",
                email,
                request=request,
                user=user,
                outcome="BLOCKED",
            )
            db.commit()
            raise HTTPException(423, f"Conta bloqueada temporariamente. Tente novamente em {minutes} minuto(s).")
        user.locked_until = None
        user.failed_login_attempts = 0

    if not user or not user.active or not verify_password(payload.password, user.password_hash):
        if user:
            user.failed_login_attempts = int(user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
                user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            audit(
                db,
                "Autenticação",
                "Falha de login",
                email,
                request=request,
                user=user,
                outcome="FAILURE",
            )
            db.commit()
        raise HTTPException(401, "E-mail ou senha inválidos")

    db.query(AuthSession).filter(AuthSession.expires_at < now).delete(synchronize_session=False)

    raw_token = secrets.token_urlsafe(48)
    expires_at = now + timedelta(hours=SESSION_HOURS)
    db.add(
        AuthSession(
            user_id=user.id,
            token=token_digest(raw_token),
            expires_at=expires_at,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
            last_seen_at=now,
        )
    )
    user.last_login_at = now
    user.failed_login_attempts = 0
    user.locked_until = None
    audit(
        db,
        "Autenticação",
        "Login",
        user.email,
        request=request,
        user=user,
    )
    db.commit()
    return LoginOut(token=raw_token, expires_at=expires_at, user=user_payload(user))


@app.post("/auth/logout")
def logout(request: Request, db: Session = Depends(db_session)):
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    session_row = db.query(AuthSession).filter(
        AuthSession.token.in_([token_digest(token), token])
    ).first()
    if session_row:
        db.delete(session_row)
        db.commit()
    return {"ok": True}


@app.get("/auth/me")
def auth_me(user: UserAccount = Depends(require_user)):
    return user_payload(user)


@app.post("/auth/change-password")
def change_password(
    payload: PasswordChangeIn,
    request: Request,
    user: UserAccount = Depends(require_user),
    db: Session = Depends(db_session),
):
    current = db.get(UserAccount, user.id)
    if not current or not verify_password(payload.current_password, current.password_hash):
        audit(db, "Usuários", "Falha na alteração de senha", current.email if current else "desconhecido", user=user, outcome="FAILURE")
        db.commit()
        raise HTTPException(400, "Senha atual incorreta")
    validate_password_policy(payload.new_password)
    if verify_password(payload.new_password, current.password_hash):
        raise HTTPException(400, "A nova senha deve ser diferente da senha atual")

    current.password_hash = hash_password(payload.new_password)
    current.password_changed_at = datetime.now(timezone.utc)
    current.must_change_password = False

    raw_token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    current_digest = token_digest(raw_token) if raw_token else ""
    query = db.query(AuthSession).filter(AuthSession.user_id == current.id)
    if current_digest:
        query = query.filter(AuthSession.token.notin_([current_digest, raw_token]))
    revoked = query.delete(synchronize_session=False)

    audit(
        db,
        "Usuários",
        "Alteração de senha",
        f"{current.email}; sessoes_revogadas={revoked}",
        user=current,
    )
    db.commit()
    return {"ok": True, "revoked_sessions": revoked}



@app.get("/security/overview")
def security_overview(
    db: Session = Depends(db_session),
    _: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA")),
):
    now = datetime.now(timezone.utc)
    active_sessions = db.query(AuthSession).filter(AuthSession.expires_at > now).count()
    locked_users = db.query(UserAccount).filter(UserAccount.locked_until > now).count()
    encrypted_recorders = db.query(Recorder).filter(Recorder.password.like("enc:v1:%")).count()
    recorder_credentials = db.query(Recorder).filter(Recorder.password.isnot(None)).count()
    encrypted_cameras = db.query(Camera).filter(Camera.password.like("enc:v1:%")).count()
    camera_credentials = db.query(Camera).filter(Camera.password.isnot(None)).count()
    recent_failures = (
        db.query(AuditLog)
        .filter(
            AuditLog.module == "Autenticação",
            AuditLog.outcome.in_(["FAILURE", "BLOCKED"]),
            AuditLog.created_at >= now - timedelta(hours=24),
        )
        .count()
    )
    return {
        "active_sessions": active_sessions,
        "locked_users": locked_users,
        "recent_login_failures_24h": recent_failures,
        "credential_key_configured": bool(_fernet()),
        "encrypted_recorder_credentials": encrypted_recorders,
        "recorder_credentials": recorder_credentials,
        "encrypted_camera_credentials": encrypted_cameras,
        "camera_credentials": camera_credentials,
        "password_policy": {
            "minimum_length": MIN_PASSWORD_LENGTH,
            "requires_uppercase": True,
            "requires_lowercase": True,
            "requires_number": True,
            "requires_special": True,
        },
        "lockout_policy": {
            "attempts": MAX_LOGIN_ATTEMPTS,
            "minutes": LOCKOUT_MINUTES,
        },
    }


@app.get("/auth/sessions")
def list_sessions(
    user: UserAccount = Depends(require_user),
    db: Session = Depends(db_session),
):
    now = datetime.now(timezone.utc)
    rows = (
        db.query(AuthSession)
        .filter(AuthSession.user_id == user.id, AuthSession.expires_at > now)
        .order_by(AuthSession.created_at.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "ip_address": row.ip_address,
            "user_agent": row.user_agent,
            "created_at": row.created_at,
            "last_seen_at": row.last_seen_at,
            "expires_at": row.expires_at,
        }
        for row in rows
    ]


@app.delete("/auth/sessions/{session_id}")
def revoke_session(
    session_id: int,
    user: UserAccount = Depends(require_user),
    db: Session = Depends(db_session),
):
    row = db.get(AuthSession, session_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "Sessão não encontrada")
    db.delete(row)
    audit(db, "Autenticação", "Sessão revogada", f"session_id={session_id}", user_name=user.name)
    db.commit()
    return {"ok": True}


@app.post("/security/encrypt-existing-credentials")
def encrypt_existing_credentials(
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA")),
):
    if not _fernet():
        raise HTTPException(503, "EDUVIGIA_CREDENTIAL_KEY não está configurada")

    updated_recorders = 0
    updated_cameras = 0

    for row in db.query(Recorder).filter(Recorder.password.isnot(None)).all():
        if row.password and not row.password.startswith("enc:v1:"):
            row.password = encrypt_secret(row.password)
            updated_recorders += 1

    for row in db.query(Camera).filter(Camera.password.isnot(None)).all():
        if row.password and not row.password.startswith("enc:v1:"):
            row.password = encrypt_secret(row.password)
            updated_cameras += 1

    audit(
        db,
        "Segurança",
        "Criptografia de credenciais existentes",
        f"gravadores={updated_recorders}; cameras={updated_cameras}",
        user_name=actor.name,
    )
    db.commit()
    return {
        "ok": True,
        "updated_recorders": updated_recorders,
        "updated_cameras": updated_cameras,
    }


@app.get("/users", response_model=list[UserOut])
def users(
    db: Session = Depends(db_session),
    _: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA")),
):
    return db.query(UserAccount).order_by(UserAccount.name.asc()).all()



@app.get("/users/overview")
def users_overview(
    db: Session = Depends(db_session),
    _: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA")),
):
    rows = (
        db.query(UserAccount, School.name)
        .outerjoin(School, School.id == UserAccount.school_id)
        .order_by(UserAccount.name.asc())
        .all()
    )
    return [
        {
            **UserOut.model_validate(user).model_dump(),
            "school_name": school_name,
        }
        for user, school_name in rows
    ]


@app.post("/users", response_model=UserOut)
def create_user(
    payload: UserIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA")),
):
    email = payload.email.strip().lower()
    if db.query(UserAccount).filter(UserAccount.email == email).first():
        raise HTTPException(409, "Já existe um usuário com este e-mail")
    validate_role_school_binding(payload.role, payload.school_id)
    if payload.school_id and not db.get(School, payload.school_id):
        raise HTTPException(404, "Escola não encontrada")
    validate_password_policy(payload.password)
    row = UserAccount(
        name=payload.name,
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        school_id=payload.school_id,
        active=payload.active,
        must_change_password=True,
    )
    db.add(row)
    audit(
        db,
        "Usuários",
        "Cadastro",
        f"{row.email} — {row.role}",
        user=actor,
    )
    db.commit()
    db.refresh(row)
    return row


@app.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA")),
):
    row = db.get(UserAccount, user_id)
    if not row:
        raise HTTPException(404, "Usuário não encontrado")
    duplicate = (
        db.query(UserAccount)
        .filter(UserAccount.email == payload.email.strip().lower(), UserAccount.id != user_id)
        .first()
    )
    if duplicate:
        raise HTTPException(409, "Já existe outro usuário com este e-mail")
    validate_role_school_binding(payload.role, payload.school_id)
    if payload.school_id and not db.get(School, payload.school_id):
        raise HTTPException(404, "Escola não encontrada")
    if row.id == actor.id and not payload.active:
        raise HTTPException(400, "Você não pode desativar o próprio usuário")
    if is_admin_role(row.role, row.school_id) and (payload.role != "ADMIN_SECRETARIA" or not payload.active):
        active_admins = sum(
            1
            for candidate in db.query(UserAccount).filter(UserAccount.active.is_(True)).all()
            if is_admin_role(candidate.role, candidate.school_id)
        )
        if active_admins <= 1:
            raise HTTPException(400, "O sistema deve manter pelo menos um administrador ativo da Secretaria")
    row.name = payload.name
    row.email = payload.email.strip().lower()
    row.role = payload.role
    row.school_id = payload.school_id
    row.active = payload.active
    audit(
        db,
        "Usuários",
        "Edição",
        f"{row.email} — {row.role} — ativo={row.active}",
        user=actor,
    )
    db.commit()
    db.refresh(row)
    return row


@app.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    payload: PasswordResetIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA")),
):
    row = db.get(UserAccount, user_id)
    if not row:
        raise HTTPException(404, "Usuário não encontrado")
    validate_password_policy(payload.new_password)
    row.password_hash = hash_password(payload.new_password)
    row.must_change_password = True
    row.password_changed_at = None
    revoked = db.query(AuthSession).filter(AuthSession.user_id == row.id).delete(
        synchronize_session=False
    )
    audit(
        db,
        "Usuários",
        "Redefinição de senha",
        f"{row.email}; sessoes_revogadas={revoked}",
        user=actor,
    )
    db.commit()
    return {"ok": True}



@app.get("/auth/permissions")
def auth_permissions(user: UserAccount = Depends(require_user)):
    canonical = canonical_role(user.role, user.school_id)
    profile = role_profile(user.role, user.school_id)
    return {
        "role": canonical,
        "role_label": profile["label"],
        "environment": profile["environment"],
        "permissions": role_permissions(user.role, user.school_id),
        "school_id": user.school_id,
        "school_required": profile["school_required"],
    }




@app.get("/occurrences/{occurrence_id}/evidence", response_model=list[EvidenceOut])
def list_evidence(
    occurrence_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    ensure_occurrence_access(db, user, db.get(Occurrence, occurrence_id))
    return (
        db.query(Evidence)
        .filter(Evidence.occurrence_id == occurrence_id)
        .order_by(Evidence.created_at.desc())
        .all()
    )


@app.post("/occurrences/{occurrence_id}/snapshot", response_model=EvidenceOut)
def create_snapshot(
    occurrence_id: int,
    camera_id: int = Form(...),
    observation: str = Form(default=""),
    db: Session = Depends(db_session),
    user: UserAccount = Depends(
        require_roles("ADMIN_SECRETARIA", "SUPERVISOR_GUARDA", "OPERADOR_GUARDA", "DESPACHANTE_GUARDA")
    ),
):
    occurrence = ensure_occurrence_access(db, user, db.get(Occurrence, occurrence_id))
    camera = ensure_camera_access(user, db.get(Camera, camera_id))
    occurrence_school = ensure_school_name_access(
        db, user, occurrence.school_name, occurrence.school_id
    )
    if occurrence_school and camera.school_id != occurrence_school.id:
        raise HTTPException(400, "A câmera e a ocorrência pertencem a escolas diferentes")

    source = build_hikvision_rtsp(camera, db)
    filename = (
        f"occ-{occurrence_id}-cam-{camera_id}-"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.jpg"
    )
    file_path = EVIDENCE_DIR / filename

    try:
        process = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-rtsp_transport",
                "tcp",
                "-i",
                source,
                "-frames:v",
                "1",
                "-q:v",
                "2",
                "-y",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Tempo limite ao capturar snapshot")

    if process.returncode != 0 or not file_path.exists():
        raise HTTPException(
            502,
            (process.stderr or "Não foi possível capturar o snapshot")[-700:],
        )

    digest = _sha256_file(file_path)
    row = Evidence(
        occurrence_id=occurrence_id, school_id=camera.school_id, camera_id=camera_id,
        device_id=camera.device_id, logical_channel=camera.logical_channel, sensor_type=camera.sensor_type,
        evidence_type="SNAPSHOT", filename=filename, original_name=filename, mime_type="image/jpeg",
        file_path=str(file_path), sha256=digest, file_size_bytes=file_path.stat().st_size,
        source_origin="LIVE", integrity_status="VERIFIED",
        observation=observation or None, created_by=user.name, created_by_user_id=user.id,
    )
    db.add(row); db.flush()
    _record_custody(db,row,"CREATED",user,observed=digest,detail="Snapshot operacional")
    db.add(
        OccurrenceEvent(
            occurrence_id=occurrence_id,
            event_type="EVIDENCIA",
            description=f"Snapshot capturado da câmera {camera.name}.",
            user_name=user.name,
        )
    )
    audit(db, "Ocorrências", "Snapshot", occurrence.protocol, user=user)
    db.commit()
    db.refresh(row)
    return row


@app.post("/occurrences/{occurrence_id}/evidence/upload", response_model=EvidenceOut)
def upload_evidence(
    occurrence_id: int,
    file: UploadFile = File(...),
    observation: str = Form(default=""),
    camera_id: int | None = Form(default=None),
    db: Session = Depends(db_session),
    user: UserAccount = Depends(
        require_roles("ADMIN_SECRETARIA", "SUPERVISOR_GUARDA", "OPERADOR_GUARDA", "DESPACHANTE_GUARDA")
    ),
):
    occurrence = ensure_occurrence_access(db, user, db.get(Occurrence, occurrence_id))
    if camera_id is not None:
        camera = ensure_camera_access(user, db.get(Camera, camera_id))
        occurrence_school = ensure_school_name_access(
            db, user, occurrence.school_name, occurrence.school_id
        )
        if occurrence_school and camera.school_id != occurrence_school.id:
            raise HTTPException(400, "A câmera e a ocorrência pertencem a escolas diferentes")

    allowed = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "application/pdf": ".pdf",
    }
    if file.content_type not in allowed:
        raise HTTPException(400, "Envie JPG, PNG ou PDF")

    safe_name = (
        f"occ-{occurrence_id}-{secrets.token_hex(8)}{allowed[file.content_type]}"
    )
    target = EVIDENCE_DIR / safe_name
    content = file.file.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(413, "Arquivo maior que 15 MB")
    target.write_bytes(content)

    camera = db.get(Camera, camera_id) if camera_id is not None else None
    digest = _sha256_file(target)
    row = Evidence(
        occurrence_id=occurrence_id,
        school_id=(camera.school_id if camera else occurrence.school_id),
        camera_id=camera_id, device_id=(camera.device_id if camera else None),
        logical_channel=(camera.logical_channel if camera else None), sensor_type=(camera.sensor_type if camera else None),
        evidence_type="ANEXO", filename=safe_name, original_name=file.filename, mime_type=file.content_type,
        file_path=str(target), sha256=digest, file_size_bytes=target.stat().st_size,
        source_origin="UPLOAD", integrity_status="VERIFIED", observation=observation or None,
        created_by=user.name, created_by_user_id=user.id,
    )
    db.add(row); db.flush()
    _record_custody(db,row,"CREATED",user,observed=digest,detail=f"Upload: {file.filename}")
    db.add(
        OccurrenceEvent(
            occurrence_id=occurrence_id,
            event_type="EVIDENCIA",
            description=f"Arquivo anexado: {file.filename}",
            user_name=user.name,
        )
    )
    audit(db, "Ocorrências", "Anexo de evidência", occurrence.protocol, user=user)
    db.commit()
    db.refresh(row)
    return row


@app.get("/evidence/{evidence_id}/file")
def download_evidence(
    evidence_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    row = db.get(Evidence, evidence_id)
    if not row:
        raise HTTPException(404, "Evidência não encontrada")
    occurrence = ensure_occurrence_access(db, user, db.get(Occurrence, row.occurrence_id)) if row.occurrence_id else None
    if row.camera_id:
        ensure_camera_access(user, db.get(Camera, row.camera_id))
    path = Path(row.file_path)
    if not path.exists():
        raise HTTPException(404, "Arquivo físico não encontrado")
    observed = _sha256_file(path)
    _record_custody(db,row,"DOWNLOAD",user,observed=observed,detail="Download autorizado")
    audit(
        db,
        "Evidências",
        "Download",
        f"evidence_id={row.id}; occurrence={occurrence.protocol if occurrence else 'NONE'};sha256={observed}",
        user=user,
    )
    db.commit()
    return FileResponse(
        path,
        media_type=row.mime_type,
        filename=row.original_name or row.filename,
    )


def scope_notification_query(query, user: UserAccount):
    restricted_school_id = scoped_school_id(user)
    if restricted_school_id is None:
        return query.filter((Notification.user_id.is_(None)) | (Notification.user_id == user.id))
    return query.filter(
        (Notification.user_id == user.id)
        | (
            Notification.user_id.is_(None)
            & ((Notification.school_id.is_(None)) | (Notification.school_id == restricted_school_id))
        )
    )


@app.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    query = scope_notification_query(db.query(Notification), user)
    if unread_only:
        already_read = db.query(NotificationRead.id).filter(
            NotificationRead.user_id == user.id,
            NotificationRead.notification_id == Notification.id,
        ).exists()
        query = query.filter(~already_read)
    rows = query.order_by(Notification.created_at.desc()).limit(limit).all()
    read_rows = {
        item.notification_id: item.read_at
        for item in db.query(NotificationRead).filter(
            NotificationRead.user_id == user.id,
            NotificationRead.notification_id.in_([row.id for row in rows] or [-1]),
        ).all()
    }
    return [
        NotificationOut(
            id=row.id,
            user_id=row.user_id,
            school_id=row.school_id,
            title=row.title,
            message=row.message,
            severity=row.severity,
            module=row.module,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            read_at=read_rows.get(row.id),
            created_at=row.created_at,
        )
        for row in rows
    ]


@app.get("/notifications/unread-count")
def notification_unread_count(
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    query = scope_notification_query(db.query(Notification), user)
    already_read = db.query(NotificationRead.id).filter(
        NotificationRead.user_id == user.id,
        NotificationRead.notification_id == Notification.id,
    ).exists()
    return {"unread": query.filter(~already_read).count()}


def _visible_notification(db: Session, user: UserAccount, notification_id: int) -> Notification:
    row = db.get(Notification, notification_id)
    if not row:
        raise HTTPException(404, "Notificação não encontrada")
    visible = scope_notification_query(db.query(Notification), user).filter(Notification.id == notification_id).first()
    if not visible:
        raise HTTPException(404, "Notificação não encontrada")
    return row


@app.patch("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    row = _visible_notification(db, user, notification_id)
    receipt = db.query(NotificationRead).filter(
        NotificationRead.notification_id == row.id,
        NotificationRead.user_id == user.id,
    ).first()
    now = datetime.now(timezone.utc)
    if not receipt:
        receipt = NotificationRead(notification_id=row.id, user_id=user.id, read_at=now)
        db.add(receipt)
    else:
        receipt.read_at = now
    db.commit()
    return NotificationOut(
        id=row.id, user_id=row.user_id, school_id=row.school_id, title=row.title, message=row.message,
        severity=row.severity, module=row.module, entity_type=row.entity_type, entity_id=row.entity_id,
        read_at=receipt.read_at, created_at=row.created_at,
    )


@app.patch("/notifications/read-all")
def mark_all_notifications_read(
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    ids = [row.id for row in scope_notification_query(db.query(Notification), user).all()]
    existing_ids = {
        item.notification_id
        for item in db.query(NotificationRead).filter(
            NotificationRead.user_id == user.id,
            NotificationRead.notification_id.in_(ids or [-1]),
        ).all()
    }
    now = datetime.now(timezone.utc)
    missing = [notification_id for notification_id in ids if notification_id not in existing_ids]
    for notification_id in missing:
        db.add(NotificationRead(notification_id=notification_id, user_id=user.id, read_at=now))
    db.commit()
    return {"ok": True, "updated": len(missing)}


@app.get("/system/health")
def system_health(
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    services = {}
    try:
        db.execute(text("SELECT 1"))
        services["database"] = {"status": "online", "detail": "PostgreSQL respondeu"}
    except Exception as error:
        services["database"] = {"status": "offline", "detail": str(error)}

    for service_name, host, port in [
        ("redis", "redis", 6379),
        ("mediamtx_rtsp", "mediamtx", 8554),
        ("mediamtx_webrtc", "mediamtx", 8889),
    ]:
        try:
            with socket.create_connection((host, port), timeout=1.5):
                services[service_name] = {"status": "online", "detail": f"{host}:{port}"}
        except OSError as error:
            services[service_name] = {"status": "offline", "detail": str(error)}

    camera_query = school_scope_query(db.query(Camera), Camera, user)
    camera_total = camera_query.count()
    camera_online = camera_query.filter(Camera.status == "ONLINE").count()
    camera_offline = camera_query.filter(Camera.status == "OFFLINE").count()
    camera_pending = camera_query.filter(Camera.status == "PENDING").count()

    overall = "online"
    if any(item["status"] == "offline" for item in services.values()):
        overall = "degraded"

    if canonical_role(user.role, user.school_id) not in {"ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO"}:
        services = {
            name: {"status": item["status"], "detail": "Detalhes restritos"}
            for name, item in services.items()
        }

    return {
        "overall": overall,
        "checked_at": datetime.now(timezone.utc),
        "services": services,
        "cameras": {
            "total": camera_total,
            "online": camera_online,
            "offline": camera_offline,
            "pending": camera_pending,
        },
    }



@app.get("/homologation/checklist")
def homologation_checklist(
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "TECNICO")),
):
    camera_query = school_scope_query(db.query(Camera), Camera, user)
    recorder_query = school_scope_query(db.query(Recorder), Recorder, user)
    cameras_total = camera_query.count()
    cameras_online = camera_query.filter(Camera.status == "ONLINE").count()
    recorders_total = recorder_query.count()
    recorders_online = recorder_query.filter(Recorder.status == "ONLINE").count()
    users_total = (
        db.query(UserAccount).filter(UserAccount.active.is_(True)).count()
        if scoped_school_id(user) is None
        else db.query(UserAccount).filter(
            UserAccount.active.is_(True), UserAccount.school_id == scoped_school_id(user)
        ).count()
    )
    support_open = db.query(SupportRequest).filter(SupportRequest.status != "RESOLVIDO").count()
    provisioned = camera_query.filter(Camera.stream_name.isnot(None)).count()

    checks = []

    def add(code, title, status, detail, required=True):
        checks.append(
            {
                "code": code,
                "title": title,
                "status": status,
                "detail": detail,
                "required": required,
            }
        )

    try:
        db.execute(text("SELECT 1"))
        add("DB", "Banco de dados", "APROVADO", "PostgreSQL respondeu corretamente")
    except Exception as error:
        add("DB", "Banco de dados", "FALHOU", str(error))

    add("USERS", "Usuários ativos", "APROVADO" if users_total else "PENDENTE", f"{users_total} usuário(s) ativo(s)")
    add("CAMERAS", "Cadastro de câmeras", "APROVADO" if cameras_total else "NAO_TESTADO", f"{cameras_total} câmera(s); {cameras_online} online")
    add("NVR", "Gravadores NVR/DVR", "APROVADO" if recorders_total else "NAO_TESTADO", f"{recorders_total} gravador(es); {recorders_online} online")
    add("STREAMS", "Streams provisionados", "APROVADO" if provisioned else "NAO_TESTADO", f"{provisioned} stream(s) provisionado(s)")
    add("SECURITY", "Chave de credenciais", "APROVADO" if bool(_fernet()) else "PENDENTE", "Chave configurada" if bool(_fernet()) else "EDUVIGIA_CREDENTIAL_KEY ausente")
    add("EVIDENCE", "Diretório de evidências", "APROVADO" if EVIDENCE_DIR.exists() else "FALHOU", str(EVIDENCE_DIR))
    add("SUPPORT", "Canal de suporte", "APROVADO", f"{support_open} solicitação(ões) aberta(s)", False)

    approved = len([item for item in checks if item["status"] == "APROVADO"])
    failed = len([item for item in checks if item["status"] == "FALHOU"])
    pending = len([item for item in checks if item["status"] in {"PENDENTE", "NAO_TESTADO"}])
    overall = "FALHOU" if failed else "PENDENTE" if pending else "APROVADO"

    return {
        "version": APP_VERSION,
        "checked_at": datetime.now(timezone.utc),
        "overall": overall,
        "summary": {
            "approved": approved,
            "failed": failed,
            "pending": pending,
            "total": len(checks),
        },
        "checks": checks,
    }


@app.get("/homologation", response_model=HomologationOut)
def homologation(
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "TECNICO")),
):
    services = {}
    for name, host, port in [
        ("postgresql", "postgres", 5432),
        ("redis", "redis", 6379),
        ("mediamtx_rtsp", "mediamtx", 8554),
        ("mediamtx_webrtc", "mediamtx", 8889),
        ("mediamtx_api", "mediamtx", 9997),
    ]:
        try:
            with socket.create_connection((host, port), timeout=1.5):
                services[name] = {"status": "ONLINE", "endpoint": f"{host}:{port}"}
        except OSError as error:
            services[name] = {"status": "OFFLINE", "detail": str(error)}

    config_status, config_paths = mediamtx_request("GET", "/v3/config/paths/list")
    runtime_status, runtime_paths = mediamtx_request("GET", "/v3/paths/list")

    cameras = school_scope_query(db.query(Camera), Camera, user).all()
    online = len([item for item in cameras if item.status == "ONLINE"])
    provisioned = len([item for item in cameras if item.stream_name])

    return {
        "version": APP_VERSION,
        "checked_at": datetime.now(timezone.utc),
        "application": {
            "api": "ONLINE",
            "database_schema": "OK",
            "evidence_directory": str(EVIDENCE_DIR),
            "evidence_directory_exists": EVIDENCE_DIR.exists(),
        },
        "services": services,
        "video": {
            "config_api_status": config_status,
            "runtime_api_status": runtime_status,
            "configured_paths": sanitize_sensitive_payload(config_paths),
            "runtime_paths": sanitize_sensitive_payload(runtime_paths),
            "test_stream": "teste",
        },
        "cameras": {
            "total": len(cameras),
            "online": online,
            "offline": len(cameras) - online,
            "provisioned": provisioned,
        },
        "ports": {
            "panel": 5177,
            "api": 8002,
            "rtsp": 18554,
            "hls": 18888,
            "webrtc": 18889,
            "webrtc_udp": 18189,
            "mediamtx_api_local": 19997,
        },
    }


@app.get("/occurrences/{occurrence_id}/print", response_class=HTMLResponse)
def print_occurrence(
    occurrence_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    occurrence = ensure_occurrence_access(db, user, db.get(Occurrence, occurrence_id))

    events = (
        db.query(OccurrenceEvent)
        .filter(OccurrenceEvent.occurrence_id == occurrence_id)
        .order_by(OccurrenceEvent.created_at.asc())
        .all()
    )
    evidence = (
        db.query(Evidence)
        .filter(Evidence.occurrence_id == occurrence_id)
        .order_by(Evidence.created_at.asc())
        .all()
    )

    event_rows = "".join(
        f"<tr><td>{event.created_at}</td><td>{event.event_type}</td>"
        f"<td>{event.description}</td><td>{event.user_name}</td></tr>"
        for event in events
    )
    evidence_rows = "".join(
        f"<tr><td>{item.created_at}</td><td>{item.evidence_type}</td>"
        f"<td>{item.original_name or item.filename}</td><td>{item.created_by}</td></tr>"
        for item in evidence
    )

    html = f"""
    <!doctype html>
    <html lang="pt-BR">
    <head>
      <meta charset="utf-8">
      <title>{occurrence.protocol}</title>
      <style>
        body {{ font-family: Arial, sans-serif; color: #17324d; margin: 38px; }}
        header {{ border-bottom: 3px solid #087f90; margin-bottom: 20px; }}
        h1 {{ color: #0b356d; }}
        table {{ width: 100%; border-collapse: collapse; margin: 14px 0; }}
        th, td {{ border: 1px solid #cad6df; padding: 8px; font-size: 12px; }}
        th {{ background: #eaf2f5; text-align: left; }}
        .meta {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
        .sign {{ margin-top: 60px; border-top: 1px solid #333; width: 320px; }}
        @media print {{ button {{ display: none; }} }}
      </style>
    </head>
    <body>
      <button onclick="window.print()">Imprimir / Salvar como PDF</button>
      <header>
        <h1>EduVigIA — Relatório de Ocorrência</h1>
        <h2>{occurrence.protocol}</h2>
      </header>
      <div class="meta">
        <p><b>Escola:</b> {occurrence.school_name}</p>
        <p><b>Categoria:</b> {occurrence.category}</p>
        <p><b>Prioridade:</b> {occurrence.priority}</p>
        <p><b>Status:</b> {occurrence.status}</p>
        <p><b>Equipe:</b> {occurrence.assigned_team or "Não definida"}</p>
        <p><b>Abertura:</b> {occurrence.created_at}</p>
      </div>
      <h3>Descrição</h3>
      <p>{occurrence.description}</p>
      <h3>Linha do tempo</h3>
      <table>
        <thead><tr><th>Data</th><th>Evento</th><th>Descrição</th><th>Usuário</th></tr></thead>
        <tbody>{event_rows}</tbody>
      </table>
      <h3>Evidências</h3>
      <table>
        <thead><tr><th>Data</th><th>Tipo</th><th>Arquivo</th><th>Responsável</th></tr></thead>
        <tbody>{evidence_rows}</tbody>
      </table>
      <div class="sign">Responsável pelo encerramento</div>
    </body>
    </html>
    """
    return HTMLResponse(html)


@app.get("/reports/export/occurrences.csv")
def export_occurrences_csv(
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA")),
):
    rows = scope_occurrence_query(db.query(Occurrence), db, user).order_by(Occurrence.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "Protocolo",
            "Escola",
            "Categoria",
            "Prioridade",
            "Status",
            "Equipe",
            "Descrição",
            "Abertura",
            "Encerramento",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.protocol,
                row.school_name,
                row.category,
                row.priority,
                row.status,
                row.assigned_team or "",
                row.description,
                row.created_at.isoformat() if row.created_at else "",
                row.closed_at.isoformat() if row.closed_at else "",
            ]
        )

    content = "\ufeff" + output.getvalue()
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=eduvigia-ocorrencias.csv"
        },
    )


@app.get("/reports/export/equipment.csv")
def export_equipment_csv(
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    rows = school_scope_query(db.query(Equipment), Equipment, user).order_by(Equipment.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "ID",
            "Categoria",
            "Nome",
            "Escola ID",
            "Fabricante",
            "Modelo",
            "Série",
            "Patrimônio",
            "Localização",
            "Status",
            "Instalação",
            "Garantia",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.id,
                row.category,
                row.name,
                row.school_id or "",
                row.manufacturer or "",
                row.model or "",
                row.serial_number or "",
                row.asset_number or "",
                row.location or "",
                row.status,
                row.installed_at.isoformat() if row.installed_at else "",
                row.warranty_until.isoformat() if row.warranty_until else "",
            ]
        )

    content = "\ufeff" + output.getvalue()
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=eduvigia-equipamentos.csv"
        },
    )


@app.get("/equipment", response_model=list[EquipmentOut])
def list_equipment(
    school_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    query = school_scope_query(db.query(Equipment), Equipment, user)
    if school_id:
        ensure_school_access(user, school_id)
        query = query.filter(Equipment.school_id == school_id)
    if status:
        query = query.filter(Equipment.status == status.upper())
    if category:
        query = query.filter(Equipment.category == category.upper())
    return query.order_by(Equipment.created_at.desc()).all()


@app.post("/equipment", response_model=EquipmentOut)
def create_equipment(
    payload: EquipmentIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    if payload.school_id:
        ensure_school_access(actor, payload.school_id)
        if not db.get(School, payload.school_id):
            raise HTTPException(404, "Escola não encontrada")
    elif scoped_school_id(actor) is not None:
        raise HTTPException(400, "Informe a escola do equipamento")
    row = Equipment(**payload.model_dump())
    db.add(row)
    audit(db, "Equipamentos", "Cadastro", row.name, user=actor)
    db.commit()
    db.refresh(row)
    return row


@app.put("/equipment/{equipment_id}", response_model=EquipmentOut)
def update_equipment(
    equipment_id: int,
    payload: EquipmentIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    row = ensure_equipment_access(actor, db.get(Equipment, equipment_id))
    if payload.school_id:
        ensure_school_access(actor, payload.school_id)
        if not db.get(School, payload.school_id):
            raise HTTPException(404, "Escola não encontrada")
    elif scoped_school_id(actor) is not None:
        raise HTTPException(400, "Informe a escola do equipamento")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    audit(db, "Equipamentos", "Edição", f"{row.id} - {row.name}", user=actor)
    db.commit()
    db.refresh(row)
    return row


@app.delete("/equipment/{equipment_id}")
def delete_equipment(
    equipment_id: int,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA")),
):
    row = ensure_equipment_access(actor, db.get(Equipment, equipment_id))
    open_maintenance = (
        db.query(MaintenanceRecord)
        .filter(
            MaintenanceRecord.equipment_id == row.id,
            MaintenanceRecord.status.in_(["ABERTA", "AGENDADA", "EM_EXECUCAO"]),
        )
        .first()
    )
    if open_maintenance:
        raise HTTPException(409, "Existe manutenção aberta para este equipamento")
    name = row.name
    db.delete(row)
    audit(db, "Equipamentos", "Exclusão", name, user=actor)
    db.commit()
    return {"ok": True}


@app.get(
    "/equipment/{equipment_id}/maintenance",
    response_model=list[MaintenanceOut],
)
def maintenance_history(
    equipment_id: int,
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    ensure_equipment_access(user, db.get(Equipment, equipment_id))
    return (
        db.query(MaintenanceRecord)
        .filter(MaintenanceRecord.equipment_id == equipment_id)
        .order_by(MaintenanceRecord.created_at.desc())
        .all()
    )


@app.post(
    "/equipment/{equipment_id}/maintenance",
    response_model=MaintenanceOut,
)
def create_maintenance(
    equipment_id: int,
    payload: MaintenanceIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    equipment = ensure_equipment_access(actor, db.get(Equipment, equipment_id))
    row = MaintenanceRecord(equipment_id=equipment_id, **payload.model_dump())
    equipment.status = "MANUTENCAO"
    db.add(row)
    notify(
        db,
        title="Manutenção registrada",
        message=f"{equipment.name}: {payload.description}",
        severity="WARNING",
        module="Equipamentos",
        school_id=equipment.school_id,
        entity_type="equipment",
        entity_id=equipment.id,
    )
    audit(db, "Equipamentos", "Manutenção aberta", equipment.name, user=actor)
    db.commit()
    db.refresh(row)
    return row


@app.patch(
    "/maintenance/{maintenance_id}/status",
    response_model=MaintenanceOut,
)
def update_maintenance_status(
    maintenance_id: int,
    payload: MaintenanceStatusIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA", "TECNICO")),
):
    row = db.get(MaintenanceRecord, maintenance_id)
    if not row:
        raise HTTPException(404, "Manutenção não encontrada")
    equipment = ensure_equipment_access(actor, db.get(Equipment, row.equipment_id))
    row.status = payload.status
    if payload.status == "CONCLUIDA":
        row.completed_at = datetime.now(timezone.utc)
        equipment.status = "OPERACIONAL"
    audit(
        db,
        "Equipamentos",
        "Status da manutenção",
        f"Manutenção #{row.id}: {row.status}",
        user=actor,
    )
    db.commit()
    db.refresh(row)
    return row



def _priority_sla_minutes(priority: str) -> int:
    return {
        "CRITICA": 5,
        "ALTA": 15,
        "MEDIA": 30,
        "BAIXA": 60,
    }.get((priority or "MEDIA").upper(), 30)


def _elapsed_minutes(created_at: datetime) -> int:
    now = datetime.now(timezone.utc)
    value = created_at
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return max(0, int((now - value).total_seconds() // 60))


def _sla_status(created_at: datetime, priority: str, closed: bool = False) -> dict:
    target = _priority_sla_minutes(priority)
    elapsed = _elapsed_minutes(created_at)
    remaining = target - elapsed
    if closed:
        status = "ENCERRADO"
    elif remaining < 0:
        status = "ESTOURADO"
    elif remaining <= max(2, int(target * 0.25)):
        status = "ATENCAO"
    else:
        status = "NO_PRAZO"
    return {
        "target_minutes": target,
        "elapsed_minutes": elapsed,
        "remaining_minutes": remaining,
        "status": status,
    }


@app.get("/operations/overview")
def operations_overview(
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    alert_query = scope_alert_query(db.query(Alert), db, user)
    occurrence_query = scope_occurrence_query(db.query(Occurrence), db, user)

    active_alerts = (
        alert_query
        .filter(Alert.status.notin_(["DESCARTADO", "ENCERRADO"]))
        .order_by(Alert.created_at.desc())
        .limit(50)
        .all()
    )
    open_occurrences = (
        occurrence_query
        .filter(Occurrence.status != "ENCERRADA")
        .order_by(Occurrence.created_at.desc())
        .limit(50)
        .all()
    )
    teams = (
        db.query(DispatchTeam).filter(DispatchTeam.active.is_(True)).all()
        if canonical_role(user.role, user.school_id) in {"ADMIN_SECRETARIA", "SUPERVISOR_GUARDA", "DESPACHANTE_GUARDA"}
        else []
    )

    alert_items = [
        {
            "id": item.id,
            "school_name": item.school_name,
            "camera_name": item.camera_name,
            "event_type": item.event_type,
            "priority": item.priority,
            "status": item.status,
            "created_at": item.created_at,
            "sla": _sla_status(item.created_at, item.priority),
        }
        for item in active_alerts
    ]

    occurrence_items = [
        {
            "id": item.id,
            "protocol": item.protocol,
            "school_name": item.school_name,
            "category": item.category,
            "priority": item.priority,
            "status": item.status,
            "assigned_team": item.assigned_team,
            "created_at": item.created_at,
            "sla": _sla_status(item.created_at, item.priority),
        }
        for item in open_occurrences
    ]

    recent_events_query = db.query(OccurrenceEvent).join(
        Occurrence, Occurrence.id == OccurrenceEvent.occurrence_id
    )
    restricted_school_id = scoped_school_id(user)
    if restricted_school_id is not None:
        school = db.get(School, restricted_school_id)
        recent_events_query = recent_events_query.filter(
            (Occurrence.school_id == restricted_school_id)
            | ((Occurrence.school_id.is_(None)) & (Occurrence.school_name == school.name))
        )
    recent_events = recent_events_query.order_by(OccurrenceEvent.created_at.desc()).limit(20).all()

    return {
        "generated_at": datetime.now(timezone.utc),
        "summary": {
            "active_alerts": len(active_alerts),
            "critical_alerts": len([item for item in active_alerts if item.priority == "CRITICA"]),
            "open_occurrences": len(open_occurrences),
            "overdue_items": len([item for item in alert_items if item["sla"]["status"] == "ESTOURADO"])
            + len([item for item in occurrence_items if item["sla"]["status"] == "ESTOURADO"]),
            "available_teams": len([item for item in teams if item.status == "DISPONIVEL"]),
            "total_teams": len(teams),
        },
        "alerts": alert_items[:20],
        "occurrences": occurrence_items[:20],
        "teams": [
            {
                "id": team.id,
                "name": team.name,
                "team_type": team.team_type,
                "status": team.status,
                "phone": team.phone,
                "current_occurrence_id": team.current_occurrence_id,
            }
            for team in teams
        ],
        "recent_events": [
            {
                "id": event.id,
                "occurrence_id": event.occurrence_id,
                "event_type": event.event_type,
                "description": event.description,
                "user_name": event.user_name,
                "created_at": event.created_at,
            }
            for event in recent_events
        ],
    }


@app.get("/operations/feed")
def operations_feed(
    after: datetime | None = Query(default=None),
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    query = db.query(OccurrenceEvent).join(
        Occurrence, Occurrence.id == OccurrenceEvent.occurrence_id
    )
    restricted_school_id = scoped_school_id(user)
    if restricted_school_id is not None:
        school = db.get(School, restricted_school_id)
        if not school:
            raise HTTPException(403, "Escola vinculada não encontrada")
        query = query.filter(
            (Occurrence.school_id == restricted_school_id)
            | ((Occurrence.school_id.is_(None)) & (Occurrence.school_name == school.name))
        )
    if after:
        query = query.filter(OccurrenceEvent.created_at > after)
    events = query.order_by(OccurrenceEvent.created_at.desc()).limit(100).all()
    return {
        "generated_at": datetime.now(timezone.utc),
        "items": [
            {
                "id": item.id,
                "occurrence_id": item.occurrence_id,
                "event_type": item.event_type,
                "description": item.description,
                "user_name": item.user_name,
                "created_at": item.created_at,
            }
            for item in events
        ],
    }



def _tcp_check(host: str, port: int, timeout: float = 2.5) -> dict:
    started = datetime.now(timezone.utc)
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            return {"status": "ONLINE", "latency_ms": elapsed_ms, "host": host, "port": int(port)}
    except OSError as error:
        return {
            "status": "OFFLINE",
            "latency_ms": None,
            "host": host,
            "port": int(port),
            "error": str(error),
        }


def _directory_usage(path_value: str) -> dict:
    path = Path(path_value)
    path.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(path)
    percent = round((usage.used / usage.total) * 100, 1) if usage.total else 0
    return {
        "path": str(path),
        "total_gb": round(usage.total / (1024 ** 3), 2),
        "used_gb": round(usage.used / (1024 ** 3), 2),
        "free_gb": round(usage.free / (1024 ** 3), 2),
        "used_percent": percent,
        "status": "CRITICAL" if percent >= 90 else "WARNING" if percent >= 80 else "OK",
    }


@app.get("/infrastructure/capacity")
def infrastructure_capacity(
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "TECNICO")),
):
    restricted_school_id = scoped_school_id(user)
    school_query = db.query(School).filter(School.active.is_(True))
    if restricted_school_id is not None:
        school_query = school_query.filter(School.id == restricted_school_id)
    camera_query = school_scope_query(db.query(Camera), Camera, user)
    recorder_query = school_scope_query(db.query(Recorder), Recorder, user)
    active_sessions_query = db.query(AuthSession).filter(AuthSession.expires_at > datetime.now(timezone.utc))
    if restricted_school_id is not None:
        active_sessions_query = active_sessions_query.join(UserAccount).filter(UserAccount.school_id == restricted_school_id)
    storage = _directory_usage(os.getenv("EDUVIGIA_DATA_DIR", "/app/data"))
    pool = _pool_snapshot()
    camera_total = camera_query.count()
    recorder_total = recorder_query.count()
    schools_total = school_query.count()
    recommended_workers = max(1, min(8, (camera_total // 250) + 1))
    return {
        "version": APP_VERSION,
        "generated_at": datetime.now(timezone.utc),
        "database_pool": pool,
        "inventory": {
            "schools": schools_total,
            "cameras": camera_total,
            "recorders": recorder_total,
            "active_sessions": active_sessions_query.count(),
        },
        "storage": storage,
        "retention": {
            "backup_days": BACKUP_RETENTION_DAYS,
            "audit_days": AUDIT_RETENTION_DAYS,
        },
        "scaling": {
            "recommended_api_workers": recommended_workers,
            "camera_capacity_per_worker": 250,
            "state": "SCALE_OUT" if camera_total > recommended_workers * 250 else "ADEQUATE",
            "note": "Dimensionamento orientativo; validar CPU, memória, bitrate e concorrência em campo.",
        },
        "endpoints": {
            "liveness": "/live",
            "readiness": "/ready",
            "metrics": "/metrics",
            "prometheus": 19090,
            "proxy_http": 80 if os.getenv("APP_ENV", "development") == "production" else 8088,
            "proxy_https": 443 if os.getenv("APP_ENV", "development") == "production" else 18443,
        },
    }


@app.get("/infrastructure/overview")
def infrastructure_overview(
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "TECNICO")),
):
    checked_at = datetime.now(timezone.utc)

    database_status = {"status": "ONLINE"}
    try:
        db.execute(text("SELECT 1"))
    except Exception as error:
        database_status = {"status": "OFFLINE", "error": str(error)}

    redis_status = _tcp_check("redis", 6379)
    mediamtx_api_status = _tcp_check("mediamtx", 9997)
    mediamtx_rtsp_status = _tcp_check("mediamtx", 8554)

    data_dir = os.getenv("EDUVIGIA_DATA_DIR", "/app/data")
    storage = _directory_usage(data_dir)

    camera_query = school_scope_query(db.query(Camera), Camera, user)
    recorder_query = school_scope_query(db.query(Recorder), Recorder, user)
    camera_total = camera_query.count()
    camera_online = camera_query.filter(Camera.status == "ONLINE").count()
    camera_offline = camera_query.filter(Camera.status == "OFFLINE").count()
    recorder_total = recorder_query.count()
    recorder_online = recorder_query.filter(Recorder.status == "ONLINE").count()

    services = {
        "api": {"status": "ONLINE"},
        "database": database_status,
        "redis": redis_status,
        "mediamtx_api": mediamtx_api_status,
        "mediamtx_rtsp": mediamtx_rtsp_status,
    }
    overall = "ONLINE"
    if any(item.get("status") == "OFFLINE" for item in services.values()):
        overall = "DEGRADED"
    if database_status["status"] == "OFFLINE":
        overall = "CRITICAL"

    return {
        "version": APP_VERSION,
        "environment": os.getenv("APP_ENV", "development"),
        "checked_at": checked_at,
        "overall": overall,
        "services": services,
        "storage": storage,
        "video": {
            "cameras_total": camera_total,
            "cameras_online": camera_online,
            "cameras_offline": camera_offline,
            "recorders_total": recorder_total,
            "recorders_online": recorder_online,
        },
        "backup": {
            "recommended_frequency": "DAILY",
            "retention_days": BACKUP_RETENTION_DAYS,
            "database": "PostgreSQL custom format",
            "evidence_path": data_dir,
            "isolated_restore_test": "REQUIRED",
        },
        "database_pool": _pool_snapshot(),
        "readiness": collect_readiness(db),
        "observability": {
            "metrics_endpoint": "/metrics",
            "prometheus_port": 19090,
            "structured_logs": True,
            "request_id_header": "X-Request-ID",
        },
        "reverse_proxy": {
            "http_port": 80 if os.getenv("APP_ENV", "development") == "production" else 8088,
            "https_port": 443 if os.getenv("APP_ENV", "development") == "production" else 18443,
            "tls": "CONFIGURED",
        },
        "ports": {
            "frontend": 5177,
            "backend": 8002,
            "postgres": 5437,
            "redis": 6382,
            "rtsp": 18554,
            "hls": 18888,
            "webrtc": 18889,
            "mediamtx_api": 19997,
            "mediamtx_metrics": 19998,
            "proxy_http": 80 if os.getenv("APP_ENV", "development") == "production" else 8088,
            "proxy_https": 443 if os.getenv("APP_ENV", "development") == "production" else 18443,
            "prometheus": 19090,
        },
    }





def _json_loads_object(value: str | None) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}




@app.get("/reports/summary")
def report_summary(
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    restricted_school_id = scoped_school_id(user)
    school_query = db.query(School).filter(School.active.is_(True))
    if restricted_school_id is not None:
        school_query = school_query.filter(School.id == restricted_school_id)
    camera_query = school_scope_query(db.query(Camera), Camera, user)
    equipment_query = school_scope_query(db.query(Equipment), Equipment, user)
    occurrence_query = scope_occurrence_query(db.query(Occurrence), db, user)
    alert_query = scope_alert_query(db.query(Alert), db, user)
    maintenance_query = db.query(MaintenanceRecord).join(
        Equipment, Equipment.id == MaintenanceRecord.equipment_id
    )
    if restricted_school_id is not None:
        maintenance_query = maintenance_query.filter(Equipment.school_id == restricted_school_id)

    return {
        "schools": school_query.count(),
        "cameras": camera_query.count(),
        "equipment": equipment_query.count(),
        "occurrences_total": occurrence_query.count(),
        "occurrences_open": occurrence_query.filter(Occurrence.status != "ENCERRADA").count(),
        "alerts_active": alert_query.filter(Alert.status.in_(["NOVO", "EM_ATENDIMENTO", "CONFIRMADO"])).count(),
        "maintenance_open": maintenance_query.filter(
            MaintenanceRecord.status.in_(["ABERTA", "AGENDADA", "EM_EXECUCAO"])
        ).count(),
        "camera_online": camera_query.filter(Camera.status == "ONLINE").count(),
        "camera_offline": camera_query.filter(Camera.status == "OFFLINE").count(),
    }


@app.get("/reports/occurrences-by-status")
def occurrences_by_status(
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_user),
):
    statuses = ["ABERTA", "EM_ANALISE", "DESPACHADA", "EM_ATENDIMENTO", "ENCERRADA"]
    query = scope_occurrence_query(db.query(Occurrence), db, user)
    return [
        {
            "status": status,
            "total": query.filter(Occurrence.status == status).count(),
        }
        for status in statuses
    ]


@app.get("/settings", response_model=list[SettingOut])
def list_settings(
    db: Session = Depends(db_session),
    _: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA")),
):
    return db.query(SystemSetting).order_by(SystemSetting.key.asc()).all()


@app.put("/settings/{key}", response_model=SettingOut)
def update_setting(
    key: str,
    payload: SettingIn,
    db: Session = Depends(db_session),
    actor: UserAccount = Depends(require_roles("ADMIN_SECRETARIA")),
):
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not row:
        row = SystemSetting(key=key, value=payload.value, description=payload.description)
        db.add(row)
    else:
        row.value = payload.value
        if payload.description is not None:
            row.description = payload.description
    audit(db, "Configurações", "Parâmetro alterado", key, user=actor)
    db.commit()
    db.refresh(row)
    return row


@app.get("/audit", response_model=list[AuditOut])
def audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(db_session),
    user: UserAccount = Depends(require_roles("ADMIN_SECRETARIA", "GESTOR_SECRETARIA")),
):
    query = db.query(AuditLog)
    restricted_school_id = scoped_school_id(user)
    if restricted_school_id is not None:
        query = query.filter(AuditLog.school_id == restricted_school_id)
    return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
