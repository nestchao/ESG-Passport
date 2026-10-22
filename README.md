# ESG-Passpord

ESG-Passpord is a Malaysian SME prototype for turning business documents into
reviewable ESG activity records and preparing SEDG questionnaire information.
The intended workflow keeps consequential decisions under human approval and
records the supporting evidence.

## Project structure

| Folder | Purpose |
|---|---|
| docs/ | Competition documentation |
| runpod/ | RunPod configuration and deployment notes |
| src/ | Application source; AI module belongs under src/ai/ |
| submission/ | Submission deliverables |
| tests/ | Application tests |

## Current status

The application is a starter scaffold. A live backend, model integration and
working deployment have not been implemented. Local research and synthetic-data
preparation are development materials and are excluded from Git.

## Configuration

Copy .env.example to .env and fill the required values locally. Never commit API
keys. Configure the application entry point and Replit run command when the
implementation is ready.

## Licence

Project code uses Apache License 2.0; see LICENSE. Third-party materials retain
their own licences and notices.
