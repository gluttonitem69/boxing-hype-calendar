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
    print("HTTP status:", resp.status_code)
    data = resp.json()
    with open("raw_events.json", "w") as f:
        json.dump(data, f, indent=2)
    events = data.get("data", [])
    print("Number of events found:", len(events))
    if events:
        print("Sample event keys:", list(events[0].keys()))
        print("Sample event:", events[0])
    else:
        print("Full response:", data)
    return events

def score_hype(client, event_title):
    prompt = f"""Rate this boxing event's mainstream hype on a scale of 1-10.
Consider influencer/celebrity crossover appeal, title stakes, rivalry narrative,
broadcast prominence, and general public buzz. Respond with ONLY a number.

Event: {event_title}"""
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt
    )
    print("Gemini raw response for '" + str(event_title) + "':", repr(response.text))
    try:
        return int(response.text.strip())
    except (ValueError, TypeError):
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
    print("Wrote", len(events), "events to docs/boxing.ics")

def main():
    client = genai.Client(api_key=GEMINI_KEY)
    raw_events = fetch_schedule()
    scored = []
    for e in raw_events:
        title = e.get("title", "")
        score = score_hype(client, title)
        e["hype_score"] = score
        scored.append(e)
        print(f"SCORED: {title}: {score}")
    filtered = [e for e in scored if e["hype_score"] >= HYPE_THRESHOLD]
    print("Events above threshold:", len(filtered))
    build_ics(filtered)

if __name__ == "__main__":
    main()
