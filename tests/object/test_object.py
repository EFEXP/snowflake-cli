from unittest import mock

import pytest
from snowflake.cli.api.constants import SUPPORTED_OBJECTS, OBJECT_TO_NAMES
from snowflake.cli.plugins.object.commands import _scope_validate
from click import ClickException


@mock.patch("snowflake.connector.connect")
@pytest.mark.parametrize(
    "object_type, expected",
    [
        ("compute-pool", "compute pools"),
        ("network-rule", "network rules"),
        ("database", "databases"),
        ("function", "functions"),
        # ("job", "jobs"),
        ("procedure", "procedures"),
        ("role", "roles"),
        ("schema", "schemas"),
        ("service", "services"),
        ("secret", "secrets"),
        ("stage", "stages"),
        ("stream", "streams"),
        ("streamlit", "streamlits"),
        ("table", "tables"),
        ("task", "tasks"),
        ("user", "users"),
        ("warehouse", "warehouses"),
        ("view", "views"),
        ("image-repository", "image repositories"),
    ],
)
def test_show(
    mock_connector, object_type, expected, mock_cursor, runner, snapshot, mock_ctx
):
    ctx = mock_ctx()
    mock_connector.return_value = ctx

    result = runner.invoke(["object", "list", object_type], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert ctx.get_queries() == [f"show {expected} like '%%'"]


DESCRIBE_TEST_OBJECTS = [
    ("compute-pool", "compute_pool_example"),
    ("network-rule", "network_rule_example"),
    ("integration", "integration_example"),
    ("database", "database_example"),
    ("function", "function_example"),
    # ("job", "job_example"),
    ("procedure", "procedure_example"),
    ("role", "role_example"),
    ("schema", "schema_example"),
    ("service", "service_example"),
    ("secret", "secret_example"),
    ("stage", "stage_example"),
    ("stream", "stream_example"),
    ("streamlit", "streamlit_example"),
    ("table", "table_example"),
    ("task", "task_example"),
    ("user", "user_example"),
    ("warehouse", "warehouse_example"),
    ("view", "view_example"),
]


@mock.patch("snowflake.connector.connect")
@pytest.mark.parametrize(
    "object_type, input_scope, input_name",
    [
        ("schema", "database", "test_db"),
        ("table", "schema", "test_schema"),
        ("service", "compute-pool", "test_pool"),
    ],
)
def test_show_with_scope(
    mock_connector, object_type, input_scope, input_name, runner, mock_ctx
):
    ctx = mock_ctx()
    mock_connector.return_value = ctx
    result = runner.invoke(
        ["object", "list", object_type, "--in", input_scope, input_name]
    )
    obj = OBJECT_TO_NAMES[object_type]
    scope_obj = OBJECT_TO_NAMES[input_scope]
    assert result.exit_code == 0, result.output
    assert ctx.get_queries() == [
        f"show {obj.sf_plural_name} like '%%' in {scope_obj.sf_name} {input_name}"
    ]


@mock.patch("snowflake.connector.connect")
@pytest.mark.parametrize(
    "object_type, input_scope, input_name, expected",
    [
        (
            "table",
            "invalid_scope",
            "name",
            "scope must be one of the following",
        ),  # invalid scope label
        (
            "table",
            "database",
            "invalid name",
            "scope name must be a valid identifier",
        ),  # invalid scope identifier
    ],
)
def test_show_with_invalid_scope(
    mock_connector, object_type, input_scope, input_name, expected, runner
):

    result = runner.invoke(
        ["object", "list", object_type, "--in", input_scope, input_name]
    )
    assert expected in result.output


@pytest.mark.parametrize(
    "object_type, input_scope, input_name",
    [
        ("user", None, None),
        ("schema", "database", "test_db"),
        ("table", "schema", "test_schema"),
        ("service", "compute-pool", "test_pool"),
    ],
)
def test_scope_validate(object_type, input_scope, input_name):
    _scope_validate(object_type, (input_scope, input_name))


@pytest.mark.parametrize(
    "object_type, input_scope, input_name, expected_msg",
    [
        (
            "table",
            "database",
            "invalid identifier",
            "scope name must be a valid identifier",
        ),
        ("table", "invalid-scope", "identifier", "scope must be one of the following"),
        (
            "table",
            "compute-pool",
            "test_pool",
            "compute-pool scope is only supported for listing service",
        ),  # 'compute-pool' scope can only be used with 'service'
    ],
)
def test_invalid_scope_validate(object_type, input_scope, input_name, expected_msg):
    with pytest.raises(ClickException) as exc:
        _scope_validate(object_type, (input_scope, input_name))
    assert expected_msg in exc.value.message


@mock.patch("snowflake.connector")
@pytest.mark.parametrize("object_type, object_name", DESCRIBE_TEST_OBJECTS)
def test_describe(
    mock_connector, object_type, object_name, mock_cursor, runner, snapshot
):
    mock_connector.connect.return_value.execute_stream.return_value = (
        None,
        mock_cursor(
            rows=[("ID", "NUMBER(38,0", "COLUMN"), ("NAME", "VARCHAR(100", "COLUMN")],
            columns=["name", "type", "kind"],
        ),
    )
    result = runner.invoke(["object", "describe", object_type, object_name])
    assert result.exit_code == 0, result.output
    assert result.output == snapshot


@mock.patch("snowflake.connector")
def test_describe_fails_image_repository(mock_cursor, runner, snapshot):
    result = runner.invoke(["object", "describe", "image-repository", "test_repo"])
    assert result.exit_code == 1, result.output
    assert result.output == snapshot


DROP_TEST_OBJECTS = [
    *DESCRIBE_TEST_OBJECTS,
    ("image-repository", "image_repository_example"),
]


@mock.patch("snowflake.connector")
@pytest.mark.parametrize(
    "object_type, object_name",
    DROP_TEST_OBJECTS,
)
def test_drop(mock_connector, object_type, object_name, mock_cursor, runner, snapshot):
    mock_connector.connect.return_value.execute_stream.return_value = (
        None,
        mock_cursor(rows=[f"{object_name} successfully dropped."], columns=["status"]),
    )

    result = runner.invoke(["object", "drop", object_type, object_name])
    assert result.exit_code == 0, result.output
    assert result.output == snapshot


@pytest.mark.parametrize("command", ["list", "drop", "describe"])
def test_that_objects_list_is_in_help(command, runner):
    result = runner.invoke(["object", command, "--help"])
    for obj in SUPPORTED_OBJECTS:
        if command == "describe" and obj == "image-repository":
            assert obj not in result.output, f"{obj} should not be in help message"
        else:
            assert obj in result.output, f"{obj} in help message"


@pytest.mark.parametrize(
    "command,expect_argument_exception",
    [
        (["object", "drop"], "OBJECT_TYPE"),
        (["object", "drop", "function"], "OBJECT_NAME"),
        (["object", "list"], "OBJECT_TYPE"),
        (["object", "describe"], "OBJECT_TYPE"),
        (["object", "describe", "function"], "OBJECT_NAME"),
    ],
)
def test_throw_exception_because_of_missing_arguments(
    runner, command, expect_argument_exception
):
    result = runner.invoke(command)
    assert result.exit_code == 2, result.output
    assert result.output.__contains__(
        f"Missing argument '{expect_argument_exception}'."
    )
