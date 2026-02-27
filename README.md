# Identity Reconciliation

A backend service that links multiple orders from the same customer even when they use different emails or phone numbers.

## Live API
```
https://identity-reconciliation-vn3x.onrender.com
```

## How It Works

When a customer places an order, they provide an email or phone number. If they use different contact details next time, this service detects the overlap and links both records together — keeping one **primary** contact and marking the rest as **secondary**.

## Endpoint

**POST** `/identify`

Request:
```json
{
  "email": "mcfly@hillvalley.edu",
  "phoneNumber": "123456"
}
```

Response:
```json
{
  "contact": {
    "primaryContatctId": 1,
    "emails": ["lorraine@hillvalley.edu", "mcfly@hillvalley.edu"],
    "phoneNumbers": ["123456"],
    "secondaryContactIds": [23]
  }
}
```

## Rules

- If no contact exists → create a new **primary** contact
- If contact exists but has new info → create a **secondary** contact linked to primary
- If two separate primaries get linked → older one stays primary, newer becomes secondary

## Tech Stack

- **FastAPI** — Python web framework
- **Supabase** — PostgreSQL database
- **Render** — Deployment

## Test It

Open the Swagger UI in your browser:
```
https://identity-reconciliation-vn3x.onrender.com/docs
```
