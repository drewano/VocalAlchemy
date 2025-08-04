import google.generativeai as genai
from src.config import GOOGLE_API_KEY

# Define the default system prompt as a constant
DEFAULT_SYSTEM_PROMPT = (
    "Tu es un assistant de synthèse expert. Voici la transcription d'une réunion. "
    "Analyse-la et fournis un résumé concis suivi d'une liste de points d'action "
    "(actions à réaliser, décisions prises) avec les personnes concernées si mentionnées. "
    "Le format de sortie doit être en Markdown. "
    "À la fin de ta réponse, ajoute une section distincte intitulée '### Personnes Concernées' et liste, en utilisant des puces, les noms des personnes mentionnées dans la transcription en lien avec des actions ou des décisions."
)


def analyze_transcript(full_transcript: str, user_prompt: str = None) -> str:
    """
    Analyze a transcript using Google's Gemini 2.5 Flash model.
    
    Args:
        full_transcript (str): The complete transcript to analyze
        user_prompt (str, optional): Custom prompt to override the default system prompt
        
    Returns:
        str: The analysis result in Markdown format
        
    Raises:
        Exception: If the API call fails
        ValueError: If full_transcript is invalid
    """
    # Validate inputs
    if not full_transcript or not isinstance(full_transcript, str):
        raise ValueError("Invalid full_transcript provided")
    
    if len(full_transcript.strip()) == 0:
        raise ValueError("Empty transcript provided")
    
    try:
        # Configure the API
        genai.configure(api_key=GOOGLE_API_KEY)
        
        # Instantiate the model
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Use user_prompt if provided and not empty, otherwise use default
        base_prompt = user_prompt if user_prompt and user_prompt.strip() else DEFAULT_SYSTEM_PROMPT
        instruction = " À la fin de ta réponse, ajoute une section distincte intitulée '### Personnes Concernées' et liste, en utilisant des puces, les noms des personnes mentionnées dans la transcription en lien avec des actions ou des décisions."
        system_prompt = f"{base_prompt}{instruction}" if (user_prompt and user_prompt.strip()) else base_prompt
        
        # Combine the system prompt with the transcript
        prompt = f"{system_prompt}\n\nTranscription:\n{full_transcript}"
        
        # Generate the content
        response = model.generate_content(prompt)
        
        # Return the response text
        return response.text
    
    except Exception as e:
        # Re-raise the exception with additional context
        raise Exception(f"Failed to analyze transcript with Gemini API: {str(e)}")