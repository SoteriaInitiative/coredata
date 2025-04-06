# About the Project
The Core Data standard is part of the [Soteria Initiative](https://soteria-initiative.org/) to establish common financial
crime data standards and includes the customer and entity data elements, collectively 
party data records, as well as transaction record standards.

Such standards are vital for financial crime professionals and systems alike.
The standards allow financial crime professionals to express criminal activity patterns
using concrete data examples. Systems such as cross-entity federated learning algorithms
need the standards so that they can rely on homogeneous input data for training and inference.

The standards are a minimum set of data elements for the objective but build on
existing more comprehensive definitions such as:
- [Financial Market Standard Body Customer Onboarding Standard](https://fmsb.com/wp-content/uploads/2024/12/20241217_Standard-for-COB_FINAL.pdf)
- [SWIFT ISO 20022 Messaging Standard](https://www2.swift.com/knowledgecentre/products/Standards%20MX/publications?protected=true&reload-date=1743955486276) (free account required)

To make the standards useful synthetic data generators will be provided and a reference
implementation of a data editor will allow the encoding of actual financial crime patterns.

# Getting Started
1. Clone the repo
```zsh
git clone https://github.com/SoteriaInitiative/coredata.git
cd coredata
```
2. Install the required dependencies
```zsh
pip install -r requirements.txt
```
3. Provide application configuration and create a service account on GCP and add a JSON key with edit permissions.
Safe the key to ``implementation/gcp-credentials/gcp-key.json`` - create the gcp-credentials folder if you don't have it.
Next, provide the proper application configurations. 
Create a ``.env`` file in the implementation root ``coredata/implementation/`` with
the following content:
```text
NUM_ROUNDS=1
GCS_BUCKET_NAME=soteria-core-data
GOOGLE_APPLICATION_CREDENTIALS=implementation/gcp-credentials/gcp-key.json
```
4. Set the Google Cloud parameters
```zsh
gcloud auth login
gcloud config set project <PROJECT_ID>
```
Now create the storage bucket and replace `us-central1` with your desired location:
```zsh
gcloud storage buckets create gs://soteria-core-data \
    --location=us-central1 \
    --default-storage-class=STANDARD

```
5. Run synthetic data generator:
```zsh
python implementation/generator.py
```
To review the raw data for ``Bank_1`` on a terminal run:
```zsh
gsutil cp gs://soteria-core-data/Bank_1_transactions.json .
cat Bank_1_transactions.json | jq . | more
```

# Project Structure
To find your way around please find a quick overview of the project structure.
```
coredata/
├── documentation/              # Use cases & design documentation
├── example/                    # Example dataset implementing the standard
├── implementation/             # Example data generator and pattern editor
├── gcp-credentials/            # Credentials for Google Cloud (you may need to create the folder)
├── standard/                   # Standard specification
├── README.md                   # This file
└── LICENSE                     # License file
```
# Contributing
Contributions are welcome! To get started:

1. Fork the project. 
2. Create a new feature branch: git checkout -b feature/<new-feature>. 
3. Commit your changes: git commit -m 'Add some feature'. 
4. Push to your branch: git push origin feature/<new-feature>. 
5. Open a Pull Request in the main repository.
# License
This project is licensed under the MIT License.
Feel free to use, modify, and distribute this project as per the terms of the license.
# Contact
Project Maintainer: Soteria Initiative – @SoteriaInitiative – contact@soteria-initiative.org
Repository: SoteriaInitiative/coredata
For general inquiries or discussion, please open an issue.