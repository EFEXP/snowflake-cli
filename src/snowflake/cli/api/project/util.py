import codecs
import os
import re
from typing import Optional

IDENTIFIER = r'((?:"[^"]*(?:""[^"]*)*")|(?:[A-Za-z_][\w$]{0,254}))'
DB_SCHEMA_AND_NAME = f"{IDENTIFIER}[.]{IDENTIFIER}[.]{IDENTIFIER}"
SCHEMA_AND_NAME = f"{IDENTIFIER}[.]{IDENTIFIER}"
GLOB_REGEX = r"^[a-zA-Z0-9_\-./*?**\p{L}\p{N}]+$"
RELATIVE_PATH = r"^[^/][\p{L}\p{N}_\-.][^/]*$"

SINGLE_QUOTED_STRING_LITERAL_REGEX = r"'((?:\\.|''|[^'\n])+?)'"

# See https://docs.snowflake.com/en/sql-reference/identifiers-syntax for identifier syntax
UNQUOTED_IDENTIFIER_REGEX = r"([a-zA-Z_])([a-zA-Z0-9_$]{0,254})"
QUOTED_IDENTIFIER_REGEX = r'"((""|[^"]){0,255})"'
VALID_IDENTIFIER_REGEX = f"(?:{UNQUOTED_IDENTIFIER_REGEX}|{QUOTED_IDENTIFIER_REGEX})"


def clean_identifier(input_: str):
    """
    Removes characters that cannot be used in an unquoted identifier,
    converting to lowercase as well.
    """
    return re.sub(r"[^a-z0-9_$]", "", f"{input_}".lower())


def is_valid_unquoted_identifier(identifier: str) -> bool:
    """
    Determines whether the provided identifier is a valid Snowflake unquoted identifier.
    """
    return re.fullmatch(UNQUOTED_IDENTIFIER_REGEX, identifier) is not None


def is_valid_quoted_identifier(identifier: str) -> bool:
    """
    Determines whether the provided identifier is a valid Snowflake quoted identifier.
    """
    return re.fullmatch(QUOTED_IDENTIFIER_REGEX, identifier) is not None


def is_valid_identifier(identifier: str) -> bool:
    """
    Determines whether the provided identifier is a valid Snowflake quoted or unquoted identifier.
    """
    return is_valid_unquoted_identifier(identifier) or is_valid_quoted_identifier(
        identifier
    )


def is_valid_object_name(name: str, max_depth=2) -> bool:
    """
    Determines whether the given identifier is a valid object name in the form <name>, <schema>.<name>, or <database>.<schema>.<name>.
    Max_depth determines how many valid identifiers are allowed. For example, account level objects would have a max depth of 0
    because they cannot be qualified by a database or schema, just the single identifier.
    """
    if max_depth < 0:
        raise ValueError("max_depth must be non-negative")
    pattern = (
        rf"{VALID_IDENTIFIER_REGEX}(?:\.{VALID_IDENTIFIER_REGEX}){{0,{max_depth}}}"
    )
    return re.fullmatch(pattern, name) is not None


def to_identifier(name: str) -> str:
    """
    Converts a name to a valid Snowflake identifier. If the name is already a valid
    Snowflake identifier, then it is returned unmodified.
    """
    if is_valid_identifier(name):
        return name

    # double quote the identifier
    return '"' + name.replace('"', '""') + '"'


def append_to_identifier(identifier: str, suffix: str) -> str:
    """
    Appends a suffix to a valid identifier.
    """
    if is_valid_unquoted_identifier(identifier):
        return to_identifier(f"{identifier}{suffix}")
    else:
        # the identifier is quoted, so insert the suffix within the quotes
        unquoted = identifier[1:-1]
        return f'"{unquoted}{suffix}"'


def unquote_identifier(identifier: str) -> str:
    """
    Returns a version of this identifier that can be used inside of a URL,
    inside of a string for a LIKE clause, or to match an identifier passed
    back as a value from a SQL statement.
    """
    if match := re.fullmatch(QUOTED_IDENTIFIER_REGEX, identifier):
        return match.group(1).replace('""', '"')
    # unquoted identifiers are internally represented as uppercase
    return identifier.upper()


def is_valid_string_literal(literal: str) -> bool:
    """
    Determines if a literal is a valid single quoted string literal
    """
    return re.fullmatch(SINGLE_QUOTED_STRING_LITERAL_REGEX, literal) is not None


def to_string_literal(raw_value: str) -> str:
    """
    Converts the raw string value to a correctly escaped, single-quoted string literal.
    """
    # encode escape sequences
    escaped = str(codecs.encode(raw_value, "unicode-escape"), "utf-8")

    # escape single quotes
    escaped = re.sub(r"^'|(?<!')'", r"\'", escaped)

    return f"'{escaped}'"


def extract_schema(qualified_name: str):
    """
    Extracts the schema from either a two-part or three-part qualified name
    (i.e. schema.object or database.schema.object). If qualified_name is not
    qualified with a schema, returns None.
    """
    if match := re.fullmatch(DB_SCHEMA_AND_NAME, qualified_name):
        return match.group(2)
    elif match := re.fullmatch(SCHEMA_AND_NAME, qualified_name):
        return match.group(1)
    return None


def generate_user_env(username: str) -> dict:
    return {
        "USER": username,
    }


def first_set_env(*keys: str):
    for k in keys:
        v = os.getenv(k)
        if v:
            return v

    return None


def get_env_username() -> Optional[str]:
    return first_set_env("USER", "USERNAME", "LOGNAME")


SUPPORTED_VERSIONS = [1]


def validate_version(version: str):
    if version in SUPPORTED_VERSIONS:
        raise ValueError(
            f"Project definition version {version} is not supported by this version of Snowflake CLI. Supported versions: {SUPPORTED_VERSIONS}"
        )


def escape_like_pattern(pattern: str, escape_sequence: str = r"\\") -> str:
    """
    When used with LIKE in Snowflake, '%' and '_' are wildcard characters and must be escaped to be used literally.
    The escape character is '\\' when used in SHOW LIKE and must be specified when used with string matching using the
    following syntax: <subject> LIKE <pattern> [ ESCAPE <escape> ].
    """
    pattern = pattern.replace("%", rf"{escape_sequence}%").replace(
        "_", rf"{escape_sequence}_"
    )
    return pattern


def identifier_to_show_like_pattern(identifier: str) -> str:
    """
    Takes an identifier and converts it into a pattern to be used with SHOW ... LIKE ... to get all rows with name
    matching this identifier
    """
    return f"'{escape_like_pattern(unquote_identifier(identifier))}'"
