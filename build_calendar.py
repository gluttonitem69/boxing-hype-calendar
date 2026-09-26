import os, json, requests
from ics import Calendar, Event
from google import genai

RAPIDAPI_KEY = os.environ["RAPIDAPI_KEY"]
GEMINI_KEY = os.environ["GEMINI_KEY"]
HYPE_THRESHOLD = 6

def fetch_schedule():
    url = "https://boxing-data-api.p.rapidapi.com/v2/events/schedule"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "boxing-data-api.p.rapidapi.com"
    }
    resp = requests.get(url, headers=headers, params={"days": 7, "page_size": 25})
    data = resp.json()
    with open("raw_events.json", "w") as f:
        json.dump(data, f)
    return data.get("data", [])

def score_hype(client, event_title):
    prompt = f"""Rate this boxing event's mainstream hype on a scale of 1-10.
Consider influencer/celebrity crossover appeal, title stakes, rivalry narrative,
broadcast prominence, and general public buzz. Respond with ONLY a number.

Event: {event_title}"""
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt
    )
    try:
        return int(response.text.strip())
    except ValueError:
        return 0

def build_ics(events):
    cal = Calendar()
    for e in events:
        ev = Event()
        ev.name = f"{e.get('title','Boxing Event')} (Hype: {e['hype_score']}/10)"
        ev.begin = e.get("date")
        ev.duration = {"hours": 3}
        ev.location = e.get("venue", "")
        cal.events.add(ev)
    os.makedirs("docs", exist_ok=True)
    with open("docs/boxing.ics", "w") as f:
        f.writelines(cal)

def main():
    client = genai.Client(api_key=GEMINI_KEY)
    raw_events = fetch_schedule()
    scored = []
    for e in raw_events:
        title = e.get("title", "")
        score = score_hype(client, title)
        e["hype_score"] = score
        scored.append(e)
        print(f"{title}: {score}")
    filtered = [e for e in scored if e["hype_score"] >= HYPE_THRESHOLD]
    build_ics(filtered)

if __name__ == "__main__":
    main()
