import os, json, requests
from datetime import datetime, timezone
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

    prompt = f"""Search the web to find out who is fighting in this boxing event.

IMPORTANT: I am scoring MAINSTREAM WESTERN POP-CULTURE HYPE, not boxing skill,
rankings, or regional fame. A fighter can be a top-ranked pound-for-pound
world champion and still score LOW here if their fame is mostly confined to
one country/region (e.g. a Japanese star famous mainly in Japan, or a
domestic-only prospect) and they haven't crossed over into US/UK mainstream
sports media or social media buzz.

Score 1-10 using these anchors:
- 9-10: Viral crossover spectacle known outside boxing entirely (influencer fighters
  like Jake Paul/Andrew Tate/KSI, celebrity/actor crossover fighters, or a boxer so
  famous they're a household name in the US/UK even to non-fans).
- 6-8: Strong mainstream Western draw (ex-UFC/MMA star crossing over, major
  US/UK title fight getting mainstream sports news coverage, big rivalry with
  trash talk that trends on social media).
- 3-5: Known and respected within the sport, may even be pound-for-pound elite,
  but fame is regional/niche and doesn't reach casual Western sports fans or
  general pop culture (e.g. huge in Japan/Mexico domestically but not in US/UK
  mainstream coverage).
- 1-2: Low-profile regional card, nobody involved is broadly recognizable.

Event title: {title}
Venue/Location: {venue}
Broadcaster(s): {networks}

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
    generated_at = datetime.now(timezone.utc).strftime("%b %d, %I:%M %p UTC")
    for e in events:
        ev = Event()
        title = e.get("title", "Boxing Event")
        ev.name = f"{title} (Hype: {e['hype_score']}/10)"
        ev.begin = e.get("date")
        ev.duration = {"hours": 3}
        ev.location = e.get("location", "")

        broadcast = e.get("broadcast", [])
        networks = ", ".join(
            n for b in broadcast for n in b.get("broadcasters", [])
        ) if broadcast else "TBA"

        search_query = title.replace(" ", "+")
        search_link = f"https://www.google.com/search?q={search_query}+boxing"

        ev.description = (
            f"Hype score: {e['hype_score']}/10 - {e.get('hype_reason','')}\n\n"
            f"Broadcast: {networks}\n\n"
            f"More info: {search_link}\n\n"
            f"Accurate as of {generated_at}"
        )
        ev.url = search_link
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
