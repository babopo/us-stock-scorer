# Shared

This folder stores shared schema notes and enum mapping between the FastAPI backend and frontend clients.

The backend remains the source of truth for scoring logic. Web frontends should only render API responses.

Executable frontend API code now lives in `packages/api-client`. Keep API paths, request defaults, web transport code, and frontend error mapping there instead of duplicating them in app-specific code.
