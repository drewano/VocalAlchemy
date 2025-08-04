# Predefined prompts for the AI analysis
PREDEFINED_PROMPTS = {
    "Synthèse de réunion": (
        "Tu es un assistant de synthèse expert. Voici la transcription d'une réunion. "
        "Analyse-la et fournis un résumé concis suivi d'une liste de points d'action "
        "(actions à réaliser, décisions prises) avec les personnes concernées si mentionnées. "
        "Le format de sortie doit être en Markdown."
    ),
    "Analyse de sentiment": (
        "Tu es un expert en analyse de sentiment. Analyse la transcription suivante et "
        "détermine le sentiment général du texte (positif, négatif ou neutre). "
        "Identifie également les émotions spécifiques exprimées (joie, colère, tristesse, etc.) "
        "et cite des extraits pertinents pour justifier ton analyse. "
        "Présente tes résultats de manière structurée en Markdown."
    ),
    "Extraction d'entités": (
        "Tu es un expert en extraction d'entités nommées. À partir de la transcription fournie, "
        "extrais et catégorise les entités importantes telles que les noms de personnes, "
        "d'organisations, de lieux, de dates, de chiffres et d'autres éléments pertinents. "
        "Présente les résultats dans un format Markdown organisé par catégories."
    )
}