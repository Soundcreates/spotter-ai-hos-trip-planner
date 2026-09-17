"""Deterministic Hours-of-Service scheduling engine.

Baseline rules (assignment assumptions):
- Property-carrying driver, 70 hrs / 8 days
- 11-hour driving limit
- 14-hour driving window
- 30-minute break after 8 cumulative driving hours
- 10 consecutive hours off duty resets 11/14 clocks
- Fueling at least once every 1,000 miles (30 minutes on-duty)
- 1 hour on-duty for pickup and 1 hour on-duty for drop-off
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

CALCULATION_VERSION = "hos-v1-70-8"

DRIVE_LIMIT_HOURS = 11.0
WINDOW_LIMIT_HOURS = 14.0
BREAK_AFTER_DRIVE_HOURS = 8.0
BREAK_MINUTES = 30
OFF_DUTY_RESET_HOURS = 10.0
CYCLE_LIMIT_HOURS = 70.0
FUEL_EVERY_MILES = 1000.0
FUEL_MINUTES = 30
PICKUP_HOURS = 1.0
DROPOFF_HOURS = 1.0

STATUS_OFF = "OFF_DUTY"
STATUS_SB = "SLEEPER_BERTH"
STATUS_DRIVE = "DRIVING"
STATUS_ON = "ON_DUTY_NOT_DRIVING"


class HOSPlanningError(Exception):
    """Raised when a trip cannot be scheduled under modeled HOS rules."""


@dataclass
class ClockState:
    drive_used: float = 0.0
    window_used: float = 0.0
    drive_since_break: float = 0.0
    cycle_used: float = 0.0
    miles_since_fuel: float = 0.0
    window_open: bool = False

    def remaining_drive(self) -> float:
        return max(0.0, DRIVE_LIMIT_HOURS - self.drive_used)

    def remaining_window(self) -> float:
        return max(0.0, WINDOW_LIMIT_HOURS - self.window_used)

    def remaining_until_break(self) -> float:
        return max(0.0, BREAK_AFTER_DRIVE_HOURS - self.drive_since_break)

    def remaining_cycle(self) -> float:
        return max(0.0, CYCLE_LIMIT_HOURS - self.cycle_used)

    def remaining_until_fuel(self) -> float:
        return max(0.0, FUEL_EVERY_MILES - self.miles_since_fuel)

    def snapshot(self) -> dict[str, float | bool]:
        return {
            "driveUsedHours": round(self.drive_used, 3),
            "windowUsedHours": round(self.window_used, 3),
            "driveSinceBreakHours": round(self.drive_since_break, 3),
            "cycleUsedHours": round(self.cycle_used, 3),
            "milesSinceFuel": round(self.miles_since_fuel, 2),
            "remainingDriveHours": round(self.remaining_drive(), 3),
            "remainingWindowHours": round(self.remaining_window(), 3),
            "remainingUntilBreakHours": round(self.remaining_until_break(), 3),
            "remainingCycleHours": round(self.remaining_cycle(), 3),
            "remainingUntilFuelMiles": round(self.remaining_until_fuel(), 2),
            "windowOpen": self.window_open,
        }


@dataclass
class Planner:
    shift_start: datetime
    initial_cycle_used: float
    average_speed_mph: float
    events: list[dict[str, Any]] = field(default_factory=list)
    segments: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    cursor: datetime | None = None
    state: ClockState | None = None
    current_location_label: str = ""

    def __post_init__(self) -> None:
        self.cursor = self.shift_start
        self.state = ClockState(cycle_used=self.initial_cycle_used)

    def _emit_segment(
        self,
        status: str,
        start: datetime,
        end: datetime,
        location: str,
        remark: str,
    ) -> None:
        if end <= start:
            return
        hours = (end - start).total_seconds() / 3600.0
        self.segments.append(
            {
                "status": status,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "hours": round(hours, 4),
                "location": location,
                "remark": remark,
            }
        )

    def _add_event(
        self,
        event_type: str,
        start: datetime,
        end: datetime,
        location: str,
        explanation: str,
        status: str,
        before: dict[str, Any],
        after: dict[str, Any],
        miles: float = 0.0,
    ) -> None:
        duration_minutes = (end - start).total_seconds() / 60.0
        self.events.append(
            {
                "type": event_type,
                "status": status,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "durationMinutes": round(duration_minutes, 2),
                "location": location,
                "miles": round(miles, 2),
                "explanation": explanation,
                "stateBefore": before,
                "stateAfter": after,
            }
        )

    def _ensure_can_work(self, hours_needed: float, kind: str) -> None:
        assert self.state is not None
        # On-duty (non-driving) can continue past 14-hour window, but driving cannot.
        # Cycle limit blocks any on-duty that would push past 70 if we later need to drive.
        if kind == "drive":
            if self.state.remaining_cycle() < hours_needed - 1e-9:
                # Try a 10-hour reset first (does NOT reset cycle).
                # If still not enough cycle, fail.
                if self.state.remaining_cycle() <= 0:
                    raise HOSPlanningError(
                        "Trip cannot be completed: 70-hour / 8-day cycle is exhausted "
                        "and a 10-hour daily reset does not restore cycle hours. "
                        "A 34-hour restart would be required (out of modeled scope)."
                    )

    def take_off_duty_reset(self, location: str, reason: str) -> None:
        assert self.cursor is not None and self.state is not None
        before = self.state.snapshot()
        start = self.cursor
        end = start + timedelta(hours=OFF_DUTY_RESET_HOURS)
        self._emit_segment(STATUS_OFF, start, end, location, reason)
        self.state.drive_used = 0.0
        self.state.window_used = 0.0
        self.state.drive_since_break = 0.0
        self.state.window_open = False
        after = self.state.snapshot()
        self._add_event(
            "rest_10h",
            start,
            end,
            location,
            reason,
            STATUS_OFF,
            before,
            after,
        )
        self.cursor = end
        self.current_location_label = location

    def take_break(self, location: str) -> None:
        assert self.cursor is not None and self.state is not None
        before = self.state.snapshot()
        start = self.cursor
        end = start + timedelta(minutes=BREAK_MINUTES)
        # Break may be off-duty; it does not extend available drive beyond window.
        # Window continues to run during break if window is open.
        if self.state.window_open:
            self.state.window_used += BREAK_MINUTES / 60.0
        self._emit_segment(STATUS_OFF, start, end, location, "30-minute rest break")
        self.state.drive_since_break = 0.0
        after = self.state.snapshot()
        self._add_event(
            "break_30m",
            start,
            end,
            location,
            "Required 30-minute break after 8 hours of driving.",
            STATUS_OFF,
            before,
            after,
        )
        self.cursor = end
        self.current_location_label = location

    def take_fuel(self, location: str, miles_marker: float) -> None:
        assert self.cursor is not None and self.state is not None
        # Fuel is on-duty not driving; requires window capacity conceptually for planning
        # but FMCSA allows on-duty past 14h — we keep it inside window when possible.
        hours = FUEL_MINUTES / 60.0
        if self.state.window_open and self.state.remaining_window() < hours:
            self.take_off_duty_reset(location, "10-hour reset before fueling (window limit).")
        if self.state.remaining_cycle() < hours:
            raise HOSPlanningError(
                "Trip cannot be completed: insufficient cycle hours remaining for a fuel stop."
            )

        before = self.state.snapshot()
        start = self.cursor
        end = start + timedelta(minutes=FUEL_MINUTES)
        if not self.state.window_open:
            self.state.window_open = True
        self.state.window_used += hours
        self.state.cycle_used += hours
        self.state.miles_since_fuel = 0.0
        self._emit_segment(
            STATUS_ON,
            start,
            end,
            location,
            f"Fuel stop near mile {int(miles_marker)}",
        )
        after = self.state.snapshot()
        self._add_event(
            "fuel",
            start,
            end,
            location,
            f"Fueling stop (required at least every {int(FUEL_EVERY_MILES)} miles).",
            STATUS_ON,
            before,
            after,
            miles=0.0,
        )
        self.cursor = end
        self.current_location_label = location

    def take_on_duty(self, hours: float, location: str, event_type: str, explanation: str) -> None:
        assert self.cursor is not None and self.state is not None
        remaining = hours
        while remaining > 1e-9:
            if not self.state.window_open:
                self.state.window_open = True
            # On-duty past 14h is allowed, but we prefer resetting if we still need to drive later.
            # For pickup/dropoff we allow window overflow for the on-duty portion.
            chunk = remaining
            if self.state.remaining_cycle() < chunk - 1e-9:
                if self.state.remaining_cycle() <= 0:
                    raise HOSPlanningError(
                        f"Trip cannot be completed: insufficient cycle hours for {event_type}."
                    )
                chunk = self.state.remaining_cycle()

            before = self.state.snapshot()
            start = self.cursor
            end = start + timedelta(hours=chunk)
            self.state.window_used += chunk
            self.state.cycle_used += chunk
            self._emit_segment(STATUS_ON, start, end, location, explanation)
            after = self.state.snapshot()
            self._add_event(
                event_type,
                start,
                end,
                location,
                explanation,
                STATUS_ON,
                before,
                after,
            )
            self.cursor = end
            remaining -= chunk
            self.current_location_label = location

            if remaining > 1e-9 and self.state.remaining_cycle() <= 0:
                raise HOSPlanningError(
                    f"Trip cannot be completed: cycle exhausted during {event_type}."
                )

    def drive_miles(self, miles: float, from_label: str, to_label: str, leg_name: str) -> None:
        assert self.cursor is not None and self.state is not None
        remaining_miles = miles
        speed = max(self.average_speed_mph, 1.0)

        while remaining_miles > 1e-6:
            if not self.state.window_open:
                self.state.window_open = True

            # Binding constraints for driving
            if self.state.remaining_cycle() <= 1e-9:
                raise HOSPlanningError(
                    "Trip cannot be completed: 70-hour cycle exhausted while driving remained."
                )

            drive_cap = min(
                self.state.remaining_drive(),
                self.state.remaining_window(),
                self.state.remaining_until_break(),
                self.state.remaining_cycle(),
            )
            fuel_miles_cap = self.state.remaining_until_fuel()
            hours_to_fuel = fuel_miles_cap / speed
            drive_cap = min(drive_cap, hours_to_fuel)

            if drive_cap <= 1e-9:
                # Determine why and insert the appropriate non-drive event.
                if self.state.remaining_until_break() <= 1e-9:
                    self.take_break(from_label if remaining_miles > miles * 0.5 else to_label)
                    continue
                if self.state.remaining_until_fuel() <= 1e-9:
                    loc = f"Fuel stop en route ({leg_name})"
                    miles_done = miles - remaining_miles
                    self.take_fuel(loc, miles_done)
                    continue
                if (
                    self.state.remaining_drive() <= 1e-9
                    or self.state.remaining_window() <= 1e-9
                ):
                    loc = from_label if remaining_miles >= miles - 1e-6 else to_label
                    reason = (
                        "10-hour off-duty reset (11-hour drive limit reached)."
                        if self.state.remaining_drive() <= 1e-9
                        else "10-hour off-duty reset (14-hour window reached)."
                    )
                    self.take_off_duty_reset(loc, reason)
                    continue
                raise HOSPlanningError("Unable to progress driving schedule.")

            miles_chunk = min(remaining_miles, drive_cap * speed)
            hours_chunk = miles_chunk / speed

            before = self.state.snapshot()
            start = self.cursor
            end = start + timedelta(hours=hours_chunk)
            self.state.drive_used += hours_chunk
            self.state.window_used += hours_chunk
            self.state.drive_since_break += hours_chunk
            self.state.cycle_used += hours_chunk
            self.state.miles_since_fuel += miles_chunk

            remark = f"Driving {leg_name}: {from_label} → {to_label}"
            self._emit_segment(STATUS_DRIVE, start, end, to_label, remark)
            after = self.state.snapshot()
            self._add_event(
                "drive",
                start,
                end,
                to_label,
                remark,
                STATUS_DRIVE,
                before,
                after,
                miles=miles_chunk,
            )
            self.cursor = end
            remaining_miles -= miles_chunk
            self.current_location_label = to_label

            # If we exactly hit fuel threshold, fuel now.
            if self.state.miles_since_fuel + 1e-6 >= FUEL_EVERY_MILES and remaining_miles > 1e-6:
                self.take_fuel(f"Fuel stop en route ({leg_name})", miles - remaining_miles)


def plan_trip(
    *,
    route: dict[str, Any],
    shift_start: datetime,
    current_cycle_used_hours: float,
    current_label: str,
    pickup_label: str,
    dropoff_label: str,
) -> dict[str, Any]:
    """Build a full HOS-compliant itinerary and duty segments from a route."""
    if current_cycle_used_hours < 0 or current_cycle_used_hours > CYCLE_LIMIT_HOURS:
        raise HOSPlanningError("currentCycleUsedHours must be between 0 and 70.")

    avg_speed = float(route.get("averageSpeedMph") or 55.0)
    legs = route.get("legs") or []
    if len(legs) < 2:
        raise HOSPlanningError("Route must include current→pickup and pickup→dropoff legs.")

    planner = Planner(
        shift_start=shift_start,
        initial_cycle_used=float(current_cycle_used_hours),
        average_speed_mph=avg_speed,
        current_location_label=current_label,
    )

    # Pre-trip: if already at 70, fail early.
    if planner.state and planner.state.remaining_cycle() <= 0:
        raise HOSPlanningError(
            "No cycle hours remaining. Driver must take a 34-hour restart before this trip."
        )

    leg1 = legs[0]
    miles1 = float(leg1.get("distanceMiles") or 0)

    if miles1 > 0.5:
        planner.drive_miles(miles1, current_label, pickup_label, "to pickup")
    else:
        planner.warnings.append("Current location is near pickup; deadhead leg skipped.")

    planner.take_on_duty(
        PICKUP_HOURS,
        pickup_label,
        "pickup",
        "1 hour on-duty for pickup.",
    )

    leg2 = legs[1]
    miles2 = float(leg2.get("distanceMiles") or 0)
    if miles2 <= 0:
        raise HOSPlanningError("Pickup to dropoff distance must be greater than zero.")

    planner.drive_miles(miles2, pickup_label, dropoff_label, "loaded")

    planner.take_on_duty(
        DROPOFF_HOURS,
        dropoff_label,
        "dropoff",
        "1 hour on-duty for drop-off.",
    )

    assert planner.cursor is not None and planner.state is not None

    compliance = {
        "calculationVersion": CALCULATION_VERSION,
        "assumptions": {
            "cycle": "70/8",
            "driveLimitHours": DRIVE_LIMIT_HOURS,
            "windowLimitHours": WINDOW_LIMIT_HOURS,
            "breakAfterDriveHours": BREAK_AFTER_DRIVE_HOURS,
            "breakMinutes": BREAK_MINUTES,
            "offDutyResetHours": OFF_DUTY_RESET_HOURS,
            "fuelEveryMiles": FUEL_EVERY_MILES,
            "fuelMinutes": FUEL_MINUTES,
            "pickupHours": PICKUP_HOURS,
            "dropoffHours": DROPOFF_HOURS,
            "adverseConditions": False,
            "sleeperBerthSplit": False,
        },
        "initialCycleUsedHours": round(float(current_cycle_used_hours), 3),
        "finalState": planner.state.snapshot(),
        "shiftStart": shift_start.isoformat(),
        "shiftEnd": planner.cursor.isoformat(),
        "totalScheduledHours": round(
            (planner.cursor - shift_start).total_seconds() / 3600.0, 3
        ),
        "warnings": planner.warnings,
        "feasible": True,
    }

    return {
        "itinerary": planner.events,
        "segments": planner.segments,
        "compliance": compliance,
    }


def clone_state_dict(data: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(data)
