# About the Project
The Core Data standard is part of the [Soteria Initiative](https://soteria-initiative.org/) to establish common financial
crime data standards and includes the customer and entity data elements, collectively 
party data records, as well as transaction record standards. For a technical overview consult the [technical documentation](https://deepwiki.com/SoteriaInitiative/coredata) - auto generation courtesy of DeepWiki.

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

3. Provide application configuration and create a service account on GCP.  The
query tool reads credentials directly from environment variables, so no JSON key
file is required.  Set the following variables in your shell:
```zsh
export GCS_BUCKET_NAME=soteria-core-data
export GCP_PROJECT_ID=<PROJECT_ID>
export GCP_PRIVATE_KEY_ID=<KEY_ID>
export GCP_PRIVATE_KEY="<BASE64_OR_MULTILINE_PRIVATE_KEY>"
export GCP_CLIENT_EMAIL=<SERVICE_ACCOUNT_EMAIL>
export GCP_CLIENT_ID=<CLIENT_ID>
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

6. Explore the data with the query tool (results are shown in tables with record counts).
   The CLI exposes the following subcommands and positional arguments:

   | Command | Positional arguments | Description |
   |---------|---------------------|-------------|
   | `senders` | – | List unique sending parties |
   | `receivers` | – | List unique receiving parties (UBOs) |
   | `receivers-for [NAME]` | `NAME` | Receivers for the given sender (defaults to `$SENDER_NAME`) |
   | `senders-for [NAME]` | `NAME` | Senders for the given receiver (defaults to `$RECEIVER_NAME`) |
   | `transactions [FIRST_NAME] [LAST_NAME] [DOB]` | `FIRST_NAME` `LAST_NAME` `DOB` | All transactions for the party. Optional `--bank` and `--start-balance` flags refine the query. |
   | `labels` | – | Transactions filtered by `--local` and `--global` label values |
   | `multi-bank` | – | Parties holding accounts at more than one bank |
   | `missing-ubos` | – | Accounts missing UBO information |

   Example usage:

```zsh
python tools/goaml_query.py receivers
python tools/goaml_query.py labels --local 1 --global 1
python tools/goaml_query.py transactions "Jessica" "Hale" "1948-11-07T00:00:00" --bank "CH National"
python tools/goaml_query.py multi-bank
python tools/goaml_query.py missing-ubos
```
Downloaded XML files are cached under ``.goaml_cache`` (override with
``GOAML_CACHE_DIR``) to avoid repeat downloads between runs. The tool resolves
party names from ``involved_parties`` sections so that
senders and receivers are identified even when transactions only reference
accounts. The ``transactions`` command reports both incoming and outgoing
payments for the given party and displays transaction amount, account balance
amount, running balance, and the local and global label flags for each record.
After the table the command also prints the final balance along with the mean
and median transaction amounts. The ``senders`` command lists all parties that
initiate transactions. The ``receivers`` command lists only parties or entities
that are determined to be ultimate beneficial owners (UBOs) of the receiving
accounts. A UBO is resolved by first checking for an entity with relationship
role ``BEOWN`` on the account that also includes an associated
``entity_person`` with role ``3`` (Beneficial owner). If no such entity exists,
the tool falls back to any related person marked as a beneficial owner.
Each query reports both how many accounts lacked sufficient information to
determine a UBO and how many listed more than one UBO. The ``multi-bank``
command reports UBOs that hold accounts at more than one bank. The ``labels``
command accepts ``--local`` and ``--global`` options to filter transactions by
specific label values. The ``missing-ubos`` command lists any accounts missing
UBO information along with the report filenames in which they appear.
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
- Synthetic goAML generator and exporter for multi-bank large cash scenarios
- goAML reports group same-day transactions by originator and track account balances
- Reports use STR code and include standard indicators 1131V and 2003G
- Export utility validates XML against the goAML XSD and can upload reports to Cloud Storage

## goAML Export Usage
Generate synthetic reports directly in goAML XML by running:

```bash
python implementation/go_aml_export.py --input example/Bank_1_transactions.json
```

The script groups transactions by originator and UTC day, recalculates account balances, validates against the XSD, and optionally uploads to the configured Cloud Storage bucket.

## goAML Generation Usage
Produce synthetic transactions and STR reports directly:

```bash
python implementation/generate_goaml.py --banks 3 --transactions 1000 --days 90 \
  --scenario_probability '{"1":0.2,"2":0.1,"3":0.1}' \
  --bank_knowledge '{"1":true,"2":false,"3":false}'
```

The generator writes goAML XML without an intermediate JSON step and honors multi-bank, split-deposit scenarios.

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

