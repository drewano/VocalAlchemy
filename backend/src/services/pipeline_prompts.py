# PROMPT 1: Identification des Intervenants
PROMPT_INTERVENANTS = """
<prompt>
  <task>
    Identifie les intervenants de la transcription. Pour chaque intervenant, renseigne son nom (si connu), son rôle/fonction, et son affiliation (délégation syndicale, direction, service, etc.).
  </task>
  <input_format>
    Texte brut de la transcription d'une réunion.
  </input_format>
  <output_format>
    Un tableau en Markdown avec les colonnes :
    - Nom
    - Rôle/Fonction
    - Affiliation (si applicable)
  </output_format>
  <example_output>
    | Nom               | Rôle/Fonction                                  | Affiliation        |
    | :---------------- | :--------------------------------------------- | :----------------- |
    | Ahmed             | Responsable informatique régional (RI)         | Direction / Support|
    | Arima Nana        | Titulaire                                      | CGT                |
    | Caroline          | Personne de la direction                       | Direction          |
    | ...               | ...                                            | ...                |
  </example_output>
  <instructions>
    - Analyse le dialogue pour déduire noms, rôles et affiliations.
    - Utilise les informations explicites (ex: "Pour la délégation CGT, les titulaires présents sont Gilles Bacal") et implicites (ex: "Monsieur le Président" référant à Christophe Ferger).
    - Regroupe les rôles similaires ou hiérarchiques (ex: "Manager", "Formateur").
    - Si une personne est mentionnée mais ne parle pas, indique "Mentionné(e)" comme rôle, sauf si un rôle spécifique est donné (ex: "Employé, victime d'un accident").
    - Les "Délégations" (CGT, Sud Solidaire, CFE-CGC) sont des affiliations.
    - Les services ou départements (ADR, DSI, CSU, etc.) sont des affiliations pour les personnels de direction/support.
    - Utilise "Non spécifié" si l'affiliation n'est pas claire.
    - Trie les personnes par ordre alphabétique de leur nom dans le tableau final.
  </instructions>
</prompt>
"""

# PROMPT 2: Structuration de l'Ordre du Jour
PROMPT_ORDRE_DU_JOUR = """
<prompt>
  <task>
    Analyse l'intégralité de la transcription pour identifier les points principaux de l'ordre du jour ou les thèmes de discussion.
    L'objectif est de créer une liste structurée qui servira de squelette pour la synthèse détaillée.
  </task>
  <context>
    - **Transcription originale :** [Ici, tu insères le texte complet de la transcription]
    - **Tableau des intervenants (sortie du prompt 1) :** {intervenants}
  </context>
  <input_format>
    Texte brut de la transcription et un tableau des participants.
  </input_format>
  <output_format>
    Une liste numérotée en Markdown, où chaque élément correspond à un point de l'ordre du jour.
    Le titre de chaque point doit être concis et représentatif du sujet traité.
  </output_format>
  <example_output>
    ```markdown
    1.  Approbation du procès-verbal de la réunion précédente
    2.  Point sur la sécurité et les accidents de travail récents
    3.  Présentation des résultats financiers du trimestre
    4.  Discussion sur la nouvelle politique de télétravail
    5.  Questions diverses
    ```
  </example_output>
  <instructions>
    - Identifie les changements de sujet clairs dans la discussion.
    - Repère les expressions comme "passons au point suivant", "le prochain sujet à l'ordre du jour est...", "concernant le point sur...".
    - Synthétise le titre de chaque point de manière claire.
    - **Ne détaille pas les discussions ici.** Ton seul objectif est de lister les thèmes abordés.
    - Numérote les points dans l'ordre où ils apparaissent dans la transcription.
  </instructions>
</prompt>
"""

# PROMPT 3: Synthèse des Échanges par Point de l'Ordre du Jour
PROMPT_SYNTHESE = """
<prompt>
  <task>
    Pour chaque point de l'ordre du jour fourni, rédige une synthèse des échanges correspondants dans la transcription. Tu dois attribuer chaque prise de parole ou argument clé à la personne concernée, en te basant sur la liste des intervenants.
  </task>
  <context>
    - **Transcription originale :** [Ici, tu insères le texte complet de la transcription]
    - **Tableau des intervenants (sortie du prompt 1) :** {intervenants}
    - **Ordre du jour (sortie du prompt 2) :** {ordre_du_jour}
  </context>
  <input_format>
    Transcription, tableau d'intervenants, et liste des points de l'ordre du jour.
  </input_format>
  <output_format>
    Un texte structuré en Markdown. Chaque point de l'ordre du jour doit commencer par un titre de niveau 3 (`###`), suivi d'une liste à puces résumant les échanges.
  </output_format>
  <example_output>
    ```markdown
    ### Point 2 : Point sur la sécurité et les accidents de travail récents

    - **Christophe Ferger (Direction)** ouvre le point en présentant les statistiques d'accidents du mois, notant une légère hausse.
    - **Arima Nana (CGT)** demande des précisions sur l'accident survenu sur le site de Lyon et questionne les mesures de prévention en place.
    - **Ahmed (RI)** explique que le rapport d'incident est en cours de finalisation et sera partagé sous 48h. Il mentionne qu'une nouvelle formation sécurité est prévue.
    - La discussion s'oriente ensuite sur le matériel de protection individuel (EPI).

    ### Point 3 : Présentation des résultats financiers du trimestre

    - **Caroline (Direction)** présente les résultats, indiquant un chiffre d'affaires en hausse de 5% mais une marge en baisse.
    - **Gilles Bacal (Sud Solidaire)** s'inquiète de l'impact de la baisse de marge sur les primes des salariés.
    ...
    ```
  </example_output>
  <instructions>
    - Parcours l'ordre du jour point par point.
    - Pour chaque point, localise la section correspondante dans la transcription.
    - Résume les arguments, questions, réponses et informations clés.
    - **Crucial :** Assigne chaque intervention à un nom de la liste des intervenants. Utilise le format `**Nom (Affiliation)** : [résumé de son propos]`.
    - Sois fidèle au déroulement des échanges.
    - **Ne te concentre pas sur les décisions formelles ou les actions à ce stade**, cela sera fait dans la prochaine étape. L'objectif ici est de capturer la discussion.
  </instructions>
</prompt>
"""

# PROMPT 4: Extraction des Décisions et Plans d'Action
PROMPT_DECISIONS = """
<prompt>
  <task>
    Analyse la transcription et la synthèse des échanges pour extraire de manière formelle toutes les décisions prises, les votes effectués et les plans d'action convenus.
  </task>
  <context>
    - **Transcription originale :** [Ici, tu insères le texte complet de la transcription]
    - **Tableau des intervenants (sortie du prompt 1) :** {intervenants}
    - **Synthèse des échanges (sortie du prompt 3) :** {synthese}
  </context>
  <input_format>
    Transcription, tableau d'intervenants, et synthèse des discussions.
  </input_format>
  <output_format>
    Un tableau Markdown unique, intitulé "Relevé de décisions et d'actions", avec les colonnes : "Décision / Action", "Responsable(s)", "Échéance (si spécifiée)".
  </output_format>
  <example_output>
    ```markdown
    ### Relevé de décisions et d'actions

    | Décision / Action                                            | Responsable(s)      | Échéance (si spécifiée) |
    | :----------------------------------------------------------- | :------------------ | :---------------------- |
    | Le procès-verbal de la réunion précédente est approuvé à l'unanimité. | Ensemble des membres | N/A                     |
    | Partager le rapport d'incident du site de Lyon.              | Ahmed               | Sous 48h                |
    | Organiser une nouvelle session de formation sécurité.        | Service RH, Ahmed   | Fin du mois prochain    |
    | Fournir une analyse de l'impact de la marge sur les primes.  | Caroline            | Prochaine réunion       |
    | La nouvelle politique de télétravail est rejetée (Vote : 4 contre, 2 pour). | Ensemble des membres | N/A                     |
    ```
  </example_output>
  <instructions>
    - Cherche les verbes et expressions indiquant un accord ou un engagement : "il est décidé que", "nous validons", "je m'engage à", "il faut que [personne] fasse", "acté", "approuvé".
    - Pour chaque action, identifie clairement **qui** est responsable en utilisant les noms de la liste des intervenants.
    - Identifie les échéances si elles sont mentionnées ("d'ici la fin de semaine", "avant le 15 du mois", etc.).
    - Si aucun responsable ou échéance n'est mentionné, indique "Non spécifié".
    - Fais la distinction entre une simple suggestion et une décision actée. Ne liste que les éléments actés ou les engagements clairs.
  </instructions>
</prompt>
"""
