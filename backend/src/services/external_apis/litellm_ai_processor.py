import logging
import litellm


class LiteLLMAIProcessor:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    async def execute_prompt(self, system_prompt: str, user_content: str) -> str:
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

        # Build full model name with provider prefix exactly once
        sanitized_model_name = (self.model_name or "").strip()
        full_model_name = (
            sanitized_model_name
            if "/" in sanitized_model_name
            else f"azure_ai/{sanitized_model_name}"
        )

        logging.info("LiteLLM calling model='%s' via Azure AI", full_model_name)
        response = await litellm.acompletion(
            model=full_model_name,
            messages=messages,
        )
        return response.choices[0].message.content
