from __future__ import annotations

import logging

import click
import typer
from click import ClickException, Context, Parameter  # type: ignore
from click.core import ParameterSource  # type: ignore
from click.types import StringParamType
from snowflake.cli.api.cli_global_context import cli_context
from snowflake.cli.api.commands.flags import (
    PLAIN_PASSWORD_MSG,
    ConnectionOption,
    MfaPasscodeOption,
)
from snowflake.cli.api.commands.snow_typer import SnowTyper
from snowflake.cli.api.config import (
    add_connection,
    connection_exists,
    get_config_section,
)
from snowflake.cli.api.constants import ObjectType
from snowflake.cli.api.output.types import (
    CollectionResult,
    CommandResult,
    MessageResult,
    ObjectResult,
)
from snowflake.cli.plugins.object.manager import ObjectManager
from snowflake.connector import ProgrammingError
from snowflake.connector.config_manager import CONFIG_MANAGER

app = SnowTyper(
    name="connection",
    help="Manages connections to Snowflake.",
)
log = logging.getLogger(__name__)


class EmptyInput:
    def __repr__(self):
        return "optional"


class OptionalPrompt(StringParamType):
    def convert(self, value, param, ctx):
        return None if isinstance(value, EmptyInput) else value


def _mask_password(connection_params: dict):
    if "password" in connection_params:
        connection_params["password"] = "****"
    return connection_params


@app.command(name="list")
def list_connections(**options) -> CommandResult:
    """
    Lists configured connections.
    """
    connections = get_config_section("connections")
    result = (
        {"connection_name": k, "parameters": _mask_password(v)}
        for k, v in connections.items()
    )
    return CollectionResult(result)


def require_integer(field_name: str):
    def callback(value: str):
        if value is None:
            return None
        if value.isdigit():
            return value
        raise ClickException(f"Value of {field_name} must be integer")

    return callback


def _password_callback(ctx: Context, param: Parameter, value: str):
    if value and ctx.get_parameter_source(param.name) == ParameterSource.COMMANDLINE:  # type: ignore
        click.echo(PLAIN_PASSWORD_MSG)

    return value


@app.command()
def add(
    connection_name: str = typer.Option(
        None,
        "--connection-name",
        "-n",
        prompt="Name for this connection",
        help="Name of the new connection.",
        show_default=False,
    ),
    account: str = typer.Option(
        None,
        "--account",
        "-a",
        "--accountname",
        prompt="Snowflake account name",
        help="Account name to use when authenticating with Snowflake.",
        show_default=False,
    ),
    user: str = typer.Option(
        None,
        "--user",
        "-u",
        "--username",
        prompt="Snowflake username",
        show_default=False,
        help="Username to connect to Snowflake.",
    ),
    password: str = typer.Option(
        EmptyInput(),
        "--password",
        "-p",
        click_type=OptionalPrompt(),
        callback=_password_callback,
        prompt="Snowflake password",
        help="Snowflake password.",
        hide_input=True,
    ),
    role: str = typer.Option(
        EmptyInput(),
        "--role",
        "-r",
        click_type=OptionalPrompt(),
        prompt="Role for the connection",
        help="Role to use on Snowflake.",
    ),
    warehouse: str = typer.Option(
        EmptyInput(),
        "--warehouse",
        "-w",
        click_type=OptionalPrompt(),
        prompt="Warehouse for the connection",
        help="Warehouse to use on Snowflake.",
    ),
    database: str = typer.Option(
        EmptyInput(),
        "--database",
        "-d",
        click_type=OptionalPrompt(),
        prompt="Database for the connection",
        help="Database to use on Snowflake.",
    ),
    schema: str = typer.Option(
        EmptyInput(),
        "--schema",
        "-s",
        click_type=OptionalPrompt(),
        prompt="Schema for the connection",
        help="Schema to use on Snowflake.",
    ),
    host: str = typer.Option(
        EmptyInput(),
        "--host",
        "-h",
        click_type=OptionalPrompt(),
        prompt="Connection host",
        help="Host name the connection attempts to connect to Snowflake.",
    ),
    port: int = typer.Option(
        EmptyInput(),
        "--port",
        "-P",
        click_type=OptionalPrompt(),
        prompt="Connection port",
        help="Port to communicate with on the host.",
        callback=require_integer(field_name="port"),
    ),
    region: str = typer.Option(
        EmptyInput(),
        "--region",
        "-R",
        click_type=OptionalPrompt(),
        prompt="Snowflake region",
        help="Region name if not the default Snowflake deployment.",
    ),
    authenticator: str = typer.Option(
        EmptyInput(),
        "--authenticator",
        "-A",
        click_type=OptionalPrompt(),
        prompt="Authentication method",
        help="Chosen authenticator, if other than password-based",
    ),
    private_key_path: str = typer.Option(
        EmptyInput(),
        "--private-key",
        "-k",
        click_type=OptionalPrompt(),
        prompt="Path to private key file",
        help="Path to file containing private key",
    ),
    **options,
) -> CommandResult:
    """Adds a connection to configuration file."""
    connection_entry = {
        "account": account,
        "user": user,
        "password": password,
        "host": host,
        "region": region,
        "port": port,
        "database": database,
        "schema": schema,
        "warehouse": warehouse,
        "role": role,
        "authenticator": authenticator,
        "private_key_path": private_key_path,
    }
    connection_entry = {k: v for k, v in connection_entry.items() if v is not None}

    if connection_exists(connection_name):
        raise ClickException(f"Connection {connection_name} already exists")

    add_connection(connection_name, connection_entry)
    return MessageResult(
        f"Wrote new connection {connection_name} to {CONFIG_MANAGER.file_path}"
    )


@app.command(requires_connection=False)
def test(
    connection: str = ConnectionOption, mfa_passcode: str = MfaPasscodeOption, **options
) -> CommandResult:
    """
    Tests the connection to Snowflake.
    """

    # Test connection
    conn = cli_context.connection

    # Test session attributes
    om = ObjectManager()
    try:
        if conn.role:
            om.use_role(new_role=conn.role)
        if conn.database:
            om.describe(
                object_type=ObjectType.DATABASE.value.cli_name, name=conn.database
            )
        if conn.schema:
            om.describe(object_type=ObjectType.SCHEMA.value.cli_name, name=conn.schema)
        if conn.warehouse:
            om.describe(
                object_type=ObjectType.WAREHOUSE.value.cli_name, name=conn.warehouse
            )
    except ProgrammingError as err:
        raise ClickException(str(err))

    result = {
        "Connection name": connection,
        "Status": "OK",
        "Host": conn.host,
        "Account": conn.account,
        "User": conn.user,
        "Role": f'{conn.role or "not set"}',
        "Database": f'{conn.database or "not set"}',
        "Warehouse": f'{conn.warehouse or "not set"}',
    }

    return ObjectResult(result)
