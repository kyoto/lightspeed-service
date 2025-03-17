"""Class with implementation of storage for token usage history."""

import logging
from datetime import datetime

import psycopg2

from ols.app.models.config import PostgresConfig

logger = logging.getLogger(__name__)


class TokenUsageHistory:
    """Class with implementation of storage for token usage history."""

    CREATE_TOKEN_USAGE_TABLE = """
        CREATE TABLE IF NOT EXISTS token_usage (
            user_id         text NOT NULL,
            provider        text NOT NULL,
            model           text NOT NULL,
            input_tokens    int,
            output_tokens   int,
            updated_at      timestamp with time zone,
            PRIMARY KEY(user_id, provider, model)
        );
        """  # noqa: S105

    INIT_TOKEN_USAGE_FOR_USER = """
        INSERT INTO token_usage (user_id, provider, model, input_tokens, output_tokens, updated_at)
        VALUES (%s, %s, %s, 0, 0, %s)
        """  # noqa: S105

    CONSUME_TOKENS_FOR_USER = """
        INSERT INTO token_usage (user_id, provider, model, input_tokens, output_tokens, updated_at)
        VALUES (%(user_id)s, %(provider)s, %(model)s, %(input_tokens)s, %(output_tokens)s, %(updated_at)s)
        ON CONFLICT (user_id, provider, model)
        DO UPDATE
           SET input_tokens=token_usage.input_tokens+%(input_tokens)s,
               output_tokens=token_usage.output_tokens+%(output_tokens)s,
               updated_at=%(updated_at)s
         WHERE token_usage.user_id=%(user_id)s
           AND token_usage.provider=%(provider)s
           AND token_usage.model=%(model)s
        """  # noqa: E501

    def __init__(self, config: PostgresConfig) -> None:
        """Initialize token usage history storage."""
        # initialize connection to DB
        self.connect(config)

        try:
            self._initialize_tables()
        except Exception as e:
            self.connection.close()
            logger.exception("Error initializing Postgres database:\n%s", e)
            raise

    def consume_tokens(
        self,
        user_id: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Consume tokens by given user."""
        logger.info(
            "Token usage for user %s, provider %s and mode %s changed by %d, %d tokens",
            user_id,
            provider,
            model,
            input_tokens,
            output_tokens,
        )
        # timestamp to be used
        updated_at = datetime.now()

        with self.connection.cursor() as cursor:
            cursor.execute(
                TokenUsageHistory.CONSUME_TOKENS_FOR_USER,
                {
                    "user_id": user_id,
                    "provider": provider,
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "updated_at": updated_at,
                },
            )

    # pylint: disable=W0201
    def connect(self, config: PostgresConfig) -> None:
        """Initialize connection to database."""
        self.connection = psycopg2.connect(
            host=config.host,
            port=config.port,
            user=config.user,
            password=config.password,
            dbname=config.dbname,
            sslmode=config.ssl_mode,
            # sslrootcert=config.ca_cert_path,
            gssencmode=config.gss_encmode,
        )
        self.connection.autocommit = True

    def _initialize_tables(self) -> None:
        """Initialize tables used by quota limiter."""
        cursor = self.connection.cursor()
        cursor.execute(TokenUsageHistory.CREATE_TOKEN_USAGE_TABLE)
        cursor.close()
        self.connection.commit()
