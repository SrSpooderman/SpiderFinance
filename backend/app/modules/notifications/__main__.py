"""Send an explicit test message to verify SMTP configuration."""

import argparse

from app.modules.notifications.infrastructure import (
    MailConfigurationError, MailDeliveryError, SmtpMailSender,
)
from app.modules.notifications.ports import MailMessage


def main() -> None:
    parser = argparse.ArgumentParser(description="Probar la conexión SMTP de SpiderFinance")
    parser.add_argument("--to", required=True, help="Destinatario del correo de prueba")
    args = parser.parse_args()
    try:
        SmtpMailSender().send(MailMessage(
            recipient=args.to,
            subject="Prueba SMTP de SpiderFinance",
            text="El transporte SMTP de SpiderFinance funciona correctamente.",
        ))
    except (MailConfigurationError, MailDeliveryError) as exc:
        parser.exit(1, f"Error SMTP: {exc}\n")
    print("Correo de prueba entregado al servidor SMTP")


if __name__ == "__main__":
    main()
