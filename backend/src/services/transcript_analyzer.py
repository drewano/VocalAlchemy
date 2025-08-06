from typing import Dict, List, Any
import os
import textwrap
import dataclasses
import langextract as lx


class TranscriptAnalyzer:
    """
    Module d'analyse de transcriptions optimisé pour extraire un plan d'action
    détaillé et structuré, destiné à alimenter un LLM de synthèse.
    """

    def _serialize_extraction(self, extraction: lx.data.Extraction) -> Dict[str, Any]:
        """Sérialise un objet Extraction en un dictionnaire."""
        return {
            'extraction_class': extraction.extraction_class,
            'extraction_text': extraction.extraction_text,
            'attributes': extraction.attributes,
            # (Optionnel) Ajout des positions pour le débogage ou le mapping
            'char_interval': (
                dataclasses.asdict(extraction.char_interval)
                if extraction.char_interval
                else None
            ),
        }

    def extract_action_plan(self, transcript: str) -> Dict:
        """
        Extrait un plan d'action de la plus haute qualité possible à partir
        d'une transcription.

        Le résultat est conçu pour être l'entrée parfaite pour un LLM chargé de
        générer un résumé et une liste de points d'action en Markdown.

        Args:
            transcript (str): Le texte de la transcription à analyser.

        Returns:
            Dict: Dictionnaire sérialisé des extractions {"extractions": [...]}.
        """
        if not transcript or not isinstance(transcript, str):
            return {"extractions": []}

        # 1) AMÉLIORATION : Prompt enrichi pour plus de robustesse
        # Ajout d'instructions sur la synthèse du "topic" et la rigueur.
        prompt_description = textwrap.dedent(
            """
            Tu es un analyste expert en transcriptions de réunions professionnelles. Ta mission est d'extraire un plan d'action structuré et détaillé. Analyse la transcription et extrais, dans l'ordre d'apparition, les éléments suivants :
            - action: Une tâche concrète à réaliser, une vérification à faire, un point à investiguer, une demande d'information à obtenir.
            - decision: Un arbitrage officiel, une validation de processus, une conclusion actée par le groupe.
            - commitment: Un engagement ou une promesse faite à une ou plusieurs personnes, souvent avec une notion de temporalité.

            Pour chaque extraction, tu dois fournir les attributs suivants avec une rigueur absolue :
            - "topic" (obligatoire): Synthétise le sujet de discussion général en quelques mots (ex: "Contrats Prépa", "Incident prestataire Eurest", "Bilan Social", "Gestion des jurys"). Le topic est souvent implicite et doit être déduit du contexte.
            - "responsible" (obligatoire): Qui est chargé de l'action/décision ? Identifie la personne par "Speaker X" ou son nom si mentionné. Si "on" est utilisé, attribue-le au locuteur principal du sujet (souvent celui qui répond aux questions).
            - "assigned_by" (optionnel): Si un locuteur assigne la tâche à un autre, indique qui assigne (par ex. "Speaker 2" qui pose une question menant à une action).
            - "participants" (optionnel): Liste les autres personnes ou groupes mentionnés dans l'action (ex: ["Caroline", "le niveau national", "Guillaume Eluin"]).
            - "deadline" (optionnel): Si une échéance est mentionnée, capture-la précisément (ex: "demain", "fin juin", "mi-juillet", "jeudi").

            Règles fondamentales :
            1. Utilise le texte EXACT de la transcription pour 'extraction_text'. Ne paraphrase jamais.
            2. Ne fais jamais chevaucher les extractions. Une portion de texte ne peut appartenir qu'à une seule extraction.
            3. Sois méticuleux et exhaustif. La qualité de ces données structurées est critique pour la synthèse finale.
            """
        ).strip()

        # 2) EXEMPLES : Les exemples existants sont de très haute qualité et
        # bien ciblés. Nous les conservons car ils couvrent des cas variés
        # et complexes présents dans la transcription.
        examples: List[lx.data.ExampleData] = [
            lx.data.ExampleData(
                text=textwrap.dedent("""
                    Speaker 4 | 11:23.821
                    [...] il y a un réel besoin. Alors voilà, je m'interroge aussi.
                    Speaker 0 | 12:04.718
                    Ok, merci. Je reparle à Caroline demain.
                """).strip(),
                extractions=[
                    lx.data.Extraction(
                        extraction_class="action",
                        extraction_text="Je reparle à Caroline demain",
                        attributes={
                            "topic": "Besoin en jurys",
                            "responsible": "Speaker 0",
                            "participants": ["Caroline"],
                            "deadline": "demain",
                            "assigned_by": "Speaker 4"
                        },
                    )
                ],
            ),
            lx.data.ExampleData(
                text=textwrap.dedent("""
                    Speaker 1 | 31:04.033
                    Donc, la question est de dire, est-ce qu'on demande à Eurest, est-ce que ça a été fait de demander à Eurest de nous mettre quelqu'un d'autre
                    Speaker 0 | 31:57.394
                    [...] Je n'ai pas repris du tout l'angle avec Guillaume Eluin pour voir où ça en était. Donc, je vais le ressaisir pour voir si lui est au courant de la situation.
                """).strip(),
                extractions=[
                    lx.data.Extraction(
                        extraction_class="action",
                        extraction_text="je vais le ressaisir pour voir si lui est au courant de la situation",
                        attributes={
                            "topic": "Incident à Stains avec prestataire Eurest",
                            "responsible": "Speaker 0",
                            "participants": ["Guillaume Eluin"],
                        },
                    )
                ],
            ),
            lx.data.ExampleData(
                text=textwrap.dedent("""
                    Speaker 0 | 03:52.248
                    Non, Ça va dépendre de l'activité d'un certain nombre de CDI. Et puis, On va regarder au cas par cas, sur le parcentre, les personnes qui sont reconduites ou pas.
                    Speaker 0 | 04:04.263
                    Donc, l'information leur sera donnée au plus tard. mi-juillet.
                """).strip(),
                extractions=[
                    lx.data.Extraction(
                        extraction_class="decision",
                        extraction_text="On va regarder au cas par cas, sur le parcentre, les personnes qui sont reconduites ou pas",
                        attributes={
                            "topic": "Reconduction des contrats CDD Prépa",
                            "responsible": "Speaker 0",
                        },
                    ),
                    lx.data.Extraction(
                        extraction_class="commitment",
                        extraction_text="l'information leur sera donnée au plus tard. mi-juillet",
                        attributes={
                            "topic": "Reconduction des contrats CDD Prépa",
                            "responsible": "Speaker 0",
                            "participants": ["les salariés"],
                            "deadline": "mi-juillet"
                        },
                    ),
                ],
            )
        ]

        # 3) AMÉLIORATION : Appel à lx.extract avec des paramètres optimisés
        # pour la qualité et la complétude sur des textes longs.
        result = lx.extract(
            text_or_documents=transcript,
            prompt_description=prompt_description,
            examples=examples,
            model_id="gemini-2.5-flash",  # Modèle récent, rapide et performant
            api_key=os.environ.get("LANGEXTRACT_API_KEY"),
            
            # La contrainte de schéma force la sortie à être un JSON valide.
            # C'est une excellente pratique que vous aviez déjà.
            use_schema_constraints=True,
            
            # Avec les contraintes de schéma de Gemini, les `fences` (```json)
            # ne sont pas nécessaires et peuvent être désactivées.
            fence_output=False,
            
            # Une température légèrement > 0 peut aider le modèle à éviter les
            # répétitions tout en restant factuel grâce au schéma. 0.3 est un bon compromis.
            temperature=0.3,
            
            # NOUVEAU : Plusieurs passes d'extraction pour une meilleure couverture.
            # Augmente le rappel en trouvant des entités manquées lors de la première passe.
            # Essentiel pour les transcriptions denses.
            extraction_passes=2,
            
            # NOUVEAU : Gestion explicite de la taille des chunks.
            # Assure que chaque chunk envoyé au LLM a un contexte suffisant
            # sans être trop large, ce qui améliore la précision locale.
            max_char_buffer=2000,
            
            # Un nombre élevé de workers accélère le traitement des longs transcripts
            # en parallélisant les appels API.
            max_workers=10
        )

        # 4) Retourne les données structurées prêtes pour la synthèse
        return {"extractions": [self._serialize_extraction(e) for e in result.extractions]}