import google.generativeai as genai

# Define the default system prompt as a constant
DEFAULT_SYSTEM_PROMPT = (
    "Tu es un assistant de synthèse expert. Tu reçois une transcription brute de réunion "
    "accompagnée d'un plan d'action structuré au format JSON (issues de LangExtract). "
    "Ta mission est de t'appuyer sur ces données structurées comme source de vérité pour : "
    "1) générer un résumé clair et concis de la réunion, 2) produire une liste finale d'actions/" 
    "décisions/engagements en respectant strictement les responsabilités et attributions fournies "
    "dans le JSON (ex. attributes.responsible, assigned_by), 3) signaler toute incohérence éventuelle "
    "entre la transcription et le JSON. Le format de sortie doit être en Markdown."
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
        full_transcript should include the enriched transcript with structured JSON.
        """
        if not full_transcript or not isinstance(full_transcript, str):
            raise ValueError("Invalid full_transcript provided")
        if len(full_transcript.strip()) == 0:
            raise ValueError("Empty transcript provided")

        try:
            system_prompt = user_prompt.strip() if user_prompt and user_prompt.strip() else DEFAULT_SYSTEM_PROMPT
            prompt = f"{system_prompt}\n\nTranscription enrichie (incluant JSON du plan d'action):\n{full_transcript}"
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            raise Exception(f"Failed to analyze transcript with Gemini API: {str(e)}")
