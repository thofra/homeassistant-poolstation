# Poolstation Integration Fix - AUTO Mode Bug

## Problem

Relays in AUTO mode always showed as OFF in Home Assistant.

**Root cause:** In `pypoolstation`, the relay state is parsed as:
```python
relay.active = info["vars"][obj["sign"]] == '1'
```
This treats any value that is not `'1'` as `False` - but AUTO mode returns `'A'` from the API, not `'1'`.

## Solution

Two parts:

### Part 1: Patch pypoolstation (Relay class)

The `Relay` class in `pypoolstation` needs a `raw_state` attribute instead of (or in addition to) the boolean `active`.

**In `pypoolstation`'s `Relay.__init__`**, change:
```python
class Relay:
    def __init__(self, id=None, pool=None, name="", sign="", active=False):
        ...
        self.active = active  # bool - loses AUTO info!
```
To:
```python
class Relay:
    def __init__(self, id=None, pool=None, name="", sign="", active=False, raw_state="0"):
        ...
        self.raw_state = raw_state          # "0", "1", or "A"
        self.active = raw_state in ("1", "A")  # True for ON and AUTO
```

**In `Pool.sync_info`**, change relay creation:
```python
# OLD (loses AUTO state):
Relay(..., active=info["vars"][r["sign"]] == '1')

# NEW (preserves raw state):
Relay(..., active=info["vars"][r["sign"]] in ("1", "A"),
           raw_state=info["vars"][r["sign"]])
```

And relay update:
```python
# OLD:
relay.active = info["vars"][obj["sign"]] == '1'

# NEW:
relay.raw_state = info["vars"][obj["sign"]]
relay.active = relay.raw_state in ("1", "A")
```

**In `Relay.set_mode`** (new method to add):
```python
async def set_mode(self, mode: str) -> str:
    """Set relay to specific mode: '0'=off, '1'=on, 'A'=auto."""
    previous = self.raw_state
    self.raw_state = mode
    self.active = mode in ("1", "A")
    try:
        await self.pool.post(UPDATE_URL, data=f"&data={json.dumps({'id': self.pool.id, 'sign': self.sign, 'value': mode})}")
        return mode
    except ClientError:
        self.raw_state = previous
        self.active = previous in ("1", "A")
        return previous
```

### Part 2: Integration changes (this folder)

- **`switch.py`**: Fixed to use `relay.raw_state` - AUTO and ON both show as `on=True`
- **`select.py`**: New entity providing full off/auto/on control
- **`__init__.py`**: Added `"select"` to PLATFORMS

## New HA Entities per Relay

After the fix, each relay creates **two entities**:

| Entity | Type | States | Use for |
|--------|------|--------|---------|
| `switch.poolstation_relay_pumpe` | Switch | on/off | Simple automations |
| `select.poolstation_relay_pumpe_mode` | Select | off/auto/on | Full control |

## API Values

| Mode | API value | `relay.active` | `relay.raw_state` |
|------|-----------|----------------|-------------------|
| OFF  | `"0"`     | `False`        | `"0"`             |
| AUTO | `"A"`     | `True`         | `"A"`             |
| ON   | `"1"`     | `True`         | `"1"`             |
