import os
import requests
import sys
import toml
from datetime import datetime, timedelta

STRAVA_API_URL = "https://www.strava.com/api/v3"
STRAVA_CLIENT_ID =  os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")

class ActivitySummary:
    def __init__(
        self,
        id: int,
        name: str,
        private: bool,
    ) -> None:
        self.id = id
        self.name = name
        self.private = private

class Activity:
    def __init__(
        self,
        id: int,
        name: str,
        start_datetime: datetime,
        end_datetime: datetime,
        private: bool,
        private_note: str,
        distance: float,
        total_elevation_gain: float,
        description: str,
        summary_polyline: str,
        photos: list[str] = [],
    ) -> None:
        self.id = id
        self.name = name
        self.start_datetime = start_datetime
        self.end_datetime = end_datetime
        self.private = private
        self.private_note = private_note
        self.distance = distance
        self.total_elevation_gain = total_elevation_gain
        self.description = description
        self.summary_polyline = summary_polyline
        self.photos = photos

def main(magic_word: str, page_output_dir: str) -> None:
    print("Getting access token from refresh token...")
    access_token = get_access_token()

    print("Finding non-private activities that contain a private note starting with the chosen magic word...")
    found_activities = find_activities(access_token, magic_word=magic_word)

    print("Generating pages for found activities...")
    generated_pages = [generate_activity_page(found_activity, output_dir=page_output_dir) for found_activity in found_activities]

    print(f"Generated the following pages: {generated_pages}")

def get_access_token() -> str:
    token_url = "/".join([STRAVA_API_URL, "oauth", "token"])
    data = {
        "grant_type": "refresh_token",
        "client_id": STRAVA_CLIENT_ID,
        "client_secret": STRAVA_CLIENT_SECRET,
        "refresh_token": STRAVA_REFRESH_TOKEN,
    }

    response = requests.post(token_url, data=data)
    response.raise_for_status()

    return response.json()["access_token"]

def find_activities(access_token: str, magic_word: str):
    activity_summaries = get_activity_summaries(access_token)

    for activity_summary in activity_summaries:
        # ignore private activities
        if activity_summary.private:
            continue

        activity = get_activity(access_token, activity_summary.id)

        # ignore activities that don't have a private note beginning with the magic word
        if not activity.private_note.startswith(magic_word):
            continue

        activity.photos = get_activity_photos(access_token, activity.id)

        yield activity

def generate_activity_page(activity: Activity, output_dir: str) -> str:
    toml_contents = {
        "title": activity.name,
        "extra": {
            "activity": activity.id,
            "distance": round(activity.distance / 1000, 2),
            "distance_imperial": round(activity.distance / 1000 * 0.621371, 2),
            "elevationgain": round(activity.total_elevation_gain, 2),
            "elevationgain_imperial": round(activity.total_elevation_gain * 3.28084, 2),
        },
    }

    if activity.summary_polyline:
        # this is ugly... escape backslashes in the polyline so that it's still escaped
        # once it's processed by the template engine and dropped into a javascript variable
        summary_polyline = activity.summary_polyline.replace("\\", "\\\\")

        toml_contents["extra"]["polyline"] = summary_polyline

    if activity.photos:
        toml_contents["extra"]["pictures"] = activity.photos

    filename = os.path.join(output_dir, f"{activity.end_datetime.date()}-{activity.id}.md")
    with open(filename, "w") as file:
        lines: list[str] = []
        lines.append(f"+++\n{toml.dumps(toml_contents)}+++")
        lines.append("")

        if activity.description:
            lines.append(f"## Description")
            lines.append("")
            lines.append(activity.description)
            lines.append("")

        file.write("\n".join(lines))

    return filename

def get_activity_summaries(access_token: str, count: int=200) -> list[ActivitySummary]:
    activities_url = "/".join([STRAVA_API_URL, "athlete", "activities"])
    headers = {"Authorization": "Bearer " + access_token}
    params = {"per_page": count, "page": 1}

    activities = requests.get(activities_url, headers=headers, params=params).json()

    return [ActivitySummary(id=activity["id"], name=activity["name"], private=activity["private"]) for activity in activities]

def get_activity(access_token: str, activity_id: int) -> Activity:
    activity_url = "/".join([STRAVA_API_URL, "activities", str(activity_id)])
    headers = {"Authorization": "Bearer " + access_token}
    params = {"include_all_efforts ": False}

    activity = requests.get(activity_url, headers=headers, params=params).json()

    return Activity(
        id=activity["id"],
        name=activity["name"],
        start_datetime=datetime.fromisoformat(activity["start_date"]),
        end_datetime=datetime.fromisoformat(activity["start_date"]) + timedelta(seconds=activity["elapsed_time"]),
        private=activity["private"],
        private_note=activity["private_note"],
        distance=activity["distance"],
        total_elevation_gain=activity["total_elevation_gain"],
        description=activity["description"],
        summary_polyline=activity["map"]["summary_polyline"],
    )

def get_activity_photos(access_token: str, activity_id: int, photo_size: int=1000) -> list[str]:
    PHOTO_TYPE_STILL = 1

    activity_photos_url = "/".join([STRAVA_API_URL, "activities", str(activity_id), "photos"])
    headers = {"Authorization": "Bearer " + access_token}
    params = {"size": photo_size}

    activity_photos = requests.get(activity_photos_url, headers=headers, params=params).json()
    photo_urls = [activity_photo["urls"][str(photo_size)] for activity_photo in activity_photos if activity_photo["type"] == PHOTO_TYPE_STILL]

    return photo_urls

if __name__ == "__main__":
    main(magic_word="ssg", page_output_dir=sys.argv[1])
