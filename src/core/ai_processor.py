import google.generativeai as genai
from src.config import GOOGLE_API_KEY


def analyze_transcript(full_transcript: str) -> str:
    """
    Analyze a transcript using Google's Gemini 2.5 Flash model.
    
    Args:
        full_transcript (str): The complete transcript to analyze
        
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
        
        # Define the system prompt
        system_prompt = (
            "Tu es un assistant de synthèse expert. Voici la transcription d'une réunion. "
            "Analyse-la et fournis un résumé concis suivi d'une liste de points d'action "
            "(actions à réaliser, décisions prises) avec les personnes concernées si mentionnées. "
            "Le format de sortie doit être en Markdown."
        )
        
        # Combine the system prompt with the transcript
        prompt = f"{system_prompt}\n\nTranscription:\n{full_transcript}"
        
        # Generate the content
        response = model.generate_content(prompt)
        
        # Return the response text
        return response.text
    
    except Exception as e:
        # Re-raise the exception with additional context
        raise Exception(f"Failed to analyze transcript with Gemini API: {str(e)}")