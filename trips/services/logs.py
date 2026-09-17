"""Convert chronological duty segments into 24-hour daily log sheets."""

from __future__ import annotations

from datetime import datetime, timedelta, date
from typing import Any

STATUS_OFF = "OFF_DUTY"
STATUS_SB = "SLEEPER_BERTH"
STATUS_DRIVE = "DRIVING"
STATUS_ON = "ON_DUTY_NOT_DRIVING"

ALL_STATUSES = (STATUS_OFF, STATUS_SB, STATUS_DRIVE, STATUS_ON)


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def build_daily_logs(
    segments: list[dict[str, Any]],
    *,
    shift_start: datetime,
    trip_end: datetime,
    meta: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Clip segments to calendar days and ensure each day totals 24 hours."""
    meta = meta or {}
    if not segments:
        # Entirely off-duty day covering shift_start date.
        day = shift_start.date()
        start = datetime.combine(day, datetime.min.time()).replace(tzinfo=shift_start.tzinfo)
        end = start + timedelta(days=1)
        return [_day_log(day, [{"status": STATUS_OFF, "start": start, "end": end, "location": "", "remark": "Off duty"}], meta)]

    # Normalize to aware/naive consistently with shift_start.
    normalized: list[dict[str, Any]] = []
    for seg in segments:
        start = _parse(seg["start"])
        end = _parse(seg["end"])
        if start.tzinfo != shift_start.tzinfo:
            # Keep as-is if both naive or both aware; otherwise strip/apply carefully.
            if shift_start.tzinfo is None and start.tzinfo is not None:
                start = start.replace(tzinfo=None)
                end = end.replace(tzinfo=None)
        normalized.append(
            {
                "status": seg["status"],
                "start": start,
                "end": end,
                "location": seg.get("location", ""),
                "remark": seg.get("remark", ""),
            }
        )

    first_day = min(normalized[0]["start"], shift_start).date()
    last_day = max(normalized[-1]["end"], trip_end).date()

    # Fill leading off-duty from midnight of first day to first segment.
    filled: list[dict[str, Any]] = []
    day_start = datetime.combine(first_day, datetime.min.time())
    if shift_start.tzinfo is not None:
        day_start = day_start.replace(tzinfo=shift_start.tzinfo)

    cursor = day_start
    for seg in normalized:
        if seg["start"] > cursor:
            filled.append(
                {
                    "status": STATUS_OFF,
                    "start": cursor,
                    "end": seg["start"],
                    "location": seg.get("location", ""),
                    "remark": "Off duty",
                }
            )
        filled.append(seg)
        cursor = seg["end"]

    # Trailing off-duty through end of last calendar day.
    final_midnight = datetime.combine(last_day + timedelta(days=1), datetime.min.time())
    if shift_start.tzinfo is not None:
        final_midnight = final_midnight.replace(tzinfo=shift_start.tzinfo)
    if cursor < final_midnight:
        filled.append(
            {
                "status": STATUS_OFF,
                "start": cursor,
                "end": final_midnight,
                "location": normalized[-1].get("location", ""),
                "remark": "Off duty",
            }
        )

    logs: list[dict[str, Any]] = []
    day = first_day
    while day <= last_day:
        day_segments = _clip_to_day(filled, day, shift_start.tzinfo)
        logs.append(_day_log(day, day_segments, meta))
        day += timedelta(days=1)
    return logs


def _clip_to_day(
    segments: list[dict[str, Any]],
    day: date,
    tzinfo,
) -> list[dict[str, Any]]:
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    if tzinfo is not None:
        start = start.replace(tzinfo=tzinfo)
        end = end.replace(tzinfo=tzinfo)

    clipped: list[dict[str, Any]] = []
    for seg in segments:
        seg_start = max(seg["start"], start)
        seg_end = min(seg["end"], end)
        if seg_end > seg_start:
            clipped.append(
                {
                    "status": seg["status"],
                    "start": seg_start,
                    "end": seg_end,
                    "location": seg.get("location", ""),
                    "remark": seg.get("remark", ""),
                }
            )

    # Ensure full coverage of the day.
    if not clipped:
        return [
            {
                "status": STATUS_OFF,
                "start": start,
                "end": end,
                "location": "",
                "remark": "Off duty",
            }
        ]

    result: list[dict[str, Any]] = []
    cursor = start
    for seg in clipped:
        if seg["start"] > cursor:
            result.append(
                {
                    "status": STATUS_OFF,
                    "start": cursor,
                    "end": seg["start"],
                    "location": "",
                    "remark": "Off duty",
                }
            )
        result.append(seg)
        cursor = seg["end"]
    if cursor < end:
        result.append(
            {
                "status": STATUS_OFF,
                "start": cursor,
                "end": end,
                "location": "",
                "remark": "Off duty",
            }
        )
    return result


def _day_log(day: date, segments: list[dict[str, Any]], meta: dict[str, Any]) -> dict[str, Any]:
    totals = {s: 0.0 for s in ALL_STATUSES}
    plot: list[dict[str, Any]] = []
    remarks: list[dict[str, Any]] = []

    for seg in segments:
        hours = (seg["end"] - seg["start"]).total_seconds() / 3600.0
        totals[seg["status"]] = totals.get(seg["status"], 0.0) + hours
        start_min = seg["start"].hour * 60 + seg["start"].minute + seg["start"].second / 60.0
        end_min = seg["end"].hour * 60 + seg["end"].minute + seg["end"].second / 60.0
        if seg["end"].date() > seg["start"].date() or (
            seg["end"].hour == 0 and seg["end"].minute == 0 and hours > 0
        ):
            end_min = 24 * 60
        plot.append(
            {
                "status": seg["status"],
                "startMinute": round(start_min, 2),
                "endMinute": round(end_min, 2),
                "hours": round(hours, 4),
                "location": seg.get("location", ""),
                "remark": seg.get("remark", ""),
            }
        )
        if seg["status"] != STATUS_OFF or seg.get("remark") not in ("Off duty", ""):
            remarks.append(
                {
                    "time": seg["start"].strftime("%H:%M"),
                    "location": seg.get("location", ""),
                    "text": seg.get("remark", ""),
                    "status": seg["status"],
                }
            )

    total_hours = sum(totals.values())
    # Normalize tiny float drift to exactly 24.
    if abs(total_hours - 24.0) < 0.05:
        drift = 24.0 - total_hours
        totals[STATUS_OFF] = round(totals[STATUS_OFF] + drift, 4)
        total_hours = 24.0

    return {
        "date": day.isoformat(),
        "month": day.month,
        "day": day.day,
        "year": day.year,
        "carrierName": meta.get("carrierName", "Spotter Demo Carrier"),
        "mainOfficeAddress": meta.get("mainOfficeAddress", "Dallas, TX"),
        "driverName": meta.get("driverName", "Demo Driver"),
        "coDriverName": meta.get("coDriverName", ""),
        "vehicleNumbers": meta.get("vehicleNumbers", "TRK-100 / TRL-200"),
        "shippingDoc": meta.get("shippingDoc", "DEMO-001"),
        "totalMilesDriving": round(
            sum(p["hours"] for p in plot if p["status"] == STATUS_DRIVE)
            * float(meta.get("averageSpeedMph") or 55.0),
            1,
        ),
        "fromLocation": meta.get("fromLocation", ""),
        "toLocation": meta.get("toLocation", ""),
        "segments": plot,
        "remarks": remarks,
        "totals": {
            "offDuty": round(totals[STATUS_OFF], 2),
            "sleeperBerth": round(totals[STATUS_SB], 2),
            "driving": round(totals[STATUS_DRIVE], 2),
            "onDutyNotDriving": round(totals[STATUS_ON], 2),
            "all": round(total_hours, 2),
        },
        "recap": {
            "onDutyToday": round(totals[STATUS_DRIVE] + totals[STATUS_ON], 2),
        },
    }
