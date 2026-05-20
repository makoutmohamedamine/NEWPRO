import logging
import os

from django.apps import AppConfig

logger = logging.getLogger(__name__)

# Interval de synchronisation automatique (en minutes, configurable via .env)
_DEFAULT_SYNC_INTERVAL_MINUTES = 30


def _get_sync_interval() -> int:
    try:
        val = int(os.environ.get("AUTO_SYNC_INTERVAL_MINUTES", _DEFAULT_SYNC_INTERVAL_MINUTES))
        return max(5, val)  # minimum 5 minutes
    except (ValueError, TypeError):
        return _DEFAULT_SYNC_INTERVAL_MINUTES


def _run_auto_sync():
    """Tache planifiee: synchronisation automatique Gmail + Outlook."""
    try:
        from django.db import connection as db_conn
        # Verifier que la DB est accessible avant de lancer la sync
        db_conn.ensure_connection()
    except Exception as exc:
        logger.debug("Auto-sync skipped (DB not ready): %s", exc)
        return

    # ── Sync Gmail ────────────────────────────────────────────────────────────
    gmail_enabled = os.environ.get("GMAIL_CLIENT_SECRET_FILE", "").strip()
    gmail_token = os.environ.get("GMAIL_TOKEN_FILE", "").strip()
    if gmail_enabled and gmail_token and os.path.exists(gmail_token):
        try:
            from .gmail_pipeline import get_gmail_pipeline
            from .views import _persist_sync_history

            pipeline = get_gmail_pipeline()
            report = pipeline.run()
            _persist_sync_history(report, "auto")
            logger.info(
                "Auto-sync Gmail OK — %d emails scannes, %d CVs crees",
                report.emails_scanned,
                report.cvs_created,
            )
        except Exception as exc:
            logger.warning("Auto-sync Gmail erreur: %s", exc)
    else:
        logger.debug("Auto-sync Gmail: token absent, sync ignoree")

    # ── Sync Outlook ──────────────────────────────────────────────────────────
    outlook_tenant = os.environ.get("AZURE_TENANT_ID", "").strip()
    outlook_client = os.environ.get("AZURE_CLIENT_ID", "").strip()
    outlook_secret = os.environ.get("AZURE_CLIENT_SECRET", "").strip()
    is_placeholder = outlook_client in {"votre-client-id-ici", ""} or outlook_secret in {"votre-client-secret-ici", ""}
    if outlook_tenant and not is_placeholder:
        try:
            from .pipeline import get_pipeline
            from .views import _persist_sync_history

            pipeline = get_pipeline()
            report = pipeline.run()
            _persist_sync_history(report, "auto")
            logger.info(
                "Auto-sync Outlook OK — %d emails scannes, %d CVs crees",
                report.emails_scanned,
                report.cvs_created,
            )
        except Exception as exc:
            logger.warning("Auto-sync Outlook erreur: %s", exc)
    else:
        logger.debug("Auto-sync Outlook: credentials absents ou placeholders, sync ignoree")


class RecruitmentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'recruitment'

    def ready(self):
        # Ne pas demarrer le scheduler dans les commandes de management (migrations, etc.)
        import sys
        is_management_command = (
            len(sys.argv) > 1 and sys.argv[1] in {
                "migrate", "makemigrations", "collectstatic", "createsuperuser",
                "shell", "dbshell", "check", "test", "gmail_auth", "gmail_sync_test",
                "setup_test_user",
            }
        )
        # Ne pas demarrer si DISABLE_AUTO_SYNC=true dans .env
        auto_sync_disabled = os.environ.get("DISABLE_AUTO_SYNC", "").strip().lower() in {"true", "1", "yes"}

        if is_management_command or auto_sync_disabled:
            return

        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.interval import IntervalTrigger

            interval_minutes = _get_sync_interval()
            scheduler = BackgroundScheduler(timezone="Africa/Casablanca")
            scheduler.add_job(
                _run_auto_sync,
                trigger=IntervalTrigger(minutes=interval_minutes),
                id="auto_email_sync",
                name="Synchronisation automatique emails",
                replace_existing=True,
                misfire_grace_time=60,
            )
            scheduler.start()
            logger.info(
                "Synchronisation automatique demarree (intervalle: %d minutes)", interval_minutes
            )
        except Exception as exc:
            logger.warning("Impossible de demarrer le scheduler auto-sync: %s", exc)
