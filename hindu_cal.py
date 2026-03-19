from __future__ import annotations

from datetime import datetime, timedelta
from math import ceil
from typing import Optional, List, Dict, Any
from zoneinfo import ZoneInfo

import swisseph as swe
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel


app = FastAPI(
    title="Hindu Calendar API",
    version="1.0.0",
    description="Real Panchang API using Swiss Ephemeris"
)


# -----------------------------
# Models
# -----------------------------

class LocationModel(BaseModel):
    latitude: float
    longitude: float
    timezone: str


class HinduDateResponse(BaseModel):
    status: str
    date: str
    location: LocationModel
    sunrise: str
    sunset: str
    tithi: str
    paksha: str
    nakshatra: str
    yoga: str
    karana: str
    weekday: str
    festival: str
    festival_candidates: List[str]


# -----------------------------
# Constants
# -----------------------------

TITHI_NAMES = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Purnima",
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Amavasya"
]

NAKSHATRA_NAMES = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashirsha", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha",
    "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha",
    "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada",
    "Uttara Bhadrapada", "Revati"
]

YOGA_NAMES = [
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana",
    "Atiganda", "Sukarma", "Dhriti", "Shoola", "Ganda",
    "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra",
    "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva",
    "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma",
    "Indra", "Vaidhriti"
]

KARANA_NAMES = [
    "Bava", "Balava", "Kaulava", "Taitila", "Garaja", "Vanija", "Vishti",
    "Bava", "Balava", "Kaulava", "Taitila", "Garaja", "Vanija", "Vishti",
    "Bava", "Balava", "Kaulava", "Taitila", "Garaja", "Vanija", "Vishti",
    "Bava", "Balava", "Kaulava", "Taitila", "Garaja", "Vanija", "Vishti",
    "Bava", "Balava", "Kaulava", "Taitila", "Garaja", "Vanija", "Vishti",
    "Bava", "Balava", "Kaulava", "Taitila", "Garaja", "Vanija", "Vishti",
    "Bava", "Balava", "Kaulava", "Taitila", "Garaja", "Vanija", "Vishti",
    "Shakuni", "Chatushpada", "Naga", "Kimstughna", "Bava", "Balava",
    "Kaulava", "Taitila", "Garaja", "Vanija", "Vishti"
]

WEEKDAY_NAMES = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
]


# -----------------------------
# Swiss Ephemeris setup
# -----------------------------

# If you have local ephemeris files, point to them here.
# swe.set_ephe_path("/path/to/ephe")
swe.set_sid_mode(swe.SIDM_LAHIRI)

RISE_FLAGS = swe.BIT_DISC_CENTER | swe.BIT_NO_REFRACTION


# -----------------------------
# Helpers
# -----------------------------

def norm360(value: float) -> float:
    return value % 360.0


def to_hhmm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def gregorian_to_jd(dt: datetime) -> float:
    return swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute / 60 + dt.second / 3600.0)


def jd_to_datetime_local(jd: float, tz_name: str) -> datetime:
    y, m, d, hour_float = swe.revjul(jd, swe.GREG_CAL)
    hour = int(hour_float)
    minute_float = (hour_float - hour) * 60
    minute = int(minute_float)
    second = int(round((minute_float - minute) * 60))
    if second == 60:
        second = 59

    tz = ZoneInfo(tz_name)
    return datetime(y, m, d, hour, minute, second, tzinfo=ZoneInfo("UTC")).astimezone(tz)


def validate_timezone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid timezone: {tz_name}") from exc


def parse_local_datetime(date_str: str, tz_name: str, time_str: Optional[str]) -> datetime:
    tz = validate_timezone(tz_name)
    try:
        base_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc

    if time_str:
        try:
            hh, mm = map(int, time_str.split(":"))
            return datetime(base_date.year, base_date.month, base_date.day, hh, mm, tzinfo=tz)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="time must be HH:MM") from exc

    return datetime(base_date.year, base_date.month, base_date.day, 6, 0, tzinfo=tz)


def sidereal_longitude(jd_ut: float, body: int) -> float:
    result = swe.calc_ut(jd_ut, body, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
    return norm360(result[0][0])


def tropical_longitude(jd_ut: float, body: int) -> float:
    result = swe.calc_ut(jd_ut, body, swe.FLG_SWIEPH)
    return norm360(result[0][0])


def lunar_phase(jd_ut: float) -> float:
    moon = sidereal_longitude(jd_ut, swe.MOON)
    sun = sidereal_longitude(jd_ut, swe.SUN)
    return norm360(moon - sun)


def sunrise_jd(local_date: datetime, lat: float, lon: float, tz_name: str) -> float:
    tz = validate_timezone(tz_name)
    local_midnight = datetime(local_date.year, local_date.month, local_date.day, 0, 0, tzinfo=tz)
    utc_midnight = local_midnight.astimezone(ZoneInfo("UTC"))
    jd_guess = gregorian_to_jd(utc_midnight)

    res = swe.rise_trans(
        jd_guess,
        swe.SUN,
        geopos=(lon, lat, 0),
        rsmi=RISE_FLAGS | swe.CALC_RISE
    )
    return res[1][0]


def sunset_jd(local_date: datetime, lat: float, lon: float, tz_name: str) -> float:
    tz = validate_timezone(tz_name)
    local_midnight = datetime(local_date.year, local_date.month, local_date.day, 0, 0, tzinfo=tz)
    utc_midnight = local_midnight.astimezone(ZoneInfo("UTC"))
    jd_guess = gregorian_to_jd(utc_midnight)

    res = swe.rise_trans(
        jd_guess,
        swe.SUN,
        geopos=(lon, lat, 0),
        rsmi=RISE_FLAGS | swe.CALC_SET
    )
    return res[1][0]


def tithi_index(jd_ut: float) -> int:
    return int(norm360(lunar_phase(jd_ut)) // 12) + 1


def paksha_from_tithi(tithi_num: int) -> str:
    return "Shukla Paksha" if tithi_num <= 15 else "Krishna Paksha"


def nakshatra_index(jd_ut: float) -> int:
    moon = sidereal_longitude(jd_ut, swe.MOON)
    return int(moon // (360 / 27)) + 1


def yoga_index(jd_ut: float) -> int:
    moon = sidereal_longitude(jd_ut, swe.MOON)
    sun = sidereal_longitude(jd_ut, swe.SUN)
    total = norm360(moon + sun)
    return int(total // (360 / 27)) + 1


def karana_index(jd_ut: float) -> int:
    phase = lunar_phase(jd_ut)
    half_tithi = int(phase // 6) + 1
    if half_tithi < 1:
        half_tithi = 1
    if half_tithi > len(KARANA_NAMES):
        half_tithi = len(KARANA_NAMES)
    return half_tithi


def sidereal_solar_sign(jd_ut: float) -> int:
    sun = sidereal_longitude(jd_ut, swe.SUN)
    return int(sun // 30) + 1


def festival_candidates(
    tithi_num: int,
    paksha: str,
    weekday: str,
    prev_solar_sign: int,
    current_solar_sign: int
) -> List[str]:
    out: List[str] = []

    if tithi_num in (11, 26):
        out.append("Ekadashi")

    if tithi_num in (14, 29):
        out.append("Pradosh")

    if tithi_num == 15:
        out.append("Purnima")

    if tithi_num == 30:
        out.append("Amavasya")

    if tithi_num in (4, 19):
        out.append("Sankashti Chaturthi" if paksha == "Krishna Paksha" else "Vinayaka Chaturthi (monthly)")

    if tithi_num == 29 and paksha == "Krishna Paksha":
        out.append("Masik Shivaratri")

    if prev_solar_sign != current_solar_sign:
        out.append("Sankranti")

    # A few weekday-based observances
    if weekday == "Tuesday" and tithi_num in (4, 19):
        out.append("Angarki Chaturthi")

    # De-duplicate while preserving order
    seen = set()
    final = []
    for item in out:
        if item not in seen:
            seen.add(item)
            final.append(item)
    return final


def compute_panchang(dt_local: datetime, lat: float, lon: float, tz_name: str) -> Dict[str, Any]:
    sunrise_today_jd = sunrise_jd(dt_local, lat, lon, tz_name)
    sunset_today_jd = sunset_jd(dt_local, lat, lon, tz_name)

    # Panchang is generally taken at sunrise for the day.
    tithi_num = tithi_index(sunrise_today_jd)
    nak_num = nakshatra_index(sunrise_today_jd)
    yog_num = yoga_index(sunrise_today_jd)
    kar_num = karana_index(sunrise_today_jd)

    weekday = WEEKDAY_NAMES[dt_local.weekday()]
    paksha = paksha_from_tithi(tithi_num)

    prev_day = dt_local - timedelta(days=1)
    prev_sunrise_jd = sunrise_jd(prev_day, lat, lon, tz_name)

    prev_sign = sidereal_solar_sign(prev_sunrise_jd)
    curr_sign = sidereal_solar_sign(sunrise_today_jd)

    candidates = festival_candidates(
        tithi_num=tithi_num,
        paksha=paksha,
        weekday=weekday,
        prev_solar_sign=prev_sign,
        current_solar_sign=curr_sign
    )

    sunrise_local = jd_to_datetime_local(sunrise_today_jd, tz_name)
    sunset_local = jd_to_datetime_local(sunset_today_jd, tz_name)

    return {
        "status": "ok",
        "sunrise": to_hhmm(sunrise_local),
        "sunset": to_hhmm(sunset_local),
        "tithi": TITHI_NAMES[tithi_num - 1],
        "paksha": paksha,
        "nakshatra": NAKSHATRA_NAMES[nak_num - 1],
        "yoga": YOGA_NAMES[yog_num - 1],
        "karana": KARANA_NAMES[kar_num - 1],
        "weekday": weekday,
        "festival": candidates[0] if candidates else "",
        "festival_candidates": candidates,
    }


# -----------------------------
# Routes
# -----------------------------

@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Hindu Calendar API is running",
        "docs": "/docs"
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/hindu-date", response_model=HinduDateResponse)
def get_hindu_date(
    date: str = Query(..., description="YYYY-MM-DD"),
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    timezone: str = Query("Asia/Kolkata", description="IANA timezone"),
    time: Optional[str] = Query(None, description="Optional HH:MM"),
):
    dt_local = parse_local_datetime(date, timezone, time)

    result = compute_panchang(
        dt_local=dt_local,
        lat=lat,
        lon=lon,
        tz_name=timezone
    )

    return HinduDateResponse(
        date=date,
        location=LocationModel(latitude=lat, longitude=lon, timezone=timezone),
        **result
    )
# ---------------------------------
# RUN SERVER (like Flask)
# ---------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",   # filename:app_variable
        host="0.0.0.0",
        port=8000,
        reload=True
    )
