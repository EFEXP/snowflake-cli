from typing import Optional

import typer
from click import ClickException
from snowflake.cli.api.commands.flags import (
    OverrideableOption,
)
from snowflake.cli.api.commands.snow_typer import SnowTyper
from snowflake.cli.api.output.types import CommandResult, SingleQueryResult
from snowflake.cli.api.project.util import is_valid_object_name
from snowflake.cli.plugins.object.common import CommentOption
from snowflake.cli.plugins.spcs.common import (
    validate_and_set_instances,
)
from snowflake.cli.plugins.spcs.compute_pool.manager import ComputePoolManager

app = SnowTyper(
    name="compute-pool",
    help="Manages compute pools.",
)


def _compute_pool_name_callback(name: str) -> str:
    """
    Verifies that compute pool name is a single valid identifier.
    """
    if not is_valid_object_name(name, 0):
        raise ClickException(f"'{name}' is not a valid compute pool name.")
    return name


ComputePoolNameArgument = typer.Argument(
    ...,
    help="Name of the compute pool.",
    callback=_compute_pool_name_callback,
    show_default=False,
)


MinNodesOption = OverrideableOption(
    1,
    "--min-nodes",
    help="Minimum number of nodes for the compute pool.",
    min=1,
)
MaxNodesOption = OverrideableOption(
    None,
    "--max-nodes",
    help="Maximum number of nodes for the compute pool.",
    min=1,
)
AutoResumeOption = OverrideableOption(
    True,
    "--auto-resume/--no-auto-resume",
    help="The compute pool will automatically resume when a service or job is submitted to it.",
)
AutoSuspendSecsOption = OverrideableOption(
    3600,
    "--auto-suspend-secs",
    help="Number of seconds of inactivity after which you want Snowflake to automatically suspend the compute pool.",
    min=1,
)


@app.command(requires_connection=True)
def create(
    name: str = ComputePoolNameArgument,
    min_nodes: int = MinNodesOption(),
    max_nodes: Optional[int] = MaxNodesOption(),
    instance_family: str = typer.Option(
        ...,
        "--family",
        help="Name of the instance family. For more information about instance families, refer to the SQL CREATE COMPUTE POOL command.",
    ),
    auto_resume: bool = AutoResumeOption(),
    initially_suspended: bool = typer.Option(
        False,
        "--init-suspend",
        help="The compute pool will start in a suspended state.",
    ),
    auto_suspend_secs: int = AutoSuspendSecsOption(),
    comment: Optional[str] = CommentOption(help="Comment for the compute pool."),
    **options,
) -> CommandResult:
    """
    Creates a compute pool with a specified number of nodes.
    """
    max_nodes = validate_and_set_instances(min_nodes, max_nodes, "nodes")
    cursor = ComputePoolManager().create(
        pool_name=name,
        min_nodes=min_nodes,
        max_nodes=max_nodes,
        instance_family=instance_family,
        auto_resume=auto_resume,
        initially_suspended=initially_suspended,
        auto_suspend_secs=auto_suspend_secs,
        comment=comment,
    )
    return SingleQueryResult(cursor)


@app.command("stop-all", requires_connection=True)
def stop_all(name: str = ComputePoolNameArgument, **options) -> CommandResult:
    """
    Deletes all services running on the compute pool.
    """
    cursor = ComputePoolManager().stop(pool_name=name)
    return SingleQueryResult(cursor)


@app.command(requires_connection=True)
def suspend(name: str = ComputePoolNameArgument, **options) -> CommandResult:
    """
    Suspends the compute pool by suspending all currently running services and then releasing compute pool nodes.
    """
    return SingleQueryResult(ComputePoolManager().suspend(name))


@app.command(requires_connection=True)
def resume(name: str = ComputePoolNameArgument, **options) -> CommandResult:
    """
    Resumes the compute pool from SUSPENDED state.
    """
    return SingleQueryResult(ComputePoolManager().resume(name))


@app.command("set", requires_connection=True)
def set_property(
    name: str = ComputePoolNameArgument,
    min_nodes: Optional[int] = MinNodesOption(default=None, show_default=False),
    max_nodes: Optional[int] = MaxNodesOption(show_default=False),
    auto_resume: Optional[bool] = AutoResumeOption(default=None, show_default=False),
    auto_suspend_secs: Optional[int] = AutoSuspendSecsOption(
        default=None, show_default=False
    ),
    comment: Optional[str] = CommentOption(
        help="Comment for the compute pool.", show_default=False
    ),
    **options,
) -> CommandResult:
    """
    Sets one or more properties or parameters for the compute pool.
    """
    cursor = ComputePoolManager().set_property(
        pool_name=name,
        min_nodes=min_nodes,
        max_nodes=max_nodes,
        auto_resume=auto_resume,
        auto_suspend_secs=auto_suspend_secs,
        comment=comment,
    )
    return SingleQueryResult(cursor)


@app.command("unset", requires_connection=True)
def unset_property(
    name: str = ComputePoolNameArgument,
    auto_resume: bool = AutoResumeOption(
        default=False,
        help="Reset the AUTO_RESUME property - The compute pool will automatically resume when a service or job is submitted to it.",
        show_default=False,
    ),
    auto_suspend_secs: bool = AutoSuspendSecsOption(
        default=False,
        help="Reset the AUTO_SUSPEND_SECS property - Number of seconds of inactivity after which you want Snowflake to automatically suspend the compute pool.",
        show_default=False,
    ),
    comment: bool = CommentOption(
        default=False,
        help="Reset the COMMENT property - Comment for the compute pool.",
        callback=None,
        show_default=False,
    ),
    **options,
) -> CommandResult:
    """
    Resets one or more properties or parameters for the compute pool to their default value(s).
    """
    cursor = ComputePoolManager().unset_property(
        pool_name=name,
        auto_resume=auto_resume,
        auto_suspend_secs=auto_suspend_secs,
        comment=comment,
    )
    return SingleQueryResult(cursor)


@app.command(requires_connection=True)
def status(pool_name: str = ComputePoolNameArgument, **options) -> CommandResult:
    """
    Retrieves status of a compute pool along with a relevant message, if one exists.
    """
    cursor = ComputePoolManager().status(pool_name=pool_name)
    return SingleQueryResult(cursor)
