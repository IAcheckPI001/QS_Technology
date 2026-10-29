"""CLI quản trị service key cho hệ thống tích hợp (website backend, CRM backend).

Chạy từ thư mục backend:

    python -m app.modules.chatbot.service_keys_cli create --integration-id website_main --channel website
    python -m app.modules.chatbot.service_keys_cli create --integration-id crm_sales --channel crm --name "CRM Sales"
    python -m app.modules.chatbot.service_keys_cli revoke --key-id <key_id>

`create` tạo integration nếu chưa có (bắt buộc --channel, --name mặc định bằng
integration-id) rồi cấp key mới; key đầy đủ chỉ in một lần, DB chỉ lưu hash.
Xoay vòng key = `create --integration-id <id>` (không cần kênh/tên) rồi `revoke`
key cũ.
"""

import argparse
import asyncio
import selectors
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, update

from app.core.security.service_key import generate_service_key
from app.db.engine import AsyncSessionFactory
from app.db.models.service_key import ServiceIntegration, ServiceKey
from app.modules.chatbot.schemas.default import ChannelType

DEFAULT_TENANT_ID = "qs_technology"


class CliError(Exception):
    """Tham số không hợp lệ: in thông báo và thoát, không cấp key."""


async def create_key(
    integration_id: str,
    channel: str | None,
    name: str | None,
    expires_in_days: int | None,
) -> None:
    generated = generate_service_key()
    expires_at = (
        datetime.now(UTC) + timedelta(days=expires_in_days) if expires_in_days else None
    )
    async with AsyncSessionFactory() as db, db.begin():
        integration = await db.get(ServiceIntegration, integration_id)
        if integration is None:
            if channel is None:
                raise CliError("integration mới: phải chọn --channel {crm,website}")
            integration = ServiceIntegration(
                id=integration_id,
                tenant_id=DEFAULT_TENANT_ID,
                channel=channel,
                name=name or integration_id,
            )
            db.add(integration)
            await db.flush()
        elif channel is not None and channel != integration.channel:
            raise CliError(
                f"integration {integration_id} thuộc kênh {integration.channel}, "
                f"không cấp key cho kênh {channel}"
            )
        db.add(
            ServiceKey(
                id=generated.key_id,
                integration_id=integration_id,
                secret_hash=generated.secret_hash,
                expires_at=expires_at,
            )
        )
    print(f"integration_id={integration_id}")
    print(f"channel={integration.channel}")
    print(f"key_id={generated.key_id}")
    print(f"expires_at={expires_at.isoformat() if expires_at else 'never'}")
    print("CHATBOT_API_KEY (chỉ hiển thị một lần, lưu vào .env của hệ thống tích hợp):")
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
    # Console Windows mặc định cp1252 không in được tiếng Việt; lỗi in sau khi đã
    # commit sẽ làm mất key vừa cấp.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Quản trị service key của Chatbot AI")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="Tạo integration (nếu chưa có) và cấp key mới")
    create.add_argument("--integration-id", required=True)
    create.add_argument(
        "--channel",
        choices=[channel.value for channel in ChannelType],
        help="Bắt buộc khi tạo integration mới; bỏ qua khi xoay vòng key",
    )
    create.add_argument("--name", help="Tên hiển thị; mặc định bằng integration-id")
    create.add_argument("--expires-in-days", type=int, default=None)

    revoke = commands.add_parser("revoke", help="Thu hồi một key")
    revoke.add_argument("--key-id", required=True)

    args = parser.parse_args()
    if args.command == "create":
        job = create_key(args.integration_id, args.channel, args.name, args.expires_in_days)
    else:
        job = revoke_key(args.key_id)
    try:
        # Windows: driver async cần SelectorEventLoop (cùng cách chunking_loader).
        asyncio.run(job, loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    except CliError as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
