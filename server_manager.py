import json
from crypto import encrypt, decrypt

FILE = "servers.json"

def load_servers():
    try:
        with open(FILE, "r") as f:
            data = json.load(f)
            for s in data:
                s["password"] = decrypt(s["password"])
            return data
    except:
        return []

def save_servers(servers):
    out = []
    for s in servers:
        s2 = s.copy()
        s2["password"] = encrypt(s["password"])
        out.append(s2)

    with open(FILE, "w") as f:
        json.dump(out, f, indent=4)
