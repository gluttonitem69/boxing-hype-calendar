import os, json, requests
from ics import Calendar, Event
from google import genai
from google.genai import types

RAPIDAPI_KEY = os.environ["RAPIDAPI_KEY"]
GEMINI_KEY = os.environ["GEMINI_KEY"]
HYPE_THRESHOLD = 5

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
    return events

def score_hype(client, event):
    title = event.get("title", "")
    venue = event.get("location", "")
    broadcast = event.get("broadcast", [])
    networks = ", ".join(
        n for b in broadcast for n in b.get("broadcasters", [])
    ) if broadcast else "unknown"

    prompt = f"""Search the web to find out who is fighting in this boxing event
and how much mainstream/public hype it has right now.

Event title: {title}
Venue/Location: {venue}
Broadcaster(s): {networks}

Score the event 1-10 using these anchors:
- 9-10: Global crossover spectacle (major influencer, legendary crossover star, undisputed title unification).
- 6-8: Strong mainstream draw (famous ex-champion, MMA/UFC crossover star, actor/celebrity fighter, major title fight, big rivalry).
- 3-5: Moderate interest (recognizable prospects, regional title, no major star power).
- 1-2: Low-profile regional card with no widely-known names.

After searching, respond with ONLY this JSON on the final line, nothing else after it:
{{"score": <integer 1-10>, "reason": "<one short phrase>"}}"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
    )
    text = response.text.strip()
    print("Gemini raw response for '" + title + "':", repr(text))

    try:
        json_line = text.splitlines()[-1]
        parsed = json.loads(json_line)
        score = int(parsed.get("score", 0))
        reason = parsed.get("reason", "")
    except (ValueError, TypeError, json.JSONDecodeError, IndexError):
        score, reason = 0, "parse_error"

    return score, reason

def build_ics(events):
    cal = Calendar()
    for e in events:
        ev = Event()
        ev.name = f"{e.get('title','Boxing Event')} (Hype: {e['hype_score']}/10)"
        ev.begin = e.get("date")
        ev.duration = {"hours": 3}
        ev.location = e.get("location", "")
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
        score, reason = score_hype(client, e)
        e["hype_score"] = score
        e["hype_reason"] = reason
        scored.append(e)
        print(f"SCORED: {e.get('title')}: {score} ({reason})")
    filtered = [e for e in scored if e["hype_score"] >= HYPE_THRESHOLD]
    print("Events above threshold:", len(filtered))
    build_ics(filtered)

if __name__ == "__main__":
    main()
