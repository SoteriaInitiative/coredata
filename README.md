# About the Project
The Core Data standard is part of the [Soteria Initiative](https://soteria-initiative.org/) to establish common financial
crime data standards and includes the customer and entity data elements, collectively 
party data records, as well as transaction record standards.

As per the current release 95% of core standards are covered exemplified below:

| Region        | Network / System       | Standard / Format           | Coverage | 
|---------------|-------------------------|------------------------------|----------------------------|
| **Europe**    | SEPA (EU)               | ISO 20022 (`pain.001`, `pacs.008`) | ✅ ~95%                     | 
| **Global**    | SWIFT (MT/MX)           | MT103 / ISO 20022 (`pacs.009`) | ✅ ~95%                  | 

Such standards are vital for financial crime professionals and systems alike.
The standards allow financial crime professionals to express criminal activity patterns
using concrete data examples. Systems such as cross-entity federated learning algorithms
need the standards so that they can rely on homogeneous input data for training and inference.

The standards are a minimum set of data elements for the objective but build on
existing more comprehensive definitions such as:
- [Financial Market Standard Body Customer Onboarding Standard](https://fmsb.com/wp-content/uploads/2024/12/20241217_Standard-for-COB_FINAL.pdf)
- [SWIFT ISO 20022 Messaging Standard](https://www2.swift.com/knowledgecentre/products/Standards%20MX/publications?protected=true&reload-date=1743955486276) (free account required)

To make the standards useful synthetic data generators is provided and a reference
implementation of a data editor will allow the encoding of actual financial crime patterns.

# 🕹 Getting Started
1. Clone the repo
```zsh
git clone https://github.com/SoteriaInitiative/coredata.git
cd coredata
```
2. Install the required dependencies
```zsh
brew install python
brew install --cask google-cloud-sdk
pip install -r app/requirements.txt
```
<details>
    <summary>💡Hint if you don't have 'brew':</summary>

If you do not have the ``brew`` tool installed, open a terminal
window and type: 
```zsh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

If you are using an Intel Mac computer type the following after the installation:
```zsh
echo 'eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"' >> ~/.bashrc
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
```

If you are using an Apple Silicon (M1, M2, etc.) computer type the following after the installation:
```zsh
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

You can verify the installation by typing:
```zsh
brew doctor
```

If terminal prints ``Your system is ready to brew`` everything worked OK.

</details>

3. Provide application configuration and create a service account on GCP and add a JSON key with edit permissions.
Safe the key to ``gcp-credentials/gcp-key.json`` - create the gcp-credentials folder if you don't have it.
Next, provide the proper application configurations. 
Create a ``.env`` file in the implementation root ``coredata/implementation`` with
the following content:
```text
GCS_BUCKET_NAME=soteria-core-data
GOOGLE_APPLICATION_CREDENTIALS=gcp-credentials/gcp-key.json
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
<details>
    <summary>💡Hint how to interpret the data:</summary>

Observe that each bank detects only a small set of transaction 
(local_label is 1 but global is 1) but the vast majority
of illicit transactions is not detected (local_label is 0 but global is 1) 
because these are not part of the local knowledge/scenario pool.

</details>

# 🗄️ Project Structure
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
# 🛠️ Contributing
Contributions are welcome! To get started:

1. Fork the project. 
2. Create an issue to work on at git-hub
2. Create a new feat, doc or std branch (replace feat with doc or std): git checkout -b feat/<issue-#>-<change>. 
3. Commit your changes: git commit -m 'Commit message'. 
4. Push to your branch: git push origin feat/<issue-#>-<change>. 
5. Open a pull request in the main repository.

# 🚀 Features

This release includes the following key features:
- 95% of SWIFT attributes are covered but RTP identifiers are missing
- Comprehensive personal identify attributes for entity identification

# ⚠️ Limitations:
Please consider the following limitations or known issues:
- The implementation is not yet fully covering full standard draft prioritizing federated learning features first
- There is a known deficiency regarding the accounts data, which currently only allows for a single account
- Missing SEPA fields for purpose_code and remittance_info
- No routing_number or SEC code coverage for ACH
- Not including wire references for Fedwire
- Missing identifiers for PBOC, Zengin, NPP
- No non-latin character support (Katakana, Cyrillic, Mandarin)
- No coverage of export licenses and other trade references
# 📄 License
This project is licensed under the MIT License.
Feel free to use, modify, and distribute this project as per the terms of the license.
# 📬 Contact
Project Maintainer: Soteria Initiative – @SoteriaInitiative – contact@soteria-initiative.org
Repository: SoteriaInitiative/coredata
For general inquiries or discussion, please open an issue.