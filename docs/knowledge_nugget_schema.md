# Knowledge Nugget Schema Definition

This document defines the structure for a "Knowledge Nugget," the core data object for our community support bot's knowledge base. This schema is designed to capture not just information, but also its context, relevance, and reliability.

## 1. Rationale

The goal is to move beyond simple Question/Answer pairs and create a richer data format that allows for more sophisticated retrieval and generation. By storing summaries, analysis, and metadata like timestamps and status, the RAG system can make better decisions about what information is relevant and trustworthy.

## 2. Schema Definition

A "Knowledge Nugget" will be a JSON object with the following structure:

```json
{
  "topic": "string",
  "timestamp": "string <ISO 8601>",
  "topic_summary": "string",
  "detailed_analysis": "string",
  "status": "string <enum: 'FACT', 'SPECULATION', 'COMMUNITY_OPINION'>",
  "keywords": ["string"],
  "source_message_ids": ["integer"],
  "user_ids_involved": ["string"]
}
```

## 3. Field Descriptions

| Field Name | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `topic` | String | A short, descriptive title for the conversation topic. | `"Oracle Cloud Free Tier Setup"` |
| `timestamp` | String | The ISO 8601 timestamp of the **last** message in the conversation, indicating recency. | `"2025-08-01T12:45:00Z"` |
| `topic_summary` | String | A concise, one-sentence summary of the core topic or question. This is ideal for embedding. | `"How to configure the Oracle Cloud Free Tier for a Telegram bot."` |
| `detailed_analysis` | String | A comprehensive, multi-sentence explanation derived from the conversation. This is the primary content returned to the user. | `"Users confirmed that the best approach is to use an 'Always Free' Ampere A1 Compute instance..."` |
| `status` | Enum | The reliability of the information. | `"FACT"` |
| `keywords` | Array[String] | A list of key terms and entities to aid in keyword-based or hybrid search. | `["oracle cloud", "free tier", "deployment", "systemd"]` |
| `source_message_ids` | Array[Int] | An array of message IDs from the source conversation that were used to generate this nugget. | `[101, 102, 105, 110]` |
| `user_ids_involved` | Array[String] | Anonymized user IDs (e.g., "User_1") of the participants. | `["User_1", "User_5", "User_12"]` |

## 4. Schema Visualization (Mermaid)

```mermaid
graph TD
    A[Conversation Thread] --> B{LLM Processing};
    B --> C[Knowledge Nugget];

    subgraph Knowledge Nugget
        C --> D[nugget_id];
        C --> E[topic_summary];
        C --> F[detailed_analysis];
        C --> G[status];
        C --> H[keywords];
        C --> I[timestamps];
        C --> J[source_ids];
    end

    subgraph Timestamps
        I --> K[first_message];
        I --> L[last_message];
    end

    subgraph Source IDs
        J --> M[message_ids];
        J --> N[user_ids];
    end


## 5. ChromaDB Storage Strategy

To effectively leverage the Knowledge Nugget schema in our RAG pipeline, we will adopt the following storage strategy in ChromaDB:

-   **Document for Embedding:** The `detailed_analysis` field will be used as the primary document for generating embeddings. It provides a richer context for semantic search.

-   **Metadata:** All other fields from the schema will be stored in the metadata payload associated with each embedding. This includes:
    -   `topic`
    -   `timestamp`
    -   `topic_summary`
    -   `status`
    -   `keywords`
    -   `source_message_ids`
    -   `user_ids_involved`

-   **ID:** A dynamically generated UUID will be used as the unique identifier for each entry in the collection.

### Retrieval Workflow

This strategy enables a powerful, two-stage retrieval process:

1.  **Semantic Search:** A user's query is embedded and used to find the top-k most similar `detailed_analysis` vectors from ChromaDB.
2.  **Filtering & Re-ranking:** The metadata from these initial results is then used to filter or re-rank them based on criteria like `status` (e.g., prefer 'FACT' over 'SPECULATION') or `timestamp` (e.g., prefer more recent information). The full `detailed_analysis` is then used to generate the final response.
