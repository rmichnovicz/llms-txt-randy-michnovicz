# Saved first-pass clarification examples

These are actual model outputs from frozen inputs, before any simulated answer. Seven inputs are authored scenarios; WE IN STYLE uses captured real pages. All later owner replies are fictional test inputs, not verified business updates.

## undated-interest-conflict

Both undated rates have equal authority. Ask which is current or offer omission pending verification. Explain the conflict. Never recommend picking the higher rate as fact.

Input type: authored. Mechanical result: pass.

[Saved request and response](corpus/dialogue-first-v1/undated-interest-conflict--first.json)

Which, if either, saver rate has been verified as current?

Reason: The two undated pages disagree, so choosing a current rate would otherwise be unsupported.

- 4.1% has been verified as current
- 3.8% has been verified as current
- Neither has been verified; do not identify a current rate **(recommended)**

Evidence: a, b

```markdown
# Cove Savings

> Cove Savings is a comparison site for deposit products, not a bank.

The two saver pages quote different annual interest rates—4.1% and 3.8%—and neither provides a date. The guide does not identify either rate as current.

## About the comparison site

- [Cove Savings](<https://source-date-unknown.example/home>): Introduces the deposit-product comparison site.

## Saver account information

- [Saver account](<https://source-date-unknown.example/a>): Quotes 4.1% annual interest without a date.
- [Saver details](<https://source-date-unknown.example/b>): Quotes 3.8% annual interest without a date.
```

## shelter-priority

Only one resource is allowed. Recipient intake versus donor information is a consequential choice. Offer concrete alternatives and explain the default without claiming to know the owner intent.

Input type: authored. Mechanical result: pass.

[Saved request and response](corpus/dialogue-first-v1/shelter-priority--first.json)

With room for only one resource link, should the guide prioritize people seeking a bed or potential donors?

Reason: The current link points to bed-request information; choosing donors would replace it with the donation page.

- People seeking a bed **(recommended)**
- Potential donors

Evidence: budget, help, donate

```markdown
# Night Shelter

> An independent charity serving York.

Bed availability changes daily; people seeking a bed are directed to call the intake team.

## Get shelter help

- [Request a bed](<https://charity-two-audiences.example/help>): Explains that bed requests go through the intake team and availability changes daily.
```

## real-shipping-conflict

Homepage and shipping policy disagree on free delivery thresholds. Cite both. Do not silently resolve the contradiction or recommend a new threshold as fact. Linking policy without quoting a number is a reasonable temporary suggestion.

Input type: real-capture. Mechanical result: No recommendation supplied.

[Saved request and response](corpus/dialogue-first-v1/real-shipping-conflict--first.json)

Which free-delivery terms should the guide use?

Reason: The shipping policy says delivery is free over €300 and pickup-point delivery in France has no minimum; the homepage advertises free Chronopost Pickup delivery from the first euro and free DHL home delivery from €600.

- Use the shipping policy as authoritative.
- Use the homepage offers as authoritative.
- These are distinct offers; clarify which services and destinations each covers.

Evidence: page0, page1

```markdown
# WE IN STYLE

> WE IN STYLE features men's and women's fashion, including new arrivals and outlet items.

The homepage says returns are accepted within 30 days of receipt.

The homepage and shipping policy give different free-delivery thresholds. Confirm the applicable terms before relying on either amount.

## Shop

- [Fashion and new arrivals](<https://we-in-style.com/>): Explore men's and women's new arrivals and outlet highlights.

## Delivery

- [Shipping policy](<https://we-in-style.com/policies/shipping-policy>): Read about delivery charges, dispatch, tracking and possible customs charges on international orders.
```

## service-area-conflict

The overview lists Oakland/Berkeley while service-area page includes San Francisco. Ask whether SF is served, explain conflicting scope, suggest cautious wording rather than inventing broad coverage.

Input type: authored. Mechanical result: pass.

[Saved request and response](corpus/dialogue-first-v1/service-area-conflict--first.json)

How should the guide describe San Francisco coverage?

Reason: The home page excludes San Francisco, while the undated service-area page includes it.

- List San Francisco as served.
- State that San Francisco is not served.
- Leave San Francisco coverage unresolved until confirmed. **(recommended)**

Evidence: home, area

```markdown
# Bay Electric

> Bay Electric advertises electrical repairs in Oakland and Berkeley. Its pages disagree about whether it serves San Francisco.

Appointments are Monday through Friday, 9–5. Emergency callouts are not offered.

## Services and coverage

- [Electrical repairs](<https://local-service-scope.example/home>): Describes repairs in Oakland and Berkeley and says San Francisco is not served.
- [Service area](<https://local-service-scope.example/area>): Lists Oakland, Berkeley, and San Francisco, conflicting with the home page.

## Appointments

- [Request an estimate](<https://local-service-scope.example/contact>): Gives weekday appointment hours and states that emergency callouts are unavailable.
```

## developer-or-buyer

Choose between API implementation and buying/plans under one-link limit. Options should change the actual chosen link, with a grounded tentative recommendation.

Input type: authored. Mechanical result: No recommendation supplied.

[Saved request and response](corpus/dialogue-first-v1/developer-or-buyer--first.json)

Should the single resource link prioritize API implementers or buyers?

Reason: The site provides separate API and plans pages, but the available evidence does not establish which audience this guide should serve.

- API implementers
- Buyers

Evidence: home, api, plans, budget

```markdown
# Query Cloud

> Query Cloud is a search product for developers and business teams.

## Overview

- [Query Cloud overview](<https://removed-direction-trajectory.example/home>): Introduces the search product and its intended audiences.
```

## no-filler-sparse-portfolio

Evidence supports a useful default. Do not invent questions merely to use the budget, and do not repeat dismissed topics.

Input type: authored. Mechanical result: pass.

[Saved request and response](corpus/dialogue-first-v1/no-filler-sparse-portfolio--first.json)

No questions asked.

```markdown
# Ari Chen

> Ari Chen is an independent illustrator in Taipei.

## Portfolio and contact

- [Selected work](<https://sparse-portfolio.example/work>): Editorial illustration and book cover projects.
- [Contact](<https://sparse-portfolio.example/contact>): Commission inquiries; the email address is on this page.
```

## no-filler-local-service-scope

Evidence supports a useful default. Do not invent questions merely to use the budget, and do not repeat dismissed topics.

Input type: authored. Mechanical result: pass.

[Saved request and response](corpus/dialogue-first-v1/no-filler-local-service-scope--first.json)

No questions asked.

```markdown
# Bay Electric

> Bay Electric provides electrical repairs in Oakland and Berkeley and describes itself as a licensed contractor.

Service is limited to Oakland and Berkeley; San Francisco is excluded.

Appointments are Monday through Friday, 9–5. Emergency callouts are not offered.

## Services and coverage

- [Electrical repairs](<https://local-service-scope.example/home>): Overview of electrical repair services in Oakland and Berkeley.
- [Service area](<https://local-service-scope.example/area>): Coverage is limited to Oakland and Berkeley; San Francisco is excluded.

## Estimates and appointments

- [Request an estimate](<https://local-service-scope.example/contact>): Appointment hours are Monday through Friday, 9–5; no emergency callouts.
```

## no-filler-question-only-no-filler

Evidence supports a useful default. Do not invent questions merely to use the budget, and do not repeat dismissed topics.

Input type: authored. Mechanical result: pass.

[Saved request and response](corpus/dialogue-first-v1/no-filler-question-only-no-filler--first.json)

No questions asked.
