"""
DocuSpace SMTP Email Notification Service
Handles standard transactional emails for space creation, login confirmation alerts,
email verification (Phase 2), and password reset.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
import html
import logging
import smtplib
from urllib.parse import quote

from backend.app.core.config import settings

logger = logging.getLogger("docuspace.email")

_UNCONFIGURED_SMTP_HOSTS = {"", "smtp.example.com", "localhost.invalid"}
_UNCONFIGURED_PASSWORD_MARKERS = (
    "not-configured",
    "replace_with",
    "change_me",
)


@dataclass
class EmailDispatchResult:
    sent: bool
    status: str
    detail: str


def is_smtp_configured() -> bool:
    """Return True only when a non-placeholder SMTP host and credentials are configured."""
    host = (settings.SMTP_HOST or "").strip().lower()
    if host in _UNCONFIGURED_SMTP_HOSTS:
        return False

    password = (settings.SMTP_PASSWORD or "").strip()
    lowered_pw = password.lower()
    if any(marker in lowered_pw for marker in _UNCONFIGURED_PASSWORD_MARKERS):
        return False

    # Allow local/internal relays without auth only if host is explicit and not a placeholder;
    # otherwise require both user and password when SMTP_USER is provided.
    if (settings.SMTP_USER or "").strip() and not password:
        return False

    return True


def _build_app_url(path: str) -> str:
    base = (settings.APP_URL or "http://localhost").rstrip("/")
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{base}{normalized_path}"


def _send_email_sync(
    recipient_email: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> EmailDispatchResult:
    if not is_smtp_configured():
        logger.info(
            "smtp_dispatch_skipped_unconfigured recipient=%s subject=%s",
            recipient_email,
            subject,
        )
        return EmailDispatchResult(
            sent=False,
            status="skipped_unconfigured",
            detail="Relais SMTP non configuré dans cet environnement (mode aperçu ou SMTP_HOST factice).",
        )

    msg = EmailMessage()
    sender = (settings.SMTP_FROM_EMAIL or settings.SMTP_USER or "no-reply@docuspace.local").strip()
    msg["Subject"] = subject
    msg["From"] = f"{settings.APP_NAME} <{sender}>"
    msg["To"] = recipient_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    host = settings.SMTP_HOST.strip()
    port = int(settings.SMTP_PORT or 587)
    user = (settings.SMTP_USER or "").strip()
    password = settings.SMTP_PASSWORD or ""

    try:
        if port == 465 and not settings.SMTP_TLS:
            with smtplib.SMTP_SSL(host, port, timeout=8) as server:
                if user and password:
                    server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=8) as server:
                server.ehlo()
                if settings.SMTP_TLS:
                    server.starttls()
                    server.ehlo()
                if user and password:
                    server.login(user, password)
                server.send_message(msg)

        logger.info("smtp_dispatch_sent recipient=%s subject=%s", recipient_email, subject)
        return EmailDispatchResult(sent=True, status="sent", detail="E-mail transmis via SMTP.")
    except Exception as exc:
        logger.warning(
            "smtp_dispatch_failed recipient=%s subject=%s error=%s",
            recipient_email,
            subject,
            type(exc).__name__,
        )
        return EmailDispatchResult(
            sent=False,
            status="error",
            detail=f"Échec d'envoi SMTP ({type(exc).__name__}).",
        )


async def send_email_async(
    recipient_email: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> EmailDispatchResult:
    return await asyncio.to_thread(
        _send_email_sync,
        recipient_email,
        subject,
        text_body,
        html_body,
    )


async def send_welcome_space_email(
    recipient_email: str,
    full_name: str,
    tenant_name: str,
    verification_token: str,
    verification_required: bool = False,
) -> EmailDispatchResult:
    """
    Envoie le message standard de bienvenue / création d'espace personnel,
    incluant le lien de confirmation de l'adresse e-mail (valable 24h).
    """
    safe_name = html.escape(full_name)
    safe_tenant = html.escape(tenant_name)
    verify_url = _build_app_url(f"/verify-email?token={quote(verification_token)}")
    safe_verify_url = html.escape(verify_url)

    verification_note_text = (
        "Action requise : confirmez votre adresse e-mail via le lien ci-dessous pour activer la connexion à votre espace :"
        if verification_required
        else "Validation optionnelle de votre adresse e-mail (recommandée pour sécuriser votre espace) :"
    )

    subject = f"[{settings.APP_NAME}] Votre espace documentaire « {tenant_name} » est prêt"

    text_body = (
        f"Bonjour {full_name},\n\n"
        f"Votre compte {settings.APP_NAME} et votre espace documentaire personnel « {tenant_name} » ont bien été créés.\n\n"
        f"{verification_note_text}\n"
        f"{verify_url}\n\n"
        "Mesures de sécurité actives sur votre espace :\n"
        "- Chiffrement des mots de passe Argon2id\n"
        "- Isolation stricte des données multi-tenant (PostgreSQL RLS)\n"
        "- Analyse antivirus ClamAV à l'importation\n\n"
        "Si vous n'êtes pas à l'origine de cette inscription, vous pouvez ignorer ce message.\n\n"
        f"L'équipe {settings.APP_NAME}"
    )

    html_body = f"""<!DOCTYPE html>
<html lang="fr">
  <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background:#0f172a; color:#e2e8f0; padding:24px;">
    <div style="max-width:560px; margin:0 auto; background:#1e293b; border:1px solid #334155; border-radius:16px; padding:28px;">
      <h2 style="margin:0 0 12px; color:#ffffff; font-size:20px;">Bienvenue sur {html.escape(settings.APP_NAME)}</h2>
      <p style="margin:0 0 14px; font-size:14px; line-height:1.6;">
        Bonjour <strong>{safe_name}</strong>,<br/>
        Votre compte et votre espace documentaire personnel <strong>« {safe_tenant} »</strong> ont bien été créés.
      </p>
      <p style="margin:0 0 16px; font-size:13px; color:#cbd5e1; line-height:1.6;">
        {html.escape(verification_note_text)}
      </p>
      <p style="margin:0 0 20px;">
        <a href="{safe_verify_url}" style="display:inline-block; background:#2563eb; color:#ffffff; text-decoration:none; font-weight:600; font-size:13px; padding:11px 18px; border-radius:10px;">
          Confirmer mon adresse e-mail et valider mon espace
        </a>
      </p>
      <p style="margin:0; font-size:12px; color:#94a3b8; line-height:1.5;">
        Lien valable 24 heures : <span style="word-break:break-all;">{safe_verify_url}</span>
      </p>
    </div>
  </body>
</html>"""

    return await send_email_async(recipient_email, subject, text_body, html_body)


async def send_login_notification_email(
    recipient_email: str,
    full_name: str,
    ip_address: str,
    user_agent: str,
    login_time_utc: datetime | None = None,
) -> EmailDispatchResult:
    """
    Envoie le message standard de notification de connexion réussie à l'utilisateur.
    """
    ts = (login_time_utc or datetime.now(timezone.utc)).strftime("%d/%m/%Y à %H:%M:%S UTC")
    ua_display = (user_agent or "Navigateur non précisé").strip()[:200]
    ip_display = (ip_address or "Inconnue").strip()

    safe_name = html.escape(full_name)
    safe_ip = html.escape(ip_display)
    safe_ua = html.escape(ua_display)
    safe_ts = html.escape(ts)
    app_url = _build_app_url("/")

    subject = f"[{settings.APP_NAME}] Confirmation de connexion à votre espace"

    text_body = (
        f"Bonjour {full_name},\n\n"
        f"Une connexion à votre compte {settings.APP_NAME} ({recipient_email}) vient d'être effectuée avec succès.\n\n"
        f"- Date et heure : {ts}\n"
        f"- Adresse IP : {ip_display}\n"
        f"- Appareil / Navigateur : {ua_display}\n\n"
        "S'il s'agit bien de vous, aucune action n'est requise.\n"
        "Si vous n'êtes pas à l'origine de cette connexion, révoquez immédiatement vos sessions actives "
        f"depuis votre espace ({app_url}) et réinitialisez votre mot de passe.\n\n"
        f"L'équipe Sécurité {settings.APP_NAME}"
    )

    html_body = f"""<!DOCTYPE html>
<html lang="fr">
  <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background:#0f172a; color:#e2e8f0; padding:24px;">
    <div style="max-width:560px; margin:0 auto; background:#1e293b; border:1px solid #334155; border-radius:16px; padding:28px;">
      <h2 style="margin:0 0 12px; color:#ffffff; font-size:18px;">Nouvelle connexion confirmée</h2>
      <p style="margin:0 0 14px; font-size:14px; line-height:1.6;">
        Bonjour <strong>{safe_name}</strong>,<br/>
        Votre connexion à votre espace <strong>{html.escape(settings.APP_NAME)}</strong> a bien été enregistrée :
      </p>
      <ul style="margin:0 0 16px; padding-left:18px; font-size:13px; color:#cbd5e1; line-height:1.7;">
        <li><strong>Date :</strong> {safe_ts}</li>
        <li><strong>Adresse IP :</strong> {safe_ip}</li>
        <li><strong>Appareil :</strong> {safe_ua}</li>
      </ul>
      <p style="margin:0; font-size:12px; color:#94a3b8; line-height:1.5;">
        Si vous n'êtes pas à l'origine de cette activité, modifiez immédiatement votre mot de passe et révoquez vos sessions dans les paramètres de sécurité.
      </p>
    </div>
  </body>
</html>"""

    return await send_email_async(recipient_email, subject, text_body, html_body)


async def send_password_reset_email(
    recipient_email: str,
    full_name: str,
    reset_token: str,
) -> EmailDispatchResult:
    """Envoie le jeton standard de réinitialisation de mot de passe (valable 1h)."""
    safe_name = html.escape(full_name)
    safe_token = html.escape(reset_token)
    subject = f"[{settings.APP_NAME}] Réinitialisation de votre mot de passe"

    text_body = (
        f"Bonjour {full_name},\n\n"
        f"Vous avez demandé la réinitialisation du mot de passe de votre compte {settings.APP_NAME}.\n"
        f"Jeton de réinitialisation (valable 1 heure) :\n{reset_token}\n\n"
        "Copiez ce jeton dans l'écran « Mot de passe oublié ? » pour définir un nouveau mot de passe.\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez simplement cet e-mail.\n"
    )

    html_body = f"""<!DOCTYPE html>
<html lang="fr">
  <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background:#0f172a; color:#e2e8f0; padding:24px;">
    <div style="max-width:560px; margin:0 auto; background:#1e293b; border:1px solid #334155; border-radius:16px; padding:28px;">
      <h2 style="margin:0 0 12px; color:#ffffff; font-size:18px;">Réinitialisation du mot de passe</h2>
      <p style="margin:0 0 14px; font-size:14px; line-height:1.6;">
        Bonjour <strong>{safe_name}</strong>,<br/>
        Utilisez le jeton ci-dessous (valable 1 heure) dans l'application pour choisir un nouveau mot de passe :
      </p>
      <div style="background:#0f172a; border:1px solid #334155; border-radius:10px; padding:12px; font-family:monospace; font-size:13px; color:#38bdf8; word-break:break-all; margin-bottom:16px;">
        {safe_token}
      </div>
      <p style="margin:0; font-size:12px; color:#94a3b8;">
        Si vous n'êtes pas à l'origine de cette demande, aucune modification n'a été appliquée.
      </p>
    </div>
  </body>
</html>"""

    return await send_email_async(recipient_email, subject, text_body, html_body)
