import google.generativeai as genai

# Additional instruction used in prompts
PEOPLE_INVOLVED_INSTRUCTION = (
    "À la fin de ta réponse, ajoute une section distincte intitulée '### Personnes Concernées' et liste, en utilisant des puces, les noms des personnes mentionnées dans la transcription en lien avec des actions ou des décisions."
)

# Define the default system prompt as a constant
DEFAULT_SYSTEM_PROMPT = (
    "Tu es un assistant de synthèse expert. Voici la transcription d'une réunion. "
    "Analyse-la et fournis un résumé concis suivi d'une liste de points d'action "
    "(actions à réaliser, décisions prises) avec les personnes concernées si mentionnées. "
    "Le format de sortie doit être en Markdown. "
    f"{PEOPLE_INVOLVED_INSTRUCTION}"
)


class GoogleAIProcessor:
    def __init__(self, api_key: str, model_name: str = 'gemini-2.5-flash') -> None:
        if not api_key or not isinstance(api_key, str):
            raise ValueError("Invalid Google API key provided")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    def analyze_transcript(self, full_transcript: str, user_prompt: str = None) -> str:
        """
        Analyze a transcript using Google's Gemini model.
        """
        if not full_transcript or not isinstance(full_transcript, str):
            raise ValueError("Invalid full_transcript provided")
        if len(full_transcript.strip()) == 0:
            raise ValueError("Empty transcript provided")

        try:
            system_prompt = user_prompt.strip() if user_prompt and user_prompt.strip() else DEFAULT_SYSTEM_PROMPT
            prompt = f"{system_prompt}\n\nTranscription:\n{full_transcript}"
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            raise Exception(f"Failed to analyze transcript with Gemini API: {str(e)}")