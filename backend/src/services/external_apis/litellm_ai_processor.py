import os
import json
import logging
import litellm


class LiteLLMAIProcessor:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def execute_prompt(self, system_prompt: str, user_content: str) -> str:
        """
        Execute a generic prompt using LiteLLM with Azure AI backend.
        system_prompt: content for the system role
        user_content: content for the user role
        """
        if not isinstance(system_prompt, str) or not system_prompt.strip():
            raise ValueError("Invalid system_prompt provided")
        if not isinstance(user_content, str) or not user_content.strip():
            raise ValueError("Invalid user_content provided")

        messages = [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_content},
        ]

        response = litellm.completion(
            model=f"azure_ai/{self.model_name}",
            messages=messages,
        )
        return response.choices[0].message.content
