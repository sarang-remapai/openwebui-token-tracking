import os
import requests
import json
from pydantic import BaseModel, Field
from typing import Generator, Any, Tuple
from .base_tracked_pipe import BaseTrackedPipe, RequestError, TokenCount


class AzureOpenAITrackedPipe(BaseTrackedPipe):
    """
    Azure OpenAI-specific implementation of the BaseTrackedPipe for handling API requests
    to Azure's OpenAI endpoints with token tracking.

    Azure OpenAI has a different API structure than standard OpenAI:
    - Uses api-key header instead of Bearer token
    - Uses deployment names in URL path
    - Requires api-version query parameter

    This class handles authentication, request formatting, and response processing
    specific to the Azure OpenAI API while leveraging the base class's token tracking
    functionality.
    """

    class Valves(BaseModel):
        """Configuration parameters for Azure OpenAI API connections."""
        API_KEY: str = Field(
            default="",
            description="API key for authenticating requests to Azure OpenAI.",
        )
        AZURE_ENDPOINT: str = Field(
            default="",
            description="Full Azure OpenAI endpoint URL (e.g., 'https://privateai-apse1-resource.cognitiveservices.azure.com' or 'https://your-resource.openai.azure.com')",
        )
        API_VERSION: str = Field(
            default="2024-08-01-preview",
            description="Azure OpenAI API version",
        )
        PROVIDER: str = Field(
            default="azure_openai", description="Name of the model provider."
        )
        DEBUG: bool = Field(default=False)

    def __init__(self):
        """Initialize the Azure OpenAI pipe with API endpoint and configuration."""
        self.valves = self.Valves(
            **{
                "API_KEY": os.getenv("AZURE_OPENAI_API_KEY", ""),
                "AZURE_ENDPOINT": os.getenv("AZURE_ENDPOINT", ""),
            }
        )
        super().__init__(
            # Provider and URL are read from Valves for each request
            provider="",
            url="",
        )

    def _headers(self) -> dict:
        """
        Build headers for Azure OpenAI API requests.

        Azure uses 'api-key' header instead of 'Authorization: Bearer'.

        :return: Dictionary containing api-key and content-type headers
        :rtype: dict
        """
        return {
            "api-key": self.valves.API_KEY,
            "content-type": "application/json",
        }

    def _payload(self, model_id: str, body: dict) -> dict:
        """
        Format the request payload for Azure OpenAI API.

        Azure OpenAI uses deployment names, but we'll use model_id as the deployment name.
        The actual deployment name mapping happens in the URL construction.

        :param model_id: The deployment name in Azure (what you configured in Azure Portal)
        :type model_id: str
        :param body: The request body containing messages and parameters
        :type body: dict
        :return: Formatted payload for the API request, including deployment_name for URL construction
        :rtype: dict
        """
        # Azure doesn't need 'model' in payload, but we keep deployment_name for URL
        payload = {**body}
        payload.pop("model", None)  # Remove model if it exists
        payload["deployment_name"] = model_id  # Store for URL construction
        return payload

    def _build_url(self, deployment_name: str) -> str:
        """
        Build the Azure OpenAI API URL with deployment name and API version.

        :param deployment_name: The deployment name configured in Azure Portal
        :type deployment_name: str
        :return: Complete API endpoint URL
        :rtype: str
        """
        # Remove trailing slash if present
        base_url = self.valves.AZURE_ENDPOINT.rstrip('/')
        return (
            f"{base_url}/openai/deployments/{deployment_name}/chat/completions"
            f"?api-version={self.valves.API_VERSION}"
        )

    def _make_stream_request(
        self, headers: dict, payload: dict
    ) -> Tuple[TokenCount, Generator[Any, None, None]]:
        """
        Make a streaming request to the Azure OpenAI API.

        :param headers: HTTP headers for the request
        :type headers: dict
        :param payload: Request payload
        :type payload: dict
        :return: Tuple of (TokenCount, response generator)
        :rtype: Tuple[TokenCount, Generator[Any, None, None]]
        :raises RequestError: If the API request fails
        """
        tokens = TokenCount()
        deployment_name = payload.pop("deployment_name")

        def generate_stream():
            try:
                self.url = self._build_url(deployment_name)
                stream_payload = {**payload, "stream_options": {"include_usage": True}}

                if self.valves.DEBUG:
                    print(f"Azure OpenAI Request URL: {self.url}")
                    print(f"Azure OpenAI Headers: {headers}")
                    print(f"Azure OpenAI Payload: {stream_payload}")

                with requests.post(
                    url=self.url,
                    headers=headers,
                    json=stream_payload,
                    stream=True,
                    timeout=(3.05, 60),
                ) as response:
                    if response.status_code != 200:
                        error_text = response.text
                        raise RequestError(
                            f"HTTP Error {response.status_code}: {error_text}"
                        )

                    for line in response.iter_lines():
                        if line:
                            line = line.decode("utf-8")
                            if line.startswith("data: "):
                                try:
                                    data = json.loads(line[6:])
                                    if data.get("usage", None):
                                        tokens.prompt_tokens = data["usage"].get(
                                            "prompt_tokens"
                                        )
                                        tokens.response_tokens = data["usage"].get(
                                            "completion_tokens"
                                        )
                                except json.JSONDecodeError:
                                    print(f"Failed to parse JSON: {line}")
                                except KeyError as e:
                                    print(f"Unexpected data structure: {e}")
                                    print(f"Full data: {data}")
                        yield line
            except requests.exceptions.RequestException as e:
                error_msg = str(e).encode('ascii', 'ignore').decode('ascii')
                raise RequestError(f"Request failed: {error_msg}")
            except Exception as e:
                error_msg = str(e).encode('ascii', 'ignore').decode('ascii')
                raise RequestError(f"Unexpected error: {error_msg}")

        return tokens, generate_stream()

    def _make_non_stream_request(
        self, headers: dict, payload: dict
    ) -> Tuple[TokenCount, Any]:
        """
        Make a non-streaming request to the Azure OpenAI API.

        :param headers: HTTP headers for the request
        :type headers: dict
        :param payload: Request payload
        :type payload: dict
        :return: Tuple of (TokenCount, response data)
        :rtype: Tuple[int, int, Any]
        :raises RequestError: If the API request fails
        """
        try:
            deployment_name = payload.pop("deployment_name")
            self.url = self._build_url(deployment_name)

            if self.valves.DEBUG:
                print(f"Azure OpenAI Request URL: {self.url}")
                print(f"Azure OpenAI Headers: {headers}")
                print(f"Azure OpenAI Payload: {payload}")

            response = requests.post(
                self.url, headers=headers, json=payload, timeout=(3.05, 60)
            )

            if response.status_code != 200:
                error_text = response.text
                raise RequestError(f"HTTP Error {response.status_code}: {error_text}")

            res = response.json()
            tokens = TokenCount()
            tokens.prompt_tokens = res["usage"]["prompt_tokens"]
            tokens.response_tokens = res["usage"]["completion_tokens"]

            return tokens, res
        except requests.exceptions.RequestException as e:
            error_msg = str(e).encode('ascii', 'ignore').decode('ascii')
            raise RequestError(f"Request failed: {error_msg}")
        except Exception as e:
            error_msg = str(e).encode('ascii', 'ignore').decode('ascii')
            raise RequestError(f"Unexpected error: {error_msg}")

    def pipes(self):
        self.provider = self.valves.PROVIDER
        return super().pipes()

    def pipe(self, body, __user__, __metadata__):
        self.provider = self.valves.PROVIDER
        return super().pipe(body, __user__, __metadata__)
