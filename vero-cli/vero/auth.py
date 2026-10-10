import os
import hmac
import hashlib
import base64
import json
import time
import secrets
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from datetime import datetime, timezone
from vero.config import VeroConfig

JWT_SECRET = os.environ.get("VERO_JWT_SECRET", "vero-enterprise-secret-key-32-chars-long-secure")

class User(BaseModel):
    id: str
    email: str
    name: str
    role: str = "analyst" # "admin", "analyst", "viewer"
    allowed_domains: List[str] = Field(default_factory=lambda: ["*"])
    is_active: bool = True

def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def _base64url_decode(data: str) -> bytes:
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data.encode("utf-8"))

def hash_password(password: str) -> str:
    """Hashes a password using PBKDF2-HMAC-SHA256 with a random salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}${key.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """Verifies a password against PBKDF2-HMAC-SHA256 hash."""
    if "$" not in hashed:
        return False
    salt, expected_hex = hashed.split("$", 1)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return hmac.compare_digest(key.hex(), expected_hex)

def hash_api_key(key: str) -> str:
    """Deterministic SHA256 hash of API key for database lookup."""
    return hashlib.sha256(key.strip().encode("utf-8")).hexdigest()

def generate_api_key(prefix: str = "vero_") -> str:
    """Generates an unguessable 40-character API key."""
    return f"{prefix}{secrets.token_urlsafe(32)}"

def create_access_token(user: User, expires_in_seconds: int = 86400 * 7, secret: str = JWT_SECRET) -> str:
    """Generates a standard HS256 JWT access token."""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "sub": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "domains": user.allowed_domains,
        "iat": now,
        "exp": now + expires_in_seconds
    }

    header_bytes = _base64url_encode(json.dumps(header, separators=(',', ':')).encode("utf-8"))
    payload_bytes = _base64url_encode(json.dumps(payload, separators=(',', ':')).encode("utf-8"))
    signing_input = f"{header_bytes}.{payload_bytes}"

    sig = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    sig_bytes = _base64url_encode(sig)

    return f"{signing_input}.{sig_bytes}"

def decode_access_token(token: str, secret: str = JWT_SECRET) -> Optional[Dict[str, Any]]:
    """Decodes and validates a standard HS256 JWT access token."""
    parts = token.strip().split(".")
    if len(parts) != 3:
        return None

    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}"

    expected_sig = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    actual_sig = _base64url_decode(sig_b64)

    if not hmac.compare_digest(expected_sig, actual_sig):
        return None

    try:
        payload_data = json.loads(_base64url_decode(payload_b64).decode("utf-8"))
        if "exp" in payload_data and payload_data["exp"] < int(time.time()):
            return None # Token expired
        return payload_data
    except Exception:
        return None

class AuthManager:
    """
    Centralized database-backed authentication and domain-level authorization manager.
    Zero local path dependencies — all users, roles, and audit trails reside in the metadata DB.
    """

    def __init__(self, connection_string: Optional[str] = None):
        cfg = VeroConfig.load()
        self.connection_string = connection_string or cfg.storage.connection_string or "sqlite:///.vero/metadata.db"
        
        engine_kwargs = {}
        if ":memory:" in self.connection_string:
            from sqlalchemy.pool import StaticPool
            engine_kwargs["connect_args"] = {"check_same_thread": False}
            engine_kwargs["poolclass"] = StaticPool

        self.engine = create_engine(self.connection_string, **engine_kwargs)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Ensures _vero_users and _vero_audit_logs exist in the database."""
        from sqlalchemy import inspect
        try:
            insp = inspect(self.engine)
            existing = insp.get_table_names()
            with self.engine.begin() as conn:
                if "_vero_users" not in existing:
                    conn.execute(text("""
                    CREATE TABLE _vero_users (
                        id VARCHAR(64) PRIMARY KEY,
                        email VARCHAR(256) NOT NULL UNIQUE,
                        name VARCHAR(128) NOT NULL,
                        password_hash VARCHAR(256),
                        api_key_hash VARCHAR(128),
                        role VARCHAR(32) NOT NULL DEFAULT 'analyst',
                        allowed_domains TEXT NOT NULL DEFAULT '["*"]',
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        created_at DATETIME,
                        last_login_at DATETIME
                    )
                    """))
                if "_vero_audit_logs" not in existing:
                    conn.execute(text("""
                    CREATE TABLE _vero_audit_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id VARCHAR(64),
                        user_email VARCHAR(256),
                        action VARCHAR(64) NOT NULL,
                        domain VARCHAR(64),
                        details_json TEXT,
                        created_at DATETIME
                    )
                    """))
        except Exception:
            pass

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, email, name, role, allowed_domains, is_active FROM _vero_users WHERE id = :id"),
                {"id": user_id}
            ).fetchone()
            if not row:
                return None
            domains = json.loads(row[4]) if row[4] else ["*"]
            return User(id=row[0], email=row[1], name=row[2], role=row[3], allowed_domains=domains, is_active=bool(row[5]))

    def get_user_by_email(self, email: str) -> Optional[Tuple[User, str]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, email, name, role, allowed_domains, is_active, password_hash FROM _vero_users WHERE email = :email"),
                {"email": email.strip().lower()}
            ).fetchone()
            if not row:
                return None
            domains = json.loads(row[4]) if row[4] else ["*"]
            user = User(id=row[0], email=row[1], name=row[2], role=row[3], allowed_domains=domains, is_active=bool(row[5]))
            return user, row[6] or ""

    def get_user_by_api_key(self, raw_key: str) -> Optional[User]:
        key_hash = hash_api_key(raw_key)
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, email, name, role, allowed_domains, is_active FROM _vero_users WHERE api_key_hash = :kh AND is_active = 1"),
                {"kh": key_hash}
            ).fetchone()
            if not row:
                return None
            domains = json.loads(row[4]) if row[4] else ["*"]
            return User(id=row[0], email=row[1], name=row[2], role=row[3], allowed_domains=domains, is_active=bool(row[5]))

    def authenticate(self, email_or_token: str, password: Optional[str] = None) -> Optional[User]:
        """Authenticates via API key, JWT token, or email/password."""
        # 1. Try as API Key
        if email_or_token.startswith("vero_"):
            return self.get_user_by_api_key(email_or_token)

        # 2. Try as JWT token
        if "." in email_or_token and not password:
            decoded = decode_access_token(email_or_token)
            if decoded and "sub" in decoded:
                return self.get_user_by_id(decoded["sub"])

        # 3. Try as Email / Password
        if password:
            res = self.get_user_by_email(email_or_token)
            if res:
                user, pwd_hash = res
                if user.is_active and verify_password(password, pwd_hash):
                    with self.engine.begin() as conn:
                        conn.execute(
                            text("UPDATE _vero_users SET last_login_at = :now WHERE id = :id"),
                            {"now": datetime.now(timezone.utc), "id": user.id}
                        )
                    return user

        return None

    def create_user(
        self,
        email: str,
        name: str,
        password: Optional[str] = None,
        role: str = "analyst",
        allowed_domains: Optional[List[str]] = None
    ) -> Tuple[User, str]:
        """Creates or updates a user and returns (user, raw_api_key)."""
        clean_email = email.strip().lower()
        raw_api_key = generate_api_key()
        api_hash = hash_api_key(raw_api_key)
        pwd_hash = hash_password(password) if password else None
        domains = allowed_domains or ["*"]

        existing = self.get_user_by_email(clean_email)
        if existing:
            user, _ = existing
            with self.engine.begin() as conn:
                conn.execute(
                    text("""
                    UPDATE _vero_users 
                    SET name = :n, password_hash = COALESCE(:p, password_hash), api_key_hash = :k, role = :r, allowed_domains = :d, is_active = 1
                    WHERE id = :i
                    """),
                    {
                        "i": user.id,
                        "n": name,
                        "p": pwd_hash,
                        "k": api_hash,
                        "r": role,
                        "d": json.dumps(domains)
                    }
                )
            return User(id=user.id, email=clean_email, name=name, role=role, allowed_domains=domains, is_active=True), raw_api_key

        user_id = f"usr_{secrets.token_hex(8)}"
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO _vero_users (id, email, name, password_hash, api_key_hash, role, allowed_domains, is_active, created_at)
                VALUES (:i, :e, :n, :p, :k, :r, :d, 1, :c)
                """),
                {
                    "i": user_id,
                    "e": clean_email,
                    "n": name,
                    "p": pwd_hash,
                    "k": api_hash,
                    "r": role,
                    "d": json.dumps(domains),
                    "c": datetime.now(timezone.utc)
                }
            )

        user = User(id=user_id, email=clean_email, name=name, role=role, allowed_domains=domains, is_active=True)
        return user, raw_api_key

    def get_all_users(self) -> List[User]:
        """Returns all registered users ordered by role and creation date."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT id, email, name, role, allowed_domains, is_active FROM _vero_users ORDER BY role = 'admin' DESC, created_at ASC")
            ).fetchall()
            return [
                User(
                    id=r[0],
                    email=r[1],
                    name=r[2],
                    role=r[3],
                    allowed_domains=json.loads(r[4]) if r[4] else ["*"],
                    is_active=bool(r[5])
                )
                for r in rows
            ]

    def delete_user(self, user_id: str) -> bool:
        """Deletes a user from the database."""
        with self.engine.begin() as conn:
            res = conn.execute(
                text("DELETE FROM _vero_users WHERE id = :id"),
                {"id": user_id}
            )
            return res.rowcount > 0

    def get_local_developer_user(self) -> User:
        """Zero-friction OSS local developer user with full administrative access."""
        return User(
            id="usr_local_dev",
            email="developer@verodata.dev",
            name="Local Engineer",
            role="admin",
            allowed_domains=["*"],
            is_active=True
        )

    def map_idp_groups_to_user(self, email: str, name: str, groups: List[str]) -> Tuple[User, str]:
        """
        Maps corporate IdP groups (Okta, OneLogin, Azure AD) to Vero role and domains.
        Elevates role and merges allowed domains based on configured group mappings.
        """
        cfg = VeroConfig.load()
        mapping = cfg.auth.oidc.group_mapping if cfg.auth and cfg.auth.oidc else {}

        resolved_role = "viewer"
        role_priority = {"admin": 3, "analyst": 2, "viewer": 1}
        allowed_domains = set()

        for g in groups:
            if g in mapping:
                m = mapping[g]
                r = m.get("role", "viewer")
                if role_priority.get(r, 1) > role_priority.get(resolved_role, 1):
                    resolved_role = r
                for d in m.get("domains", []):
                    allowed_domains.add(d)

        if not allowed_domains:
            allowed_domains = {"global"}

        domains_list = ["*"] if "*" in allowed_domains else list(allowed_domains)
        return self.create_user(
            email=email,
            name=name,
            role=resolved_role,
            allowed_domains=domains_list
        )

    def can_access_domain(self, user: User, domain: str) -> bool:
        """Enforces domain-level authorization partitioning."""
        if not domain or domain == "global":
            return True
        if user.role == "admin":
            return True
        if "*" in user.allowed_domains:
            return True
        return domain in user.allowed_domains

    def can_execute_query(self, user: User) -> bool:
        """Enforces role-based query execution permission."""
        return user.role in ["admin", "analyst"]

    def can_manage_context(self, user: User) -> bool:
        """Enforces role-based rules and metrics management permission."""
        return user.role == "admin"

    def log_audit(
        self,
        user_id: Optional[str],
        email: Optional[str],
        action: str,
        domain: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Appends an immutable record to _vero_audit_logs."""
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text("""
                    INSERT INTO _vero_audit_logs (user_id, user_email, action, domain, details_json, created_at)
                    VALUES (:u, :e, :a, :d, :det, :c)
                    """),
                    {
                        "u": user_id or "anonymous",
                        "e": email or "anonymous",
                        "a": action,
                        "d": domain or "global",
                        "det": json.dumps(details or {}),
                        "c": datetime.now(timezone.utc)
                    }
                )
        except Exception:
            pass

    def seed_default_admin(self) -> Tuple[User, Optional[str]]:
        """Ensures an initial admin user exists so the system is immediately usable."""
        with self.engine.connect() as conn:
            admin_row = conn.execute(
                text("SELECT id, email, name, role, allowed_domains, is_active FROM _vero_users WHERE email = 'admin@verodata.dev' LIMIT 1")
            ).fetchone()
            if admin_row:
                return User(
                    id=admin_row[0],
                    email=admin_row[1],
                    name=admin_row[2],
                    role=admin_row[3],
                    allowed_domains=json.loads(admin_row[4]) if admin_row[4] else ["*"],
                    is_active=bool(admin_row[5])
                ), None

        # Create default admin
        return self.create_user(
            email="admin@verodata.dev",
            name="Vero Administrator",
            password="admin",
            role="admin",
            allowed_domains=["*"]
        )
