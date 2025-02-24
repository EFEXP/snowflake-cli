import base64
import json
import re
import subprocess
from urllib.parse import urlparse

import requests
from click import ClickException
from snowflake.cli.api.sql_execution import SqlExecutionMixin
from snowflake.connector.cursor import DictCursor


class NoImageRepositoriesFoundError(ClickException):
    def __init__(self):
        super().__init__(
            f"No image repository found. To run this command, please switch to a role with read access to at least one image repository or create a new image repository first."
        )


class RegistryManager(SqlExecutionMixin):
    def get_token(self):
        """
        Get token to authenticate with registry.
        """
        self._execute_query(
            "alter session set PYTHON_CONNECTOR_QUERY_RESULT_FORMAT = 'json'"
        ).fetchall()
        # disable session deletion
        self._conn._all_async_queries_finished = lambda: False  # noqa: SLF001
        if self._conn._rest is None:  # noqa: SLF001
            raise Exception("Failed to connect to Snowflake to retrieve token.")
        # obtain and create the token
        token_data = self._conn._rest._token_request("ISSUE")  # noqa: SLF001

        return {
            "token": token_data["data"]["sessionToken"],
            "expires_in": token_data["data"]["validityInSecondsST"],
        }

    def login_to_registry(self, repo_url):
        """
        Logs in to the registry using basic authentication and generates a bearer authentication token.
        """
        token = json.dumps(self.get_token())
        parsed_url = urlparse(repo_url)

        scheme = parsed_url.scheme
        host = parsed_url.netloc

        login_url = f"{scheme}://{host}/login"
        creds = base64.b64encode(f"0sessiontoken:{token}".encode("utf-8"))
        creds = creds.decode("utf-8")
        resp = requests.get(login_url, headers={"Authorization": f"Basic {creds}"})

        if resp.status_code != 200:
            raise ClickException(f"Failed to login to the repository {resp.text}")
        return json.loads(resp.text)["token"]

    def _has_url_scheme(self, url: str):
        return re.fullmatch(r"^.*//.+", url) is not None

    def get_registry_url(self) -> str:
        repositories_query = "show image repositories in account"
        result_set = self._execute_query(repositories_query, cursor_class=DictCursor)
        results = result_set.fetchall()
        if len(results) == 0:
            raise NoImageRepositoriesFoundError()
        sample_repository_url = results[0]["repository_url"]
        if not self._has_url_scheme(sample_repository_url):
            sample_repository_url = f"//{sample_repository_url}"
        return urlparse(sample_repository_url).netloc

    def docker_registry_login(self) -> str:
        registry_url = self.get_registry_url()
        token = self.get_token()
        command = [
            "docker",
            "login",
            "--username",
            "0sessiontoken",
            "--password-stdin",
            registry_url,
        ]
        try:
            return subprocess.check_output(command, input=json.dumps(token), text=True)
        except subprocess.CalledProcessError as e:
            raise ClickException(f"Login Failed: {e.stderr}".strip())
