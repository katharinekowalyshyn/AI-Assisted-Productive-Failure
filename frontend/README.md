## Frontend: TutorChat UI

This folder contains a minimal single-page web UI that talks to the backend
TutorChat API.

### Layout

- `index.html` – main page and layout.
- `styles.css` – modern dark UI styling.
- `app.js` – `TutorChatApp` class that calls the backend and manages state.

### Running locally (Node.js)

Use the Node.js/Express dev server:

```bash
cd frontend
npm install
npm run dev
```

Then open `http://localhost:3000/` in your browser.

Make sure the backend is running on `http://localhost:8000` (see the backend
README).

- The frontend, by default, sends requests to `http://localhost:8000/api`.
- To change this, either:
  - Set `window.TUTORCHAT_API_BASE_URL` in `index.html`, or
  - Edit the default in `app.js`.
- Ensure CORS settings in `backend/main.py` allow `http://localhost:3000`.

### Where to extend

- UI behavior and state: edit `TutorChatApp` in `app.js`.
- Styling / theming: edit `styles.css`.
- New controls (e.g., language level, target language) can be wired into the
  request payload that `app.js` sends to `/api/chat/`.

