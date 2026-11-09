# Workshop Desk

A small fictional makerspace booking website. Requires Python 3.10 or newer and uses only the standard library.

```sh
python3 app.py
```

Open http://127.0.0.1:8000. All prices and bookings are simulated. The server listens on localhost. It creates a SQLite database beside the app on first run. To reset the demo, stop the server and remove `workshops.sqlite3`, or point `WORKSHOP_DB` at a fresh file before starting.

- `GET /api/workshops?q=bike&page=1` lists workshops, two per page.
- `POST /api/bookings` takes JSON with integer `workshop_id` and `quantity`, plus an `Idempotency-Key` header supplied by the client. The UI's Retry button resends the previous request.
