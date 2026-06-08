import os

SECRET_KEY = os.getenv("SECRET_KEY", "chave-local-dev")

SQLALCHEMY_DATABASE_URI = os.getenv(
    "DATABASE_URL",
    "sqlite:////var/data/logistock.db"
)

if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
        "postgres://",
        "postgresql://",
        1
    )

SQLALCHEMY_TRACK_MODIFICATIONS = False


# ==================================================
# EMAIL - BREVO
# ==================================================

MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp-relay.brevo.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
MAIL_USE_TLS = True
MAIL_USE_SSL = False

MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")

MAIL_DEFAULT_SENDER = (
    "LogiStock",
    os.getenv("MAIL_DEFAULT_SENDER", "claudineymoura@gmail.com")
)