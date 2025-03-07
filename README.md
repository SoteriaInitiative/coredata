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
- [SWIFT ISO 20022 Messaging Standard](https://www2.swift.com/knowledgecentre/publications/iso_20022_fnc_instit_get_st/4.0?topic=technical-implementation.htm) (free account required)

To make the standards useful synthetic data generators will be provided and a reference
implementation of a data editor will allow the encoding of actual financial crime patterns.

# Getting Started
1. Clone the repo
```
git clone https://github.com/SoteriaInitiative/coredata.git
cd coredata
```
2. Install the required dependencies
```
pip install requirements.txt
```
3. Run the generator and then explore the ```example.json``` file
```
python generator.py
```
# Project Structure
To find your way around please find a quick overview of the project structure.
```
coredata/
├── documentation/              # Standard design documentation
├── example/                    # Example dataset implementing the standard
├── implementation/             # Example data generator and pattern editor
├── standard                    # Standard specification
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