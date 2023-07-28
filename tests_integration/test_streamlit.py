import uuid
import pytest

from unittest import mock
from tests_integration.snowflake_connector import test_database, snowflake_session
from tests_integration.test_utils import (
    row_from_mock,
    rows_from_mock,
    row_from_snowflake_session,
    rows_from_snowflake_session,
    contains_row_with,
)


@pytest.mark.integration
@mock.patch("snowcli.cli.streamlit.print_db_cursor")
def test_streamlit_create_and_deploy(
    mock_print,
    runner,
    snowflake_session,
    test_database,
    _new_streamlit_role,
    test_root_path,
):
    streamlit_name = "test_streamlit_create_and_deploy_snowcli"
    streamlit_app_path = test_root_path / "test_files/streamlit.py"

    result = runner.invoke_with_config_and_integration_connection(
        ["streamlit", "create", streamlit_name, "--file", streamlit_app_path]
    )
    assert result.exit_code == 0

    result = runner.invoke_with_config_and_integration_connection(
        ["streamlit", "deploy", streamlit_name, "--file", streamlit_app_path]
    )
    assert result.exit_code == 0

    runner.invoke_with_config_and_integration_connection(["streamlit", "list"])
    expect = snowflake_session.execute_string(
        f"show streamlits like '{streamlit_name}'"
    )
    assert contains_row_with(
        row_from_mock(mock_print), row_from_snowflake_session(expect)[0]
    )

    runner.invoke_with_config_and_integration_connection(
        ["streamlit", "describe", streamlit_name]
    )
    mock_rows = rows_from_mock(mock_print)
    expect = snowflake_session.execute_string(f"describe streamlit {streamlit_name}")
    assert contains_row_with(mock_rows[-2], row_from_snowflake_session(expect)[0])
    expect = snowflake_session.execute_string(
        f"call system$generate_streamlit_url_from_name('{streamlit_name}')"
    )
    assert contains_row_with(mock_rows[-1], row_from_snowflake_session(expect)[0])

    runner.invoke_with_config_and_integration_connection(
        ["streamlit", "share", streamlit_name, _new_streamlit_role]
    )
    assert contains_row_with(
        row_from_mock(mock_print),
        {"status": "Statement executed successfully."},
    )
    result = snowflake_session.execute_string(
        f"use role {_new_streamlit_role}; show streamlits like '{streamlit_name}'; use role accountadmin"
    )
    assert contains_row_with(
        rows_from_snowflake_session(result)[1], {"name": streamlit_name.upper()}
    )

    runner.invoke_with_config_and_integration_connection(
        ["streamlit", "drop", streamlit_name]
    )
    assert contains_row_with(
        row_from_mock(mock_print),
        {"status": f"{streamlit_name.upper()} successfully dropped."},
    )
    result = snowflake_session.execute_string(
        f"show streamlits like '{streamlit_name}'"
    )
    assert row_from_snowflake_session(result) == []


@pytest.mark.integration
@mock.patch("snowcli.cli.streamlit.print_db_cursor")
def test_streamlit_create_from_stage(
    mock_print, runner, snowflake_session, _new_streamlit_role, test_root_path
):
    stage_name = "test_streamlit_create_from_stage"
    streamlit_name = "test_streamlit_create_from_stage_snowcli"
    streamlit_filename = "streamlit.py"
    streamlit_app_path = test_root_path / f"test_files/{streamlit_filename}"

    result = snowflake_session.execute_string(
        f"create stage {stage_name}; put file://{streamlit_app_path} @{stage_name} auto_compress=false overwrite=true;"
    )
    assert contains_row_with(
        rows_from_snowflake_session(result)[1],
        {
            "source": streamlit_filename,
            "target": streamlit_filename,
            "status": "UPLOADED",
        },
    )

    result = runner.invoke_with_config_and_integration_connection(
        [
            "streamlit",
            "create",
            streamlit_name,
            "--file",
            streamlit_app_path,
            "--from-stage",
            stage_name,
        ]
    )
    assert result.exit_code == 0

    runner.invoke_with_config_and_integration_connection(["streamlit", "list"])
    expect = snowflake_session.execute_string(
        f"show streamlits like '{streamlit_name}'"
    )
    assert contains_row_with(
        row_from_mock(mock_print), row_from_snowflake_session(expect)[0]
    )

    runner.invoke_with_config_and_integration_connection(
        ["streamlit", "describe", streamlit_name]
    )
    mock_rows = rows_from_mock(mock_print)
    expect = snowflake_session.execute_string(f"describe streamlit {streamlit_name}")
    assert contains_row_with(mock_rows[-2], row_from_snowflake_session(expect)[0])
    expect = snowflake_session.execute_string(
        f"call system$generate_streamlit_url_from_name('{streamlit_name}')"
    )
    assert contains_row_with(mock_rows[-1], row_from_snowflake_session(expect)[0])

    runner.invoke_with_config_and_integration_connection(
        ["streamlit", "share", streamlit_name, "public"]
    )
    assert contains_row_with(
        row_from_mock(mock_print),
        {"status": "Statement executed successfully."},
    )
    result = snowflake_session.execute_string(
        f"use role {_new_streamlit_role}; show streamlits like '{streamlit_name}'; use role accountadmin"
    )
    assert contains_row_with(
        rows_from_snowflake_session(result)[1], {"name": streamlit_name.upper()}
    )

    runner.invoke_with_config_and_integration_connection(
        ["streamlit", "drop", streamlit_name]
    )
    assert contains_row_with(
        row_from_mock(mock_print),
        {"status": f"{streamlit_name.upper()} successfully dropped."},
    )
    result = snowflake_session.execute_string(
        f"show streamlits like '%{streamlit_name}%'"
    )
    assert row_from_snowflake_session(result) == []


@pytest.fixture
def _new_streamlit_role(snowflake_session, test_database):
    role_name = f"snowcli_streamlit_role_{uuid.uuid4().hex}"
    result = snowflake_session.execute_string(
        f"set user = (select current_user()); "
        f"create role {role_name}; "
        f"grant all on database {test_database} to role {role_name};"
        f"grant usage on schema {test_database}.public to role {role_name}; "
        f"grant role {role_name} to user IDENTIFIER($USER)"
    )
    assert contains_row_with(
        row_from_snowflake_session(result),
        {"status": "Statement executed successfully."},
    )
    yield role_name
    result = snowflake_session.execute_string(f"drop role {role_name}")
    assert contains_row_with(
        row_from_snowflake_session(result),
        {"status": f"{role_name.upper()} successfully dropped."},
    )
