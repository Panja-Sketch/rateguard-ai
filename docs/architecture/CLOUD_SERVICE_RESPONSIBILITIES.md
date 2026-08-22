# Cloud Service Responsibilities Matrix

| Service | Primary Responsibility | Content Stored / Executed |
| :--- | :--- | :--- |
| **Cloud Storage** | Binary & Text Artifact Store | Source workbooks (`.xlsx`), filing PDFs, compiled IPIR JSON packages, generated HTML audit reports. |
| **Cloud Firestore** | Workflow State & Evidence Metadata | Assurance run status, workflow stage progress, audit event timeline, evidence lineage records. |
| **Google BigQuery** | Portfolio Analytics Store | 50,000 synthetic policy records, structured SQL predicate filters, exposure result summaries. |
| **Cloud Pub/Sub** | Asynchronous Job Queue | Light job messages (`AssuranceJob`: `run_id`, `job_id`, `source_id`). No raw file payloads. |
| **Cloud Run** *(Future)* | Runtime Execution Engine | FastAPI REST API endpoints & internal Pub/Sub worker subscriber service. |
| **Vertex AI / Gemini** | Agent Reasoning & Synthesis | ADK multi-agent decision making, semantic diff analysis, evidence-backed recommendations. |

