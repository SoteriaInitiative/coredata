# Core Data Specification

## 1. Purpose

Financial crime prevention heavily depends on the collection, distribution and manipulation of data.
Since multiple different systems are typically used without standardization data needs to be adapted from one system
to the next and from one financial institution to the next. This process is both **costly**, **time-consuming** and limits the
adoption of the most effective technologies to fight crime, such as collaborative multi-entity AI, e.g., 
federated learning.
Additionally, the lack of a standard makes it unnecessarily hard for financial crime officers in public 
and private sectors to **effectively communicate** about threat patters because one client type may mean two 
different things to two different people.

The document aims to establish a binding standard similar in nature of HTML for the internet.

## 2. Scope

Financial crime prevention needs to capture data about people, transactions, entities, vessels, goods and services
as well as their relationships, timing and location.

For that reason the data standard targets all systems **receiving**, **processing** and **sending** data of that nature
to corporate, law enforcement or any other system with the objective to detect financial crime.

Out of scope are data feeding systems, which may follow different industry standard norms (e.g., SWIFT)

---

## 3. Background & Context

* Current state and issues.
* Constraints (e.g., performance, regulatory, compatibility).

---

## 4. Decision Record

Captures all **key decisions**, both technical and design-related, in a structured way.

### 4.1 Options Considered

| Option   | Pros                      | Cons                 | Outcome    |
| -------- | ------------------------- | -------------------- | ---------- |
| Option A | Fast, well-supported      | Steep learning curve | ✅ Accepted |
| Option B | Simple, low entry barrier | Doesn’t scale        | ❌ Rejected |

### 4.2 Final Decision

* Description of the chosen approach (technical + design aspects).
* Reasoning behind the decision.
* Trade-offs explicitly acknowledged.

### 4.3 Design Implications

* Architectural impact (scalability, maintainability, security).
* Performance or reliability considerations.
* UX/operability considerations if relevant.

### 4.4 Future Reconsideration Triggers

* Conditions that would require revisiting this decision (e.g., new standards, performance bottlenecks, cost shifts).

---

## 5. Standard Requirements

* Mandatory rules derived from the decision.
* Recommended practices for implementation.

---

## 6. Compliance & Verification

* How adherence will be checked (reviews, automated tests, monitoring).
* Metrics/KPIs tied to the design goals.

---

## 7. Roles & Responsibilities

Who is responsible for implementing, reviewing, and maintaining compliance.

---

## 8. Change Management & Version History

| Version | Date       | Author | Decision / Change | Notes |
| ------- | ---------- | ------ | ----------------- | ----- |
| 1.0     | YYYY-MM-DD | Author | Initial release   | –     |

---

## 9. Appendices *(Optional)*

* Design diagrams, benchmarks, code snippets.
* Links to RFCs, specs, or research papers.