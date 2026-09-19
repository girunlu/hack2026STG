# From Ping to Pitch: AI for Wealth Managers

**UnRiskOmega AG** — hackathon task definition (`task_def.txt`).

## About UnRiskOmega

UnRiskOmega is a Swiss WealthTech company providing modular digital investment advisory and self-service solutions for financial institutions. Its platform combines portfolio analytics, risk profiling, suitability and compliance checks, investment proposals and digital investment journeys.

UnRiskOmega supports:

- more than **25 banks**
- over **1,000 active advisors**
- **500,000 portfolios**

...combining expertise in banking, quantitative finance and enterprise software.

---

## Description — From Ping to Pitch

Wealth managers regularly face short-notice client calls, unexpected meetings and time-consuming preparation for scheduled conversations.

To prepare properly, they may need to review:

- portfolio performance
- asset allocation
- suitability
- investment rules
- open proposals
- client notes
- market developments
- the bank's current investment view

...across several systems.

**The information exists, but it is distributed.** Turning it into a coherent client-specific storyline takes time that advisors often do not have.

---

## Deep Dive — The Core Product Experience

The prototype should simulate a feature within **URO Advisor Pro**, UnRiskOmega's investment-advisory solution for wealth managers.

The intended workflow begins with a simple advisor action, such as clicking a **Generate Briefing** button within the client or portfolio view. The system then collects the relevant information, analyzes it and presents a client-specific briefing that can be absorbed in approximately **60 seconds**.

### Your Challenge

Build a working prototype of an AI-powered briefing assistant for wealth managers. Once triggered by the advisor, the assistant should combine:

1. Client, portfolio and position data from URO Advisor Pro
2. Relevant information from the bank's CRM context
3. Current financial-market news
4. The bank's house view or CIO investment view

The assistant must transform these inputs into a concise briefing that can be read and understood in approximately 60 seconds.

The briefing should answer four practical questions:

| Question | Required content |
| --- | --- |
| **What happened?** | Summarize recent portfolio development and identify its main drivers. |
| **What is the current situation?** | Highlight relevant allocation deviations, risks, suitability issues, investment-rule violations and other portfolio observations. |
| **What could happen next?** | Connect the portfolio with relevant market developments and the bank's strategic or tactical investment view. |
| **What should the advisor do?** | Suggest specific next best actions based on the available data. |

Possible actions may include resolving an investment-rule violation, addressing a deviation from the Strategic Asset Allocation, identifying securities to buy, sell or switch, following up on an open proposal or considering a known client preference.

> **Note:** Text at the top of slide 2 indicates the prototype should **NOT** be implemented directly inside the live URO environment. It should instead be presented within a **mocked URO Advisor Pro interface** based on the screenshots and visual guidance provided by UnRiskOmega.

---

## Minimum Product Requirements

The prototype must demonstrate an end-to-end workflow covering the following steps:

1. **Trigger the briefing** — The advisor starts the briefing from a clear entry point in the mocked URO Advisor Pro interface.
2. **Collect the relevant data** — The solution combines available client, portfolio, security, CRM, market-news and house-view information.
3. **Identify what matters** — The system determines which developments, risks, violations, opportunities and client-specific circumstances deserve the advisor's attention.
4. **Create a coherent storyline** — The output should connect portfolio facts, market context and client information instead of presenting unrelated summaries from different sources.
5. **Recommend next best actions** — The assistant proposes concrete and relevant actions that the advisor could consider during or after the client conversation.
6. **Present the result clearly** — The briefing must be structured for an advisor working under time pressure and should be readable in approximately 60 seconds.

---

## The Goal

The result should help a wealth manager enter a client conversation with a clear understanding of:

- The client's current situation
- The most relevant portfolio developments
- The issues or opportunities that deserve attention
- The likely questions the client may raise
- The most appropriate next steps

The objective is a practical tool that reduces preparation time, improves advisor confidence and supports more consistent, informed client conversations.

---

## Required Briefing Content

The generated briefing should contain **three core sections**.

### 1. Recent Portfolio Development

Explain how the portfolio has developed and identify the main drivers.

Relevant information may include:

- Recent portfolio performance
- Positions or asset classes with the largest positive or negative contribution
- Concentration in individual securities, sectors, currencies or asset classes
- Material changes since the previous client interaction
- Relevant market events connected to recent portfolio movements

### 2. Portfolio Health Check

Summarize the portfolio's current state and highlight issues requiring attention.

Relevant information may include:

- Deviation from the Strategic Asset Allocation
- Suitability or investment-rule violations
- Risk-profile alignment
- Concentration risks
- Client-specific restrictions or preferences
- Open investment proposals
- Pending tasks
- Reinvestment opportunities
- Relevant information from client notes, tags or previous interactions

The assistant should **prioritize the most important findings** instead of listing every available metric.

### 3. Portfolio Outlook and Next Best Actions

Connect the client's portfolio with current market developments and the bank's strategic or tactical investment view.

The output should:

- Identify developments that may be relevant to the portfolio
- Explain why they matter for this specific client
- Distinguish portfolio facts from external market context
- Suggest concrete next steps
- Support recommendations with the underlying data
- Avoid generic or unsupported statements

Possible next best actions include:

- Rebalancing toward the Strategic Asset Allocation
- Resolving a suitability or investment-rule violation
- Reducing an identified concentration
- Reinvesting available liquidity
- Reviewing an open investment proposal
- Identifying securities to buy, sell or switch
- Following up on a relevant client preference, objective or concern

---

## Data Provided by UnRiskOmega

Participants will work with realistic mock or synthetic data. **No live client information will be provided.**

The available data may include:

| Category | Fields |
| --- | --- |
| Client | Client information, client risk profile, ESG profile, client notes and tags |
| Portfolio | Portfolio positions and weights, historical performance, asset allocation, past investment proposals |
| Compliance | Suitability violations, investment-rule violations |
| Workflow | Open client-specific tasks |
| Securities | Security type, currency, price, volatility, asset-class allocation |

UnRiskOmega will provide the mock data through **flat files**.

Participants will also receive:

- Screenshots of the URO Advisor Pro interface
- Visual and brand guidance for the mocked interface
- Sample portfolio information
- Sample ex-custody portfolio reports for the relevant bonus challenge

---

## External Information Sources

The assistant should enrich the provided portfolio and client data with external information.

### Financial-Market News

Teams should identify a practical method for retrieving relevant market news. Freely available sources such as **Yahoo Finance** may be used for the prototype.

The market information should be filtered according to its relevance to the client's **actual holdings and portfolio exposures**. A general market summary without a clear connection to the portfolio provides limited value.

### Bank House View or CIO View

Teams should also incorporate a sample strategic or tactical investment view from a bank. Publicly available investment reports, market outlooks or CIO publications from established financial institutions may be used as mock inputs.

The assistant should show how the client's current portfolio relates to this view. Examples include:

- an underweight or overweight asset class
- a tactical market position
- a portfolio exposure affected by the bank's outlook

For a production implementation, UnRiskOmega and its clients would connect the feature to approved professional data sources and internal bank publications.

---

## Example Scenario

A client calls unexpectedly because their portfolio has fallen in value.

- The **portfolio data** shows that most of the decline is concentrated in one semiconductor holding.
- The **market-news input** indicates that the price movement followed a sector-wide reaction to recent earnings announcements rather than a broad market decline.
- The **client information** shows that the client is sensitive to risk and plans to use part of the invested assets for a property purchase in the following year.

The assistant should combine these facts into one briefing that explains:

- What caused the portfolio decline
- Whether the development is isolated or market-wide
- Why it matters for this client
- Which risks or constraints require attention
- Which actions the advisor could discuss during the call

The advisor should receive a **useful conversation briefing** rather than three separate data summaries.

---

## Bonus Challenges

Teams can extend the core solution through one or more bonus features.

### Ex-Custody Portfolio Import

Allow the advisor to upload a portfolio statement from another custodian as a **PDF**.

The solution should:

- Extract the portfolio positions
- Identify weights and currencies
- Assign positions to the appropriate asset classes
- Create a virtual portfolio
- Label it clearly as an ex-custody portfolio
- Include it in the portfolio analysis and 60-second briefing

The virtual portfolio should behave like a portfolio already available in URO Advisor Pro.

### Interactive Follow-Up Assistant

Add a chatbot-style interaction that allows the advisor to ask follow-up questions based on the information already collected.

Example questions include:

- What is the client's total semiconductor exposure?
- Has the client previously raised concerns about volatility?
- Which positions contribute most to the current risk?
- How would a proposed rebalancing affect the portfolio allocation?
- Which open proposal is most relevant to this conversation?

The answers should remain **grounded in the available data** and clearly indicate when the information required for an answer is unavailable.

### Creative Briefing Format

Explore an original format that helps the advisor absorb the briefing quickly.

Possible formats include:

- A structured visual briefing card
- A conversational interface
- A voice briefing
- Prioritized alerts and action cards
- A combination of text and data visualization

The format should improve usability and remain appropriate for a professional wealth-management environment.

---

## Final Presentation

Each team should present a working end-to-end prototype through a **live demonstration** supported by a short PowerPoint presentation.

The presentation should cover:

- The advisor problem being addressed
- The initial trigger and complete user flow
- The generated 60-second briefing
- The data sources used
- How the analysis and recommendation logic works
- The technical architecture
- Which elements use mock data
- Which integrations would be required in production
- Any completed bonus features

> A previously unseen **test client** may be provided shortly before the final presentation. Teams should use this client to demonstrate that their solution can generate a useful briefing from new input rather than relying on a single preconfigured example.

The presentation should be concise and follow the same principle as the product: **surface the information that matters and get to the point quickly.**
