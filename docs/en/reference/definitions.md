---
title: Terms and Abbreviations
description: Attribution, advertising hierarchy, data, and optimization terminology
compact: "Canonical glossary for attribution, advertising, evaluation, machine learning, optimization, data, and deployment terms, including GMV, MLP, R-squared, sMAPE, Kendall's tau, Huber loss, Adam, epoch, one-hot encoding, and elasticity."
lang: en-US
---

# Terms and Abbreviations

This page defines the specific meaning of terms in this project for readers who understand basic marketing or data analysis but may not be familiar with advertising-attribution systems.

## Core Business Terms <span class="status-label status-verified" aria-label="Verified"></span>

### AMC (Amazon Marketing Cloud)

Amazon Marketing Cloud is a privacy-safe analytics environment. AMC-style paths in this project are aggregated demonstration data and do not imply that user-level details can be exported.

### MTA (Multi-Touch Attribution)

A method for allocating Outcome credit among multiple historical marketing touchpoints. This project runs Markov and path-level Shapley.

### MTA-SIM (Multi-Touch Attribution Simulator)

The external synthetic-data generator used to create controlled attribution datasets and simulation ground truth for framework evaluation.

### Touchpoint

One classifiable advertising interaction. This project uses a five-segment normalized key:

`AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`

### Customer Path

An ordered sequence of touchpoints in the observation window, separated with ` > `.

### Outcome

A business result to which the model allocates credit. This project includes unique converted users, purchase count, and revenue.

### GMV (Gross Merchandise Value)

The total value of merchandise sold over a period before deductions such as returns, fees, or advertising cost. The contributed strategy-evaluation network uses revenue as its available approximation of GMV.

### Campaign Group, Campaign, and Ad Group

The project uses the `Campaign Group → Campaign → Ad Group → Keyword/SKU/Target/Audience` hierarchy. `ad_product` is a Campaign attribute, not an independent level.

## Advertising Platform Terms <span class="status-label status-verified" aria-label="Verified"></span>

### ASIN (Amazon Standard Identification Number)

A unique identifier for a product sold on Amazon. While a [SKU](#sku-stock-keeping-unit) is a seller-defined identifier, an ASIN is Amazon-assigned and consistent across all sellers of the same product.

### SKU (Stock Keeping Unit)

A seller-defined unique identifier for a sellable item within a platform and marketplace. One Product may map to multiple SKUs. See also [ASIN](#asin-amazon-standard-identification-number).

### CPC (Cost Per Click)

A billing model where the advertiser pays for each click on their ad. In this project, `CPC` cost is assigned only to `CLICK` interaction types.

### CPM (Cost Per Mille / Cost Per Thousand Impressions)

A billing model where the advertiser pays per thousand impressions. In this project, `CPM` cost is assigned only to `IMPRESSION` interaction types.

### DSP (Demand-Side Platform)

Amazon's programmatic advertising platform that allows advertisers to buy display, video, and audio ads programmatically. In this project, DSP is one of the four ad products alongside SP, SB, and SD.

### SP (Sponsored Products)

Cost-per-click ads for individual product listings on Amazon, appearing in search results and product detail pages.

### SB (Sponsored Brands)

Cost-per-click ads featuring a brand logo, custom headline, and multiple products, appearing in prominent search result positions.

### SD (Sponsored Display)

Display ads that target relevant audiences both on and off Amazon, using interest-based or product-based targeting.

### Impression

An ad display event counted when an ad is rendered on screen. Together with [CLICK](#click), it is one of the two `INTERACTION_TYPE` values used in this project's five-segment touchpoint key.

### Click

A user interaction event where a user clicks on an ad. Together with [IMPRESSION](#impression), it is one of the two `INTERACTION_TYPE` values used in this project's five-segment touchpoint key.

## Attribution Terms <span class="status-label status-verified" aria-label="Verified"></span>

### Attribution Share

The proportion of one Outcome that a touchpoint receives after allocation across all touchpoints. Shares for the same Outcome sum to 1.

### Markov Chain

A model describing paths with state-transition probabilities. This project calculates credit from the decrease in conversion probability when a touchpoint is removed.

### Removal Effect

The non-negative estimated decrease in conversion probability relative to baseline after a touchpoint is removed from the transition network.

### Shapley Value

A fair credit allocation from cooperative game theory. This project's path-unanimity implementation splits one path's Outcome equally among its unique touchpoints.

### Causal Incrementality

The additional Outcome actually caused by advertising relative to the “no advertising” counterfactual. An observational MTA attribution share does not automatically equal causal incrementality.

## Evaluation Metrics <span class="status-label status-verified" aria-label="Verified"></span>

### MAE (Mean Absolute Error)

The average of the absolute differences between predicted and actual values. It tells you how far off your estimates are on average, in the same units as the original numbers. A lower MAE means better accuracy. Unlike [RMSE](#rmse-root-mean-squared-error), MAE treats all errors equally regardless of size.

### RMSE (Root Mean Squared Error)

The square root of the average squared differences between predicted and actual values. It penalizes large errors more heavily than small ones, so a single bad prediction has a bigger impact on RMSE than on [MAE](#mae-mean-absolute-error). Like MAE, lower is better.

### TVD (Total Variation Distance)

Half the sum of absolute differences between two probability distributions, point by point. It ranges from 0 (identical distributions) to 1 (completely different). In this project, TVD compares the full attribution-share vector from a model against either another model or the ground truth. It answers "how different are these two allocations overall?" rather than "which touchpoint differs most?"

### Spearman's Rho (Spearman Rank Correlation, ρ)

A measure of how well two rankings agree, ranging from -1 (perfectly reversed) to +1 (perfectly identical). Unlike a direct share comparison, rho cares only about order: do Markov and Shapley rank the same touchpoints as most important? A rho of `None` means one set of values has no ranking (e.g., uniform equal shares), which is a deliberate signal rather than a measurement failure.

### Top-K Overlap

The fraction of the top K touchpoints (by attribution share) that two models agree on. For example, Top-5 overlap of 0.8 means 4 of the top 5 touchpoints appear in both models' top 5. It measures agreement among the most important touchpoints specifically, complementing [TVD](#tvd-total-variation-distance) which measures distribution-wide agreement.

### Conservation Error

The difference between a model's sum of allocated shares and the required total (1 for shares, the observed outcome total for values). A value of zero means the model perfectly conserved the input total. Non-zero values indicate a calculation defect.

### R-squared (Coefficient of Determination)

The share of outcome variance explained by a prediction relative to predicting the observed mean. One is perfect, zero is no better than the mean, and a negative value is worse than the mean baseline. The contributed network's held-out R-squared is negative.

### sMAPE (Symmetric Mean Absolute Percentage Error)

The average absolute prediction error divided by the average magnitude of the prediction and observation, expressed symmetrically so swapping them does not change the score. Lower is better; the zero-versus-zero case contributes zero error.

### Kendall's Tau

A rank-agreement statistic based on concordant and discordant pairs. This project's strategy baseline comparison uses tau-b, which adjusts for tied values and returns no statistic when a ranking has no direction.

### Huber Loss

A training loss that behaves like squared error for small residuals and absolute error for large residuals. It preserves a smooth gradient near the target while reducing the influence of extreme observations.

### L1 Distance (Manhattan Distance)

The sum of absolute differences between two vectors across all dimensions. In this project, [TVD](#tvd-total-variation-distance) is defined as half the L1 distance between share vectors, normalizing the result to [0, 1].

## Technical Terms <span class="status-label status-verified" aria-label="Verified"></span>

### CSV (Comma-Separated Values)

A plain-text tabular data format where each line is a row and commas separate columns. All data inputs and outputs in this project use CSV with a header row. Leading and trailing whitespace is stripped before validation.

### ISO Date Format

An internationally standardized date representation (`YYYY-MM-DD`, e.g., `2026-01-01`). All dates in project data contracts must use this format. The standard is maintained by the [International Organization for Standardization](https://www.iso.org).

### UTC (Coordinated Universal Time)

The primary time standard by which the world regulates clocks. All timestamps in project data are stored and compared in UTC to avoid timezone-related ordering inconsistencies.

### SHA-256 (Secure Hash Algorithm 256-bit)

A cryptographic hash function that produces a 256-bit (32-byte) fingerprint of any data. The strategy module uses SHA-256 digests to verify that the AMC attribution and entity evidence files have not changed since the strategy request was created.

### HMAC (Hash-based Message Authentication Code)

A keyed digest used to prove that a message came from a party holding the shared secret and was not changed in transit. The team-server deployment validates GitHub's SHA-256 webhook HMAC before queueing a requested commit.

### HTTP (Hypertext Transfer Protocol)

The request-and-response protocol a browser uses to ask a server for a page or a piece of data. The dashboard client and its backend speak it, and the numeric status a response carries — 200 for success, 403 for a refusal, 503 for a dependency that is configured but unreachable — is part of every endpoint contract in this project.

### HTTPS (Hypertext Transfer Protocol Secure)

The encrypted form of HTTP carried over Transport Layer Security. The deployment bundle requires credential-free HTTPS repository addresses when a Gitea access token supplies authentication, and recommends HTTPS for every externally reachable webhook and dashboard address.

### TLS (Transport Layer Security)

The protocol that encrypts an HTTPS connection and authenticates the server certificate. A public team-server deployment terminates TLS at its reverse proxy and keeps certificate verification enabled for GitHub webhook delivery.

### SSH (Secure Shell)

An encrypted remote-access protocol also used by Git transports. The deployment bundle accepts SSH-based Gitea access only with a dedicated private key and a pinned known-hosts file.

### ACL (Access Control List)

A filesystem permission list that grants a named user narrowly scoped access in addition to the file owner, group, and general mode bits. The deployment installer uses execute-only ACL entries so `mta-dashboard` can traverse private parent directories without listing or reading their other contents.

### TCP (Transmission Control Protocol)

The reliable network transport used by the dashboard and webhook listening sockets. A free local TCP port is available for a process to bind; it does not by itself prove that a firewall or reverse proxy permits external access.

### DNS (Domain Name System)

The naming system that maps a server name to network addresses. The deployment installer reports configured public names but does not infer or modify DNS records.

### DNN (Deep Neural Network)

A machine learning model with multiple layers of interconnected nodes. In this project, the [DNN credit model](/en/attribution/standardized-interface/dnn) learns to predict attribution shares from touchpoint segment structure, enabling predictions for campaigns with no historical path data.

### MLP (Multi-Layer Perceptron)

A feed-forward neural network made from fully connected layers. The contributed strategy-evaluation model uses a 32-unit then 16-unit hidden stack to predict log-transformed revenue.

### Adam (Adaptive Moment Estimation)

A gradient-based optimization algorithm that maintains moving averages of both gradients and squared gradients to adapt each parameter's learning rate. The contributed network implements Adam directly.

### Epoch

One complete pass through the training observations. Early stopping ends training when validation performance has not improved for a declared number of epochs.

### One-Hot Encoding

A representation of one categorical value as several binary fields, with exactly one field active for the selected category. The contributed adapter uses it for day-of-week and marketplace inputs.

### SHAP (SHapley Additive exPlanations)

A widely used library for explaining model predictions using Shapley values. This project's Shapley implementation is an exact closed-form solution for a specific path-unanimity game and does not use the SHAP package. The two should not be confused.

### JSON (JavaScript Object Notation)

A lightweight text-based data interchange format. Strategy requests and outputs in this project use JSON.

### API (Application Programming Interface)

A defined way for one program to request services from another. In this project, Amazon Ads API and Amazon Marketing Cloud API provide the upstream data that feeds into attribution and strategy calculations, and the dashboard's own backend exposes one to its browser client.

### REST (Representational State Transfer)

A convention for building a web API in which each address names a thing and the HTTP method names what to do with it: read it, replace it, or remove it. The dashboard backend follows it, which is why reading the snapshot and starting a pipeline stage are the same address family rather than two unrelated protocols.

### SQL (Structured Query Language)

The language a relational database understands. This project's queries are written against PostgreSQL.

### ORM (Object-Relational Mapper)

A library that maps database rows onto objects in a programming language, so a query is written in that language instead of as SQL text. `dashboard/models.py` defines this project's mapping with SQLAlchemy; writing a query through it means a column renamed in one place cannot silently keep working elsewhere.

### WSGI (Web Server Gateway Interface)

The standard calling convention between a Python web application and the server process that runs it. Flask applications are WSGI applications, which is what lets the same code be served by a development server locally and by a production server such as Gunicorn on a deployment host.

### YAML (Yet Another Markup Language)

An indentation-based text format for configuration. The name is also read as
the recursive "YAML Ain't Markup Language". Continuous-integration platforms including GitHub Actions and Alibaba Cloud Yunxiao describe their pipelines in it.

### CI/CD (Continuous Integration / Continuous Delivery)

Continuous Integration is the practice of building and testing every change automatically as it lands. Continuous Delivery extends that to releasing the tested result. This repository already practises both through GitHub Actions; [Backend Setup and Deployment](/en/introduction/backend/setups) specifies the Alibaba-hosted target.

### Yunxiao (Alibaba Cloud DevOps)

Alibaba Cloud's hosted DevOps platform, published in Chinese as 云效. Its pipeline product is called Flow, its code hosting is called Codeup, and its application-centred delivery layer is called AppStack. Flow occupies the same role Jenkins does but is a managed service rather than a server the team runs.

### ECS (Elastic Compute Service)

Alibaba Cloud's virtual machine service. An ECS instance is an ordinary Linux server that the team is responsible for patching, sizing, and keeping alive.

### SAE (Serverless App Engine)

Alibaba Cloud's serverless application platform. It runs a container image without the team provisioning or maintaining a virtual machine, and bills for what runs. Compared with ECS it removes the machine-level work, at the cost of requiring the application to be packaged as an image.

### ACR (Alibaba Cloud Container Registry)

Alibaba Cloud's store for container images. A pipeline that deploys by image builds one, pushes it here, and the deployment target pulls it from here.

### VPC (Virtual Private Cloud)

A private network inside a cloud account. Resources placed in one can reach each other without traversing the public internet, which is how a deployed backend is expected to reach its PostgreSQL instance.

### RAM (Resource Access Management)

Alibaba Cloud's permission system. Authorizing a pipeline to deploy to a machine means granting it a RAM role rather than storing a machine password.

## Product Economics Terms <span class="status-label status-verified" aria-label="Verified"></span>

### COGS (Cost of Goods Sold)

The direct unit cost of producing or acquiring one unit of a product, excluding advertising Spend. In this project, `ProductEconomics.unit_cogs` stays unset rather than zero-filled when a source has not reported it, since a missing COGS is not the same fact as a zero-cost product.

### Contribution Margin

Unit price minus unit COGS: the profit contributed by one additional unit sold before advertising Spend is subtracted. `ProductEconomics.unit_contribution_margin` may be given directly by a source or derived from price and COGS; see [Margin Source](/en/introduction/data-models/vocabularies/margin-source.md).

## Strategy and Optimization Terms <span class="status-label status-verified" aria-label="Verified"></span>

### Budget Seed

An explainable initial budget for later review or optimization. Current output is a Seed, not an optimum.

### Response Curve

A function relating budget or Spend to expected Outcome. Saturation means the marginal return from additional budget gradually declines.

### Marginal Revenue

Expected additional revenue from one added unit of budget. Budget optimization must estimate it; it is not the same as historically attributed revenue.

### Constraint

A rule that an optimized plan must satisfy, such as total budget, minimum budget, inventory, activation eligibility, or budget increment.

### Concavity

The property of a [Response Curve](#response-curve) whose marginal return falls as budget rises: each added unit of budget buys less than the one before it. It is what makes an allocation equalizing [Marginal Revenue](#marginal-revenue) across Campaigns a true maximum rather than one of several local answers, so this project's fitted curves are constrained to keep it.

### Shadow Price of Budget

The value of one additional unit of the total budget at the optimum. When every Campaign's [Response Curve](#response-curve) is concave, there is exactly one price at which each unconstrained Campaign's marginal expected revenue is equal and the authorized budget is exactly exhausted; Campaigns whose floor or ceiling binds sit at that bound. This project's optimizer finds that price by bisection rather than by a general-purpose solver.

### Budget Response

How much actual Spend and then revenue change when a Campaign's configured budget changes. It is a different quantity from [Attribution Share](#attribution-share), which divides credit for outcomes that already occurred, and from [Causal Incrementality](#causal-incrementality), which requires an assignment that supports a causal claim.

### Extrapolation

Reading a fitted [Response Curve](#response-curve) at a budget outside the range the fit observed. The estimate rests on the curve's assumed shape rather than on evidence, so this project flags every extrapolated allocation rather than letting the number stand unqualified.

### Pooled Transfer

Fitting a Campaign's [Response Curve](#response-curve) from comparable Campaigns because it lacks sufficient budget variation of its own. The estimate is legitimate but is not that Campaign's observed behavior, so it is labelled wherever it appears.

### Elasticity

The proportional change in an outcome associated with a proportional change in an input. The contributed model assigns prior elasticity weights to advertising types when adjusting a prediction for a changed budget mix; those priors are assumptions, not effects identified from this project's observations.

### ROAS (Return on Ad Spend)

Attributed revenue divided by advertising Spend. ROAS is a ratio and must not be confused with maximizing total revenue or profit as though they were the same objective.

### ROI (Return on Investment)

Attributed revenue minus advertising cost, divided by advertising cost: `(revenue - cost) / cost`. Unlike [ROAS](#roas-return-on-ad-spend), ROI subtracts the cost and can be negative when costs exceed revenue. Both are calculated per touchpoint in this project's model outputs.

### CPA (Cost Per Acquisition / Cost Per Action)

Advertising cost divided by attributed purchase count: `cost / attributed purchases`. It answers "how much did I spend for each purchase attributed to this touchpoint?" A lower CPA is generally better, but it must be interpreted alongside revenue and ROAS — a very low CPA on very few purchases may not be meaningful.

### Cost Per Converted User

Advertising cost divided by attributed converted users. Similar to [CPA](#cpa-cost-per-acquisition--cost-per-action) but uses unique purchasing users rather than order count as the denominator. The two diverge when a single user purchases multiple times.

## Data Governance Terms <span class="status-label status-verified" aria-label="Verified"></span>

### Ground Truth

A reference answer used to evaluate a model. MTA-SIM's `simulation_ground_truth` is valid only for the synthetic mechanism and is prohibited as a training feature.

### Data Leakage

Using information during training that is unavailable at decision time—for example, using Ground Truth as an input—which produces a misleading evaluation.

### Repository Fact / External / Inference / Recommendation

- <span class="status-label status-verified" aria-label="Verified"></span> **Verified**: confirmed directly by code or data in this repository.
- <span class="status-label status-external" aria-label="External"></span> **External**: from a cited external repository or source.
- <span class="status-label status-inference" aria-label="Inference"></span> **Inference**: an evidence-based interpretation rather than direct measurement.
- <span class="status-label status-recommendation" aria-label="Recommendation"></span> **Recommendation**: a design or next step pending review.
