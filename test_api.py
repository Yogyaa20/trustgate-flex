import asyncio
import httpx
import sqlite3
import time

async def main():
    # Find alice's email, asset id, device id
    conn = sqlite3.connect("trustgate.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, email FROM users WHERE name LIKE 'Alice%'")
    user = cursor.fetchone()
    alice_id, alice_email = user[0], user[1]

    cursor.execute("SELECT id FROM devices WHERE user_id = ?", (alice_id,))
    device_id = cursor.fetchone()[0]

    cursor.execute("SELECT id FROM assets LIMIT 1")
    asset_id = cursor.fetchone()[0]
    conn.close()

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        # Wait for server
        for i in range(10):
            try:
                r = await client.get("/health")
                break
            except httpx.ConnectError:
                await asyncio.sleep(1)

        print("1. Health Check")
        r = await client.get("/health")
        print(r.status_code, r.json())

        print("\n2. Login")
        login_data = {"username": alice_email, "password": "demo123"}
        r = await client.post("/api/v1/auth/login", json=login_data)
        print(r.status_code)
        if r.status_code != 200:
            print(r.text)
            return
        
        token = r.json()["access_token"]
        print("Token:", token[:20] + "...")

        print("\n3. Access Request")
        req_data = {
            "asset_id": asset_id,
            "device_id": device_id,
            "request_type": "READ",
            "location_hash": "office-hq"
        }
        r = await client.post(
            "/api/v1/access/request", 
            json=req_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        print(r.status_code)
        import json
        print(json.dumps(r.json(), indent=2))

asyncio.run(main())
