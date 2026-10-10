import pytest
from pathlib import Path
from alembic.config import Config
from alembic import command
from vero.auth import (
    User,
    AuthManager,
    hash_password,
    verify_password,
    generate_api_key,
    hash_api_key,
    create_access_token,
    decode_access_token
)

def test_auth_crypto_primitives():
    # 1. Password hashing
    pwd = "EnterprisePassword!99"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False

    # 2. API Key generation & hashing
    key = generate_api_key()
    assert key.startswith("vero_")
    key_hash = hash_api_key(key)
    assert len(key_hash) == 64
    assert hash_api_key(key) == key_hash

    # 3. JWT Token lifecycle
    user = User(
        id="usr_12345",
        email="alice@company.com",
        name="Alice Analyst",
        role="analyst",
        allowed_domains=["finance"]
    )
    token = create_access_token(user, expires_in_seconds=3600)
    assert token.count(".") == 2

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "usr_12345"
    assert decoded["email"] == "alice@company.com"
    assert decoded["role"] == "analyst"
    assert decoded["domains"] == ["finance"]

    # Tampered token fails
    tampered = token[:-4] + "xxxx"
    assert decode_access_token(tampered) is None

def test_database_auth_manager_and_rbac(tmp_path):
    test_db = tmp_path / "test_auth.db"
    db_url = f"sqlite:///{test_db}"

    # Run Alembic migrations to create tables up to 003
    ini_path = Path(__file__).parent.parent / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    mgr = AuthManager(connection_string=db_url)

    # 1. Seed initial admin
    admin, admin_key = mgr.seed_default_admin()
    assert admin.role == "admin"
    assert admin.email == "admin@verodata.dev"
    assert admin_key is not None

    # Authenticate via admin API key
    authed_admin = mgr.authenticate(admin_key)
    assert authed_admin is not None
    assert authed_admin.id == admin.id

    # Authenticate via admin password
    authed_pwd = mgr.authenticate("admin@verodata.dev", "admin")
    assert authed_pwd is not None
    assert authed_pwd.id == admin.id

    # 2. Create domain-scoped analyst
    finance_user, fin_key = mgr.create_user(
        email="bob@company.com",
        name="Bob Finance",
        password="finance_secure",
        role="analyst",
        allowed_domains=["finance"]
    )

    # Domain authorization verification
    assert mgr.can_access_domain(finance_user, "finance") is True
    assert mgr.can_access_domain(finance_user, "global") is True
    assert mgr.can_access_domain(finance_user, "marketing") is False  # Restricted!

    # Admin can access all domains
    assert mgr.can_access_domain(admin, "marketing") is True
    assert mgr.can_access_domain(admin, "finance") is True

    # Role-based capability verification
    assert mgr.can_execute_query(finance_user) is True
    assert mgr.can_manage_context(finance_user) is False
    assert mgr.can_manage_context(admin) is True

    # 3. Create viewer (read-only dashboards/chat, no ad-hoc SQL execution)
    viewer_user, _ = mgr.create_user(
        email="viewer@company.com",
        name="Carol Viewer",
        role="viewer",
        allowed_domains=["marketing"]
    )
    assert mgr.can_execute_query(viewer_user) is False
    assert mgr.can_access_domain(viewer_user, "marketing") is True
    assert mgr.can_access_domain(viewer_user, "finance") is False
