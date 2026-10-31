# Empório da Música — Customer Service Agent

Prototype of a text-based customer service agent for **Empório da Música**, a fictional musical instrument store in Campo Grande/MS (Brazil). The agent answers customers in Portuguese, deciding when to query store data (products, prices, stock, orders, promotions) and when to consult the store's policy manual (returns, opening hours, payment, shipping).

> Work in progress — technical case for the AI Engineer role at Artefact.

## How to run
_TODO: environment setup, model provider, commands._

## Technical decisions
_TODO: agent approach, model and provider, data handling, policy retrieval, prompt strategy, conversation history, interface._

## Assumptions
_TODO: ambiguities found in the data and policies, and how they were resolved._

## Example conversations
_TODO: see `examples/`._

## Known limitations and next steps
_TODO._

## Use of AI coding assistants
_TODO: which tools were used and how._

## Data
The `data/` folder contains the material provided by the store:

| File | Content |
|---|---|
| `products.csv` | Catalog: price, category, stock, status, specs |
| `categories.csv` | Product categories |
| `promotions.csv` | Promotions per product (active or inactive) |
| `customers.csv` | Customer contact data |
| `orders.csv` / `order_items.csv` | Orders, status, tracking and items |
| `politicas_da_loja.pdf` | Internal customer service policy manual |
