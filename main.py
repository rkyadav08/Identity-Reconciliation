from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from supabase import create_client, Client
from datetime import datetime, timezone

app = FastAPI(title="Identity Reconciliation")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


class IdentifyRequest(BaseModel):
    email: Optional[str] = None
    phoneNumber: Optional[str] = None


class ContactResponse(BaseModel):
    primaryContatctId: int
    emails: list[str]
    phoneNumbers: list[str]
    secondaryContactIds: list[int]


class IdentifyResponse(BaseModel):
    contact: ContactResponse


def get_all_contacts_in_cluster(primary_id: int) -> list[dict]:
    """Get the primary contact and all its secondaries."""
    res = supabase.table("Contact").select("*").eq("id", primary_id).is_("deletedAt", "null").execute()
    contacts = res.data

    res2 = supabase.table("Contact").select("*").eq("linkedId", primary_id).is_("deletedAt", "null").execute()
    contacts += res2.data

    return contacts


def find_primary(contact: dict) -> dict:
    """Given any contact, find its primary."""
    if contact["linkPrecedence"] == "primary":
        return contact
    res = supabase.table("Contact").select("*").eq("id", contact["linkedId"]).execute()
    if res.data:
        return res.data[0]
    return contact


def build_response(primary: dict, all_contacts: list[dict]) -> IdentifyResponse:
    emails = []
    phones = []
    secondary_ids = []


    if primary.get("email") and primary["email"] not in emails:
        emails.append(primary["email"])
    if primary.get("phoneNumber") and primary["phoneNumber"] not in phones:
        phones.append(primary["phoneNumber"])

    for c in sorted(all_contacts, key=lambda x: x["createdAt"]):
        if c["id"] == primary["id"]:
            continue
        secondary_ids.append(c["id"])
        if c.get("email") and c["email"] not in emails:
            emails.append(c["email"])
        if c.get("phoneNumber") and c["phoneNumber"] not in phones:
            phones.append(c["phoneNumber"])

    return IdentifyResponse(
        contact=ContactResponse(
            primaryContatctId=primary["id"],
            emails=emails,
            phoneNumbers=phones,
            secondaryContactIds=secondary_ids,
        )
    )


@app.post("/identify", response_model=IdentifyResponse)
async def identify(request: IdentifyRequest):
    email = request.email
    phone = request.phoneNumber

    if not email and not phone:
        raise HTTPException(status_code=400, detail="At least one of email or phoneNumber must be provided")

    now = datetime.now(timezone.utc).isoformat()


    matched: list[dict] = []

    if email:
        res = supabase.table("Contact").select("*").eq("email", email).is_("deletedAt", "null").execute()
        matched += res.data

    if phone:
        res = supabase.table("Contact").select("*").eq("phoneNumber", phone).is_("deletedAt", "null").execute()
        for c in res.data:
            if not any(x["id"] == c["id"] for x in matched):
                matched.append(c)

    
    if not matched:
        new_contact = {
            "phoneNumber": phone,
            "email": email,
            "linkedId": None,
            "linkPrecedence": "primary",
            "createdAt": now,
            "updatedAt": now,
            "deletedAt": None,
        }
        res = supabase.table("Contact").insert(new_contact).execute()
        created = res.data[0]
        return build_response(created, [created])


    primaries: list[dict] = []
    for c in matched:
        p = find_primary(c)
        if not any(x["id"] == p["id"] for x in primaries):
            primaries.append(p)


    primaries.sort(key=lambda x: x["createdAt"])
    true_primary = primaries[0]


    if len(primaries) > 1:
        for p in primaries[1:]:
            supabase.table("Contact").update({
                "linkedId": true_primary["id"],
                "linkPrecedence": "secondary",
                "updatedAt": now,
            }).eq("id", p["id"]).execute()


            supabase.table("Contact").update({
                "linkedId": true_primary["id"],
                "updatedAt": now,
            }).eq("linkedId", p["id"]).execute()


    all_contacts = get_all_contacts_in_cluster(true_primary["id"])

    existing_emails = {c["email"] for c in all_contacts if c.get("email")}
    existing_phones = {c["phoneNumber"] for c in all_contacts if c.get("phoneNumber")}

    new_email = email and email not in existing_emails
    new_phone = phone and phone not in existing_phones


    if new_email or new_phone:
        new_secondary = {
            "phoneNumber": phone,
            "email": email,
            "linkedId": true_primary["id"],
            "linkPrecedence": "secondary",
            "createdAt": now,
            "updatedAt": now,
            "deletedAt": None,
        }
        res = supabase.table("Contact").insert(new_secondary).execute()
        all_contacts.append(res.data[0])

    return build_response(true_primary, all_contacts)


@app.get("/health")
async def health():
    return {"status": "ok"}
