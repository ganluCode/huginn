"""一键初始化数据库脚本

按顺序执行：
1. 检查 PostgreSQL 连接
2. 检查 Redis 连接（非阻塞）
3. 运行 Alembic 迁移
"""

import subprocess
import sys

from huginn.core.config import settings


def check_postgresql() -> bool:
    """检查 PostgreSQL 连接"""
    try:
        import psycopg2
        conn = psycopg2.connect(settings.database_url_sync)
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        _ = cursor.fetchone()[0]  # 仅验证连接，不使用结果
        cursor.close()
        conn.close()

        # 解析连接信息
        import urllib.parse
        parsed = urllib.parse.urlparse(settings.database_url_sync)
        user = parsed.username or "huginn"
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        dbname = parsed.path.lstrip("/") if parsed.path else "huginn"

        print(f"✓ PostgreSQL connected ({user}@{host}:{port}/{dbname})")
        return True
    except Exception as e:
        print(f"✗ PostgreSQL connection failed: {e}")
        return False


def check_redis() -> bool:
    """检查 Redis 连接（非阻塞）"""
    try:
        import redis
        client = redis.from_url(settings.redis_url)
        client.ping()
        print(f"✓ Redis connected ({settings.redis_url})")
        return True
    except Exception as e:
        print(f"⚠ Redis connection failed: {e} (non-blocking)")
        return False


def run_migrations() -> bool:
    """运行 Alembic 迁移"""
    try:
        # 运行 alembic upgrade head
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            print(f"✗ Migration failed: {result.stderr}")
            return False

        # 获取表列表
        from huginn.core.models import Base
        tables = sorted(Base.metadata.tables.keys())
        print("✓ Database migrated")
        print(f"  Tables: {', '.join(tables)}")
        return True
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        return False


def main():
    """主函数"""
    print("Huginn Database Initialization")
    print("=" * 40)

    # 检查 PostgreSQL
    if not check_postgresql():
        sys.exit(1)

    # 检查 Redis（非阻塞）
    check_redis()

    # 运行迁移
    if not run_migrations():
        sys.exit(1)

    print("\n✓ Initialization complete")
    sys.exit(0)


if __name__ == "__main__":
    main()
