# User Case Collection
This document contains a description of use cases that the standard should 
enable.

The description follows the guidelines published by [Figma](https://www.figma.com/resource-library/what-is-a-use-case/) and are numbered 
sequentially. Feel free to add more use cases either in the completed or pending
section. Pending use cases represent future requirements and completed use cases
represent known or designed uses of the standard.

# Completed Use Cases
## 1. Standardized Input Data to Enable Federated Learning

<b>Primary actor:</b> AML/CTF detection system

<b>Secondary actor:</b> Compliance officer, law enforcement

<b>Goals:</b> Allow training for federated learning models to enhance industry reliance and detection quality

<b>Stakeholders:</b> Law enforcement, financial institutions, regulators, policy makers

<b>Preconditions:</b> -

<b>Triggers:</b> -

<b>Scenario:</b> A federated learning model likes to ingest data for local model training.
The input data should have the same semantics for each system, that is an individual party should have 
name, middle name, last name for example and not just a name attribute. Similarly, the industry
of the party should be encoded with the same industry coding system. That same sort of
standardization is necessary across a number of vital data elements.

# Pending Use Cases
## 1. Structured Actionable Sharing of AML/CTF Intelligence
<b>Primary actor:</b> Financial crime investigator

<b>Secondary actor:</b> Financial crime investogator, law enforcement agent, detection model engineer

<b>Goals:</b> Create, document, explain and share an observed financial crime typology

<b>Stakeholders:</b> Financial crime investogator, law enforcement agent, detection model engineer

<b>Preconditions:</b> A verify financial crime activity pattern, a data standard has been agreed between primary and secondary actors

<b>Triggers:</b> A new financial crime pattern/typology has been identified

<b>Scenario:</b> A financial crime investigator has identified a specific transaction pattern that involves entities
with a particular set of characteristics. To share this knowledge the investogator either needs to describe the 
patter in prose or encode the pattern in commonly understood data structures to document the new pattern.
Prose description is subject to subjective interpretation such as using different or unavailable categories for
client types, industry codes or corporate identifiers (TIN vs LEI) in addition to using different semantics of attributes
(full name vs first, middle and last names). Editing a JSON file directly may be possible for a technically versed
financial professional but more accessible is a tools to describe entities and transactions that allows the export of the
pattern for sharing with the financial crime community. 
<b>Alternative Scenario:</b> Rather than creating example data in an editor, the financial crime professional
will run an editor tool on actual data and extract the patterns automatically for review in a visual tool before
it is shared with the financial crime community.

# Use Case Template
Please describe your use case as follows:

<b>Primary actor:</b> someone initiating an activity

<b>Secondary actor:</b> someone benefitting from some activity

<b>Goals:</b> objective of the activity

<b>Stakeholders:</b> involved or affected parties

<b>Preconditions:</b> activities or conditions to satisfy before starting

<b>Triggers:</b> an event that starts the activity

<b>Scenario:</b> ...
