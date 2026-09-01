System Design:
approach: batch processing due to the small size of transactions expected on a daily basis. on average, the number of expected daily transactions, transfers, and promotions is single digit. as such data loading and transformation can be done in batch. for purposes of the this project, i am deifning it on a dialy basis. 

tradeoffs:
1. batch processing.
    - why? simple to implement, easy to maintain, and can be scheduled to run at off-peak hours.
    - drawback: not real-time, we might miss fradulent transfers. 
2. consistency over avalibility. 
    - why: we can ensure that the data is consistent across all users. this is a financial services app, as such customers want their funds and transactions to be accurate and consistent. additionally users are technical and nontechnical members of venmito, as such avalibility is not as important as consistency.
    - drawback: users might not be able to access the data at all times. however, this is a tradeoff we are willing to make for the sake of consistency.
3. stateless:
    - why? it is an internal tool. we dont need to remember users information for any client requirements. 

4. data storage: sqlite
    - why: structured data simple to implement, easy to maintain, and can be scheduled to run at off-peak hours.
    - drawback: not real-time, we might miss fradulent transfers.

5. protocol: rest api
    -why? this is not a real time system, and we can use a rest api to expose the data to the users. additionally, it is simple to implement and easy to maintain.
    
    
These choices priorityze current needs. in the future, when the volume of transactions increases, we can consider moving to a more robust data storage solution and a more complex architecture integrating real time processing, avlaiibility, etc...



```
                       +-----------------------------------+
                       |           ADMIN USERS             |
                       +-----------------------------------+
                                   |           |
               (Non-Technical Users)           (Technical Users)
              Dashboard & Manual Upload         Database View & ML API
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
|  * File Upload Endpoint         |             |  * Database Viewer Interface    |
|  * Visualizations Engine        |             |  * REST/gRPC API for Data Pull  |
|  * Summary Statistics Generator |             |  * Model Training Data Export   |
+---------------------------------+             +---------------------------------+
                 |                                               |
                 | (Manual Uploads)                              | (Direct API Queries)
                 v                                               v
+---------------------------------------------------------------------------------+
|                                 APP ENGINE                                      |
|                                                                                 |
|   +-------------------------------------------------------------------------+   |
|   |                       DATA PIPELINE & ETL ENGINE                        |   |
|   |  * Ingestion: Ingest CSV, JSON, XML (Manual & Scheduled Transfers)      |   |
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
|  +-----------------------------------+   +-----------------------------------+  |
|  |       PERSISTENT DATABASE         |   |         OBJECT STORAGE            |  |
|  |  (Cloud SQL or SQLite on Disk)    |   |     (Google Cloud Storage)        |  |
|  |                                   |   |                                   |  |
|  |  * Unified Clean Schemas          |   |  * Raw Uploaded File Archives     |  |
|  |  * Normalized Analytics Tables    |   |  * Model Artifacts (.pkl/.joblib) |  |
|  |  * Audit & Ingestion Logs         |   |                                   |  |
|  +-----------------------------------+   +-----------------------------------+  |
|                                                                                 |
+---------------------------------------------------------------------------------+

```

### System Architecture Breakdown

**1. Entry Point & Role Routing**

* **Frontend Gateway:** Single entry point (domain) where users choose their experience. Authentication determines if a user can access technical endpoints or just the non-technical dashboard.

**2. Data Processing & Pipeline (ETL)**

* **Ingestion Layer:** Accepts CSV, JSON, and XML files either via manual upload from non-technical users or through the scheduled cron job/transfer system.
* **Transformation Engine:** Parses incoming files into memory, applies schema rules, standardizes column types/names, and normalizes the payload into a uniform record structure.
* **Storage Dispatcher:** Writes raw copies of incoming files to Object Storage for auditing/recovery, then commits clean records to the persistent database.

**3. Dual Interaction Modules**

* **Non-Technical Interface:** Reads aggregate data directly from the persistent database to generate real-time charts, KPIs, and summary metrics. Triggers the ingestion pipeline when a user uploads a new file.
* **Technical Interface & API:** Exposes read-only views into raw database tables, structured SQL query capabilities, and high-throughput REST/gRPC endpoints designed for pulling clean datasets into machine learning frameworks (e.g., training fraud models).

**4. Storage Layer**

* **Database:** Houses the normalized schema. Receives writes from the transformation engine and responds to read queries from both user interfaces.
* **Object Storage:** Retains immutable raw uploads and serves as a repository for stored machine learning model binaries.
    

We are using a provider for SQL database. 
-Why? A managed database is one that does not require as much administration and operational support (creating databases, performing backups, updating the database instances and the underlying operating system) as an self-managed database.

-Cloud SQL by Google Cloud, enable customers to satisfy a wide range of government and industry regulatory compliance requirements across the world. Venmito is a financial services company. 

