import functions_framework
import requests
import json
import os
import datetime

from cryptography.fernet import Fernet

board_id_test = "6988c0a8ab2dccb7f9839ee0"
list_id_emails = "6988c0ad06a599850a6acd19"
list_id_cooldowns = "6988c0b45015f53b4fe6dac5"
list_id_queue = "6988eb8235b43d09958f3763"

def make_trello_request(method, url, **kwargs):
    headers = {
        "Accept": "application/json"
    }

    query = {
        "key": "188109d0864072342e627715e4d7c1ce",
        "token": os.environ["TRELLO_API_TOKEN"],
        **kwargs
    }

    response = requests.request(
        method,
        url,
        headers=headers,
        params=query,
    )

    return response

def get_queue_from_trello():
    response = make_trello_request("GET", f"https://api.trello.com/1/lists/{list_id_queue}/cards")
    if response.status_code == 200:
        queue_data = json.loads(response.text)
        return [(card["name"], card["id"]) for card in queue_data]
    else:
        return []

@functions_framework.http
def index(request):
    if request.method == "POST":
        if "advance_queue" in request.args:
            queue = get_queue_from_trello()
            response = make_trello_request("DELETE", f"https://api.trello.com/1/cards/{queue[0][1]}")
            return "OK"
        elif "new_donation" in request.args:
            data = json.loads(request.form["data"])
            if data.get("verification_token") == os.environ["KOFI_VERIFICATION_TOKEN"] and data.get("type") == "Donation":
                dono_name = data["from_name"]
                dono_email = data["email"]
                dono_amount = float(data["amount"])

                email_cards_response = make_trello_request("GET", f"https://api.trello.com/1/lists/{list_id_emails}/cards")
                email_cards = json.loads(email_cards_response.text)

                fernet = Fernet(os.environ["ENCRYPTION_KEY"])
                existing_card = list(filter(lambda card: fernet.decrypt(card["desc"]).decode() == dono_email, email_cards))
                if len(existing_card) == 0:
                    email_encrypted = fernet.encrypt(dono_email.encode())
                    make_trello_request("POST", "https://api.trello.com/1/cards", idList=list_id_emails, name=f"*** Please enter Twitch name for {dono_name} ***", desc=email_encrypted)
                else:
                    dono_name = existing_card[0]["name"]

                add_to_queue = True
                if dono_amount < 25.0:
                    cooldown_cards_response = make_trello_request("GET", f"https://api.trello.com/1/lists/{list_id_cooldowns}/cards")
                    cooldown_cards = json.loads(cooldown_cards_response.text)
                    cooldown_card = list(filter(lambda card: card["name"] == dono_name, cooldown_cards))
                    
                    if len(cooldown_card) > 0:
                        cooldown_date = datetime.datetime.fromisoformat(cooldown_card[0]["desc"])
                        time_since = datetime.datetime.now() - cooldown_date
                        if time_since.days < 90:
                            add_to_queue = False
                        else:
                            make_trello_request("PUT", f"https://api.trello.com/1/cards/{cooldown_card[0]['id']}", desc=datetime.datetime.now().isoformat())
                    else:
                        make_trello_request("POST", "https://api.trello.com/1/cards", idList=list_id_cooldowns, name=dono_name, desc=datetime.datetime.now().isoformat())

                if add_to_queue:
                    make_trello_request("POST", "https://api.trello.com/1/cards", idList=list_id_queue, name=dono_name)
                
        return "OK"
    elif request.method == "GET" and "get_queue" in request.args:
        queue = get_queue_from_trello()
        return json.dumps(queue)

    return "OK"
