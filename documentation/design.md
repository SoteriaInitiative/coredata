# Standard Design Considerations
The party and entity standard is design with three primary objectives:
1. Allow description of financial crime patters with data examples
2. Permit cross-entity systems to rely on a minimum input data structure
3. Build up data structures that facilitate law enforcement and prosecution

One key principle resulting from the above objective is to keep the standard simple enough to avoid
needless data mapping efforts and facilitate the adoption of the standard and ultimately cross-entity 
financial crime detection. That principal is carefully balanced against the needs to maintain adequate details
to successfully prosecute and convict criminals.

The design considerations below document key decisions influencing the standards design, alternatives that were 
considered and the reasoning for a specific decision. 

# Specific Considerations
## Data Format
Multiple data description languages are possible. There are often trade-offs between readability and processing
efficiency and the ability to change the data schema later on. As an emergent and user focused standard
processing efficiency is less of a concern but change, readability and a wide group of users are important.
The ability to spot errors easily is hence an important secondary objective. Special characters in a data language
can support readability and avoid errors.

Decision: JSON

Justification: + Allows nested data, +future extension easier, -data redundancy as nested data needs to be copied

Alternatives considered: Object relational/SQL, XML, Binary JSON, TOML, GraphQl; +data efficient -complex to adapt -few users -error prone -needs serveror seperate schema

## Primary Data Construct
The standard might have selected two separate data representations for transactions and party data. However,
financial crime patters usually combine party and transaction characteristics. In a nested data structure such
as JSON one type of data needs to be the one that includes the other.
The data for parties, while more extensive than the raw transaction data, does not change that often.
Further, there may be multiple accounts for each party and transactions would be associated with the account.
Therefore, if every current party record is copied into every transaction that is far less overall data then
if all historic transactions on all accounts were copied into every party data change.

Decision: Transaction

Justification: + less data duplication volume, +future extension easier

Alternatives considered: Object relational; +efficient bur -complex to adapt

## Handling External Data
One consequence of selecting a nested data structure and a transaction perspective is that
some second order data constructs may not always be able to populate all attributes by design. For instance,
The account information for the sender at a sending institution would be far more extensive the for the receiver and
the correspondent bank facilitating payments may have far less information than the sender or receiver institution.

Decision (Tentative): External data can be omitted. Pending investigation of effect on multi-entity federated learning 
and mitigation options (segregated models by transaction role types)

Justification: + pragmatic - might have adverse effect as same account info would look different in different FL nodes

Alternatives considered: Object relational; +efficient bur -complex to adapt

## Categorical Data Encoding
Categorical data can be modeled either as an attribute for each category or as a value type. Since modeling
as an attribute requires data standard changes value type modeling is preferred here.

Decision (Tentative): Categories will be encoded as value types with yet to be defined type standards for each value type.

Justification: + change resistant + avoids sparse/empty columns - processing for machine learning might need standardization

Alternatives considered: attribute encoding; - hard to read, - many null columns

## Risk Based Data Attribute Collection
The data standard requires the same set of data attributes, independent of the risk classification of the entity. While
that may require additional data elements that may not be needed at present, there is no guarantee such data may not be
required at a future point in time. Additionally, for the purpose of machine learning across institutions, there
is a high probability not every institution rates teh same entity at same risk level.

While there is value in performing customer/transaction reviews with a risk-base perspective, collecting the data is 
not an recommended approach. What is unavailable is that certain functions/roles to an account or an entity may not
legally be required to disclose specific details (e.g., US company directors), in such cases the commissions must be 
treated consistently.


Decision (Tentative): Same set of data attributes for all risk classes of parties, consistent omissions of attributes 
for specific type of roles/functions only.

Justification: + aids machine learning + ensure data availability in case of risk class change - challanging for certain roles/functions

Alternatives considered: optional attributes; - arbitrary data imbalance reduces AI benefits

