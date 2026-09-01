High level design based on what I found on the data and the requirements. The design is based on a dual interface system, one for non-technical users and one for technical users. The non-technical users will have a UI with visualizations and manual upload capabilities, while the technical users will have access to a database view and an API for data exporting.

```
                       +-----------------------------------+
                       |           ADMIN USERS             |
                       +-----------------------------------+
                                   |           |
               (Non-Technical Users)           (Technical Users)
              UI & Manual Upload          Endpoints, Questionable Uploads, and Exports
                                   |           |
                                   v           v
                       +-----------------------------------+
                       |      FRONTEND / INTERFACE GATEWAY  |
                       |       (Role Selection & Auth)     |
                       +-----------------------------------+
                                   |           |
                 +-----------------+           +-----------------+
                 |                                               |
                 v                                               v
+---------------------------------+             +---------------------------------+
|      NON-TECHNICAL MODULE       |             |        TECHNICAL MODULE         |
|  * File Upload Endpoint         |             |  * Database Overviews           |
|  * Visualizations               |             |  * REST API Endpoints  |
|  * Summary Statistics Generator |             |  * Model Training Data Export   |
+---------------------------------+             +---------------------------------+
                 |                                               |
                 | (Manual Uploads)                              | (Direct Exports )
                 v                                               v
+---------------------------------------------------------------------------------+
|                                 APP ENGINE                                      |
|                                                                                 |
|   +-------------------------------------------------------------------------+   |
|   |                       DATA PIPELINE & ETL ENGINE                        |   |
|   |  * Ingestion: Ingest CSV, JSON, XML (Manual Transfers)                  |   |
|   |  * Validation: Schema check, type conversion, data cleaning             |   |
|   |  * Normalization: Map all formats to unified relational schema          |   |
|   +-------------------------------------------------------------------------+   |
|                                        |                                        |
+----------------------------------------|----------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                               PERSISTENT STORAGE                                |
|                                                                                 |
|  +-----------------------------------+                                          |
|  |       PERSISTENT DATABASE         |                                          |
|  |  (PostgreSQL  Supabase)           |                                          |
|  |                                   |                                          |
|  |  * Unified Clean Schemas          |                                          |
|  |  * Normalized Analytics Tables    |                                          |
|  |  * Audit & Ingestion Logs         |                                          |
|  +-----------------------------------+                                          | 
|                                                                                 |
+---------------------------------------------------------------------------------+

