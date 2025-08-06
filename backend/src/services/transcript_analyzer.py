from typing import Dict, List
import os
import textwrap
import langextract as lx


class TranscriptAnalyzer:
    """Module dédié à l'analyse de transcriptions avec LangExtract.

    Cette classe fournit des méthodes pour extraire différentes informations
    à partir d'une transcription.
    """

    def extract_action_plan(self, transcript: str) -> Dict:
        """Extrait un plan d'action à partir d'une transcription.

        Extraction des actions, décisions et engagements, en liant chaque item
        à la personne responsable via l'attribut "responsible" et, si pertinent,
        l'émetteur via "assigned_by".

        Args:
            transcript (str): Le texte de la transcription à analyser.

        Returns:
            Dict: Dictionnaire sérialisé des extractions: {"extractions": [...]}
        """
        if not transcript or not isinstance(transcript, str):
            return {"extractions": []}

        # 1) Définition du prompt pour LangExtract
        prompt_description = textwrap.dedent(
            """
            Analyse la transcription et extrais, dans l'ordre d'apparition, les éléments suivants:
            - action: tâches à réaliser, demandes explicites, points à traiter.
            - decision: décisions actées ou arbitrages explicites.
            - commitment: engagements pris avec une échéance ou une promesse explicite.

            Contraintes:
            - Utilise le texte exact pour extraction_text (pas de paraphrase).
            - Pas de chevauchement d'extractions.
            - Chaque entité doit contenir un attribut "responsible" indiquant la personne responsable
              (le locuteur ou une personne mentionnée). Si applicable, ajoute "assigned_by" pour la personne
              qui a assigné la tâche/prise de décision.
            - Reste concis dans les attributs et privilégie les informations présentes explicitement dans le texte.
            """
        ).strip()

        # 2) Exemple de qualité basé sur la transcription fournie
        example_text = textwrap.dedent(
            """
            Speaker 1 | 09:10.164
            Donc, ce n'est pas forcément les personnes qui n'ont pas souhaité suivre de formation, en l'occurrence. Ça peut être. Et il y a combien de personnes qui n'ont pas fait de formation ces trois dernières années ? 53, C'est ça. Donc, tu vas reprendre au cas par cas toutes les personnes pour voir les raisons pour lesquelles ils n'ont pas suivi. De formation

            Speaker 2 | 09:31.542
            Exactement.
            """
        ).strip()

        examples: List[lx.data.ExampleData] = [
            lx.data.ExampleData(
                text=example_text,
                extractions=[
                    lx.data.Extraction(
                        extraction_class="action",
                        extraction_text="reprendre au cas par cas toutes les personnes",
                        attributes={"responsible": "Gwenaëlla", "assigned_by": "Richard"},
                    )
                ],
            )
        ]

        # 3) Appel à lx.extract en utilisant la clé API via variables d'environnement
        #    LangExtract lira LANGEXTRACT_API_KEY si disponible.
        result = lx.extract(
            text_or_documents=transcript,
            prompt_description=prompt_description,
            examples=examples,
            model_id="gemini-2.5-flash",
            api_key=os.environ.get("LANGEXTRACT_API_KEY"),
        )

        # 4) Retourne une forme robuste et sérialisée
        return {"extractions": [e.to_dict() for e in result.extractions]}
