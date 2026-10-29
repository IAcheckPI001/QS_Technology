"""CLI quản trị service key cho hệ thống tích hợp (CRM backend).

Chạy từ thư mục backend:

    python -m app.modules.chatbot.service_keys_cli create --integration-id crm_sales --name "CRM Sales"
    python -m app.modules.chatbot.service_keys_cli revoke --key-id <key_id>

`create` tạo integration nếu chưa có rồi cấp key mới; key đầy đủ chỉ in một lần,
DB chỉ lưu hash. Xoay vòng key = `create` cùng integration-id rồi `revoke` key cũ.
"""

import argparse
import asyncio
import selectors
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, update

from app.core.security.service_key import generate_service_key
from app.db.engine import AsyncSessionFactory
from app.db.models.service_key import ServiceIntegration, ServiceKey

DEFAULT_TENANT_ID = "qs_technology"


async def create_key(integration_id: str, name: str, expires_in_days: int | None) -> None:
    generated = generate_service_key()
    expires_at = (
        datetime.now(UTC) + timedelta(days=expires_in_days) if expires_in_days else None
    )
    async with AsyncSessionFactory() as db, db.begin():
        if await db.get(ServiceIntegration, integration_id) is None:
            db.add(ServiceIntegration(id=integration_id, tenant_id=DEFAULT_TENANT_ID, name=name))
            await db.flush()
        db.add(
            ServiceKey(
                id=generated.key_id,
                integration_id=integration_id,
                secret_hash=generated.secret_hash,
                expires_at=expires_at,
            )
        )
    print(f"integration_id={integration_id}")
    print(f"key_id={generated.key_id}")
    print(f"expires_at={expires_at.isoformat() if expires_at else 'never'}")
    print("CHATBOT_API_KEY (chỉ hiển thị một lần, lưu vào .env của CRM backend):")
    print(generated.token)


async def revoke_key(key_id: str) -> None:
    async with AsyncSessionFactory() as db, db.begin():
        result = await db.execute(
            update(ServiceKey)
            .where(ServiceKey.id == key_id, ServiceKey.revoked_at.is_(None))
            .values(revoked_at=func.now())
        )
    print(f"revoked={result.rowcount} key_id={key_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Quản trị service key của Chatbot AI")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="Tạo integration (nếu chưa có) và cấp key mới")
    create.add_argument("--integration-id", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--expires-in-days", type=int, default=None)

    revoke = commands.add_parser("revoke", help="Thu hồi một key")
    revoke.add_argument("--key-id", required=True)

    args = parser.parse_args()
    if args.command == "create":
        job = create_key(args.integration_id, args.name, args.expires_in_days)
    else:
        job = revoke_key(args.key_id)
    # Windows: driver async cần SelectorEventLoop (cùng cách chunking_loader).
    asyncio.run(job, loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))


if __name__ == "__main__":
    main()
