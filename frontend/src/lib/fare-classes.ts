/**
 * Fare class constants and extension code builder for fuel dump guidance.
 *
 * Fuel dumps only work on discounted economy fare classes where YQ (carrier
 * fuel surcharge) is a significant portion of the total fare. Full-fare
 * economy (Y) and premium cabins have base fares so high that YQ savings
 * are irrelevant — and Y-class fares typically don't dump YQ at all.
 */

/** Discounted economy classes that successfully dump YQ */
export const DUMPABLE_CLASSES = ["M", "Q", "T", "K", "V", "G", "W"] as const;

/** Full-fare economy and premium classes — YQ dump doesn't apply */
export const NON_DUMPABLE_CLASSES = ["Y", "B", "J", "C", "F"] as const;

export const FARE_CLASS_EXPLAINER =
  "Fuel dumps only work on discounted economy (M/Q/T/K/V/G/W). " +
  "Full-fare Y class costs $4,000+ and doesn't dump YQ. " +
  "Use the extension code below in ITA Matrix to force cheap fare classes.";

export const EXTENSION_CODE_INSTRUCTION =
  "When reviewing ITA Matrix results, look for itineraries in the dumpable booking classes above. Avoid Y-class results — they won't dump YQ.";

/**
 * ITA Matrix's current version does NOT support any command-line prefix syntax
 * (/f, +f, bc=) in the extension codes field — it throws "Illegal COMMAND-LINE prefix".
 *
 * Always return empty string. Booking class filtering must be handled in the
 * app pipeline (post-filter results or UI guidance to the user).
 */
export function buildExtensionCode(_fareBasisHint?: string | null): string { // eslint-disable-line @typescript-eslint/no-unused-vars
  return "";
}
