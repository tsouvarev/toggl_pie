#!/usr/bin/env python3

import os
from csv import writer
from datetime import datetime
from io import StringIO
from typing import Optional

import arrow
import httpx
import typer
from funcy import group_by_keys, walk_values
from pandas import DataFrame
from whatever import that

HOURS_IN_WORKDAY = 8
API_TOKEN = os.getenv("API_TOKEN")

app = typer.Typer()


@app.command()
def csv(
    since: Optional[datetime] = typer.Argument(None),
    until: Optional[datetime] = typer.Argument(None),
    workdays: Optional[int] = typer.Option(None),
):
    fulltime_durations = _get_fulltime_durations(since, until, workdays)
    with StringIO() as f:
        wr = writer(f)
        wr.writerows(fulltime_durations.items())
        print(f"\n{f.getvalue()}")


@app.command()
def png(
    since: Optional[datetime] = typer.Argument(None),
    until: Optional[datetime] = typer.Argument(None),
    workdays: Optional[int] = typer.Option(None),
    filename: str = "res.png",
):
    fulltime_durations = _get_fulltime_durations(since, until, workdays)
    df = DataFrame(fulltime_durations.values(), index=fulltime_durations)
    plot = df.plot.pie(y=0, legend=False, autopct="%.2f%%")
    plot.yaxis.set_label_text("")
    plot.figure.savefig(filename)


def _get_fulltime_durations(since, until, workdays):
    since = _normalize(since, default=_get_midnight)
    until = _normalize(until, default=_get_now)

    entries = _get_entries(since, until)
    tags_with_duration = _group_entries_by_tag(entries)
    duration_with_lost_minutes = _add_lost_minutes(
        tags_with_duration, since, until, workdays
    )
    return duration_with_lost_minutes


def _normalize(dt, default):
    if dt:
        return _localize(dt)
    return default()


def _localize(dt):
    return arrow.get(dt, tzinfo="MSK")


def _get_midnight():
    return _get_now().replace(hour=0, minute=0, second=0, microsecond=0)


def _get_now():
    return arrow.get()


def _get_entries(since, until):
    auth = (API_TOKEN, "api_token")
    print(f"Interval: {since.isoformat()}, {until.isoformat()}")
    params = {"start_date": since.isoformat(), "end_date": until.isoformat()}
    resp = httpx.get(
        "https://api.track.toggl.com/api/v8/time_entries", auth=auth, params=params
    )
    return resp.json()


def _group_entries_by_tag(entries):
    entries_by_tag = group_by_keys(that["tags"], entries)
    tags_with_hours = walk_values(
        lambda e: sum(x["duration"] for x in e) / 60 / 60, entries_by_tag
    )
    return tags_with_hours


def _add_lost_minutes(tags_with_hours, since, until, workdays):
    days_between = workdays or (until - since).days
    lost_minutes = days_between * HOURS_IN_WORKDAY - sum(tags_with_hours.values())
    print(f"Workdays: {days_between}")
    return tags_with_hours | {"без разметки": lost_minutes}


if __name__ == "__main__":
    app()
