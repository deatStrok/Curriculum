from __future__ import annotations

import argparse
from datetime import datetime

import pytz
from apscheduler.schedulers.blocking import BlockingScheduler

from database import get_admin_client
from settings import APP_TIMEZONE
from send_engine import send_batch_for_user


def scheduled_run() -> None:
    supabase = get_admin_client()
    settings_rows = supabase.table("user_settings").select("user_id,schedule_enabled,schedule_hour,timezone").eq("schedule_enabled", True).execute().data or []
    utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)

    for row in settings_rows:
        timezone_name = row.get("timezone") or APP_TIMEZONE
        try:
            local_now = utc_now.astimezone(pytz.timezone(timezone_name))
        except Exception:
            local_now = utc_now.astimezone(pytz.timezone(APP_TIMEZONE))

        if int(row.get("schedule_hour") or 9) == local_now.hour:
            try:
                result = send_batch_for_user(row["user_id"])
                print(f"{row['user_id']} -> {result}")
            except Exception as exc:
                print(f"Erro no usuário {row['user_id']}: {exc}")


def run_scheduler() -> None:
    scheduler = BlockingScheduler(timezone=APP_TIMEZONE)
    scheduler.add_job(
        scheduled_run,
        trigger="cron",
        minute=0,
        id="multi_user_daily_sender",
        replace_existing=True,
    )
    scheduler.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Executa todos os usuários agendados uma vez")
    args = parser.parse_args()

    if args.once:
        scheduled_run()
    else:
        run_scheduler()
