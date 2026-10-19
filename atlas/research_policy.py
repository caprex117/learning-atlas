"""Shared, conservative Tavily allowance for this app, including failed attempts."""
from datetime import datetime, timedelta, timezone

INTERVAL_DAYS=21
MONTHLY_CREDITS=40
REFRESH_CREDITS=8
LOOKUP_CREDITS=2
MAX_NEW=5
MAX_RECHECK=3


def timestamp(value):
    return datetime.fromisoformat(str(value).replace('Z','+00:00'))


def spent(data, at=None):
    at=at or datetime.now(timezone.utc)
    total=0
    for run in data.get('discovery_runs',[]):
        if run['origin']=='seed' or timestamp(run['started_at']).strftime('%Y-%m')!=at.strftime('%Y-%m'):
            continue
        info=run.get('details',{})
        # A timeout can occur after a paid request. Keep its whole reservation.
        key='reserved_credits' if run['status'] in ('running','failed') else 'tavily_credits'
        total+=float(info.get(key,info.get('reserved_credits',info.get('tavily_credits',0))))
    return total


def check_allowance(data, reserve, at=None):
    used=spent(data,at)
    if used+reserve>MONTHLY_CREDITS:
        raise ValueError(f'Límite mensual de Learning Atlas: {used:g}/{MONTHLY_CREDITS} créditos reservados o usados. Esta operación necesita hasta {reserve} más; no se llamó a Tavily.')


def catalog_runs(data):
    return [r for r in data.get('discovery_runs',[]) if r['status'] in ('completed','partial')
            and r.get('details',{}).get('purpose','catalog')=='catalog']


def next_due(data):
    runs=catalog_runs(data)
    if not runs:
        return None
    return max(timestamp(r['finished_at']) for r in runs)+timedelta(days=INTERVAL_DAYS)
