from snowflake.cli.plugins.spcs.common import validate_and_set_instances
from tests.testing_utils.fixtures import *
from click import ClickException
from snowflake.connector.errors import ProgrammingError
from snowflake.cli.plugins.spcs.common import handle_object_already_exists
from snowflake.cli.api.exceptions import ObjectAlreadyExistsError, ObjectType
from unittest.mock import Mock


@pytest.mark.parametrize(
    "min_instances, max_instances, expected_max",
    [
        (2, None, 2),  # max_instances is None, set max_instances to min_instances
        (
            5,
            10,
            10,
        ),  # max_instances is valid non-None value, return max_instances unchanged
    ],
)
def test_validate_and_set_instances(min_instances, max_instances, expected_max):
    assert expected_max == validate_and_set_instances(
        min_instances, max_instances, "name"
    )


@pytest.mark.parametrize(
    "min_instances, max_instances, expected_msg",
    [
        (0, 1, "min_name must be positive"),  # non-positive min_instances
        (-1, 1, "min_name must be positive"),  # negative min_instances
        (
            2,
            1,
            "max_name must be greater or equal to min_name",
        ),  # min_instances > max_instances
    ],
)
def test_validate_and_set_instances_invalid(min_instances, max_instances, expected_msg):
    with pytest.raises(ClickException) as exc:
        validate_and_set_instances(min_instances, max_instances, "name")
    assert expected_msg in exc.value.message


SPCS_OBJECT_EXISTS_ERROR = ProgrammingError(
    msg="Object 'TEST_OBJECT' already exists.", errno=2002
)


def test_handle_object_exists_error():
    mock_type = Mock(spec=ObjectType)
    test_name = "TEST_OBJECT"
    with pytest.raises(ObjectAlreadyExistsError):
        handle_object_already_exists(SPCS_OBJECT_EXISTS_ERROR, mock_type, test_name)


def test_handle_object_exists_error_other_error():
    # For any errors other than 'Object 'XYZ' already exists.', simply pass the error through
    other_error = ProgrammingError(msg="Object does not already exist.", errno=0)
    with pytest.raises(ProgrammingError) as e:
        handle_object_already_exists(other_error, Mock(spec=ObjectType), "TEST_OBJECT")
    assert other_error == e.value
