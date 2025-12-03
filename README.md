# Out-App Django Backend for Messaging App

This folder contains a Django + Channels backend for the messaging frontend. It provides REST endpoints and WebSocket routes for rooms and messages.

Quick start:

1. Create and activate a Python virtual env

```powershell
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies
```powershell
pip install -r requirements.txt
```

3. Run migrations
```powershell
python manage.py makemigrations
python manage.py migrate
```

4. Run the ASGI server (daphne) on port 8001 so it doesn't conflict with any other backend
```powershell
daphne -b 127.0.0.1 -p 8001 chatbackend_out.asgi:application
```
Or run `python manage.py runserver 127.0.0.1:8001` for HTTP-only (no channels)

5. Update your frontend env to point at this backend if needed:
```
VITE_API_URL=http://localhost:8001/api
VITE_WS_URL=ws://localhost:8001
NEXT_PUBLIC_API_URL=http://localhost:8001/api
NEXT_PUBLIC_WS_URL=ws://localhost:8001
```

Endpoints:
- `GET /api/rooms/` — list rooms
- `POST /api/rooms/` — create room
- `POST /api/rooms/join/` — find room by key (body { room_key: 'KEY' })
- `GET /api/rooms/<id>/` — room detail
- `GET /api/rooms/<id>/messages/` — list messages
- `POST /api/rooms/<id>/messages/` — create message
- WebSocket: `ws://host/ws/chat/<room_id>/` — real-time messages
