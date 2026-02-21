# Codespaces Runbook

Use this runbook for an end-to-end local check in Codespaces.

## 1) Start dependencies

```bash
make up
```

## 2) Seed demo docs

```bash
make seed
```

## 3) Ingest into Weaviate

```bash
make ingest
```

## 4) Start API

```bash
make run
```

## 5) Run red-team/usefulness checks

```bash
make redteam
```
