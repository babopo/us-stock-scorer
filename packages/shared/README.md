# Shared

This folder stores shared schema notes and enum mapping between the FastAPI backend and frontend clients.

The backend remains the source of truth for scoring logic. The mini program should only render API responses.

Executable frontend API code now lives in `packages/api-client`. Keep API paths, request defaults, platform transports, and frontend error mapping there instead of duplicating them in the Mini Program or future Web admin app.
