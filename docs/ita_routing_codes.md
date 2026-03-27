# ITA Matrix Routing Code Reference

> Reference guide for ITA Matrix routing code syntax. Used by agents and automation.
> ITA Matrix URL: `https://matrix.itasoftware.com`

---

## Basic Syntax

Routing codes are entered in the **"Routing codes"** field under "More options" on the ITA Matrix search page.

### Forcing a Carrier on a Segment

```
FORCE <carrier>:<origin>-<destination>
```

Example: Force Lufthansa from JFK to Frankfurt:
```
FORCE LH:JFK-FRA
```

### Multiple Segments

Separate segments with ` / ` (space-slash-space):

```
FORCE LH:JFK-FRA / FORCE LH:FRA-BKK
```

### Connection Points (Via Cities)

Chain cities with hyphens within a single segment:

```
FORCE QR:JFK-DOH-BKK
```

This forces QR on JFK→DOH and DOH→BKK (QR selects flights).

### Multi-Carrier on Same Routing

Use slash between carrier codes:

```
FORCE BA/AA:JFK-LHR-SYD
```

This allows either BA or AA metal on both legs.

---

## Advanced Features

### Fare Basis / Booking Class Forcing

Append `BC=<code>` after the routing to force a specific fare basis:

```
FORCE LH:JFK-FRA-BKK BC=YLOWUS
```

This restricts results to the YLOWUS fare basis code, which may have different surcharge rules.

### Nonstop Forcing

```
NONSTOP <carrier>:<origin>-<destination>
```

Forces a nonstop flight (no connections) on the specified carrier.

### Minimum Connection Time

```
MINCONNECT H:MM
```

Example — require at least 2 hours between connections:
```
MINCONNECT 2:00
```

### Maximum Connection Time

```
MAXCONNECT H:MM
```

### Forcing a Specific Alliance

Not directly supported in routing codes. Use the carrier pair syntax (`FORCE BA/AA:...`) to approximate alliance routing.

---

## Fuel Dump Routing Patterns

### TP_DUMP (Ticketing Point Manipulation)

The most common dump type. Routes via a specific city to break the YQ assessment into separate pricing units.

```
FORCE LH:JFK-FRA / FORCE LH:FRA-BKK / FORCE AA:BKK-JFK
```

**How it works:** The ticketing point (FRA) creates a break in the pricing. LH's YQ is assessed per pricing unit. By breaking the itinerary at FRA, the transatlantic YQ may not apply to the Asia segment, and vice versa. The return on AA (no YQ) completes the roundtrip.

### CARRIER_SWITCH

Uses a carrier that doesn't charge YQ on the long-haul sector:

```
FORCE QR:JFK-DOH-BKK / FORCE AA:BKK-JFK
```

**How it works:** Qatar Airways (QR) does not charge YQ. The outbound goes via DOH on QR metal. The return on AA also has no YQ. Total YQ = $0.

### FARE_BASIS

Forces a specific fare basis code that structurally excludes YQ:

```
FORCE LH:JFK-FRA-BKK BC=YLOWUS / FORCE AA:BKK-JFK
```

**How it works:** Certain fare basis codes have pricing rules that exclude carrier surcharges. The BC= parameter restricts ITA Matrix to only show fares using that basis.

### ALLIANCE_RULE

Joint carrier designation triggers interline pricing that waives YQ:

```
FORCE BA/AA:JFK-LHR-SYD / FORCE BA/AA:SYD-LHR-JFK
```

**How it works:** When BA and AA are jointly ticketed under their interline agreement, YQ may be waived on certain routes. The `/` between carriers signals an interline fare construction.

---

## Common Pitfalls

1. **Case sensitivity** — Carrier codes must be uppercase (`LH`, not `lh`). Airport codes must be uppercase (`JFK`, not `jfk`).

2. **Spacing around `/`** — Segment separator must have spaces: ` / ` not `/`.

3. **Carrier code format** — Always 2 letters. Do not use 3-letter ICAO codes (use `LH` not `DLH`).

4. **Airport code format** — Always 3 letters. Use IATA codes only.

5. **Order matters** — Segments are evaluated left to right. Outbound first, then return.

6. **Date sensitivity** — Some routing codes only produce results for certain date ranges. Always search 3–6 weeks out for best availability.

7. **No results ≠ invalid code** — If ITA Matrix returns no results, the routing may be valid but no inventory exists for the selected dates. Try different dates before declaring the pattern broken.

8. **YQ assessment varies** — The same routing code may produce different YQ amounts on different dates or fare classes. Always check the fare breakdown.

---

## Reading ITA Matrix Results

After searching with a routing code:

1. **Results list** shows total price per itinerary
2. **Click a fare** to expand the construction table
3. **Look for the "Taxes" breakdown** — YQ appears as a separate line item
4. **YQ = $0.00** means the dump is working
5. **Compare base fare** to a normal search to verify the construction is competitive

### Tax Code Reference

| Code | Description | Dumpable? |
|------|-------------|-----------|
| YQ | Carrier fuel surcharge | ✅ Yes — target of fuel dumps |
| YR | Government-imposed surcharge | ❌ No — cannot be eliminated |
| US | US Transportation Tax | ❌ No |
| XF | US Passenger Facility Charge | ❌ No |
| AY | US September 11 Security Fee | ❌ No |
| GB | UK Air Passenger Duty | ❌ No |
| DE | Germany Aviation Tax | ❌ No |

---

## Tips for Agents

- **Always verify YQ = $0** in the fare breakdown before booking
- **Try backup routing** if primary returns high YQ
- **Date flexibility helps** — shift dates by 1–3 days if no results
- **Fare class matters** — some dumps only work in specific booking classes
- **Screenshot the breakdown** — save proof of the YQ-free construction before booking
